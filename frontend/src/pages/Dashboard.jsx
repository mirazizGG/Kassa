import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import api from '../api/axios';
import { TrendingUp, Users, Package, AlertTriangle, ArrowRight, ShoppingCart, PlusCircle } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

const StatCard = ({ title, value, icon: Icon, color, trend, description }) => {
    // Helper for dynamic class name merging
    const cn = (...classes) => classes.filter(Boolean).join(' ');

    return (
        <Card className="overflow-hidden border-none shadow-md hover:shadow-lg transition-all duration-200">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">{title}</CardTitle>
                <div className={cn("p-2 rounded-lg bg-opacity-10", color.bg, color.text)}>
                    <Icon className="w-4 h-4" />
                </div>
            </CardHeader>
            <CardContent>
                <div className="text-2xl font-bold">{value}</div>
                <p className="text-xs text-muted-foreground mt-1">
                    {trend ? (
                        <span className="text-emerald-500 font-medium">{trend} o'sish</span>
                    ) : (
                        description || "O'zgarishsiz"
                    )}
                </p>
            </CardContent>
        </Card>
    );
};

const Dashboard = () => {
    const navigate = useNavigate();
    const { data: stats, isLoading, isError } = useQuery({
        queryKey: ['dashboard-stats'],
        queryFn: async () => {
            const res = await api.get('/finance/stats');
            return res.data;
        },
        retry: 1
    });

    if (isLoading) {
        return <div className="flex justify-center items-center h-screen">Yuklanmoqda...</div>;
    }

    if (isError) {
        return (
            <div className="flex flex-col justify-center items-center h-screen text-red-500 gap-4">
                <AlertTriangle className="w-16 h-16" />
                <h2 className="text-2xl font-bold">Server bilan aloqa yo'q!</h2>
                <p>Iltimos, internetni tekshiring yoki administratorga murojaat qiling.</p>
                <Button onClick={() => window.location.reload()}>Qayta urinish</Button>
            </div>
        );
    }

    // Default values if stats is undefined but no error (edge case)
    const displayStats = stats || { dailySales: "0 so'm", clientCount: "0", lowStock: "0", totalProducts: "0" };

    const goToPOS = () => navigate('/pos');
    const goToInventory = () => navigate('/inventory');
    const goToCRM = () => navigate('/crm');
    const goToFinance = () => navigate('/finance');

    return (
        <div className="space-y-8 animate-in fade-in duration-500">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight text-foreground">Asosiy Ko'rsatkichlar</h1>
                    <p className="text-muted-foreground">Bugungi holat va do'kon statistikasi</p>
                </div>
                <div className="flex gap-3">
                    <Button variant="outline" className="gap-2" onClick={goToFinance}>
                        Hisobotlar <ArrowRight className="w-4 h-4" />
                    </Button>
                    <Button className="gap-2 shadow-lg shadow-primary/20" onClick={goToPOS}>
                        <PlusCircle className="w-4 h-4" /> Yangi Savdo
                    </Button>
                </div>
            </div>

            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
                <div className="cursor-pointer" onClick={goToFinance}>
                    <StatCard
                        title="Bugungi Savdo"
                        value={displayStats.dailySales}
                        icon={TrendingUp}
                        color={{ bg: "bg-indigo-500", text: "text-indigo-600" }}
                    />
                </div>
                <div className="cursor-pointer" onClick={goToCRM}>
                    <StatCard
                        title="Mijozlar"
                        value={displayStats.clientCount}
                        icon={Users}
                        color={{ bg: "bg-emerald-500", text: "text-emerald-600" }}
                    />
                </div>
                <div className="cursor-pointer" onClick={goToInventory}>
                    <StatCard
                        title="Kam Qolgan Mahsulotlar"
                        value={displayStats.lowStock}
                        icon={AlertTriangle}
                        color={{ bg: "bg-amber-500", text: "text-amber-600" }}
                        description="Tezda to'ldiring"
                    />
                </div>
                <div className="cursor-pointer" onClick={goToInventory}>
                    <StatCard
                        title="Jami Mahsulotlar"
                        value={displayStats.totalProducts}
                        icon={Package}
                        color={{ bg: "bg-slate-500", text: "text-slate-600" }}
                    />
                </div>
            </div>

            {/* <div className="grid gap-6 md:grid-cols-7">
                ... removed extras ...
            </div> */}
        </div>
    );
};

export default Dashboard;
