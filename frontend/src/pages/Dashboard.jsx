
import React from 'react';
import { Link } from 'react-router-dom';
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
import FilterBar from '../components/FilterBar';
import SalesChart from '../components/SalesChart';
import TopProducts from '../components/TopProducts';

const Dashboard = () => {
    const today = new Date().toISOString().split('T')[0];
    const role = localStorage.getItem('role');
    const [filters, setFilters] = React.useState({
        employee_id: '',
        start_date: today,
        end_date: today
    });

    const { data: stats, isLoading, error } = useQuery({
        queryKey: ['dashboard-stats', filters],
        queryFn: async () => {
             const params = {};
             if (filters.employee_id && filters.employee_id !== 'all') params.employee_id = filters.employee_id;
             if (filters.start_date) params.start_date = filters.start_date;
             if (filters.end_date) params.end_date = filters.end_date;

             try {
                const response = await api.get('/finance/stats', { params });
                return response.data;
             } catch (e) {
                console.error("Stats API failed", e);
                throw e;
             }
        }
    });

    if (isLoading) return <div className="p-8">Yuklanmoqda...</div>;
    if (error) return <div className="p-8 text-destructive">Xatolik yuz berdi: {error.message}</div>;

    const cards = [
        {
            title: "Davr Savdosi",
            value: stats?.dailySalesFormatted || "0 so'm",
            icon: DollarSign,
            description: "Tanlangan vaqtdagi tushum",
            color: "text-blue-600 dark:text-blue-400",
            bg: "bg-blue-100/50 dark:bg-blue-900/20",
            iconBg: "bg-blue-100 dark:bg-blue-900/50",
            borderColor: "border-blue-200 dark:border-blue-800"
        },
        ...(role === 'admin' ? [
            {
                title: "Sof Foyda",
                value: stats?.netProfitFormatted || "0 so'm",
                icon: TrendingUp,
                description: "Daromad - Chiqimlar",
                color: "text-emerald-600 dark:text-emerald-400",
                bg: "bg-emerald-100/50 dark:bg-emerald-900/20",
                iconBg: "bg-emerald-100 dark:bg-emerald-900/50",
                borderColor: "border-emerald-200 dark:border-emerald-800"
            }
        ] : []),
        ...(role === 'admin' || role === 'manager' ? [
            {
                title: "Xarajatlar",
                value: `${stats?.totalExpenses?.toLocaleString() || 0} so'm`,
                icon: Briefcase,
                description: "Jami chiqimlar",
                color: "text-amber-600 dark:text-amber-400",
                bg: "bg-amber-100/50 dark:bg-amber-900/20",
                iconBg: "bg-amber-100 dark:bg-amber-900/50",
                borderColor: "border-amber-200 dark:border-amber-800"
            }
        ] : []),
        {
            title: "Mijozlar",
            value: stats?.clientCount || "0",
            icon: Users,
            description: "Jami mijozlar",
            color: "text-indigo-600 dark:text-indigo-400",
            bg: "bg-indigo-100/50 dark:bg-indigo-900/20",
            iconBg: "bg-indigo-100 dark:bg-indigo-900/50",
            borderColor: "border-indigo-200 dark:border-indigo-800"
        }
    ];

    return (
        <div className="space-y-6">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h2 className="text-3xl font-bold tracking-tight">Boshqaruv Paneli</h2>
                    <p className="text-muted-foreground">Do'koningizning umumiy holati</p>
                </div>
                <FilterBar filters={filters} onFilterChange={setFilters} />
            </div>

            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                {cards.map((card, index) => (
                    <Card key={index} className={`hover:shadow-lg transition-all duration-300 border ${card.bg} ${card.borderColor}`}>
                        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                            <CardTitle className="text-sm font-medium text-muted-foreground">
                                {card.title}
                            </CardTitle>
                            <div className={`p-2 rounded-full ${card.iconBg}`}>
                                <card.icon className={`h-5 w-5 ${card.color}`} />
                            </div>
                        </CardHeader>
                        <CardContent>
                            <div className="text-3xl font-bold tracking-tight">{card.value}</div>
                            <p className="text-xs text-muted-foreground mt-1 font-medium">
                                {card.description}
                            </p>
                        </CardContent>
                    </Card>
                ))}
            </div>

            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-7">
                <SalesChart filters={filters} />
                <TopProducts filters={filters} />
            </div>

            {/* Low Stock Section removed */}
            
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-7">
                 <Card className="col-span-7 transition-all hover:shadow-md">
                    <CardHeader>
                        <CardTitle>Tezkor Havolalar</CardTitle>
                        <CardDescription>Tez-tez ishlatiladigan bo'limlarga o'tish</CardDescription>
                    </CardHeader>
                    <CardContent className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                         
                         {/* POS Link */}
                         <Link to="/pos" className="group relative overflow-hidden rounded-2xl border bg-white p-6 shadow-sm transition-all hover:shadow-lg hover:-translate-y-1 hover:border-emerald-200">
                             <div className="absolute inset-0 bg-gradient-to-br from-emerald-50/50 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
                             <div className="relative flex flex-col items-center gap-3 text-center">
                                 <div className="p-4 rounded-2xl bg-emerald-100 text-emerald-600 group-hover:bg-emerald-600 group-hover:text-white transition-colors duration-300">
                                     <DollarSign className="h-8 w-8" />
                                 </div>
                                 <div className="space-y-1">
                                     <h3 className="font-bold text-lg text-gray-900">Yangi Savdo</h3>
                                     <p className="text-sm text-muted-foreground">Sotuv oynasini ochish</p>
                                 </div>
                             </div>
                         </Link>

                         {/* Inventory Link */}
                         <Link to="/inventory" className="group relative overflow-hidden rounded-2xl border bg-white p-6 shadow-sm transition-all hover:shadow-lg hover:-translate-y-1 hover:border-blue-200">
                             <div className="absolute inset-0 bg-gradient-to-br from-blue-50/50 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
                             <div className="relative flex flex-col items-center gap-3 text-center">
                                 <div className="p-4 rounded-2xl bg-blue-100 text-blue-600 group-hover:bg-blue-600 group-hover:text-white transition-colors duration-300">
                                     <Package className="h-8 w-8" />
                                 </div>
                                 <div className="space-y-1">
                                     <h3 className="font-bold text-lg text-gray-900">Mahsulotlar</h3>
                                     <p className="text-sm text-muted-foreground">Omborni boshqarish</p>
                                 </div>
                             </div>
                         </Link>

                         {/* CRM Link */}
                         <Link to="/crm" className="group relative overflow-hidden rounded-2xl border bg-white p-6 shadow-sm transition-all hover:shadow-lg hover:-translate-y-1 hover:border-purple-200">
                             <div className="absolute inset-0 bg-gradient-to-br from-purple-50/50 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
                             <div className="relative flex flex-col items-center gap-3 text-center">
                                 <div className="p-4 rounded-2xl bg-purple-100 text-purple-600 group-hover:bg-purple-600 group-hover:text-white transition-colors duration-300">
                                     <Users className="h-8 w-8" />
                                 </div>
                                 <div className="space-y-1">
                                     <h3 className="font-bold text-lg text-gray-900">Mijozlar</h3>
                                     <p className="text-sm text-muted-foreground">Mijozlar bazasi</p>
                                 </div>
                             </div>
                         </Link>

                         {/* Finance Link */}
                         {(role === 'admin' || role === 'manager') && (
                             <Link to="/finance" className="group relative overflow-hidden rounded-2xl border bg-white p-6 shadow-sm transition-all hover:shadow-lg hover:-translate-y-1 hover:border-amber-200">
                                 <div className="absolute inset-0 bg-gradient-to-br from-amber-50/50 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
                                 <div className="relative flex flex-col items-center gap-3 text-center">
                                     <div className="p-4 rounded-2xl bg-amber-100 text-amber-600 group-hover:bg-amber-600 group-hover:text-white transition-colors duration-300">
                                         <Briefcase className="h-8 w-8" />
                                     </div>
                                     <div className="space-y-1">
                                         <h3 className="font-bold text-lg text-gray-900">Hisobotlar</h3>
                                         <p className="text-sm text-muted-foreground">Moliya va kirim-chiqim</p>
                                     </div>
                                 </div>
                             </Link>
                         )}

                    </CardContent>
                 </Card>
            </div>
        </div>
    );
};

export default Dashboard;
