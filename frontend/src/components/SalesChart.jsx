import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid } from "recharts";
import { useQuery } from '@tanstack/react-query';
import api from '../api/axios';
import { Loader2 } from 'lucide-react';

const SalesChart = ({ filters }) => {
    const { data, isLoading } = useQuery({
        queryKey: ['dashboard-chart', filters?.employee_id],
        queryFn: async () => {
            const params = {};
            if (filters?.employee_id && filters.employee_id !== 'all') {
                params.employee_id = filters.employee_id;
            }
            const response = await api.get('/finance/dashboard-chart', { params });
            return response.data;
        }
    });

    if (isLoading) {
        return (
            <Card className="col-span-4">
                <CardHeader>
                    <CardTitle>Savdo Statistikasi</CardTitle>
                </CardHeader>
                <CardContent className="h-[300px] flex items-center justify-center">
                    <Loader2 className="h-8 w-8 animate-spin" />
                </CardContent>
            </Card>
        );
    }

    const chartData = data?.labels.map((label, index) => ({
        name: label,
        total: data.data[index]
    })) || [];

    return (
        <Card className="col-span-4">
            <CardHeader>
                <CardTitle>Savdo Statistikasi (7 kun)</CardTitle>
            </CardHeader>
            <CardContent className="pl-2">
                <ResponsiveContainer width="100%" height={350}>
                    <AreaChart data={chartData}>
                        <defs>
                            <linearGradient id="colorTotal" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="5%" stopColor="hsl(var(--primary))" stopOpacity={0.3}/>
                                <stop offset="95%" stopColor="hsl(var(--primary))" stopOpacity={0}/>
                            </linearGradient>
                        </defs>
                        <XAxis 
                            dataKey="name" 
                            stroke="#888888" 
                            fontSize={12} 
                            tickLine={false} 
                            axisLine={false}
                        />
                        <YAxis
                            stroke="#888888"
                            fontSize={12}
                            tickLine={false}
                            axisLine={false}
                            tickFormatter={(value) => `${value}`}
                        />
                        <CartesianGrid vertical={false} strokeDasharray="3 3" className="stroke-muted" />
                        <Tooltip 
                             contentStyle={{ 
                                backgroundColor: "hsl(var(--background))", 
                                borderColor: "hsl(var(--border))",
                                borderRadius: "8px" 
                            }}
                            itemStyle={{ color: "hsl(var(--foreground))" }}
                        />
                        <Area 
                            type="monotone" 
                            dataKey="total" 
                            stroke="hsl(var(--primary))" 
                            fillOpacity={1} 
                            fill="url(#colorTotal)" 
                            strokeWidth={2}
                        />
                    </AreaChart>
                </ResponsiveContainer>
            </CardContent>
        </Card>
    );
};

export default SalesChart;
