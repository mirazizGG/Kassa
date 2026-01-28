
import React from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { useQuery } from '@tanstack/react-query';
import api from '../api/axios';
import {
    Users,
    Package,
    AlertTriangle,
    DollarSign,
    TrendingUp,
    Briefcase
} from 'lucide-react';
import SalesChart from '../components/SalesChart';
import TopProducts from '../components/TopProducts';

const Dashboard = () => {
    const { data: stats, isLoading, error } = useQuery({
        queryKey: ['dashboard-stats'],
        queryFn: async () => {
             // Mock data fallback if API fails (or handle gracefully)
             try {
                const response = await api.get('/finance/stats');
                return response.data;
             } catch (e) {
                console.error("Stats API failed", e);
                // Return dummy data for dev if needed, or rethrow
                throw e;
             }
        }
    });

    if (isLoading) return <div className="p-8">Yuklanmoqda...</div>;
    if (error) return <div className="p-8 text-destructive">Xatolik yuz berdi: {error.message}</div>;

    const cards = [
        {
            title: "Kunlik Savdo",
            value: stats?.dailySales || "0 so'm",
            icon: DollarSign,
            description: "Bugungi tushum",
            color: "text-green-500"
        },
        {
            title: "Mijozlar",
            value: stats?.clientCount || "0",
            icon: Users,
            description: "Jami mijozlar",
            color: "text-blue-500"
        },
        {
            title: "Kam Qolgan",
            value: stats?.lowStock || "0",
            icon: AlertTriangle,
            description: "Tugayotgan mahsulotlar",
            color: "text-amber-500"
        },
        {
            title: "Mahsulotlar",
            value: stats?.totalProducts || "0",
            icon: Package,
            description: "Jami nomdagi mahsulot",
            color: "text-purple-500"
        }
    ];

    return (
        <div className="space-y-6">
            <div>
                <h2 className="text-3xl font-bold tracking-tight">Boshqaruv Paneli</h2>
                <p className="text-muted-foreground">Do'koningizning umumiy holati</p>
            </div>

            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                {cards.map((card, index) => (
                    <Card key={index} className="hover:shadow-md transition-shadow">
                        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                            <CardTitle className="text-sm font-medium">
                                {card.title}
                            </CardTitle>
                            <card.icon className={`h-4 w-4 ${card.color}`} />
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-bold">{card.value}</div>
                            <p className="text-xs text-muted-foreground">
                                {card.description}
                            </p>
                        </CardContent>
                    </Card>
                ))}
            </div>

            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-7">
                <SalesChart />
                <TopProducts />
            </div>
            
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-7">
                 <Card className="col-span-7">
                    <CardHeader>
                        <CardTitle>Tezkor Havolalar</CardTitle>
                        <CardDescription>Tez-tez ishlatiladigan bo'limlarga o'tish</CardDescription>
                    </CardHeader>
                    <CardContent className="grid grid-cols-2 md:grid-cols-4 gap-4">
                         {/* Quick Links can go here if needed later */}
                         <div className="p-4 border rounded-lg hover:bg-muted/50 transition-colors cursor-pointer flex flex-col items-center justify-center gap-2 text-center text-muted-foreground hover:text-foreground">
                             <DollarSign className="h-6 w-6" />
                             <span>Yangi Savdo</span>
                         </div>
                          <div className="p-4 border rounded-lg hover:bg-muted/50 transition-colors cursor-pointer flex flex-col items-center justify-center gap-2 text-center text-muted-foreground hover:text-foreground">
                             <Package className="h-6 w-6" />
                             <span>Mahsulot Qo'shish</span>
                         </div>
                          <div className="p-4 border rounded-lg hover:bg-muted/50 transition-colors cursor-pointer flex flex-col items-center justify-center gap-2 text-center text-muted-foreground hover:text-foreground">
                             <Users className="h-6 w-6" />
                             <span>Mijoz Qo'shish</span>
                         </div>
                          <div className="p-4 border rounded-lg hover:bg-muted/50 transition-colors cursor-pointer flex flex-col items-center justify-center gap-2 text-center text-muted-foreground hover:text-foreground">
                             <Briefcase className="h-6 w-6" />
                             <span>Hisobotlarni Ko'rish</span>
                         </div>
                    </CardContent>
                 </Card>
            </div>
        </div>
    );
};

export default Dashboard;
