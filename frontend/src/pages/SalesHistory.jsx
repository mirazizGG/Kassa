
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
    CreditCard,
    RotateCcw,
    AlertCircle,
    Loader2
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { format } from "date-fns";
import { Skeleton } from "@/components/ui/skeleton";
import FilterBar from '../components/FilterBar';
import { Button } from "@/components/ui/button";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "@/components/ui/dialog";
import { toast } from "sonner";
import { useMutation, useQueryClient } from '@tanstack/react-query';

const SalesHistory = () => {
    const today = new Date().toISOString().split('T')[0];
    const [filters, setFilters] = React.useState({
        employee_id: '',
        start_date: today,
        end_date: today
    });

    const [expandedSale, setExpandedSale] = React.useState(null);
    const queryClient = useQueryClient();

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

    const refundMutation = useMutation({
        mutationFn: (saleId) => api.post(`/sales/${saleId}/refund`),
        onSuccess: () => {
            queryClient.invalidateQueries(['sales-history']);
            queryClient.invalidateQueries(['finance-stats']);
            queryClient.invalidateQueries(['dashboard-stats']);
            queryClient.invalidateQueries(['products']); 
            toast.success("Muvaffaqiyatli!", { description: "Savdo qaytarildi va mahsulotlar omborga qo'shildi." });
        },
        onError: (error) => {
            toast.error("Xatolik!", { description: error.response?.data?.detail || "Savdoni qaytarib bo'lmadi." });
        }
    });

    const handleRefund = (id) => {
        refundMutation.mutate(id);
    };

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
                                            {format(new Date(sale.created_at.endsWith('Z') ? sale.created_at : sale.created_at + 'Z'), 'dd.MM.yyyy HH:mm')}
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
                                                    <div className="flex items-center justify-between">
                                                        <h4 className="font-semibold flex items-center gap-2">
                                                            <Package className="w-4 h-4 text-primary" />
                                                            Sotilgan Mahsulotlar
                                                        </h4>
                                                        
                                                        {sale.status === 'completed' && (
                                                            <Dialog>
                                                                <DialogTrigger asChild>
                                                                    <Button variant="destructive" size="sm" className="gap-2 h-8">
                                                                        <RotateCcw className="w-3.5 h-3.5" />
                                                                        Vozvrat qilish
                                                                    </Button>
                                                                </DialogTrigger>
                                                                <DialogContent>
                                                                    <DialogHeader>
                                                                        <DialogTitle className="flex items-center gap-2">
                                                                            <AlertCircle className="w-5 h-5 text-destructive" />
                                                                            Haqiqatdan ham qaytarmoqchimisiz?
                                                                        </DialogTitle>
                                                                        <DialogDescription>
                                                                            Ushbu amal tanlangan barcha mahsulotlarni omborga qaytaradi va moliya tushumidan ayirib tashlaydi.
                                                                        </DialogDescription>
                                                                    </DialogHeader>
                                                                    <DialogFooter>
                                                                        <DialogHeader className="w-full"> {/* Just using header for spacing if needed or just buttons */}
                                                                           <div className="flex justify-end gap-2 pt-4">
                                                                                <DialogTrigger asChild>
                                                                                    <Button variant="outline">Yo'q, bekor qilish</Button>
                                                                                </DialogTrigger>
                                                                                <Button 
                                                                                    variant="destructive"
                                                                                    onClick={() => handleRefund(sale.id)}
                                                                                >
                                                                                    Ha, qaytarish
                                                                                </Button>
                                                                           </div>
                                                                        </DialogHeader>
                                                                    </DialogFooter>
                                                                </DialogContent>
                                                            </Dialog>
                                                        )}
                                                    </div>
                                                    
                                                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
                                                        {sale.items.map((item, idx) => (
                                                            <div key={idx} className={`flex justify-between items-center p-2 rounded-md bg-secondary/50 border text-sm ${sale.status === 'refunded' ? 'opacity-60 grayscale' : ''}`}>
                                                                <span className="font-medium">{item.product?.name || 'Mahsulot'}</span>
                                                                <span className="text-muted-foreground">
                                                                    {item.quantity} x {item.price.toLocaleString()} = {(item.quantity * item.price).toLocaleString()}
                                                                </span>
                                                            </div>
                                                        ))}
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
