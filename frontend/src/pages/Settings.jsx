import React, { useState, useEffect } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import api from '../api/axios';
import {
    Settings as SettingsIcon,
    Store,
    MapPin,
    Phone,
    FileText,
    Save,
    Loader2,
    Image as ImageIcon
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";
import { Skeleton } from "@/components/ui/skeleton";

const Settings = () => {
    const [formData, setFormData] = useState({
        name: '',
        address: '',
        phone: '',
        header_text: '',
        footer_text: '',
        logo_url: ''
    });

    const { data: settings, isLoading } = useQuery({
        queryKey: ['settings'],
        queryFn: async () => {
            const res = await api.get('/settings');
            return res.data;
        }
    });

    useEffect(() => {
        if (settings) {
            setFormData({
                name: settings.name || '',
                address: settings.address || '',
                phone: settings.phone || '',
                header_text: settings.header_text || '',
                footer_text: settings.footer_text || '',
                logo_url: settings.logo_url || ''
            });
        }
    }, [settings]);

    const mutation = useMutation({
        mutationFn: (data) => api.put('/settings', data),
        onSuccess: () => {
            toast.success("Sozlamalar saqlandi!");
        },
        onError: (err) => {
            toast.error("Xatolik!", { description: err.response?.data?.detail || "Saqlab bo'lmadi" });
        }
    });

    const handleSubmit = (e) => {
        e.preventDefault();
        mutation.mutate(formData);
    };

    if (isLoading) {
        return (
            <div className="space-y-6 animate-pulse">
                <Skeleton className="h-10 w-48" />
                <div className="grid gap-6">
                    <Skeleton className="h-40 w-full" />
                    <Skeleton className="h-60 w-full" />
                </div>
            </div>
        );
    }

    return (
        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight">Tizim Sozlamalari</h1>
                    <p className="text-muted-foreground">Do'kon ma'lumotlari va kvitansiya (check) dizaynini sozlash</p>
                </div>
            </div>

            <form onSubmit={handleSubmit} className="grid gap-6">
                <div className="grid gap-6 md:grid-cols-2">
                    <Card className="border-none shadow-md bg-background/60 backdrop-blur-xl">
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2">
                                <Store className="w-5 h-5 text-primary" />
                                Do'kon Ma'lumotlari
                            </CardTitle>
                            <CardDescription>Mijozlarga ko'rinadigan asosiy ma'lumotlar</CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div className="space-y-2">
                                <Label htmlFor="name">Do'kon Nomi</Label>
                                <Input 
                                    id="name" 
                                    value={formData.name} 
                                    onChange={e => setFormData({...formData, name: e.target.value})}
                                    placeholder="Masalan: Safia Food"
                                />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="address">Manzil</Label>
                                <div className="relative">
                                    <MapPin className="absolute left-3 top-3 w-4 h-4 text-muted-foreground" />
                                    <Input 
                                        id="address" 
                                        className="pl-10"
                                        value={formData.address} 
                                        onChange={e => setFormData({...formData, address: e.target.value})}
                                        placeholder="Toshkent sh., Yunusobod tumani..."
                                    />
                                </div>
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="phone">Telefon Raqami</Label>
                                <div className="relative">
                                    <Phone className="absolute left-3 top-3 w-4 h-4 text-muted-foreground" />
                                    <Input 
                                        id="phone" 
                                        className="pl-10"
                                        value={formData.phone} 
                                        onChange={e => setFormData({...formData, phone: e.target.value})}
                                        placeholder="+998 90 123 45 67"
                                    />
                                </div>
                            </div>
                        </CardContent>
                    </Card>

                    <Card className="border-none shadow-md bg-background/60 backdrop-blur-xl">
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2">
                                <FileText className="w-5 h-5 text-primary" />
                                Check (Kvitansiya) Sozlamalari
                            </CardTitle>
                            <CardDescription>Chop etiladigan chek ma'lumotlari</CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div className="space-y-2">
                                <Label htmlFor="header">Check Yuqori Qismi (Header)</Label>
                                <Textarea 
                                    id="header" 
                                    value={formData.header_text} 
                                    onChange={e => setFormData({...formData, header_text: e.target.value})}
                                    placeholder="Xush kelibsiz! Haridingiz uchun rahmat."
                                    rows={3}
                                />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="footer">Check Pastki Qismi (Footer)</Label>
                                <Textarea 
                                    id="footer" 
                                    value={formData.footer_text} 
                                    onChange={e => setFormData({...formData, footer_text: e.target.value})}
                                    placeholder="Taklif va shikoyatlar uchun: @bot_username"
                                    rows={3}
                                />
                            </div>
                        </CardContent>
                    </Card>
                </div>

                <div className="flex justify-end">
                    <Button type="submit" size="lg" className="w-full sm:w-auto gap-2" disabled={mutation.isPending}>
                        {mutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                        O'zgarishlarni Saqlash
                    </Button>
                </div>
            </form>
        </div>
    );
};

export default Settings;
