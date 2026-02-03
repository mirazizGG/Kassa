import React from 'react';
import {
    TrendingUp,
    TrendingDown,
    DollarSign,
    PieChart,
    Plus,
    Receipt,
    Wallet,
    Calendar,
    User,
    ArrowUpRight,
    Loader2
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../api/axios';
import FilterBar from '../components/FilterBar';
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { toast } from "sonner";
import { format } from "date-fns";

const StatCard = ({ title, value, icon: Icon, type = "neutral" }) => (
    <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">
                {title}
            </CardTitle>
            <Icon className={`h-4 w-4 ${type === 'positive' ? 'text-emerald-500' : type === 'negative' ? 'text-rose-500' : 'text-muted-foreground'}`} />
        </CardHeader>
        <CardContent>
            <div className="text-2xl font-bold">{value}</div>
        </CardContent>
    </Card>
);

const Finance = () => {
    const queryClient = useQueryClient();
    const today = new Date().toISOString().split('T')[0];
    const [filters, setFilters] = React.useState({
        employee_id: '',
        start_date: today,
        end_date: today
    });
    const [isDialogOpen, setIsDialogOpen] = React.useState(false);
    const [newExpense, setNewExpense] = React.useState({
        reason: '',
        amount: '',
        category: 'Boshqa'
    });

    const { data: stats, isLoading: statsLoading } = useQuery({
        queryKey: ['finance-stats', filters],
        queryFn: async () => {
            const params = {};
            if (filters.employee_id && filters.employee_id !== 'all') params.employee_id = filters.employee_id;
            if (filters.start_date) params.start_date = filters.start_date;
            if (filters.end_date) params.end_date = filters.end_date;
            
            const response = await api.get('/finance/stats', { params });
            return response.data;
        }
    });

    const { data: expenses = [], isLoading: expensesLoading } = useQuery({
        queryKey: ['expenses', filters],
        queryFn: async () => {
            const params = {};
            if (filters.employee_id && filters.employee_id !== 'all') params.employee_id = filters.employee_id;
            if (filters.start_date) params.start_date = filters.start_date;
            if (filters.end_date) params.end_date = filters.end_date;
            
            const response = await api.get('/finance/expenses', { params });
            return response.data;
        }
    });

    const expenseMutation = useMutation({
        mutationFn: (data) => api.post('/finance/expenses', data),
        onSuccess: () => {
            queryClient.invalidateQueries(['expenses']);
            queryClient.invalidateQueries(['finance-stats']);
            queryClient.invalidateQueries(['dashboard-stats']);
            toast.success("Xarajat qo'shildi!");
            setIsDialogOpen(false);
            setNewExpense({ reason: '', amount: '', category: 'Boshqa' });
        },
        onError: (error) => {
            toast.error("Xatolik!", { description: error.response?.data?.detail || "Xarajatni qo'shib bo'lmadi" });
        }
    });

    const handleAddExpense = (e) => {
        e.preventDefault();
        if (!newExpense.reason || !newExpense.amount) {
            toast.error("Ma'lumotlarni to'liq kiriting");
            return;
        }
        expenseMutation.mutate({
            ...newExpense,
            amount: parseFloat(newExpense.amount)
        });
    };

    const handleExport = async () => {
        try {
            const params = {};
            if (filters.start_date) params.start_date = filters.start_date;
            if (filters.end_date) params.end_date = filters.end_date;

            const response = await api.get('/finance/export-sales', {
                params,
                responseType: 'blob',
            });
            const url = window.URL.createObjectURL(new Blob([response.data]));
            const link = document.createElement('a');
            link.href = url;
            link.setAttribute('download', `hisobot_${new Date().toISOString().split('T')[0]}.csv`);
            document.body.appendChild(link);
            link.click();
            link.remove();
        } catch (error) {
            console.error('Export error:', error);
            toast.error("Hisobotni yuklab olishda xatolik yuz berdi");
        }
    };

    return (
        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight">Moliya va Hisobotlar</h1>
                    <p className="text-muted-foreground">Do'kon daromadi, xarajatlar va foyda tahlili</p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                    <FilterBar filters={filters} onFilterChange={setFilters} />
                    <Button variant="outline" className="shadow-sm" onClick={handleExport}>
                        Export CSV
                    </Button>
                    
                    <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
                        <DialogTrigger asChild>
                            <Button className="gap-2 shadow-lg shadow-primary/20">
                                <Plus className="h-4 w-4" />
                                Xarajat Qo'shish
                            </Button>
                        </DialogTrigger>
                        <DialogContent>
                            <DialogHeader>
                                <DialogTitle>Yangi Xarajat Kiritish</DialogTitle>
                                <DialogDescription>
                                    Do'kon uchun qilingan chiqimni ro'yxatga oling.
                                </DialogDescription>
                            </DialogHeader>
                            <form onSubmit={handleAddExpense} className="space-y-4 pt-4">
                                <div className="space-y-2">
                                    <Label htmlFor="reason">Xarajat sababi</Label>
                                    <Input 
                                        id="reason" 
                                        placeholder="Masalan: Ijara to'lovi" 
                                        value={newExpense.reason}
                                        onChange={e => setNewExpense({...newExpense, reason: e.target.value})}
                                    />
                                </div>
                                <div className="grid grid-cols-2 gap-4">
                                    <div className="space-y-2">
                                        <Label htmlFor="amount">Summa (so'm)</Label>
                                        <Input 
                                            id="amount" 
                                            type="number" 
                                            placeholder="100000" 
                                            value={newExpense.amount}
                                            onChange={e => setNewExpense({...newExpense, amount: e.target.value})}
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <Label htmlFor="category">Kategoriya</Label>
                                        <Select 
                                            value={newExpense.category} 
                                            onValueChange={v => setNewExpense({...newExpense, category: v})}
                                        >
                                            <SelectTrigger>
                                                <SelectValue />
                                            </SelectTrigger>
                                            <SelectContent>
                                                <SelectItem value="Boshqa">Boshqa</SelectItem>
                                                <SelectItem value="Ijara">Ijara</SelectItem>
                                                <SelectItem value="Ish haqi">Ish haqi</SelectItem>
                                                <SelectItem value="Oziq-ovqat">Oziq-ovqat</SelectItem>
                                                <SelectItem value="Logistika">Logistika</SelectItem>
                                                <SelectItem value="Soliq">Soliq</SelectItem>
                                                <SelectItem value="Kommunal">Kommunal</SelectItem>
                                            </SelectContent>
                                        </Select>
                                    </div>
                                </div>
                                <DialogFooter className="pt-4">
                                    <Button type="button" variant="ghost" onClick={() => setIsDialogOpen(false)}>Bekor qilish</Button>
                                    <Button type="submit" disabled={expenseMutation.isPending}>
                                        {expenseMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                                        Saqlash
                                    </Button>
                                </DialogFooter>
                            </form>
                        </DialogContent>
                    </Dialog>
                </div>
            </div>

            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                <StatCard
                    title="Umumiy Savdo"
                    value={statsLoading ? "..." : stats?.dailySalesFormatted || "0 so'm"}
                    icon={DollarSign}
                    type="positive"
                />
                <StatCard
                    title="Mahsulot Tannarxi"
                    value={statsLoading ? "..." : `${stats?.totalCost?.toLocaleString() || 0} so'm`}
                    icon={Receipt}
                    type="negative"
                />
                <StatCard
                    title="Umumiy Xarajat"
                    value={statsLoading ? "..." : `${stats?.totalExpenses?.toLocaleString() || 0} so'm`}
                    icon={TrendingDown}
                    type="negative"
                />
                <Card className="bg-primary/5 border-primary/20">
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Sof Foyda</CardTitle>
                        <TrendingUp className="h-4 w-4 text-primary" />
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold text-primary">{statsLoading ? "..." : stats?.netProfitFormatted || "0 so'm"}</div>
                        <p className="text-xs text-muted-foreground mt-1">Savdo - Tannarx - Xarajat</p>
                    </CardContent>
                </Card>
            </div>

            <div className="grid gap-6 md:grid-cols-7">
                <Card className="md:col-span-4 border-none shadow-md overflow-hidden bg-background/60 backdrop-blur-xl">
                    <CardHeader>
                        <div className="flex items-center justify-between">
                            <div>
                                <CardTitle className="flex items-center gap-2">
                                    <Wallet className="w-5 h-5 text-primary" />
                                    Xarajatlar Tarixi
                                </CardTitle>
                                <CardDescription>Oxirgi kiritilgan chiqimlar ro'yxati</CardDescription>
                            </div>
                        </div>
                    </CardHeader>
                    <CardContent className="p-0">
                        <Table>
                            <TableHeader className="bg-muted/30">
                                <TableRow>
                                    <TableHead className="pl-6">Sabab / Kategoriya</TableHead>
                                    <TableHead>Summa</TableHead>
                                    <TableHead>Xodim</TableHead>
                                    <TableHead className="pr-6">Sana</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {expensesLoading ? (
                                     [1, 2, 3].map(i => (
                                        <TableRow key={i}><TableCell colSpan={4} className="h-12 text-center">Yuklanmoqda...</TableCell></TableRow>
                                     ))
                                ) : expenses.length === 0 ? (
                                    <TableRow>
                                        <TableCell colSpan={4} className="h-32 text-center text-muted-foreground">
                                            Hozircha xarajatlar yo'q
                                        </TableCell>
                                    </TableRow>
                                ) : expenses.map((exp) => (
                                    <TableRow key={exp.id}>
                                        <TableCell className="pl-6">
                                            <div className="font-medium">{exp.reason}</div>
                                            <div className="text-[10px] text-muted-foreground uppercase">{exp.category}</div>
                                        </TableCell>
                                        <TableCell className="font-mono text-rose-500">
                                            -{exp.amount.toLocaleString()} so'm
                                        </TableCell>
                                        <TableCell>
                                            <div className="flex items-center gap-1 text-xs">
                                                <User className="w-3 h-3 opacity-50" />
                                                {exp.creator?.username || "Tizim"}
                                            </div>
                                        </TableCell>
                                        <TableCell className="pr-6 text-xs text-muted-foreground">
                                            <div className="flex items-center gap-1">
                                                <Calendar className="w-3 h-3 opacity-50" />
                                                {format(new Date(exp.created_at), 'dd.MM.yyyy HH:mm')}
                                            </div>
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </CardContent>
                </Card>

                <Card className="md:col-span-3 flex flex-col justify-center items-center text-center p-8 border-dashed">
                    <PieChart className="w-16 h-16 text-muted-foreground mb-4 opacity-20" />
                    <h3 className="text-xl font-semibold mb-2">Tahliliy Grafiklar</h3>
                    <p className="text-muted-foreground mb-6 max-w-[250px]">
                        Xarajatlar turlari va foyda dinamikasi bo'yicha vizual tahlil tez orada tayyor bo'ladi.
                    </p>
                    <Button variant="outline" className="gap-2" disabled>
                        Batafsil Tahlil <ArrowUpRight className="h-4 w-4" />
                    </Button>
                </Card>
            </div>
        </div>
    );
};

export default Finance;
