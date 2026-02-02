import React, { useState, useEffect, useRef } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import api from '../api/axios';
import { queryClient } from '../api/queryClient';
import {
    Search,
    ShoppingCart,
    Trash2,
    Plus,
    Minus,
    CreditCard,
    Banknote,
    Loader2,
    X,
    Maximize2,
    Minimize2,
    Smartphone,
    HandCoins,
    Users
} from 'lucide-react';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogDescription,
    DialogFooter
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { useHotkeys } from 'react-hotkeys-hook';

const POS = () => {
    const [searchTerm, setSearchTerm] = useState('');
    const [cart, setCart] = useState([]);
    const [selectedCategory, setSelectedCategory] = useState(null);
    const [isPaymentModalOpen, setIsPaymentModalOpen] = useState(false);
    const [paymentAmounts, setPaymentAmounts] = useState({ cash: '', card: '', perevod: '', qarz: '' });
    const [selectedClient, setSelectedClient] = useState(null);
    const [isFullscreen, setIsFullscreen] = useState(false);
    const searchInputRef = useRef(null);

    // Fetch Products
    const { data: products = [], isLoading } = useQuery({
        queryKey: ['products'],
        queryFn: async () => {
            const res = await api.get('/inventory/products');
            return res.data;
        }
    });

    // Fetch Categories
    const { data: categories = [] } = useQuery({
        queryKey: ['categories'],
        queryFn: async () => {
            const res = await api.get('/inventory/categories');
            return res.data;
        }
    });

    // Fetch Clients
    const { data: clients = [] } = useQuery({
        queryKey: ['clients'],
        queryFn: async () => {
            const res = await api.get('/crm/clients');
            return res.data;
        }
    });

    // Sale Mutation
    const saleMutation = useMutation({
        mutationFn: (data) => api.post('/sales/', data),
        onSuccess: () => {
            toast.success("Sotuv amalga oshirildi!");
            setCart([]);
            setIsPaymentModalOpen(false);
            setPaymentAmounts({ cash: '', card: '', perevod: '', qarz: '' });
            queryClient.invalidateQueries({ queryKey: ['products'] }); 
        },
        onError: (err) => {
            const responseData = err.response?.data;
            let message = "Sotuvni amalga oshirib bo'lmadi";
            
            if (responseData?.detail) {
                const detail = responseData.detail;
                message = typeof detail === 'string' 
                    ? detail 
                    : (Array.isArray(detail) ? detail.map(d => `${d.loc?.join('.') || 'error'}: ${d.msg}`).join(', ') : JSON.stringify(detail));
            } else if (err.message) {
                message = err.message;
            }
            
            toast.error("Xatolik!", { description: message });
        }
    });

    // Logic
    const addToCart = (product) => {
        if (product.stock <= 0) {
            toast.error("Mahsulot qolmagan!");
            return;
        }

        setCart(prev => {
            const existing = prev.find(item => item.product_id === product.id);
            if (existing) {
                if (existing.quantity >= product.stock) {
                    toast.warning("Boshqa qoldiq yo'q");
                    return prev;
                }
                return prev.map(item =>
                    item.product_id === product.id
                        ? { ...item, quantity: item.quantity + 1 }
                        : item
                );
            }
            return [...prev, {
                product_id: product.id,
                name: product.name,
                price: product.sell_price,
                quantity: 1,
                max_stock: product.stock
            }];
        });
        setSearchTerm(''); // Clear search after adding
        searchInputRef.current?.focus();
    };

    const updateQuantity = (id, delta) => {
        setCart(prev => prev.map(item => {
            if (item.product_id === id) {
                const newQty = item.quantity + delta;
                if (newQty > item.max_stock) {
                    toast.warning("Omborda yetarli emas");
                    return item;
                }
                if (newQty < 1) return item;
                return { ...item, quantity: newQty };
            }
            return item;
        }));
    };

    const removeFromCart = (id) => {
        setCart(prev => prev.filter(item => item.product_id !== id));
    };

    const cartTotal = cart.reduce((sum, item) => sum + (item.price * item.quantity), 0);
    const totalPaid = Number(paymentAmounts.cash) + Number(paymentAmounts.card) + Number(paymentAmounts.perevod) + Number(paymentAmounts.qarz);

    const handlePayment = () => {
        setPaymentAmounts({ cash: '', card: '', perevod: '', qarz: '' });
        setIsPaymentModalOpen(true);
    };

    const handleFillRemaining = (method) => {
        // Calculate remaining amount needed
        const currentTotal = Number(paymentAmounts.cash) + Number(paymentAmounts.card) + Number(paymentAmounts.perevod) + Number(paymentAmounts.qarz);
        // Exclude the current field we are clicking
        const otherTotal = currentTotal - Number(paymentAmounts[method]);
        const remaining = Math.max(0, cartTotal - otherTotal);
        
        setPaymentAmounts(prev => ({
            ...prev,
            [method]: remaining
        }));
    };

    const submitSale = () => {
        if (Number(paymentAmounts.qarz) > 0 && !selectedClient) {
            toast.error("Iltimos, mijozni tanlang!");
            return;
        }

        // Determine main payment method
        let method = 'mixed';
        if (Number(paymentAmounts.cash) >= cartTotal) method = 'cash';
        else if (Number(paymentAmounts.card) >= cartTotal) method = 'card';
        else if (Number(paymentAmounts.perevod) >= cartTotal) method = 'perevod';
        else if (Number(paymentAmounts.qarz) >= cartTotal) method = 'qarz';

        const saleData = {
            total_amount: cartTotal,
            payment_method: method,
            client_id: selectedClient,
            items: cart.map(item => ({
                product_id: item.product_id,
                quantity: item.quantity,
                price: item.price
            })),
            // Split amounts
            cash_amount: Number(paymentAmounts.cash) || 0,
            card_amount: Number(paymentAmounts.card) || 0,
            transfer_amount: Number(paymentAmounts.perevod) || 0,
            debt_amount: Number(paymentAmounts.qarz) || 0
        };
        saleMutation.mutate(saleData);
    };

    // Filtered Products
    const filteredProducts = products.filter(p => {
        const matchesSearch = p.name.toLowerCase().startsWith(searchTerm.toLowerCase()) ||
            p.barcode?.startsWith(searchTerm);
        const matchesCategory = selectedCategory ? p.category_id === selectedCategory : true;
        return matchesSearch && matchesCategory;
    });

    // Shortcuts
    useHotkeys('f2', () => searchInputRef.current?.focus(), { preventDefault: true });
    useHotkeys('enter', () => {
        if (cart.length > 0 && !isPaymentModalOpen) handlePayment();
    }, { enableOnFormTags: ['INPUT'] });

    // Handle barcode scanner (simple version)
    useEffect(() => {
        const handleScan = (e) => {
            // Very basic layout for focused input scanning
            // For real barcode scanners acting as keyboard, usually they end with Enter
        };
        // Ideally checking for fast input sequence ending with Enter
    }, []);

    // Auto-search logic for barcode (if exact match found, add to cart immediately)
    useEffect(() => {
        if (!searchTerm) return;
        const exactMatch = products.find(p => p.barcode === searchTerm);
        if (exactMatch) {
            addToCart(exactMatch);
        }
    }, [searchTerm, products]);


    return (
        <div className="flex h-full w-full gap-4 overflow-hidden p-4">
            {/* Left Side - Products */}
            <div className="flex-1 flex flex-col gap-4 overflow-hidden">
                <Card className="flex-1 flex flex-col overflow-hidden border-none shadow-md bg-card/80 backdrop-blur">
                    <div className="p-4 border-b flex gap-4 items-center">
                        <div className="relative flex-1">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                            <Input
                                ref={searchInputRef}
                                placeholder="Mahsulot qidirish (shtrix-kod yoki nom) [F2]"
                                className="pl-10 h-12 text-lg"
                                value={searchTerm}
                                onChange={(e) => setSearchTerm(e.target.value)}
                                autoFocus
                            />
                        </div>
                    </div>

                    {/* Categories Bar */}
                    <ScrollArea className="w-full whitespace-nowrap border-b bg-muted/30">
                        <div className="flex p-2 gap-2">
                            <Button
                                variant={selectedCategory === null ? "default" : "outline"}
                                onClick={() => setSelectedCategory(null)}
                                className="rounded-full"
                                size="sm"
                            >
                                Barchasi
                            </Button>
                            {categories.map(c => (
                                <Button
                                    key={c.id}
                                    variant={selectedCategory === c.id ? "default" : "outline"}
                                    onClick={() => setSelectedCategory(c.id)}
                                    className="rounded-full"
                                    size="sm"
                                >
                                    {c.name}
                                </Button>
                            ))}
                        </div>
                    </ScrollArea>

                    <ScrollArea className="flex-1 p-4 bg-muted/10">
                        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6 gap-4 pb-20">
                            {filteredProducts.map(product => (
                                <Card
                                    key={product.id}
                                    className={cn(
                                        "cursor-pointer hover:shadow-lg transition-all active:scale-95 flex flex-col justify-between overflow-hidden border-0 bg-card",
                                        product.stock <= 0 && "opacity-50 grayscale pointer-events-none"
                                    )}
                                    onClick={() => addToCart(product)}
                                >
                                    <div className="h-24 bg-gradient-to-br from-primary/10 to-primary/5 p-4 flex items-center justify-center">
                                        <div className="text-4xl font-bold text-primary/20">
                                            {product.name.charAt(0).toUpperCase()}
                                        </div>
                                    </div>
                                    <div className="p-3">
                                        <h3 className="font-bold truncate" title={product.name}>{product.name}</h3>
                                        <div className="flex justify-between items-center mt-1">
                                            <span className="font-mono text-xs text-muted-foreground">{product.stock} {product.unit}</span>
                                            <span className="font-bold text-primary">{product.sell_price.toLocaleString()}</span>
                                        </div>
                                    </div>
                                </Card>
                            ))}
                            {filteredProducts.length === 0 && (
                                <div className="col-span-full flex flex-col items-center justify-center h-40 text-muted-foreground">
                                    <Search className="w-8 h-8 mb-2 opacity-50" />
                                    <p>Mahsulotlar topilmadi</p>
                                </div>
                            )}
                        </div>
                    </ScrollArea>
                </Card>
            </div>

            {/* Right Side - Cart */}
            <div className="w-[400px] flex flex-col gap-4">
                <Card className="flex-1 flex flex-col overflow-hidden border-none shadow-xl bg-card">
                    <div className="p-4 border-b bg-primary text-primary-foreground flex justify-between items-center">
                        <div className="flex items-center gap-2">
                            <ShoppingCart className="w-5 h-5" />
                            <h2 className="font-bold text-lg">Savatcha</h2>
                        </div>
                        <Badge variant="secondary" className="font-mono text-lg px-3">
                            {cartTotal.toLocaleString()} so'm
                        </Badge>
                    </div>

                    <ScrollArea className="flex-1 p-4">
                        <div className="space-y-3">
                            {cart.map(item => (
                                <div key={item.product_id} className="flex gap-3 items-center bg-muted/30 p-2 rounded-lg group animate-in slide-in-from-right-5 fade-in duration-300">
                                    <div className="flex-1">
                                        <div className="font-medium truncate">{item.name}</div>
                                        <div className="text-sm text-muted-foreground">
                                            {item.price.toLocaleString()} x {item.quantity} = {(item.price * item.quantity).toLocaleString()}
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-1 bg-background rounded-md border shadow-sm">
                                        <Button
                                            variant="ghost"
                                            size="icon"
                                            className="h-8 w-8 rounded-none rounded-l-md hover:bg-destructive/10 hover:text-destructive"
                                            onClick={() => item.quantity > 1 ? updateQuantity(item.product_id, -1) : removeFromCart(item.product_id)}
                                        >
                                            {item.quantity === 1 ? <Trash2 className="w-4 h-4" /> : <Minus className="w-3 h-3" />}
                                        </Button>
                                        <div className="w-8 text-center font-bold text-sm select-none">{item.quantity}</div>
                                        <Button
                                            variant="ghost"
                                            size="icon"
                                            className="h-8 w-8 rounded-none rounded-r-md"
                                            onClick={() => updateQuantity(item.product_id, 1)}
                                        >
                                            <Plus className="w-3 h-3" />
                                        </Button>
                                    </div>
                                </div>
                            ))}
                            {cart.length === 0 && (
                                <div className="text-center py-20 text-muted-foreground opacity-50">
                                    <ShoppingCart className="w-12 h-12 mx-auto mb-3" />
                                    <p>Savatcha bo'sh</p>
                                    <p className="text-xs mt-1">Mahsulotlarni qo'shish uchun bosing yoki skanerlang</p>
                                </div>
                            )}
                        </div>
                    </ScrollArea>

                    <div className="p-4 bg-muted/50 border-t space-y-4">
                        <div className="space-y-1">
                            <div className="flex justify-between text-sm">
                                <span className="text-muted-foreground">Jami Mahsulotlar:</span>
                                <span className="font-bold">{cart.reduce((a, b) => a + b.quantity, 0)} dona</span>
                            </div>
                            <div className="flex justify-between text-xl font-bold pt-2 border-t mt-2">
                                <span>Jami Summa:</span>
                                <span className="text-primary">{cartTotal.toLocaleString()} so'm</span>
                            </div>
                        </div>

                        <Button
                            size="lg"
                            className="w-full text-lg shadow-lg shadow-emerald-500/20"
                            disabled={cart.length === 0 || saleMutation.isPending}
                            onClick={handlePayment}
                            variant="success"
                        >
                            {saleMutation.isPending ? <Loader2 className="mr-2 animate-spin" /> : <CreditCard className="mr-2" />}
                            To'lov Qilish (Enter)
                        </Button>
                    </div>
                </Card>
            </div>

            {/* Payment Modal */}
            <Dialog open={isPaymentModalOpen} onOpenChange={setIsPaymentModalOpen}>
                <DialogContent className="sm:max-w-[480px] p-0 gap-0 border-0 shadow-2xl overflow-hidden rounded-2xl">
                    <DialogTitle className="sr-only">To'lov oynasi</DialogTitle>
                    <DialogDescription className="sr-only">
                        Savdo uchun to'lov usulini tanlang va summani kiriting.
                    </DialogDescription>
                     {/* Header */}
                    <div className="bg-slate-900 p-6 text-white text-center relative overflow-hidden">
                        <div className="relative z-10">
                            <p className="text-slate-400 font-medium mb-1 uppercase tracking-wider text-xs">Jami To'lov Summasi</p>
                            <div className="text-5xl font-bold tracking-tight">{cartTotal.toLocaleString()}</div>
                            <p className="text-slate-500 text-sm mt-1">so'm</p>
                        </div>
                    </div>
                    
                    <div className="p-6 space-y-6 bg-white">
                        <div className="space-y-4">
                            {/* Cash */}
                            <div className="flex items-center gap-3">
                                <div className="h-12 w-12 rounded-xl bg-emerald-100 text-emerald-600 flex items-center justify-center shrink-0 border border-emerald-200">
                                    <Banknote className="w-6 h-6" />
                                </div>
                                <div className="flex-1 space-y-1">
                                    <Label className="text-xs text-muted-foreground font-bold uppercase tracking-wide">Naqd Pul</Label>
                                    <Input 
                                        type="number" 
                                        placeholder="0" 
                                        className="h-10 border-slate-200 text-lg font-bold focus-visible:ring-emerald-500" 
                                        value={paymentAmounts.cash}
                                        onChange={(e) => setPaymentAmounts(prev => ({ ...prev, cash: e.target.value }))}
                                        autoFocus
                                    />
                                </div>
                                <Button 
                                    size="sm" 
                                    variant="outline" 
                                    className="h-10 px-3 bg-emerald-50 text-emerald-700 border-emerald-200 hover:bg-emerald-100 hover:text-emerald-800 font-semibold self-end" 
                                    onClick={() => handleFillRemaining('cash')}
                                >
                                    Jami
                                </Button>
                            </div>

                            {/* Card */}
                            <div className="flex items-center gap-3">
                                <div className="h-12 w-12 rounded-xl bg-blue-100 text-blue-600 flex items-center justify-center shrink-0 border border-blue-200">
                                    <CreditCard className="w-6 h-6" />
                                </div>
                                <div className="flex-1 space-y-1">
                                    <Label className="text-xs text-muted-foreground font-bold uppercase tracking-wide">Karta (Terminal)</Label>
                                    <Input 
                                        type="number" 
                                        placeholder="0" 
                                        className="h-10 border-slate-200 text-lg font-bold focus-visible:ring-blue-500" 
                                        value={paymentAmounts.card}
                                        onChange={(e) => setPaymentAmounts(prev => ({ ...prev, card: e.target.value }))}
                                    />
                                </div>
                                <Button 
                                    size="sm" 
                                    variant="outline" 
                                    className="h-10 px-3 bg-blue-50 text-blue-700 border-blue-200 hover:bg-blue-100 hover:text-blue-800 font-semibold self-end" 
                                    onClick={() => handleFillRemaining('card')}
                                >
                                    Jami
                                </Button>
                            </div>

                             {/* Perevod */}
                            <div className="flex items-center gap-3">
                                <div className="h-12 w-12 rounded-xl bg-purple-100 text-purple-600 flex items-center justify-center shrink-0 border border-purple-200">
                                     <Smartphone className="w-6 h-6" />
                                </div>
                                <div className="flex-1 space-y-1">
                                    <Label className="text-xs text-muted-foreground font-bold uppercase tracking-wide">Perevod</Label>
                                    <Input 
                                        type="number" 
                                        placeholder="0" 
                                        className="h-10 border-slate-200 text-lg font-bold focus-visible:ring-purple-500" 
                                        value={paymentAmounts.perevod}
                                        onChange={(e) => setPaymentAmounts(prev => ({ ...prev, perevod: e.target.value }))}
                                    />
                                </div>
                                <Button 
                                    size="sm" 
                                    variant="outline" 
                                    className="h-10 px-3 bg-purple-50 text-purple-700 border-purple-200 hover:bg-purple-100 hover:text-purple-800 font-semibold self-end" 
                                    onClick={() => handleFillRemaining('perevod')}
                                >
                                    Jami
                                </Button>
                            </div>

                            {/* Debt */}
                            <div className="flex items-center gap-3">
                                <div className="h-12 w-12 rounded-xl bg-amber-100 text-amber-600 flex items-center justify-center shrink-0 border border-amber-200">
                                     <HandCoins className="w-6 h-6" />
                                </div>
                                <div className="flex-1 space-y-1">
                                    <Label className="text-xs text-muted-foreground font-bold uppercase tracking-wide">Nasiya (Qarz)</Label>
                                    <Input 
                                        type="number" 
                                        placeholder="0" 
                                        className="h-10 border-slate-200 text-lg font-bold focus-visible:ring-amber-500" 
                                        value={paymentAmounts.qarz}
                                        onChange={(e) => setPaymentAmounts(prev => ({ ...prev, qarz: e.target.value }))}
                                    />
                                </div>
                                <Button 
                                    size="sm" 
                                    variant="outline" 
                                    className="h-10 px-3 bg-amber-50 text-amber-700 border-amber-200 hover:bg-amber-100 hover:text-amber-800 font-semibold self-end" 
                                    onClick={() => handleFillRemaining('qarz')}
                                >
                                    Jami
                                </Button>
                            </div>
                        </div>

                        {/* Client Select for Debt */}
                        {Number(paymentAmounts.qarz) > 0 && (
                            <div className="animate-in fade-in zoom-in-95 duration-200 p-4 bg-amber-50 rounded-xl border border-amber-100">
                                <Label className="text-sm font-medium text-amber-900 mb-2 block">Mijozni tanlang (Qarz uchun)</Label>
                                <Select
                                    value={selectedClient?.toString()}
                                    onValueChange={(val) => setSelectedClient(parseInt(val))}
                                >
                                    <SelectTrigger className="h-11 bg-white border-amber-200 text-amber-900">
                                        <SelectValue placeholder="Mijozni qidirish..." />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {clients.map(c => (
                                            <SelectItem key={c.id} value={c.id.toString()}>
                                                {c.name} {c.phone ? `(${c.phone})` : ''}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>
                        )}

                        {/* Summary & Actions */}
                        <div className="pt-4 border-t border-slate-100 space-y-4">
                            <div className="flex justify-between items-center bg-slate-50 p-4 rounded-xl">
                                <div className="flex flex-col">
                                    <span className="text-sm font-medium text-slate-500">Kassada to'lanmoqda:</span>
                                    <span className={cn("text-2xl font-bold", totalPaid >= cartTotal ? "text-emerald-600" : "text-slate-800")}>
                                        {totalPaid.toLocaleString()}
                                    </span>
                                </div>
                                {totalPaid >= cartTotal ? (
                                    <div className="text-right">
                                        <span className="text-xs text-slate-500 block uppercase font-bold">Qaytim</span>
                                        <span className="text-xl font-bold text-emerald-600">{(totalPaid - cartTotal).toLocaleString()}</span>
                                    </div>
                                ) : (
                                    <div className="text-right">
                                        <span className="text-xs text-slate-500 block uppercase font-bold">Yana kerak</span>
                                        <span className="text-xl font-bold text-rose-500">{(cartTotal - totalPaid).toLocaleString()}</span>
                                    </div>
                                )}
                            </div>

                            <div className="flex gap-3 h-14">
                                <Button 
                                    variant="outline" 
                                    onClick={() => setIsPaymentModalOpen(false)}
                                    className="h-full px-6 border-2 text-slate-500 hover:text-slate-700 hover:bg-slate-50"
                                >
                                    Bekor qilish
                                </Button>
                                <Button 
                                    onClick={submitSale} 
                                    disabled={saleMutation.isPending || totalPaid < cartTotal} 
                                    className={cn(
                                        "flex-1 h-full text-xl font-bold shadow-lg transition-all",
                                        totalPaid >= cartTotal 
                                            ? "bg-emerald-600 hover:bg-emerald-700 text-white shadow-emerald-200" 
                                            : "bg-slate-200 text-slate-400 cursor-not-allowed shadow-none"
                                    )}
                                >
                                    {saleMutation.isPending && <Loader2 className="mr-2 animate-spin" />}
                                    {totalPaid >= cartTotal ? "To'lovni Tasdiqlash" : "Summa yetarli emas"}
                                </Button>
                            </div>
                        </div>
                    </div>
                </DialogContent>
            </Dialog>
        </div>
    );
};

export default POS;
