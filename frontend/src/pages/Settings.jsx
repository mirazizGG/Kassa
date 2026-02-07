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
    Image as ImageIcon,
    ShieldCheck,
    DownloadCloud,
    History,
    Star
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
        logo_url: '',
        low_stock_threshold: 5,
        bonus_percentage: 1,
        debt_reminder_days: 30
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
                logo_url: settings.logo_url || '',
                low_stock_threshold: settings.low_stock_threshold || 5,
                bonus_percentage: settings.bonus_percentage || 1,
                debt_reminder_days: settings.debt_reminder_days || 30
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
                            <div className="space-y-2 pt-2">
                                <Label htmlFor="threshold" className="text-primary font-bold">Kam Qolgan Mahsulotlar</Label>
                                <div className="flex items-center gap-4 bg-muted/20 p-3 rounded-lg border border-dashed">
                                    <Input 
                                        id="threshold" 
                                        type="number"
                                        value={formData.low_stock_threshold} 
                                        onChange={e => setFormData({...formData, low_stock_threshold: parseInt(e.target.value) || 0})}
                                        className="w-28 h-12 text-xl font-bold text-primary"
                                    />
                                    <span className="text-xs text-muted-foreground">
                                        Mahsulot soni shundan kam bo'lsa, dashboardda ogohlantirish chiqadi.
                                    </span>
                                </div>
                            </div>
                        </CardContent>
                    </Card>

                    <Card className="border-none shadow-md bg-background/60 backdrop-blur-xl">
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2">
                                <Star className="w-5 h-5 text-orange-500" />
                                Marketing va Sodiqlik
                            </CardTitle>
                            <CardDescription>Mijozlarni jalb qilish va keshbek tizimi</CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-6">
                            <div className="space-y-3">
                                <Label htmlFor="bonus" className="text-orange-700 font-bold">Keshbek (Bonus) Foizi</Label>
                                <div className="flex items-center gap-4 bg-orange-50/50 p-4 rounded-xl border border-orange-100">
                                    <div className="relative w-32">
                                        <Input 
                                            id="bonus" 
                                            type="number"
                                            value={formData.bonus_percentage} 
                                            onChange={e => setFormData({...formData, bonus_percentage: parseFloat(e.target.value) || 0})}
                                            className="h-14 pr-10 text-2xl font-black border-orange-200 focus-visible:ring-orange-500 text-orange-700 bg-white"
                                        />
                                        <span className="absolute right-3 top-3.5 text-orange-600 font-bold text-xl">%</span>
                                    </div>
                                    <p className="text-sm text-orange-900/70 leading-relaxed font-medium">
                                        Mijoz xarid qilganda, ushbu foiz miqdorida uning balansiga bonus yoziladi.
                                    </p>
                                </div>
                            </div>

                            <div className="space-y-3">
                                <Label htmlFor="debt_days" className="text-rose-700 font-bold text-base">Qarzni Qaytarish Muddati</Label>
                                <div className="flex items-center gap-4 bg-rose-50/50 p-4 rounded-xl border border-rose-100">
                                    <div className="relative w-32">
                                        <Input 
                                            id="debt_days" 
                                            type="number"
                                            value={formData.debt_reminder_days} 
                                            onChange={e => setFormData({...formData, debt_reminder_days: parseInt(e.target.value) || 0})}
                                            className="h-14 pr-12 text-2xl font-black border-rose-200 focus-visible:ring-rose-500 text-rose-700 bg-white"
                                        />
                                        <span className="absolute right-3 top-4.5 text-rose-600 font-bold text-xs">KUN</span>
                                    </div>
                                    <p className="text-sm text-rose-900/70 leading-relaxed font-medium">
                                        Nasiya savdo muddati tugashi uchun belgilangan kun.
                                    </p>
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

            <div className="grid gap-6 md:grid-cols-2">
                <Card className="border-none shadow-md bg-background/60 backdrop-blur-xl border-l-4 border-l-emerald-500">
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <ShieldCheck className="w-5 h-5 text-emerald-500" />
                            Ma'lumotlar Xavfsizligi
                        </CardTitle>
                        <CardDescription>Baza zahira nusxasini boshqarish va xavfsizlik</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-100 dark:bg-emerald-950/20 dark:border-emerald-900/30">
                            <div className="flex items-start gap-3">
                                <div className="p-2 rounded-lg bg-white dark:bg-emerald-900 shadow-sm text-emerald-600">
                                    <History className="w-4 h-4" />
                                </div>
                                <div className="space-y-1">
                                    <p className="text-sm font-semibold text-emerald-900 dark:text-emerald-100">Avtomatik Zahiralash Faol</p>
                                    <p className="text-xs text-emerald-700/80 dark:text-emerald-400/80">
                                        Sotuvlar va smena yopilishida tizim avtomatik ravishda nusxa oladi.
                                    </p>
                                </div>
                            </div>
                        </div>
                        
                        <div className="flex flex-col gap-3">
                            <Button 
                                type="button"
                                variant="outline" 
                                className="w-full justify-start gap-2 h-12 border-emerald-200 hover:bg-emerald-50 hover:text-emerald-700 transition-all dark:border-emerald-900 dark:hover:bg-emerald-900/50"
                                onClick={async () => {
                                    try {
                                        const res = await api.post('/settings/backup');
                                        toast.success("Muvaffaqiyatli!", { description: res.data.message });
                                    } catch (err) {
                                        toast.error("Xatolik!", { description: "Zahira olib bo'lmadi" });
                                    }
                                }}
                            >
                                <DownloadCloud className="w-4 h-4" />
                                Hozir zahira nusxasini olish (Manual Backup)
                            </Button>
                            <p className="text-[10px] text-muted-foreground px-1">
                                * Zahira nusxalari serverning <code>backups/</code> papkasida saqlanadi.
                            </p>
                        </div>
                    </CardContent>
                </Card>
            </div>
        </div>
    );
};

export default Settings;
