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
    DialogFooter
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { useHotkeys } from 'react-hotkeys-hook';

const POS = () => {
    const [searchTerm, setSearchTerm] = useState('');
    const [cart, setCart] = useState([]);
    const [selectedCategory, setSelectedCategory] = useState(null);
    const [isPaymentModalOpen, setIsPaymentModalOpen] = useState(false);
    const [paymentMethod, setPaymentMethod] = useState('cash');
    const [selectedClient, setSelectedClient] = useState(null);
    const [amountPaid, setAmountPaid] = useState('');
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
            setAmountPaid('');
            queryClient.invalidateQueries(['products']); // Update stock
        },
        onError: (err) => {
            toast.error("Xatolik!", { description: err.response?.data?.detail || "Sotuvni amalga oshirib bo'lmadi" });
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

    const handlePayment = () => {
        setIsPaymentModalOpen(true);
    };

    const submitSale = () => {
        if (paymentMethod === 'qarz' && !selectedClient) {
            toast.error("Iltimos, mijozni tanlang!");
            return;
        }

        const saleData = {
            total_amount: cartTotal,
            payment_method: paymentMethod,
            client_id: selectedClient,
            items: cart.map(item => ({
                product_id: item.product_id,
                quantity: item.quantity,
                price: item.price
            }))
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
                            className="w-full text-lg shadow-lg shadow-primary/20"
                            disabled={cart.length === 0 || saleMutation.isPending}
                            onClick={handlePayment}
                        >
                            {saleMutation.isPending ? <Loader2 className="mr-2 animate-spin" /> : <CreditCard className="mr-2" />}
                            To'lov Qilish (Enter)
                        </Button>
                    </div>
                </Card>
            </div>

            {/* Payment Modal */}
            <Dialog open={isPaymentModalOpen} onOpenChange={setIsPaymentModalOpen}>
                <DialogContent className="sm:max-w-[400px]">
                    <DialogHeader>
                        <DialogTitle>To'lovni Tasdiqlash</DialogTitle>
                    </DialogHeader>
                    <div className="grid gap-4 py-4">
                        <div className="bg-muted p-4 rounded-lg text-center">
                            <div className="text-sm text-muted-foreground">To'lanadigan summa</div>
                            <div className="text-3xl font-bold text-primary">{cartTotal.toLocaleString()} so'm</div>
                        </div>

                        <div className="grid grid-cols-2 gap-2">
                            <Button
                                variant={paymentMethod === 'cash' ? 'default' : 'outline'}
                                onClick={() => setPaymentMethod('cash')}
                                className="h-20 flex flex-col gap-1"
                            >
                                <Banknote className="w-6 h-6" />
                                Naqd Pul
                            </Button>
                            <Button
                                variant={paymentMethod === 'card' ? 'default' : 'outline'}
                                onClick={() => setPaymentMethod('card')}
                                className="h-20 flex flex-col gap-1"
                            >
                                <CreditCard className="w-6 h-6" />
                                Karta
                            </Button>
                            <Button
                                variant={paymentMethod === 'perevod' ? 'default' : 'outline'}
                                onClick={() => setPaymentMethod('perevod')}
                                className="h-20 flex flex-col gap-1"
                            >
                                <Smartphone className="w-6 h-6" />
                                Perevod
                            </Button>
                            <Button
                                variant={paymentMethod === 'qarz' ? 'default' : 'outline'}
                                onClick={() => setPaymentMethod('qarz')}
                                className="h-20 flex flex-col gap-1"
                            >
                                <HandCoins className="w-6 h-6" />
                                Qarz (Nasiya)
                            </Button>
                        </div>

                        {paymentMethod === 'qarz' && (
                            <div className="grid gap-2 animate-in fade-in slide-in-from-top-2 duration-300">
                                <Label htmlFor="client-select" className="flex items-center gap-2">
                                    <Users className="w-4 h-4" /> Mijozni tanlang
                                </Label>
                                <Select
                                    value={selectedClient?.toString()}
                                    onValueChange={(val) => setSelectedClient(parseInt(val))}
                                >
                                    <SelectTrigger id="client-select">
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

                        {paymentMethod === 'cash' && (
                            <div className="space-y-4 bg-muted/50 p-4 rounded-lg animate-in fade-in slide-in-from-top-2">
                                <div className="space-y-2">
                                    <Label>Mijoz bergan summa</Label>
                                    <Input
                                        type="number"
                                        placeholder="0"
                                        className="text-xl font-bold h-12"
                                        value={amountPaid}
                                        onChange={(e) => setAmountPaid(e.target.value)}
                                        autoFocus
                                    />
                                </div>
                                <div className="flex justify-between items-center pt-2 border-t">
                                    <span className="font-medium text-muted-foreground">Qaytim:</span>
                                    <span className={`text-2xl font-bold ${(amountPaid - cartTotal) < 0 ? 'text-destructive' : 'text-emerald-600'
                                        }`}>
                                        {amountPaid ? (amountPaid - cartTotal).toLocaleString() : '0'} so'm
                                    </span>
                                </div>
                            </div>
                        )}
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setIsPaymentModalOpen(false)}>Bekor qilish</Button>
                        <Button onClick={submitSale} disabled={saleMutation.isPending}>
                            {saleMutation.isPending && <Loader2 className="mr-2 animate-spin" />}
                            To'lovni Yakunlash
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
};

export default POS;
