import React from 'react';
import {
    TrendingUp,
    TrendingDown,
    DollarSign,
    PieChart
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useQuery } from '@tanstack/react-query';
import api from '../api/axios';
import FilterBar from '../components/FilterBar';

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
    const today = new Date().toISOString().split('T')[0];
    const [filters, setFilters] = React.useState({
        employee_id: '',
        start_date: today,
        end_date: today
    });

    const { data: stats, isLoading } = useQuery({
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

    const handleExport = async () => {
        try {
            const params = {};
            if (filters.start_date) params.start_date = filters.start_date;
            if (filters.end_date) params.end_date = filters.end_date;

            const response = await api.get('/finance/reports/export', {
                params,
                responseType: 'blob',
            });
            const url = window.URL.createObjectURL(new Blob([response.data]));
            const link = document.createElement('a');
            link.href = url;
            link.setAttribute('download', `sotuvlar_${new Date().toISOString().split('T')[0]}.csv`);
            document.body.appendChild(link);
            link.click();
            link.remove();
        } catch (error) {
            console.error('Export error:', error);
            alert("Hisobotni yuklab olishda xatolik yuz berdi");
        }
    };

    return (
        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight">Moliya va Hisobotlar</h1>
                    <p className="text-muted-foreground">Do'kon daromadi, xarajatlar va foyda tahlili</p>
                </div>
                <div className="flex items-center gap-2">
                    <FilterBar filters={filters} onFilterChange={setFilters} />
                    <Button className="shadow-lg shadow-primary/20" onClick={handleExport}>
                        To'liq Hisobot (Excel/CSV)
                    </Button>
                </div>
            </div>

            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                <StatCard
                    title="Jami Savdo"
                    value={isLoading ? "..." : stats?.dailySales || "0 so'm"}
                    icon={DollarSign}
                    type="positive"
                />
                <StatCard
                    title="Sof Foyda"
                    value="Hozircha hisoblanmadi"
                    icon={TrendingUp}
                    type="positive"
                />
                <StatCard
                    title="Xarajatlar"
                    value="0 so'm"
                    icon={TrendingDown}
                    type="negative"
                />
                <StatCard
                    title="Mijozlar"
                    value={isLoading ? "..." : stats?.clientCount || "0"}
                    icon={PieChart}
                />
            </div>

            <Card className="h-[400px] flex items-center justify-center border-dashed">
                <div className="text-center text-muted-foreground">
                    <PieChart className="w-12 h-12 mx-auto mb-4 opacity-50" />
                    <h3 className="text-lg font-medium">Grafiklar tez orada qo'shiladi</h3>
                    <p>Savdo dinamikasi va xarajatlar tahlili</p>
                </div>
            </Card>
        </div>
    );
};

export default Finance;
