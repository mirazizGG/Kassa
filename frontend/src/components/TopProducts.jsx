import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useQuery } from '@tanstack/react-query';
import api from '../api/axios';
import { Loader2, TrendingUp } from 'lucide-react';

const TopProducts = ({ filters }) => {
    const { data: products, isLoading } = useQuery({
        queryKey: ['top-products', filters],
        queryFn: async () => {
             const params = {};
             if (filters?.employee_id && filters.employee_id !== 'all') params.employee_id = filters.employee_id;
             if (filters?.start_date) params.start_date = filters.start_date;
             if (filters?.end_date) params.end_date = filters.end_date;

             const response = await api.get('/finance/top-products', { params });
             return response.data;
        }
    });

    if (isLoading) {
        return (
            <Card className="col-span-3">
                 <CardHeader>
                    <CardTitle>Top Mahsulotlar</CardTitle>
                </CardHeader>
                <CardContent className="h-[300px] flex items-center justify-center">
                    <Loader2 className="h-8 w-8 animate-spin" />
                </CardContent>
            </Card>
        )
    }
    
    const maxVal = products?.length > 0 ? Math.max(...products.map(p => p.value)) : 100;

    return (
        <Card className="col-span-3">
            <CardHeader>
                <CardTitle className="flex items-center gap-2">
                    <TrendingUp className="h-5 w-5 text-primary" />
                    Top 5 Mahsulot
                </CardTitle>
            </CardHeader>
            <CardContent>
                <div className="space-y-5">
                    {products?.map((product, index) => (
                        <div key={index} className="space-y-2">
                            <div className="flex items-center justify-between text-sm">
                                <span className="font-medium">{product.name}</span>
                                <span className="font-bold">{product.value} <span className="text-muted-foreground font-normal text-xs">dona</span></span>
                            </div>
                            <div className="h-2 w-full bg-muted/50 rounded-full overflow-hidden">
                                <div 
                                    className="h-full bg-primary rounded-full transition-all duration-1000 ease-out"
                                    style={{ width: `${(product.value / maxVal) * 100}%` }}
                                />
                            </div>
                        </div>
                    ))}
                    {(!products || products.length === 0) && (
                         <div className="text-center text-muted-foreground py-8">Sotuvlar yo'q</div>
                    )}
                </div>
            </CardContent>
        </Card>
    );
};

export default TopProducts;
