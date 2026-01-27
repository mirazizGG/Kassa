import React from 'react';
import {
    TrendingUp,
    TrendingDown,
    DollarSign,
    PieChart
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

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
    return (
        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight">Moliya va Hisobotlar</h1>
                    <p className="text-muted-foreground">Do'kon daromadi, xarajatlar va foyda tahlili</p>
                </div>
                <Button className="shadow-lg shadow-primary/20">
                    To'liq Hisobot (Excel)
                </Button>
            </div>

            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                <StatCard
                    title="Jami Savdo (Oy)"
                    value="0 so'm"
                    icon={DollarSign}
                    type="positive"
                />
                <StatCard
                    title="Sof Foyda"
                    value="0 so'm"
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
                    title="O'rtacha Chek"
                    value="0 so'm"
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
