import React, { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import api from '../api/axios';
import { queryClient } from '../api/queryClient';
import {
    Users,
    Search,
    Plus,
    Phone,
    CreditCard,
    MoreHorizontal,
    HandCoins,
    Loader2,
    Star,
    Calendar
} from 'lucide-react';
import { format, isPast } from "date-fns";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogFooter
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";
import { cn } from "@/lib/utils.js";

const CRM = () => {
    const [searchTerm, setSearchTerm] = useState('');
    const [isPaymentModalOpen, setIsPaymentModalOpen] = useState(false);
    const [selectedClient, setSelectedClient] = useState(null);
    const [paymentData, setPaymentData] = useState({
        amount: '',
        payment_method: 'cash',
        note: ''
    });

    const { data: clients = [], isLoading } = useQuery({
        queryKey: ['clients'],
        queryFn: async () => {
            const res = await api.get('/crm/clients');
            return res.data;
        }
    });

    const payMutation = useMutation({
        mutationFn: (data) => api.post(`/crm/clients/${selectedClient.id}/pay`, data),
        onSuccess: () => {
            queryClient.invalidateQueries(['clients']);
            setIsPaymentModalOpen(false);
            setPaymentData({ amount: '', payment_method: 'cash', note: '' });
            toast.success("To'lov qabul qilindi!");
        },
        onError: (err) => {
            toast.error("Xatolik!", { description: err.response?.data?.detail || "To'lovni amalga oshirib bo'lmadi" });
        }
    });

    const handlePaymentSubmit = (e) => {
        e.preventDefault();
        payMutation.mutate({
            amount: parseFloat(paymentData.amount),
            payment_method: paymentData.payment_method,
            note: paymentData.note,
            client_id: selectedClient.id
        });
    };

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
                        <TableHeader className="bg-muted/30">
                            <TableRow>
                                <TableHead>Mijoz Ismi</TableHead>
                                <TableHead>Telefon</TableHead>
                                <TableHead>Bonus</TableHead>
                                <TableHead>Balans / Muddat</TableHead>
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
                                    <TableCell className="pl-8">
                                        <div className="font-semibold">{client.name}</div>
                                    </TableCell>
                                    <TableCell className="text-muted-foreground">
                                         {client.phone ? (
                                             <div className="flex items-center gap-2">
                                                 <Phone className="w-3 h-3 text-primary/60" /> {client.phone}
                                             </div>
                                         ) : '-'}
                                    </TableCell>
                                    <TableCell>
                                        <div className="flex items-center gap-2 font-black text-lg text-orange-600">
                                            <Star className="w-5 h-5 fill-orange-500" />
                                            {client.bonus_balance?.toLocaleString() || 0}
                                        </div>
                                    </TableCell>
                                    <TableCell>
                                        <div className={cn("font-black text-lg", client.balance < 0 ? "text-destructive" : "text-emerald-600")}>
                                            {client.balance.toLocaleString()} <span className="text-[10px] text-muted-foreground uppercase">so'm</span>
                                        </div>
                                        {client.balance < 0 && client.debt_due_date && (
                                            <div className={cn(
                                                "text-[10px] flex items-center gap-1 mt-1 font-medium",
                                                isPast(new Date(client.debt_due_date)) ? "text-rose-600 animate-pulse" : "text-slate-500"
                                            )}>
                                                <Calendar className="w-3 h-3" />
                                                {format(new Date(client.debt_due_date), 'dd.MM.yyyy')}
                                            </div>
                                        )}
                                    </TableCell>
                                    <TableCell>
                                        <Badge variant={client.balance < 0 ? "destructive" : "secondary"} className="font-normal">
                                            {client.balance < 0 ? "Qarzdor" : "Aktiv"}
                                        </Badge>
                                    </TableCell>
                                    <TableCell className="text-right pr-8">
                                        <div className="flex justify-end gap-2">
                                            {client.balance < 0 && (
                                                <Button 
                                                    size="sm" 
                                                    variant="outline" 
                                                    className="gap-2 text-emerald-600 border-emerald-200 hover:bg-emerald-50"
                                                    onClick={() => {
                                                        setSelectedClient(client);
                                                        setPaymentData(prev => ({ ...prev, amount: Math.abs(client.balance).toString() }));
                                                        setIsPaymentModalOpen(true);
                                                    }}
                                                >
                                                    <HandCoins className="w-4 h-4" /> To'lov
                                                </Button>
                                            )}
                                            <Button variant="ghost" size="icon">
                                                <MoreHorizontal className="w-4 h-4" />
                                            </Button>
                                        </div>
                                    </TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </CardContent>
            </Card>

            {/* Client Payment Modal */}
            <Dialog open={isPaymentModalOpen} onOpenChange={setIsPaymentModalOpen}>
                <DialogContent className="sm:max-w-[400px]">
                    <DialogHeader>
                        <DialogTitle>Qarz To'lovi: {selectedClient?.name}</DialogTitle>
                    </DialogHeader>
                    <form onSubmit={handlePaymentSubmit}>
                        <div className="grid gap-4 py-4">
                            <div className="grid gap-2">
                                <Label htmlFor="amount">To'lov Summasi</Label>
                                <Input 
                                    id="amount" 
                                    type="number" 
                                    value={paymentData.amount}
                                    onChange={e => setPaymentData({ ...paymentData, amount: e.target.value })}
                                    required
                                    autoFocus
                                />
                            </div>
                            <div className="grid gap-2">
                                <Label htmlFor="method">To'lov Usuli</Label>
                                <Select 
                                    value={paymentData.payment_method} 
                                    onValueChange={val => setPaymentData({...paymentData, payment_method: val})}
                                >
                                    <SelectTrigger id="method">
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="cash">Naqd</SelectItem>
                                        <SelectItem value="card">Plastik Karta</SelectItem>
                                        <SelectItem value="transfer">Perevod</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>
                            <div className="grid gap-2">
                                <Label htmlFor="note">Izoh (ixtiyoriy)</Label>
                                <Input 
                                    id="note" 
                                    value={paymentData.note}
                                    onChange={e => setPaymentData({ ...paymentData, note: e.target.value })}
                                    placeholder="Masalan: Qarzning bir qismi"
                                />
                            </div>
                        </div>
                        <DialogFooter>
                            <Button variant="outline" type="button" onClick={() => setIsPaymentModalOpen(false)}>Bekor qilish</Button>
                            <Button type="submit" disabled={payMutation.isPending}>
                                {payMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                                To'lovni tasdiqlash
                            </Button>
                        </DialogFooter>
                    </form>
                </DialogContent>
            </Dialog>
        </div>
    );
};

export default CRM;
