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
    const { data: stats = { dailySales: "0 so'm", clientCount: "0", lowStock: "0", totalProducts: "0" } } = useQuery({
        queryKey: ['dashboard-stats'],
        queryFn: async () => {
            const res = await api.get('/finance/stats');
            return res.data;
        }
    });

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
                        value={stats.dailySales}
                        icon={TrendingUp}
                        color={{ bg: "bg-indigo-500", text: "text-indigo-600" }}
                    />
                </div>
                <div className="cursor-pointer" onClick={goToCRM}>
                    <StatCard
                        title="Mijozlar"
                        value={stats.clientCount}
                        icon={Users}
                        color={{ bg: "bg-emerald-500", text: "text-emerald-600" }}
                    />
                </div>
                <div className="cursor-pointer" onClick={goToInventory}>
                    <StatCard
                        title="Kam Qolgan Mahsulotlar"
                        value={stats.lowStock}
                        icon={AlertTriangle}
                        color={{ bg: "bg-amber-500", text: "text-amber-600" }}
                        description="Tezda to'ldiring"
                    />
                </div>
                <div className="cursor-pointer" onClick={goToInventory}>
                    <StatCard
                        title="Jami Mahsulotlar"
                        value={stats.totalProducts}
                        icon={Package}
                        color={{ bg: "bg-slate-500", text: "text-slate-600" }}
                    />
                </div>
            </div>

            <div className="grid gap-6 md:grid-cols-7">
                <Card className="col-span-4 border-none shadow-md overflow-hidden bg-card">
                    <CardHeader className="flex flex-row items-center justify-between">
                        <div>
                            <CardTitle>Oxirgi Savdolar</CardTitle>
                            <CardDescription>Do'kondagi so'nggi tranzaksiyalar ro'yxati</CardDescription>
                        </div>
                        <Button variant="ghost" size="sm" className="text-primary font-semibold" onClick={goToPOS}>
                            Barchasi
                        </Button>
                    </CardHeader>
                    <CardContent className="p-0">
                        <Table>
                            <TableHeader className="bg-muted/50">
                                <TableRow>
                                    <TableHead className="pl-6">Vaqt</TableHead>
                                    <TableHead>Mijoz</TableHead>
                                    <TableHead>Summa</TableHead>
                                    <TableHead className="pr-6">Status</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                <TableRow>
                                    <TableCell colSpan={4} className="h-24 text-center text-muted-foreground">
                                        Hozircha savdolar yo'q. POS sahifasidan yangi savdo qo'shing.
                                    </TableCell>
                                </TableRow>
                            </TableBody>
                        </Table>
                    </CardContent>
                </Card>

                <Card className="col-span-3 border-none shadow-md bg-card/80 backdrop-blur-xl">
                    <CardHeader>
                        <CardTitle>Tezkor Amallar</CardTitle>
                        <CardDescription>Tez-tez ishlatiladigan funksiyalar</CardDescription>
                    </CardHeader>
                    <CardContent className="grid gap-4">
                        <Button className="w-full justify-start h-12 text-base gap-3" size="lg" onClick={goToPOS}>
                            <ShoppingCart className="w-5 h-5" /> Yangi Savdo Boshlash
                        </Button>
                        <Button variant="outline" className="w-full justify-start h-12 text-base gap-3" size="lg" onClick={goToCRM}>
                            <Users className="w-5 h-5" /> Mijoz Qo'shish
                        </Button>
                        <Button variant="outline" className="w-full justify-start h-12 text-base gap-3 border-dashed" size="lg" onClick={goToInventory}>
                            <Package className="w-5 h-5" /> Omborni Ko'zdan Kechirish
                        </Button>
                    </CardContent>
                    <CardFooter className="pt-2 border-t mt-4">
                        <p className="text-xs text-center w-full text-muted-foreground">
                            Tezkor amallar uchun
                        </p>
                    </CardFooter>
                </Card>
            </div>
        </div>
    );
};

export default Dashboard;
