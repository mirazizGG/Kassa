import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '../api/axios';
import {
    Users,
    Search,
    Plus,
    Phone,
    CreditCard,
    MoreHorizontal
} from 'lucide-react';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";

const CRM = () => {
    const [searchTerm, setSearchTerm] = useState('');

    const { data: clients = [], isLoading } = useQuery({
        queryKey: ['clients'],
        queryFn: async () => {
            const res = await api.get('/crm/clients');
            return res.data;
        }
    });

    const filteredClients = clients.filter(client =>
        client.name.toLowerCase().startsWith(searchTerm.toLowerCase()) ||
        client.phone?.startsWith(searchTerm)
    );

    return (
        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight">Mijozlar (CRM)</h1>
                    <p className="text-muted-foreground">Doimiy mijozlar bazasi va qarzlar nazorati</p>
                </div>
                <Button className="gap-2 shadow-lg shadow-primary/20">
                    <Plus className="w-4 h-4" /> Yangi Mijoz
                </Button>
            </div>

            <Card className="border-none shadow-md overflow-hidden bg-background/60 backdrop-blur-xl">
                <CardHeader className="p-6 pb-0">
                    <div className="relative flex-1 max-w-sm">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                        <Input
                            placeholder="Ism yoki telefon orqali qidiruv..."
                            className="pl-10"
                            value={searchTerm}
                            onChange={(e) => setSearchTerm(e.target.value)}
                        />
                    </div>
                </CardHeader>
                <CardContent className="p-0 mt-6">
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead className="pl-8">Mijoz Ismi</TableHead>
                                <TableHead>Telefon</TableHead>
                                <TableHead>Balans (Qarz)</TableHead>
                                <TableHead>Status</TableHead>
                                <TableHead className="text-right pr-8">Amallar</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {isLoading ? (
                                <TableRow>
                                    <TableCell colSpan={5} className="h-24 text-center">Yuklanmoqda...</TableCell>
                                </TableRow>
                            ) : filteredClients.length === 0 ? (
                                <TableRow>
                                    <TableCell colSpan={5} className="h-24 text-center text-muted-foreground">Mijozlar topilmadi</TableCell>
                                </TableRow>
                            ) : filteredClients.map((client) => (
                                <TableRow key={client.id} className="group hover:bg-muted/50 transition-colors">
                                    <TableCell className="pl-8 font-semibold">{client.name}</TableCell>
                                    <TableCell className="flex items-center gap-2 text-muted-foreground">
                                        <Phone className="w-3 h-3" /> {client.phone || '-'}
                                    </TableCell>
                                    <TableCell>
                                        <div className="font-bold">
                                            {client.balance.toLocaleString()} <span className="text-[10px] text-muted-foreground">so'm</span>
                                        </div>
                                    </TableCell>
                                    <TableCell>
                                        <Badge variant={client.balance < 0 ? "destructive" : "secondary"}>
                                            {client.balance < 0 ? "Qarzdor" : "Aktiv"}
                                        </Badge>
                                    </TableCell>
                                    <TableCell className="text-right pr-8">
                                        <Button variant="ghost" size="icon">
                                            <MoreHorizontal className="w-4 h-4" />
                                        </Button>
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

export default CRM;
