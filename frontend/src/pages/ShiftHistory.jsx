import React from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '../api/axios';
import {
    History,
    Calendar,
    User,
    Banknote,
    BadgeAlert,
    Clock,
    ChevronRight,
    Search
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { format } from "date-fns";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";

const ShiftHistory = () => {
    const { data: shifts = [], isLoading } = useQuery({
        queryKey: ['shifts-history'],
        queryFn: async () => {
            const res = await api.get('/pos/shifts/history');
            return res.data;
        }
    });

    return (
        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight">Smenalar Tarixi</h1>
                    <p className="text-muted-foreground">Barcha yopilgan va ochiq smenalar nazorati</p>
                </div>
            </div>

            <Card className="border-none shadow-md overflow-hidden bg-background/60 backdrop-blur-xl">
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <History className="w-5 h-5 text-primary" />
                        Smenalar Ro'yxati
                    </CardTitle>
                    <CardDescription>Kassirlarning kirish-chiqish va kassa qoldiqlari tarixi</CardDescription>
                </CardHeader>
                <CardContent className="p-0">
                    <Table>
                        <TableHeader className="bg-muted/30">
                            <TableRow>
                                <TableHead className="pl-6">Kassir</TableHead>
                                <TableHead>Ochilgan</TableHead>
                                <TableHead>Yopilgan</TableHead>
                                <TableHead>Boshlang'ich</TableHead>
                                <TableHead>Yakuniy</TableHead>
                                <TableHead>Farq</TableHead>
                                <TableHead>Status</TableHead>
                                <TableHead className="pr-6 text-right">Amallar</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {isLoading ? (
                                [1, 2, 3, 4, 5].map(i => (
                                    <TableRow key={i}>
                                        <TableCell colSpan={8} className="p-4"><Skeleton className="h-8 w-full" /></TableCell>
                                    </TableRow>
                                ))
                            ) : shifts.length === 0 ? (
                                <TableRow>
                                    <TableCell colSpan={8} className="h-40 text-center text-muted-foreground">
                                        Smenalar topilmadi
                                    </TableCell>
                                </TableRow>
                            ) : shifts.map((shift) => {
                                const diff = shift.closing_balance !== null 
                                    ? shift.closing_balance - shift.opening_balance 
                                    : null;
                                    
                                return (
                                    <TableRow key={shift.id} className="hover:bg-muted/50 transition-colors">
                                        <TableCell className="pl-6 font-medium">
                                            <div className="flex items-center gap-2">
                                                <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center text-primary font-bold text-xs">
                                                    {shift.cashier?.username.charAt(0).toUpperCase()}
                                                </div>
                                                <div>
                                                    <div>{shift.cashier?.full_name || shift.cashier?.username}</div>
                                                    <div className="text-[10px] text-muted-foreground uppercase">{shift.cashier?.role}</div>
                                                </div>
                                            </div>
                                        </TableCell>
                                        <TableCell className="text-xs">
                                            <div className="flex items-center gap-1">
                                                <Clock className="w-3 h-3 opacity-50" />
                                                {format(new Date(shift.opened_at), 'dd.MM.yyyy HH:mm')}
                                            </div>
                                        </TableCell>
                                        <TableCell className="text-xs">
                                            {shift.closed_at ? (
                                                <div className="flex items-center gap-1">
                                                    <Clock className="w-3 h-3 opacity-50" />
                                                    {format(new Date(shift.closed_at), 'dd.MM.yyyy HH:mm')}
                                                </div>
                                            ) : '-'}
                                        </TableCell>
                                        <TableCell className="font-mono text-sm">
                                            {shift.opening_balance.toLocaleString()}
                                        </TableCell>
                                        <TableCell className="font-mono text-sm">
                                            {shift.closing_balance !== null ? shift.closing_balance.toLocaleString() : '-'}
                                        </TableCell>
                                        <TableCell className="font-mono text-sm">
                                            {diff !== null ? (
                                                <span className={diff >= 0 ? 'text-emerald-500' : 'text-rose-500'}>
                                                    {diff > 0 ? '+' : ''}{diff.toLocaleString()}
                                                </span>
                                            ) : '-'}
                                        </TableCell>
                                        <TableCell>
                                            <Badge variant={shift.status === 'open' ? 'default' : 'secondary'} className="uppercase text-[9px]">
                                                {shift.status === 'open' ? 'Ochiq' : 'Yopilgan'}
                                            </Badge>
                                        </TableCell>
                                        <TableCell className="pr-6 text-right">
                                            <Button variant="ghost" size="icon" className="h-8 w-8 hover:bg-primary/10 hover:text-primary">
                                                <ChevronRight className="w-4 h-4" />
                                            </Button>
                                        </TableCell>
                                    </TableRow>
                                );
                            })}
                        </TableBody>
                    </Table>
                </CardContent>
            </Card>
        </div>
    );
};

export default ShiftHistory;
