import React from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '../api/axios';
import {
    Activity,
    User,
    Clock,
    Info,
    AlertTriangle,
    FileText
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { format } from "date-fns";
import { Skeleton } from "@/components/ui/skeleton";
import FilterBar from '../components/FilterBar';

const AuditLogs = () => {
    const today = new Date().toISOString().split('T')[0];
    const [filters, setFilters] = React.useState({
        employee_id: '',
        start_date: today,
        end_date: today
    });

    const { data: logs = [], isLoading } = useQuery({
        queryKey: ['audit-logs', filters],
        queryFn: async () => {
            const params = {};
            if (filters.employee_id && filters.employee_id !== 'all') params.employee_id = filters.employee_id;
            if (filters.start_date) params.start_date = filters.start_date;
            if (filters.end_date) params.end_date = filters.end_date;

            const res = await api.get('/audit/logs', { params });
            return res.data;
        }
    });

    return (
        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight">Audit va Nazorat</h1>
                    <p className="text-muted-foreground">Tizimdagi barcha muhim amallar va o'zgarishlar tarixi</p>
                </div>
                <FilterBar filters={filters} onFilterChange={setFilters} />
            </div>

            <Card className="border-none shadow-md overflow-hidden bg-background/60 backdrop-blur-xl">
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <Activity className="w-5 h-5 text-primary" />
                        Amallar Tarixi
                    </CardTitle>
                    <CardDescription>Kim, qachon va qanday amalni bajargani haqida ma'lumot</CardDescription>
                </CardHeader>
                <CardContent className="p-0">
                    <Table>
                        <TableHeader className="bg-muted/30">
                            <TableRow>
                                <TableHead className="pl-6">Xodim</TableHead>
                                <TableHead>Amal</TableHead>
                                <TableHead>Batafsil</TableHead>
                                <TableHead>Sana</TableHead>
                                <TableHead className="pr-6">Status</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {isLoading ? (
                                [1, 2, 3, 4, 5].map(i => (
                                    <TableRow key={i}>
                                        <TableCell colSpan={5} className="p-4"><Skeleton className="h-8 w-full" /></TableCell>
                                    </TableRow>
                                ))
                            ) : logs.length === 0 ? (
                                <TableRow>
                                    <TableCell colSpan={5} className="h-40 text-center text-muted-foreground">
                                        Hozircha amallar tarixi bo'sh
                                    </TableCell>
                                </TableRow>
                            ) : logs.map((log) => (
                                <TableRow key={log.id} className="hover:bg-muted/50 transition-colors">
                                    <TableCell className="pl-6 font-medium">
                                        <div className="flex items-center gap-2">
                                            <div className="w-8 h-8 rounded-full bg-secondary flex items-center justify-center">
                                                <User className="w-4 h-4 text-muted-foreground" />
                                            </div>
                                            <div>
                                                <div className="text-sm font-semibold">{log.user?.full_name || log.user?.username}</div>
                                                <div className="text-[10px] text-muted-foreground uppercase">{log.user?.role}</div>
                                            </div>
                                        </div>
                                    </TableCell>
                                    <TableCell>
                                        <Badge variant="outline" className="bg-primary/5 text-primary border-primary/20">
                                            {log.action}
                                        </Badge>
                                    </TableCell>
                                    <TableCell className="max-w-[300px] truncate text-sm text-muted-foreground" title={log.details}>
                                        {log.details}
                                    </TableCell>
                                    <TableCell className="text-xs text-muted-foreground">
                                        <div className="flex items-center gap-1">
                                            <Clock className="w-3 h-3" />
                                            {format(new Date(log.created_at), 'dd.MM.yyyy HH:mm')}
                                        </div>
                                    </TableCell>
                                    <TableCell className="pr-6">
                                        <div className="flex items-center gap-1 text-emerald-500 font-medium text-xs">
                                            <div className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                                            Muvaffaqiyatli
                                        </div>
                                    </TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </CardContent>
            </Card>
        </div>
    );
};

export default AuditLogs;
