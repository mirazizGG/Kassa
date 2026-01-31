
import React from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '../api/axios';
import {
    History,
    Calendar,
    User,
    DollarSign,
    Package,
    ChevronDown,
    ChevronUp,
    Search,
    CreditCard
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { format } from "date-fns";
import { Skeleton } from "@/components/ui/skeleton";
import FilterBar from '../components/FilterBar';
import { Button } from "@/components/ui/button";

const SalesHistory = () => {
    const today = new Date().toISOString().split('T')[0];
    const [filters, setFilters] = React.useState({
        employee_id: '',
        start_date: today,
        end_date: today
    });

    const [expandedSale, setExpandedSale] = React.useState(null);

    const { data: sales = [], isLoading } = useQuery({
        queryKey: ['sales-history', filters],
        queryFn: async () => {
            const params = {};
            if (filters.employee_id && filters.employee_id !== 'all') params.employee_id = filters.employee_id;
            if (filters.start_date) params.start_date = filters.start_date;
            if (filters.end_date) params.end_date = filters.end_date;

            const res = await api.get('/sales/', { params });
            return res.data;
        }
    });

    const toggleExpand = (id) => {
        setExpandedSale(expandedSale === id ? null : id);
    };

    return (
        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight">Savdolar Tarixi</h1>
                    <p className="text-muted-foreground">Barcha amalga oshirilgan savdolar va sotilgan mahsulotlar</p>
                </div>
                <FilterBar filters={filters} onFilterChange={setFilters} />
            </div>

            <Card className="border-none shadow-md overflow-hidden bg-background/60 backdrop-blur-xl">
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <History className="w-5 h-5 text-primary" />
                        Savdolar Ro'yxati
                    </CardTitle>
                </CardHeader>
                <CardContent className="p-0">
                    <Table>
                        <TableHeader className="bg-muted/30">
                            <TableRow>
                                <TableHead className="w-[50px]"></TableHead>
                                <TableHead>Kassir</TableHead>
                                <TableHead>Mijoz</TableHead>
                                <TableHead>Sana</TableHead>
                                <TableHead>Summa</TableHead>
                                <TableHead>To'lov Usuli</TableHead>
                                <TableHead>Status</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {isLoading ? (
                                [1, 2, 3, 4, 5].map(i => (
                                    <TableRow key={i}>
                                        <TableCell colSpan={7} className="p-4"><Skeleton className="h-8 w-full" /></TableCell>
                                    </TableRow>
                                ))
                            ) : sales.length === 0 ? (
                                <TableRow>
                                    <TableCell colSpan={7} className="h-40 text-center text-muted-foreground">
                                        Savdolar topilmadi
                                    </TableCell>
                                </TableRow>
                            ) : sales.map((sale) => (
                                <React.Fragment key={sale.id}>
                                    <TableRow 
                                        className="hover:bg-muted/50 transition-colors cursor-pointer"
                                        onClick={() => toggleExpand(sale.id)}
                                    >
                                        <TableCell>
                                            {expandedSale === sale.id ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                                        </TableCell>
                                        <TableCell className="font-medium">
                                            {sale.cashier?.full_name || sale.cashier?.username || "Noma'lum"}
                                        </TableCell>
                                        <TableCell>
                                            {sale.client?.name || '-'}
                                        </TableCell>
                                        <TableCell className="text-xs">
                                            {format(new Date(sale.created_at), 'dd.MM.yyyy HH:mm')}
                                        </TableCell>
                                        <TableCell className="font-bold">
                                            {sale.total_amount.toLocaleString()} so'm
                                        </TableCell>
                                        <TableCell>
                                            <Badge variant="outline" className="capitalize">
                                                {sale.payment_method === 'cash' ? 'Naqd' : 
                                                 sale.payment_method === 'card' ? 'Karta' : 
                                                 sale.payment_method === 'qarz' ? 'Qarz' : sale.payment_method}
                                            </Badge>
                                        </TableCell>
                                        <TableCell>
                                            <Badge variant={sale.status === 'completed' ? 'default' : 'destructive'}>
                                                {sale.status === 'completed' ? 'Tayyor' : 'Qaytarilgan'}
                                            </Badge>
                                        </TableCell>
                                    </TableRow>
                                    {expandedSale === sale.id && (
                                        <TableRow className="bg-muted/20">
                                            <TableCell colSpan={7} className="p-4">
                                                <div className="rounded-lg border bg-card p-4 space-y-3">
                                                    <h4 className="font-semibold flex items-center gap-2">
                                                        <Package className="w-4 h-4 text-primary" />
                                                        Sotilgan Mahsulotlar
                                                    </h4>
                                                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
                                                        {sale.items.map((item, idx) => (
                                                            <div key={idx} className="flex justify-between items-center p-2 rounded-md bg-secondary/50 border text-sm">
                                                                <span className="font-medium">{item.product?.name || 'Mahsulot'}</span>
                                                                <span className="text-muted-foreground">
                                                                    {item.quantity} x {item.price.toLocaleString()} = {(item.quantity * item.price).toLocaleString()}
                                                                </span>
                                                            </div>
                                                        ))}
                                                    </div>
                                                </div>
                                            </TableCell>
                                        </TableRow>
                                    )}
                                </React.Fragment>
                            ))}
                        </TableBody>
                    </Table>
                </CardContent>
            </Card>
        </div>
    );
};

export default SalesHistory;
