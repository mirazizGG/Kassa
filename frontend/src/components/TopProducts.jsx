import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useQuery } from '@tanstack/react-query';
import api from '../api/axios';
import { Loader2, TrendingUp } from 'lucide-react';

const TopProducts = () => {
    const { data: products, isLoading } = useQuery({
        queryKey: ['top-products'],
        queryFn: async () => {
             const response = await api.get('/finance/top-products');
             return response.data; // Expecting [{name: 'Product A', value: 10}, ...]
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

    return (
        <Card className="col-span-3">
            <CardHeader>
                <CardTitle className="flex items-center gap-2">
                    <TrendingUp className="h-5 w-5 text-primary" />
                    Top 5 Mahsulot
                </CardTitle>
            </CardHeader>
            <CardContent>
                <div className="space-y-6">
                    {products?.map((product, index) => (
                        <div key={index} className="flex items-center">
                            <div className="flex-1 space-y-1">
                                <p className="text-sm font-medium leading-none">{product.name}</p>
                            </div>
                            <div className="font-bold relative ml-auto">
                                +{product.value} <span className="text-muted-foreground text-xs font-normal">dona</span>
                            </div>
                        </div>
                    ))}
                    {(!products || products.length === 0) && (
                         <div className="text-center text-muted-foreground py-4">Sotuvlar yo'q</div>
                    )}
                </div>
            </CardContent>
        </Card>
    );
};

export default TopProducts;
