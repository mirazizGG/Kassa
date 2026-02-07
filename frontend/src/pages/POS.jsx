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
    Users,
    Star
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
import { cn } from "@/lib/utils.js";
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
    const [isShiftModalOpen, setIsShiftModalOpen] = useState(false);
    const [shiftBalance, setShiftBalance] = useState('');
    const [isWeightModalOpen, setIsWeightModalOpen] = useState(false);
    const [selectedProductForWeight, setSelectedProductForWeight] = useState(null);
    const [weightInput, setWeightInput] = useState('');
    const [amountInput, setAmountInput] = useState('');
    const [bonusSpent, setBonusSpent] = useState(0);
    const searchInputRef = useRef(null);
    const role = localStorage.getItem('role');

    // Fetch Active Shift
    const { data: activeShift, isLoading: isShiftLoading } = useQuery({
        queryKey: ['active-shift'],
        queryFn: async () => {
            const res = await api.get('/pos/shifts/active');
            return res.data;
        }
    });

    // Auto-open shift modal if cashier has no active shift
    useEffect(() => {
        if (!isShiftLoading && !activeShift && role === 'cashier') {
             // Small delay to ensure UI is ready
             const timer = setTimeout(() => setIsShiftModalOpen(true), 500);
             return () => clearTimeout(timer);
        }
    }, [activeShift, isShiftLoading, role]);

    const toggleFullscreen = () => {
        if (!document.fullscreenElement) {
            document.documentElement.requestFullscreen();
            setIsFullscreen(true);
        } else {
            if (document.exitFullscreen) {
                document.exitFullscreen();
                setIsFullscreen(false);
            }
        }
    };


    const openShiftMutation = useMutation({
        mutationFn: (data) => api.post('/pos/shifts/open', data),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['active-shift'] });
            setIsShiftModalOpen(false);
            setShiftBalance('');
            toast.success("Smena ochildi!");
        }
    });

    const closeShiftMutation = useMutation({
        mutationFn: (data) => api.post('/pos/shifts/close', data),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['active-shift'] });
            setIsShiftModalOpen(false);
            setShiftBalance('');
            toast.success("Smena yopildi!");
        }
    });


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

    // Fetch Settings
    const { data: settings } = useQuery({
        queryKey: ['settings'],
        queryFn: async () => {
            const res = await api.get('/settings');
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
            setBonusSpent(0);
            queryClient.invalidateQueries({ queryKey: ['products'] }); 
            queryClient.invalidateQueries({ queryKey: ['sales-history'] });
            queryClient.invalidateQueries({ queryKey: ['finance-stats'] });
            queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] });
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
    const addToCart = (product, forcedQuantity = null) => {
        /* 
        if (product.stock <= 0) {
            toast.error("Mahsulot qolmagan!");
            return;
        }
        */

        // If it's a weighted item and no quantity provided, open modal
        if ((product.unit === 'kg' || product.unit === 'litr') && forcedQuantity === null) {
            setSelectedProductForWeight(product);
            setWeightInput('');
            setAmountInput('');
            setIsWeightModalOpen(true);
            return;
        }

        const quantityToAdd = forcedQuantity !== null ? forcedQuantity : 1;

        setCart(prev => {
            const existing = prev.find(item => item.product_id === product.id);
            if (existing) {
                /*
                if (existing.quantity + quantityToAdd > product.stock) {
                    toast.warning("Boshqa qoldiq yo'q");
                    return prev;
                }
                */
                return prev.map(item =>
                    item.product_id === product.id
                        ? { ...item, quantity: item.quantity + quantityToAdd }
                        : item
                );
            }
            return [...prev, {
                product_id: product.id,
                name: product.name,
                price: product.sell_price,
                quantity: quantityToAdd,
                max_stock: product.stock,
                unit: product.unit
            }];
        });
        setSearchTerm(''); // Clear search after adding
        searchInputRef.current?.focus();
    };

    const updateQuantity = (id, delta) => {
        setCart(prev => prev.map(item => {
            if (item.product_id === id) {
                const newQty = item.quantity + delta;
                /*
                if (newQty > item.max_stock) {
                    toast.warning("Omborda yetarli emas");
                    return item;
                }
                */
                if (newQty < 1) return item;
                return { ...item, quantity: newQty };
            }
            return item;
        }));
    };

    const removeFromCart = (id) => {
        setCart(prev => prev.filter(item => item.product_id !== id));
    };

    const cartTotal = Math.round(cart.reduce((sum, item) => sum + (item.price * item.quantity), 0));
    const bonusBalance = clients.find(c => c.id === selectedClient)?.bonus_balance || 0;
    const bonusEarned = Math.floor((cartTotal - (Number(paymentAmounts.qarz) || 0)) * (settings?.bonus_percentage || 1) / 100);
    const totalPaid = Number(paymentAmounts.cash) + Number(paymentAmounts.card) + Number(paymentAmounts.perevod) + Number(paymentAmounts.qarz) + Number(bonusSpent);

    const handlePayment = () => {
        if (!activeShift) {
            toast.info("Savdo qilish uchun avval smena oching");
            return;
        }
        setPaymentAmounts({ cash: '', card: '', perevod: '', qarz: '' });
        setBonusSpent(0);
        setIsPaymentModalOpen(true);
    };

    const handleFillRemaining = (method) => {
        // Exclude the current field we are clicking
        const otherTotal = Number(paymentAmounts.cash) + Number(paymentAmounts.card) + Number(paymentAmounts.perevod) + Number(paymentAmounts.qarz) + Number(bonusSpent) - Number(paymentAmounts[method]);
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
            debt_amount: Number(paymentAmounts.qarz) || 0,
            bonus_spent: Number(bonusSpent) || 0
        };
        saleMutation.mutate(saleData);
    };

    // Filtered Products
    const filteredProducts = products.filter(p => {
        const matchesSearch = p.name.toLowerCase().startsWith(searchTerm.toLowerCase()) ||
            p.barcode?.startsWith(searchTerm);
        const matchesCategory = selectedCategory ? p.category_id === selectedCategory : true;
        return matchesSearch && matchesCategory;
    }).sort((a, b) => {
        // Favorites first
        if (a.is_favorite && !b.is_favorite) return -1;
        if (!a.is_favorite && b.is_favorite) return 1;
        return 0;
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
                        <Button
                            variant="ghost"
                            size="icon"
                            onClick={toggleFullscreen}
                            className="h-12 w-12 rounded-xl text-muted-foreground hover:bg-muted"
                            title="To'liq ekran"
                        >
                            {isFullscreen ? <Minimize2 className="w-6 h-6" /> : <Maximize2 className="w-6 h-6" />}
                        </Button>
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
                                        "cursor-pointer hover:shadow-lg transition-all active:scale-95 flex flex-col justify-between overflow-hidden border-0 bg-card relative"
                                    )}
                                    onClick={() => addToCart(product)}
                                >
                                    {product.is_favorite && (
                                        <div className="absolute top-2 right-2 z-10">
                                            <Star className="w-4 h-4 text-amber-500 fill-amber-500" />
                                        </div>
                                    )}
                                    <div className="h-24 bg-gradient-to-br from-primary/10 to-primary/5 p-4 flex items-center justify-center">
                                        <div className="text-4xl font-bold text-primary/20">
                                            {product.name.charAt(0).toUpperCase()}
                                        </div>
                                    </div>
                                    <div className="p-3">
                                        <h3 className="font-bold truncate" title={product.name}>{product.name}</h3>
                                            <span className="font-bold text-primary ml-auto">{product.sell_price.toLocaleString()}</span>
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
                        <div className="flex flex-col items-end">
                            <Badge 
                                variant={activeShift ? "outline" : "destructive"} 
                                className={cn("cursor-pointer mb-1", activeShift ? "bg-emerald-500/20 text-white border-emerald-400" : "animate-pulse")}
                                onClick={() => setIsShiftModalOpen(true)}
                            >
                                {activeShift ? "Smena Ochiq" : "Smena Yopiq"}
                            </Badge>
                        </div>
                    </div>

                    <ScrollArea className="flex-1 p-4">
                        <div className="space-y-3">
                            {cart.map(item => (
                                <div key={item.product_id} className="flex gap-3 items-center bg-muted/30 p-2 rounded-lg group animate-in slide-in-from-right-5 fade-in duration-300">
                                    <div className="flex-1">
                                        <div className="font-medium truncate">{item.name}</div>
                                        <div className="text-sm text-muted-foreground">
                                            {item.price.toLocaleString()} x {item.quantity} = {Math.round(item.price * item.quantity).toLocaleString()}
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
                                        <div className="px-2 text-center font-bold text-sm select-none min-w-[70px]">
                                            {Math.round(item.price * item.quantity).toLocaleString()}
                                        </div>
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
                                <span className="font-bold">{cart.length} tur</span>
                            </div>
                            <div className="flex justify-between text-xl font-bold pt-2 border-t mt-2">
                                <span>Jami Summa:</span>
                                <span className="text-primary">{Math.round(cartTotal).toLocaleString()} so'm</span>
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

                            {/* Bonus Selection (New) */}
                            {selectedClient && bonusBalance > 0 && (
                                <div className="flex items-center gap-3 animate-in fade-in slide-in-from-left-2">
                                    <div className="h-12 w-12 rounded-xl bg-orange-100 text-orange-600 flex items-center justify-center shrink-0 border border-orange-200">
                                        <Star className="w-6 h-6 fill-orange-500" />
                                    </div>
                                    <div className="flex-1 space-y-1">
                                        <Label className="text-xs text-muted-foreground font-bold uppercase tracking-wide">Bonuslatish (Mavjud: {bonusBalance})</Label>
                                        <Input 
                                            type="number" 
                                            placeholder="0" 
                                            max={bonusBalance}
                                            className="h-10 border-slate-200 text-lg font-bold focus-visible:ring-orange-500" 
                                            value={bonusSpent}
                                            onChange={(e) => {
                                                const val = Math.min(bonusBalance, parseFloat(e.target.value) || 0);
                                                setBonusSpent(val);
                                            }}
                                        />
                                    </div>
                                    <Button 
                                        size="sm" 
                                        variant="outline" 
                                        className="h-10 px-3 bg-orange-50 text-orange-700 border-orange-200 hover:bg-orange-100 hover:text-orange-800 font-semibold self-end" 
                                        onClick={() => {
                                            const otherTotal = Number(paymentAmounts.cash) + Number(paymentAmounts.card) + Number(paymentAmounts.perevod) + Number(paymentAmounts.qarz);
                                            const needed = Math.max(0, cartTotal - otherTotal);
                                            setBonusSpent(Math.min(bonusBalance, needed));
                                        }}
                                    >
                                        Jami
                                    </Button>
                                </div>
                            )}

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

                        {/* Client & Bonus Selection Area */}
                        <div className="space-y-4">
                            <div className="p-4 bg-slate-50 rounded-xl border border-slate-100">
                                <div className="flex justify-between items-center mb-2">
                                    <Label className="text-sm font-medium text-slate-900">Mijozni tanlang</Label>
                                    {selectedClient && selectedClient !== "null" && (
                <Badge variant="outline" className="bg-orange-50 text-orange-700 border-orange-200 text-sm font-bold px-3 py-1">
                    Bonus: {bonusBalance?.toLocaleString()}
                </Badge>
            )}
                                </div>
                                <Select
                                    value={selectedClient?.toString()}
                                    onValueChange={(val) => setSelectedClient(val === "null" ? null : parseInt(val))}
                                >
                                    <SelectTrigger className="h-11 bg-white border-slate-200">
                                        <SelectValue placeholder="Mijoz tanlash (Keshbek va Qarz uchun)" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="null">Tanlanmagan</SelectItem>
                                        {clients.map(c => (
                                            <SelectItem key={c.id} value={c.id.toString()}>
                                                {c.name} {c.phone ? `(${c.phone})` : ''}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                                
                                {selectedClient && selectedClient !== "null" && (
                                    <div className="mt-2 flex items-center gap-2 text-xs text-muted-foreground uppercase tracking-tight font-bold">
                <Star className="w-4 h-4 text-orange-500 fill-orange-500" />
                <span>Ushbu xariddan bonus: </span>
                <span className="text-orange-600 text-base">+{bonusEarned?.toLocaleString()}</span>
            </div>
                                )}
                            </div>
                        </div>

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

            <Dialog open={isWeightModalOpen} onOpenChange={setIsWeightModalOpen}>
                <DialogContent className="sm:max-w-[420px] p-0 overflow-hidden border-none shadow-2xl">
                    <DialogHeader className="p-4 bg-primary text-primary-foreground">
                        <DialogTitle className="text-xl font-black flex items-center justify-between uppercase tracking-tighter">
                            {selectedProductForWeight?.name}
                            <Badge variant="outline" className="text-sm py-0.5 px-2 border-primary-foreground/30 text-primary-foreground font-mono">
                                {selectedProductForWeight?.sell_price.toLocaleString()} s / {selectedProductForWeight?.unit}
                            </Badge>
                        </DialogTitle>
                    </DialogHeader>
                    
                    <div className="p-6 space-y-4 bg-background">
                        <div className="space-y-2 uppercase">
                            <Label className="text-sm font-black text-primary tracking-tighter">
                                Sotiladigan Summa
                            </Label>
                            <div className="relative">
                                    <Input 
                                        type="number" 
                                        value={amountInput} 
                                        onChange={(e) => {
                                            const val = e.target.value;
                                            setAmountInput(val);
                                            if (val && selectedProductForWeight) {
                                                const calcWeight = (parseFloat(val) / selectedProductForWeight.sell_price).toFixed(5);
                                                setWeightInput(calcWeight);
                                            } else {
                                                setWeightInput('');
                                            }
                                        }}
                                        onKeyDown={(e) => {
                                            if (e.key === 'Enter' && weightInput > 0) {
                                                addToCart(selectedProductForWeight, parseFloat(weightInput));
                                                setIsWeightModalOpen(false);
                                            }
                                        }}
                                        placeholder="0"
                                        className="text-[60px] h-24 font-bold border-2 border-primary/10 focus:border-primary shadow-inner text-center bg-muted/10 rounded-2xl transition-all leading-none p-0"
                                        autoFocus
                                        style={{ fontSize: '60px' }}
                                    />
                                    <div className="absolute right-6 top-1/2 -translate-y-1/2 text-xl font-black text-muted-foreground/20 pointer-events-none uppercase">
                                        so'm
                                    </div>
                            </div>
                        </div>
                    </div>

                    <DialogFooter className="p-4 pt-0 bg-background flex gap-2 sm:gap-2">
                        <Button 
                            variant="outline" 
                            onClick={() => setIsWeightModalOpen(false)} 
                            className="h-12 text-sm font-bold flex-1 rounded-xl"
                        >
                            Bekor qilish
                        </Button>
                        <Button 
                            className="h-12 text-lg font-black flex-1 rounded-xl shadow-lg shadow-primary/20 uppercase tracking-tight"
                            disabled={!weightInput || parseFloat(weightInput) <= 0}
                            onClick={() => {
                                addToCart(selectedProductForWeight, parseFloat(weightInput));
                                setIsWeightModalOpen(false);
                            }}
                        >
                            Savatga Qo'shish
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Shift Modal */}
            <Dialog open={isShiftModalOpen} onOpenChange={setIsShiftModalOpen}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>{activeShift ? "Smenani Yopish" : "Yangi Smena Ochish"}</DialogTitle>
                        <DialogDescription>
                            {activeShift 
                                ? "Ish kuningizni yakunlash uchun kassadagi qoldiqni kiriting." 
                                : "Savdoni boshlash uchun kassadagi boshlang'ich summani kiriting."}
                        </DialogDescription>
                    </DialogHeader>
                        <div className="space-y-4 py-4">
                            {activeShift && (
                                <div className="bg-muted/50 p-4 rounded-lg space-y-2 mb-4">
                                    <div className="flex justify-between text-sm">
                                        <span>Boshlang'ich kassa:</span>
                                        <span className="font-bold">{activeShift.opening_balance?.toLocaleString()} so'm</span>
                                    </div>
                                    <div className="flex justify-between text-sm text-emerald-600">
                                        <span>Naqd savdo:</span>
                                        <span className="font-bold">+{activeShift.total_cash?.toLocaleString() || 0} so'm</span>
                                    </div>
                                    <div className="flex justify-between text-sm text-blue-600">
                                        <span>Karta (terminal):</span>
                                        <span className="font-bold">{activeShift.total_card?.toLocaleString() || 0} so'm</span>
                                    </div>
                                    <div className="flex justify-between text-sm text-amber-600">
                                        <span>Nasiya (qarz):</span>
                                        <span className="font-bold">{activeShift.total_debt?.toLocaleString() || 0} so'm</span>
                                    </div>
                                    <div className="border-t pt-2 flex justify-between font-bold text-lg">
                                        <span>Kassada bo'lishi kerak:</span>
                                        <span>{(activeShift.opening_balance + (activeShift.total_cash || 0)).toLocaleString()} so'm</span>
                                    </div>
                                </div>
                            )}
                            <div className="space-y-2">
                                <Label>{activeShift ? "Haqiqiy naqd pul (Kassadagi)" : "Boshlang'ich balans"}</Label>
                                <Input 
                                    type="number" 
                                    value={shiftBalance} 
                                    onChange={(e) => setShiftBalance(e.target.value)} 
                                    placeholder="0"
                                    autoFocus
                                />
                            </div>
                        </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setIsShiftModalOpen(false)}>Bekor qilish</Button>
                        <Button 
                            onClick={() => {
                                if (activeShift) {
                                    closeShiftMutation.mutate({ closing_balance: Number(shiftBalance) || 0 });
                                } else {
                                    openShiftMutation.mutate({ opening_balance: Number(shiftBalance) || 0 });
                                }
                            }}
                            disabled={openShiftMutation.isPending || closeShiftMutation.isPending}
                        >
                            {(openShiftMutation.isPending || closeShiftMutation.isPending) && <Loader2 className="mr-2 animate-spin h-4 w-4" />}
                            {activeShift ? "Smenani Yakunlash" : "Smenani Boshlash"}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
};

export default POS;
