import { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import api, { API_URL } from '../api/axios';
import { queryClient } from '../api/queryClient';
import {
    Truck,
    Plus,
    Search,
    History,
    FileText,
    CreditCard,
    MoreHorizontal,
    Image as ImageIcon,
    Loader2,
    Calendar,
    Phone,
    MapPin,
    ArrowUpRight,
    ArrowDownLeft,
    ChevronRight,
    Eye
} from 'lucide-react';
import { format } from "date-fns";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "@/components/ui/dialog";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { toast } from "sonner";
import { cn } from "@/lib/utils.js";

const Suppliers = () => {
    const [searchTerm, setSearchTerm] = useState('');
    const [isAddSupplierOpen, setIsAddSupplierOpen] = useState(false);
    const [isAddSupplyOpen, setIsAddSupplyOpen] = useState(false);
    const [isAddPaymentOpen, setIsAddPaymentOpen] = useState(false);
    const [selectedSupplier, setSelectedSupplier] = useState(null);
    const [isHistoryOpen, setIsHistoryOpen] = useState(false);

    // Form states
    const [newSupplier, setNewSupplier] = useState({ name: '', phone: '' });
    const [newSupply, setNewSupply] = useState({ supplier_id: '', total_amount: '', note: '', image: null });
    const [newPayment, setNewPayment] = useState({ supplier_id: '', amount: '', payment_method: 'cash', note: '' });
    
    // Search states for selection
    const [supplySearch, setSupplySearch] = useState('');
    const [paymentSearch, setPaymentSearch] = useState('');

    // Queries
    const { data: suppliers = [], isLoading } = useQuery({
        queryKey: ['suppliers'],
        queryFn: async () => {
            const res = await api.get('/suppliers/');
            return res.data;
        }
    });

    const { data: history = [], isLoading: historyLoading } = useQuery({
        queryKey: ['supplier-history', selectedSupplier?.id],
        queryFn: async () => {
            const res = await api.get(`/suppliers/${selectedSupplier.id}/history`);
            return res.data;
        },
        enabled: !!selectedSupplier && isHistoryOpen
    });

    // Mutations
    const addSupplierMutation = useMutation({
        mutationFn: (data) => api.post('/suppliers/', data),
        onSuccess: () => {
            queryClient.invalidateQueries(['suppliers']);
            setIsAddSupplierOpen(false);
            setNewSupplier({ name: '', phone: '' });
            toast.success("Firma muvaffaqiyatli qo'shildi");
        }
    });

    const addSupplyMutation = useMutation({
        mutationFn: (formData) => api.post('/suppliers/receipts', formData, {
            headers: { 'Content-Type': 'multipart/form-data' }
        }),
        onSuccess: () => {
            queryClient.invalidateQueries(['suppliers']);
            queryClient.invalidateQueries(['supplier-history']);
            setIsAddSupplyOpen(false);
            setNewSupply({ supplier_id: '', total_amount: '', note: '', image: null });
            toast.success("Kirim muvaffaqiyatli qayd etildi");
        }
    });

    const addPaymentMutation = useMutation({
        mutationFn: (formData) => api.post('/suppliers/payments', formData, {
            headers: { 'Content-Type': 'multipart/form-data' }
        }),
        onSuccess: () => {
            queryClient.invalidateQueries(['suppliers']);
            queryClient.invalidateQueries(['supplier-history']);
            setIsAddPaymentOpen(false);
            setNewPayment({ supplier_id: '', amount: '', payment_method: 'cash', note: '' });
            toast.success("To'lov muvaffaqiyatli qayd etildi");
        }
    });

    // Handlers
    const handleAddSupply = (e) => {
        e.preventDefault();
        const fd = new FormData();
        fd.append('supplier_id', newSupply.supplier_id);
        fd.append('total_amount', newSupply.total_amount);
        fd.append('note', newSupply.note);
        if (newSupply.image) fd.append('image', newSupply.image);
        addSupplyMutation.mutate(fd);
    };

    const handleAddPayment = (e) => {
        e.preventDefault();
        const fd = new FormData();
        fd.append('supplier_id', newPayment.supplier_id);
        fd.append('amount', newPayment.amount);
        fd.append('payment_method', newPayment.payment_method);
        fd.append('note', newPayment.note);
        addPaymentMutation.mutate(fd);
    };

    const filteredSuppliers = suppliers.filter(s => 
        s.name.toLowerCase().startsWith(searchTerm.toLowerCase()) || 
        s.phone?.includes(searchTerm)
    );

    return (
        <div className="space-y-6 p-4">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight">Firmalar (Postavshiklar)</h1>
                    <p className="text-muted-foreground">Kirimlar, to'lovlar va qarzlar nazorati</p>
                </div>
                <div className="flex gap-2">
                    <Dialog open={isAddSupplierOpen} onOpenChange={setIsAddSupplierOpen}>
                        <DialogTrigger asChild>
                            <Button className="gap-2 shadow-lg shadow-primary/20">
                                <Plus className="h-4 w-4" /> Yangi Firma
                            </Button>
                        </DialogTrigger>
                        <DialogContent>
                            <DialogHeader>
                                <DialogTitle>Yangi Firma Qo'shish</DialogTitle>
                                <DialogDescription>Firma ma'lumotlarini kiriting.</DialogDescription>
                            </DialogHeader>
                            <div className="grid gap-4 py-4">
                                <div className="space-y-2">
                                    <Label>Firma Nomi</Label>
                                    <Input value={newSupplier.name} onChange={e => setNewSupplier({...newSupplier, name: e.target.value})} placeholder="Masalan: Artel" />
                                </div>
                                <div className="space-y-2">
                                    <Label>Telefon</Label>
                                    <Input value={newSupplier.phone} onChange={e => setNewSupplier({...newSupplier, phone: e.target.value})} placeholder="+998 90 123 45 67" />
                                </div>
                            </div>
                            <DialogFooter>
                                <Button onClick={() => addSupplierMutation.mutate(newSupplier)} disabled={addSupplierMutation.isPending}>
                                    {addSupplierMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                                    Saqlash
                                </Button>
                            </DialogFooter>
                        </DialogContent>
                    </Dialog>

                    <Button variant="outline" className="gap-2" onClick={() => setIsAddSupplyOpen(true)}>
                        <Truck className="h-4 w-4" /> Kirim Qilish
                    </Button>
                    <Button variant="secondary" className="gap-2" onClick={() => setIsAddPaymentOpen(true)}>
                        <CreditCard className="h-4 w-4" /> To'lov Qilish
                    </Button>
                </div>
            </div>

            <Card className="border-none shadow-md overflow-hidden bg-card/50 backdrop-blur">
                <CardHeader className="p-6">
                    <div className="relative max-w-md">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                        <Input 
                            placeholder="Firma qidirish..." 
                            className="pl-10 h-10" 
                            value={searchTerm} 
                            onChange={e => setSearchTerm(e.target.value)}
                        />
                    </div>
                </CardHeader>
                <CardContent className="p-0 border-t">
                    <Table>
                        <TableHeader className="bg-muted/30">
                            <TableRow>
                                <TableHead className="pl-6">Firma</TableHead>
                                <TableHead>Aloqa</TableHead>
                                <TableHead className="text-right">Joriy Qarzimiz</TableHead>
                                <TableHead className="pr-6 text-right">Amallar</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {isLoading ? (
                                <TableRow><TableCell colSpan={4} className="h-24 text-center">Yuklanmoqda...</TableCell></TableRow>
                            ) : filteredSuppliers.length === 0 ? (
                                <TableRow><TableCell colSpan={4} className="h-24 text-center text-muted-foreground">Firmalar topilmadi</TableCell></TableRow>
                            ) : filteredSuppliers.map(s => (
                                <TableRow key={s.id} className="cursor-pointer hover:bg-muted/50 transition-colors" onClick={() => {
                                    setSelectedSupplier(s);
                                    setIsHistoryOpen(true);
                                }}>
                                    <TableCell className="pl-6 py-4">
                                        <div className="font-bold text-lg">{s.name}</div>
                                    </TableCell>
                                    <TableCell>
                                        <div className="flex items-center gap-1 text-sm">
                                            <Phone className="h-3 w-3 text-muted-foreground" />
                                            {s.phone || '-'}
                                        </div>
                                    </TableCell>
                                    <TableCell className="text-right">
                                        <Badge variant={s.balance > 0 ? "destructive" : "secondary"} className="text-base font-bold px-3">
                                            {s.balance.toLocaleString()} so'm
                                        </Badge>
                                    </TableCell>
                                    <TableCell className="pr-6 text-right">
                                        <Button variant="ghost" size="sm" className="gap-1">
                                            Sverka <ChevronRight className="h-4 w-4" />
                                        </Button>
                                    </TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </CardContent>
            </Card>

            {/* Sverka / History Dialog */}
            <Dialog open={isHistoryOpen} onOpenChange={setIsHistoryOpen}>
                <DialogContent className="sm:max-w-[800px] max-h-[90vh] flex flex-col p-0 overflow-hidden">
                    <DialogHeader className="p-6 pb-2 border-b">
                        <div className="flex justify-between items-start">
                            <div>
                                <DialogTitle className="text-2xl font-bold">{selectedSupplier?.name}</DialogTitle>
                                <DialogDescription>To'liq hisob-kitoblar tarixi</DialogDescription>
                            </div>
                            <Badge variant={selectedSupplier?.balance > 0 ? "destructive" : "secondary"} className="text-lg py-1 px-4">
                                Jami Qarz: {selectedSupplier?.balance.toLocaleString()}
                            </Badge>
                        </div>
                    </DialogHeader>
                    <ScrollArea className="flex-1 p-6">
                        <div className="space-y-4">
                            {historyLoading ? (
                                <div className="text-center py-10">Yuklanmoqda...</div>
                            ) : history.length === 0 ? (
                                <div className="text-center py-10 text-muted-foreground">Tarix bo'sh</div>
                            ) : history.map((item, idx) => (
                                <div key={idx} className={cn(
                                    "flex items-center gap-4 p-4 rounded-xl border transition-all",
                                    item.type === 'receipt' ? "bg-red-50/10 border-red-100" : "bg-emerald-50/10 border-emerald-100"
                                )}>
                                    <div className={cn(
                                        "p-3 rounded-full shrink-0",
                                        item.type === 'receipt' ? "bg-red-100 text-red-600" : "bg-emerald-100 text-emerald-600"
                                    )}>
                                        {item.type === 'receipt' ? <ArrowUpRight className="h-5 w-5" /> : <ArrowDownLeft className="h-5 w-5" />}
                                    </div>
                                    <div className="flex-1">
                                        <div className="flex justify-between">
                                            <span className="font-bold text-lg">
                                                {item.type === 'receipt' ? 'Mahsulot Keldi (Kirim)' : 'To\'lov Qilindi'}
                                            </span>
                                            <span className={cn(
                                                "font-black text-lg",
                                                item.type === 'receipt' ? "text-red-600" : "text-emerald-600"
                                            )}>
                                                {item.type === 'receipt' ? '+' : '-'}{item.amount.toLocaleString()} so'm
                                            </span>
                                        </div>
                                        <div className="flex items-center gap-4 text-sm text-muted-foreground mt-1">
                                            <span className="flex items-center gap-1"><Calendar className="h-3 w-3" /> {format(new Date(item.date), 'dd.MM.yyyy HH:mm')}</span>
                                            {item.note && <span className="italic">"{item.note}"</span>}
                                            {item.method && <Badge variant="outline" className="text-[10px] uppercase font-bold">{item.method}</Badge>}
                                        </div>
                                    </div>
                                    {item.image && (
                                        <a href={`${API_URL}${item.image}`} target="_blank" rel="noreferrer" className="shrink-0 bg-white border p-1 rounded-lg hover:shadow-md transition-all">
                                            <div className="relative group">
                                                <img src={`${API_URL}${item.image}`} alt="Nakladnoy" className="w-16 h-16 object-cover rounded shadow-inner" />
                                                <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity rounded">
                                                    <Eye className="h-5 w-5 text-white" />
                                                </div>
                                            </div>
                                        </a>
                                    )}
                                </div>
                            ))}
                        </div>
                    </ScrollArea>
                </DialogContent>
            </Dialog>

            {/* Add Supply Modal */}
            <Dialog open={isAddSupplyOpen} onOpenChange={setIsAddSupplyOpen}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Kirimni Ro'yxatdan O'tkazish</DialogTitle>
                        <DialogDescription>Firma tomonidan kelgan nakladnoyni kiriting.</DialogDescription>
                    </DialogHeader>
                    <form onSubmit={handleAddSupply} className="space-y-4 py-4">
                        <div className="space-y-2">
                            <Label>Firmani Tanlang</Label>
                            <div className="relative">
                                <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                                <Input 
                                    placeholder="Firma qidirish..." 
                                    className="pl-9 mb-2"
                                    value={supplySearch}
                                    onChange={e => setSupplySearch(e.target.value)}
                                />
                            </div>
                            <ScrollArea className="h-[150px] border rounded-md p-2">
                                {suppliers.filter(s => s.name.toLowerCase().startsWith(supplySearch.toLowerCase())).length === 0 ? (
                                    <div className="text-center py-4 text-muted-foreground italic text-sm">
                                        Yo'q (Firma topilmadi)
                                    </div>
                                ) : (
                                    <div className="space-y-1">
                                        {suppliers
                                            .filter(s => s.name.toLowerCase().startsWith(supplySearch.toLowerCase()))
                                            .map(s => (
                                                <div 
                                                    key={s.id}
                                                    onClick={() => {
                                                        setNewSupply({...newSupply, supplier_id: s.id});
                                                        setSupplySearch(''); // Clear search after selection
                                                    }}
                                                    className={cn(
                                                        "flex items-center justify-between p-2 rounded-md cursor-pointer text-sm transition-colors",
                                                        newSupply.supplier_id == s.id ? "bg-primary text-primary-foreground" : "hover:bg-muted"
                                                    )}
                                                >
                                                    <span className="font-medium">{s.name}</span>
                                                    <Badge variant={newSupply.supplier_id == s.id ? "secondary" : "outline"} className="text-[10px]">
                                                        Qarz: {s.balance.toLocaleString()}
                                                    </Badge>
                                                </div>
                                            ))
                                        }
                                    </div>
                                )}
                            </ScrollArea>
                            {newSupply.supplier_id && (
                                <div className="text-[10px] text-emerald-600 font-bold mt-1">
                                    Tanlandi: {suppliers.find(s => s.id == newSupply.supplier_id)?.name}
                                </div>
                            )}
                        </div>
                        <div className="space-y-2">
                            <Label>Jami Summa (Nakladnoy summasi)</Label>
                            <Input type="number" value={newSupply.total_amount} onChange={e => setNewSupply({...newSupply, total_amount: e.target.value})} required />
                        </div>
                        <div className="space-y-2">
                            <Label>Izoh</Label>
                            <Input value={newSupply.note} onChange={e => setNewSupply({...newSupply, note: e.target.value})} placeholder="Masalan: Shakar va yog' keldi" />
                        </div>
                        <div className="space-y-2">
                            <Label>Nakladnoy Rasmi (ixtiyoriy)</Label>
                            <div className="flex items-center gap-2">
                                <Input type="file" accept="image/*" onChange={e => setNewSupply({...newSupply, image: e.target.files[0]})} className="cursor-pointer" />
                                {newSupply.image && <ImageIcon className="text-emerald-500 h-6 w-6" />}
                            </div>
                        </div>
                        <DialogFooter>
                            <Button type="submit" disabled={addSupplyMutation.isPending} className="w-full">
                                {addSupplyMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                                Kirimni Saqlash
                            </Button>
                        </DialogFooter>
                    </form>
                </DialogContent>
            </Dialog>

            {/* Add Payment Modal */}
            <Dialog open={isAddPaymentOpen} onOpenChange={setIsAddPaymentOpen}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Firma Haqini To'lash</DialogTitle>
                        <DialogDescription>Firmaga berilgan pulni qayd eting.</DialogDescription>
                    </DialogHeader>
                    <form onSubmit={handleAddPayment} className="space-y-4 py-4">
                        <div className="space-y-2">
                            <Label>Firmani Tanlang</Label>
                            <div className="relative">
                                <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                                <Input 
                                    placeholder="Firma qidirish..." 
                                    className="pl-9 mb-2"
                                    value={paymentSearch}
                                    onChange={e => setPaymentSearch(e.target.value)}
                                />
                            </div>
                            <ScrollArea className="h-[150px] border rounded-md p-2">
                                {suppliers.filter(s => s.name.toLowerCase().startsWith(paymentSearch.toLowerCase())).length === 0 ? (
                                    <div className="text-center py-4 text-muted-foreground italic text-sm">
                                        Yo'q (Firma topilmadi)
                                    </div>
                                ) : (
                                    <div className="space-y-1">
                                        {suppliers
                                            .filter(s => s.name.toLowerCase().startsWith(paymentSearch.toLowerCase()))
                                            .map(s => (
                                                <div 
                                                    key={s.id}
                                                    onClick={() => {
                                                        setNewPayment({...newPayment, supplier_id: s.id});
                                                        setPaymentSearch(''); // Clear search after selection
                                                    }}
                                                    className={cn(
                                                        "flex items-center justify-between p-2 rounded-md cursor-pointer text-sm transition-colors",
                                                        newPayment.supplier_id == s.id ? "bg-primary text-primary-foreground" : "hover:bg-muted"
                                                    )}
                                                >
                                                    <span className="font-medium">{s.name}</span>
                                                    <Badge variant={newPayment.supplier_id == s.id ? "secondary" : "outline"} className="text-[10px]">
                                                        Qarz: {s.balance.toLocaleString()}
                                                    </Badge>
                                                </div>
                                            ))
                                        }
                                    </div>
                                )}
                            </ScrollArea>
                            {newPayment.supplier_id && (
                                <div className="text-[10px] text-emerald-600 font-bold mt-1">
                                    Tanlandi: {suppliers.find(s => s.id == newPayment.supplier_id)?.name}
                                </div>
                            )}
                        </div>
                        <div className="space-y-2">
                            <Label>To'lov Summasi</Label>
                            <Input type="number" value={newPayment.amount} onChange={e => setNewPayment({...newPayment, amount: e.target.value})} required />
                        </div>
                        <div className="space-y-2">
                            <Label>To'lov Usuli</Label>
                            <select 
                                className="w-full flex h-10 rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring"
                                value={newPayment.payment_method}
                                onChange={e => setNewPayment({...newPayment, payment_method: e.target.value})}
                            >
                                <option value="cash">Naqd (Kassadan)</option>
                                <option value="safe">Naqd (Seyfdan)</option>
                                <option value="card">Plastik Card</option>
                                <option value="transfer">Perechisleniya</option>
                            </select>
                        </div>
                        <div className="space-y-2">
                            <Label>Izoh</Label>
                            <Input value={newPayment.note} onChange={e => setNewPayment({...newPayment, note: e.target.value})} placeholder="Masalan: Shakar pulidan 1 mln berildi" />
                        </div>
                        <DialogFooter>
                            <Button type="submit" disabled={addPaymentMutation.isPending} className="w-full bg-emerald-600 hover:bg-emerald-700">
                                {addPaymentMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                                To'lovni Saqlash
                            </Button>
                        </DialogFooter>
                    </form>
                </DialogContent>
            </Dialog>
        </div>
    );
};

export default Suppliers;
