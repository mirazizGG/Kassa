import { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import api from '../api/axios';
import { queryClient } from '../api/queryClient';
import {
    Package,
    Search,
    Plus,
    Edit,
    Trash2,
    Filter,
    MoreHorizontal,
    AlertCircle,
    Loader2,
    Truck,
    FolderPlus,
    History,
    Star
} from 'lucide-react';
import { format } from "date-fns";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow
} from "@/components/ui/table";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
    DialogTrigger
} from "@/components/ui/dialog";
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuLabel,
    DropdownMenuSeparator,
    DropdownMenuTrigger
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { toast } from "sonner";
import { cn } from "@/lib/utils.js";

const Inventory = () => {
    const [searchTerm, setSearchTerm] = useState('');
    const role = localStorage.getItem('role');
    const [selectedCategory, setSelectedCategory] = useState('all');
    const [sortBy, setSortBy] = useState('name-asc');
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [isCategoryModalOpen, setIsCategoryModalOpen] = useState(false);
    const [newCategoryName, setNewCategoryName] = useState('');
    const [editingProduct, setEditingProduct] = useState(null);

    // Form state
    const [formData, setFormData] = useState({
        name: '',
        barcode: '',
        category_id: null,
        buy_price: 0,
        sell_price: 0,
        stock: 0,
        unit: 'dona'
    });

    // Supply state
    const [isSupplyModalOpen, setIsSupplyModalOpen] = useState(false);
    const [supplyData, setSupplyData] = useState({
        product_id: '',
        quantity: 0,
        buy_price: 0
    });
    const [isHistoryOpen, setIsHistoryOpen] = useState(false);
    const [isStockLogOpen, setIsStockLogOpen] = useState(false);

    const { data: products = [], isLoading } = useQuery({
        queryKey: ['products'],
        queryFn: async () => {
            const res = await api.get('/inventory/products');
            return res.data;
        }
    });

    const { data: categories = [] } = useQuery({
        queryKey: ['categories'],
        queryFn: async () => {
            const res = await api.get('/inventory/categories');
            return res.data;
        }
    });

    const { data: supplies = [], isLoading: historyLoading } = useQuery({
        queryKey: ['supplies'],
        queryFn: async () => {
            const res = await api.get('/inventory/supplies');
            return res.data;
        },
        enabled: isHistoryOpen
    });

    const { data: stockLogs = [], isLoading: logsLoading } = useQuery({
        queryKey: ['stock-logs'],
        queryFn: async () => {
            const res = await api.get('/inventory/logs');
            return res.data;
        },
        enabled: isStockLogOpen
    });

    const { data: settings } = useQuery({
        queryKey: ['settings'],
        queryFn: async () => {
            const res = await api.get('/settings');
            return res.data;
        }
    });

    const threshold = settings?.low_stock_threshold ?? 5;

    const productMutation = useMutation({
        mutationFn: (data) => editingProduct
            ? api.put(`/inventory/products/${editingProduct.id}`, data)
            : api.post('/inventory/products', data),
        onSuccess: () => {
            queryClient.invalidateQueries(['products']);
            setIsModalOpen(false);
            setEditingProduct(null);
            resetForm();
            toast.success(editingProduct ? "Mahsulot yangilandi" : "Yangi mahsulot qo'shildi");
        },
        onError: (err) => {
            toast.error("Xatolik!", { description: err.response?.data?.detail || "Amalni bajarib bo'lmadi" });
        }
    });

    const deleteMutation = useMutation({
        mutationFn: (id) => api.delete(`/inventory/products/${id}`),
        onSuccess: () => {
            queryClient.invalidateQueries(['products']);
            toast.success("Mahsulot ochirildi");
        }
    });

    const supplyMutation = useMutation({
        mutationFn: (data) => api.post('/inventory/supplies', data),
        onSuccess: () => {
            queryClient.invalidateQueries(['products']);
            setIsSupplyModalOpen(false);
            setSupplyData({ product_id: '', quantity: 0, buy_price: 0 });
            toast.success("Kirim muvaffaqiyatli bajarildi");
        },
        onError: (err) => {
            toast.error("Xatolik!", { description: err.response?.data?.detail || "Amalni bajarib bo'lmadi" });
        }
    });

    const categoryMutation = useMutation({
        mutationFn: (name) => api.post('/inventory/categories', { name }),
        onSuccess: () => {
            queryClient.invalidateQueries(['categories']);
            setIsCategoryModalOpen(false);
            setNewCategoryName('');
            toast.success("Kategoriya yaratildi");
        },
        onError: (err) => {
            toast.error("Xatolik!", { description: err.response?.data?.detail || "Kategoriya yaratib bo'lmadi" });
        }
    });

    const favoriteMutation = useMutation({
        mutationFn: (productId) => api.post(`/inventory/products/${productId}/toggle-favorite`),
        onSuccess: () => {
            queryClient.invalidateQueries(['products']);
            toast.success("Mahsulot holati yangilandi");
        },
        onError: (err) => {
            toast.error("Xatolik!", { description: err.response?.data?.detail || "Amalni bajarib bo'lmadi" });
        }
    });

    const handleCategorySubmit = (e) => {
        e.preventDefault();
        categoryMutation.mutate(newCategoryName);
    };

    const handleSupplySubmit = (e) => {
        e.preventDefault();
        supplyMutation.mutate({
            ...supplyData,
            product_id: parseInt(supplyData.product_id),
            quantity: parseFloat(supplyData.quantity),
            buy_price: parseFloat(supplyData.buy_price)
        });
    };

    const resetForm = () => {
        setFormData({
            name: '',
            barcode: '',
            category_id: null,
            buy_price: 0,
            sell_price: 0,
            stock: 0,
            unit: 'dona'
        });
    };

    const handleEdit = (product) => {
        setEditingProduct(product);
        setFormData({
            name: product.name,
            barcode: product.barcode || '',
            category_id: product.category_id,
            buy_price: product.buy_price,
            sell_price: product.sell_price,
            stock: product.stock,
            unit: product.unit
        });
        setIsModalOpen(true);
    };

    const handleSubmit = (e) => {
        e.preventDefault();
        productMutation.mutate(formData);
    };

    const filteredProducts = products.filter(p => {
        const matchesSearch = p.name.toLowerCase().startsWith(searchTerm.toLowerCase()) ||
            p.barcode?.startsWith(searchTerm);
        const matchesCategory = selectedCategory === 'all' || p.category_id?.toString() === selectedCategory;
        return matchesSearch && matchesCategory;
    }).sort((a, b) => {
        switch (sortBy) {
            case 'price-asc': return a.sell_price - b.sell_price;
            case 'price-desc': return b.sell_price - a.sell_price;
            case 'stock-asc': return a.stock - b.stock;
            case 'stock-desc': return b.stock - a.stock;
            case 'name-asc': return a.name.localeCompare(b.name);
            default: return 0;
        }
    });

    return (
        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight">Ombor va Mahsulotlar</h1>
                    <p className="text-muted-foreground">Do'kondagi barcha mahsulotlarni boshqarish</p>
                </div>

                <Dialog open={isModalOpen} onOpenChange={(open) => {
                    setIsModalOpen(open);
                    if (!open) {
                        setEditingProduct(null);
                        resetForm();
                    }
                }}>
                    <DialogTrigger asChild>
                        <Button className="gap-2 shadow-lg shadow-primary/20" onClick={() => { setEditingProduct(null); resetForm(); }}>
                            <Plus className="w-4 h-4" /> Yangi Mahsulot
                        </Button>
                    </DialogTrigger>



                    <Dialog open={isCategoryModalOpen} onOpenChange={setIsCategoryModalOpen}>
                        <DialogTrigger asChild>
                            <Button variant="outline" className="gap-2 ml-2">
                                <FolderPlus className="w-4 h-4" /> Kategoriya
                            </Button>
                        </DialogTrigger>
                        <DialogContent className="sm:max-w-[400px]">
                            <form onSubmit={handleCategorySubmit}>
                                <DialogHeader>
                                    <DialogTitle>Yangi Kategoriya</DialogTitle>
                                    <DialogDescription>
                                        Yangi mahsulot kategoriyasi nomini kiriting.
                                    </DialogDescription>
                                </DialogHeader>
                                <div className="grid gap-4 py-4">
                                    <div className="grid gap-2">
                                        <Label htmlFor="cat-name">Nomi</Label>
                                        <Input
                                            id="cat-name"
                                            value={newCategoryName}
                                            onChange={(e) => setNewCategoryName(e.target.value)}
                                            placeholder="Masalan: Ichimliklar"
                                            required
                                        />
                                    </div>
                                </div>
                                <DialogFooter>
                                    <Button type="submit" disabled={categoryMutation.isPending}>
                                        {categoryMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                                        Yaratish
                                    </Button>
                                </DialogFooter>
                            </form>
                        </DialogContent>
                    </Dialog>



                    {/* Supply button removed */}

                    <Dialog open={isHistoryOpen} onOpenChange={setIsHistoryOpen}>
                        <DialogTrigger asChild>
                            <Button variant="ghost" className="gap-2 ml-2">
                                <Truck className="w-4 h-4" /> Kirimlar
                            </Button>
                        </DialogTrigger>
                        <DialogContent className="sm:max-w-[700px] max-h-[80vh] flex flex-col">
                            <DialogHeader>
                                <DialogTitle>Kirimlar Tarixi</DialogTitle>
                                <DialogDescription>
                                    Barcha kirim qilingan mahsulotlar ro'yxati.
                                </DialogDescription>
                            </DialogHeader>
                            <div className="flex-1 overflow-auto py-4">
                                <Table>
                                    <TableHeader>
                                        <TableRow>
                                            <TableHead>Sana</TableHead>
                                            <TableHead>Mahsulot</TableHead>
                                            <TableHead>Soni</TableHead>
                                            <TableHead>Narx</TableHead>
                                            <TableHead className="text-right">Jami</TableHead>
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {historyLoading ? (
                                            [1, 2, 3].map(i => (
                                                <TableRow key={i}>
                                                    <TableCell colSpan={5} className="h-12 animate-pulse bg-muted/30" />
                                                </TableRow>
                                            ))
                                        ) : supplies.length === 0 ? (
                                            <TableRow>
                                                <TableCell colSpan={5} className="text-center text-muted-foreground h-24">
                                                    Hozircha kirimlar yo'q
                                                </TableCell>
                                            </TableRow>
                                        ) : supplies.map(item => {
                                            const product = products.find(p => p.id === item.product_id);
                                            return (
                                                <TableRow key={item.id}>
                                                    <TableCell className="text-xs text-muted-foreground">
                                                        {format(new Date(item.created_at), 'dd.MM.yyyy HH:mm')}
                                                    </TableCell>
                                                    <TableCell className="font-medium">
                                                        {product ? product.name : `#${item.product_id}`}
                                                    </TableCell>
                                                    <TableCell>{item.quantity}</TableCell>
                                                    <TableCell>{item.buy_price.toLocaleString()}</TableCell>
                                                    <TableCell className="text-right font-bold">
                                                        {(item.quantity * item.buy_price).toLocaleString()}
                                                    </TableCell>
                                                </TableRow>
                                            );
                                        })}
                                    </TableBody>
                                </Table>
                            </div>
                        </DialogContent>
                    </Dialog>

                    <Dialog open={isStockLogOpen} onOpenChange={setIsStockLogOpen}>
                        <DialogTrigger asChild>
                            <Button variant="ghost" className="gap-2 ml-2">
                                <History className="w-4 h-4" /> Loglar
                            </Button>
                        </DialogTrigger>
                        <DialogContent className="sm:max-w-[800px] max-h-[85vh] flex flex-col">
                            <DialogHeader>
                                <DialogTitle>Ombor Harakati Tarixi</DialogTitle>
                                <DialogDescription>
                                    Barcha mahsulotlarning kirim-chiqim va o'zgarishlar tarixi.
                                </DialogDescription>
                            </DialogHeader>
                            <div className="flex-1 overflow-auto py-4">
                                <Table>
                                    <TableHeader>
                                        <TableRow>
                                            <TableHead>Sana</TableHead>
                                            <TableHead>Mahsulot</TableHead>
                                            <TableHead>Turi</TableHead>
                                            <TableHead>Miqdor</TableHead>
                                            <TableHead>Sabab / Izoh</TableHead>
                                            <TableHead>Xodim</TableHead>
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {logsLoading ? (
                                            [1, 2, 3, 4, 5].map(i => (
                                                <TableRow key={i}>
                                                    <TableCell colSpan={6} className="h-12 animate-pulse bg-muted/30" />
                                                </TableRow>
                                            ))
                                        ) : stockLogs.length === 0 ? (
                                            <TableRow>
                                                <TableCell colSpan={6} className="text-center text-muted-foreground h-24">
                                                    Hozircha harakatlar yo'q
                                                </TableCell>
                                            </TableRow>
                                        ) : stockLogs.map(log => (
                                            <TableRow key={log.id} className="text-sm">
                                                <TableCell className="text-xs text-muted-foreground">
                                                    {format(new Date(log.created_at), 'dd.MM HH:mm')}
                                                </TableCell>
                                                <TableCell className="font-medium">
                                                    {log.product?.name || `#${log.product_id}`}
                                                </TableCell>
                                                <TableCell>
                                                    <Badge 
                                                        variant="outline" 
                                                        className={cn(
                                                            "capitalize font-normal",
                                                            log.type === 'sale' && "text-blue-500 border-blue-500/20 bg-blue-500/5",
                                                            log.type === 'restock' && "text-emerald-500 border-emerald-500/20 bg-emerald-500/5",
                                                            log.type === 'refund' && "text-orange-500 border-orange-500/20 bg-orange-500/5",
                                                            log.type === 'adjustment' && "text-purple-500 border-purple-500/20 bg-purple-500/5"
                                                        )}
                                                    >
                                                        {log.type === 'sale' ? 'Sotuv' : 
                                                         log.type === 'restock' ? 'Kirim' :
                                                         log.type === 'refund' ? 'Vozvrat' : 'To\'g\'rilash'}
                                                    </Badge>
                                                </TableCell>
                                                <TableCell className={cn(
                                                    "font-black text-base",
                                                    log.quantity > 0 ? "text-emerald-600" : "text-rose-600"
                                                )}>
                                                    {log.quantity > 0 ? `+${log.quantity?.toLocaleString()}` : log.quantity?.toLocaleString()}
                                                </TableCell>
                                                <TableCell className="max-w-[150px] truncate text-xs" title={log.reason}>
                                                    {log.reason || '-'}
                                                </TableCell>
                                                <TableCell className="text-xs">
                                                    {log.user?.username || '-'}
                                                </TableCell>
                                            </TableRow>
                                        ))}
                                    </TableBody>
                                </Table>
                            </div>
                        </DialogContent>
                    </Dialog>
                    <DialogContent className="sm:max-w-[500px]">
                        <form onSubmit={handleSubmit}>
                            <DialogHeader>
                                <DialogTitle>{editingProduct ? "Mahsulotni Tahrirlash" : "Yangi Mahsulot Qo'shish"}</DialogTitle>
                                <DialogDescription>
                                    Mahsulot ma'lumotlarini to'liq kiriting. Barcha maydonlar muhim.
                                </DialogDescription>
                            </DialogHeader>
                            <div className="grid gap-4 py-4">
                                <div className="grid grid-cols-4 items-center gap-4">
                                    <Label htmlFor="name" className="text-right">Nomi</Label>
                                    <Input id="name" className="col-span-3" value={formData.name} onChange={(e) => setFormData({ ...formData, name: e.target.value })} required />
                                </div>
                                <div className="grid grid-cols-4 items-center gap-4">
                                    <Label htmlFor="category" className="text-right">Kategoriya</Label>
                                    <Select
                                        value={formData.category_id?.toString()}
                                        onValueChange={(val) => setFormData({ ...formData, category_id: parseInt(val) })}
                                    >
                                        <SelectTrigger className="col-span-3">
                                            <SelectValue placeholder="Kategoriyani tanlang" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="null">Kategoriyasiz</SelectItem>
                                            {categories.map(c => (
                                                <SelectItem key={c.id} value={c.id.toString()}>
                                                    {c.name}
                                                </SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                </div>
                                <div className="grid grid-cols-4 items-center gap-4">
                                    <Label htmlFor="barcode" className="text-right">Shtrix Kod</Label>
                                    <Input id="barcode" className="col-span-3" value={formData.barcode} onChange={(e) => setFormData({ ...formData, barcode: e.target.value })} />
                                </div>
                                <div className="grid grid-cols-4 items-center gap-4">
                                    <Label htmlFor="buy_price" className="text-right">Keltirilgan Narx</Label>
                                    <Input id="buy_price" type="number" className="col-span-3" value={formData.buy_price} onChange={(e) => setFormData({ ...formData, buy_price: parseFloat(e.target.value) })} required />
                                </div>
                                <div className="grid grid-cols-4 items-center gap-4">
                                    <Label htmlFor="sell_price" className="text-right">Sotish Narxi</Label>
                                    <Input id="sell_price" type="number" className="col-span-3" value={formData.sell_price} onChange={(e) => setFormData({ ...formData, sell_price: parseFloat(e.target.value) })} required />
                                </div>
                                {/* Stock input removed */}
                                <div className="grid grid-cols-4 items-center gap-4">
                                    <Label htmlFor="unit" className="text-right">Birlik</Label>
                                    <Select
                                        value={formData.unit}
                                        onValueChange={(val) => setFormData({ ...formData, unit: val })}
                                    >
                                        <SelectTrigger className="col-span-3">
                                            <SelectValue placeholder="Birlikni tanlang" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="dona">dona</SelectItem>
                                            <SelectItem value="kg">kg (vaznli)</SelectItem>
                                            <SelectItem value="litr">litr (vaznli)</SelectItem>
                                            <SelectItem value="metr">metr</SelectItem>
                                            <SelectItem value="pachka">pachka</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </div>
                            </div>
                            <DialogFooter>
                                <Button type="submit" disabled={productMutation.isPending} className="w-full sm:w-auto">
                                    {productMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                                    {editingProduct ? "Saqlash" : "Qo'shish"}
                                </Button>
                            </DialogFooter>
                        </form>
                    </DialogContent>
                </Dialog>
            </div>

            <Card className="border shadow-sm overflow-hidden bg-card/50 backdrop-blur-xl hover:bg-card/80 transition-colors">
                <CardHeader className="p-6 pb-0">
                    <div className="flex flex-col sm:flex-row gap-4 items-center justify-between">
                        <div className="relative flex-1 max-w-sm w-full">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                            <Input
                                placeholder="Nomi yoki shtrix kodi bo'yicha qidiruv..."
                                className="pl-10 bg-background/50 border-input ring-offset-background focus-visible:ring-primary"
                                value={searchTerm}
                                onChange={(e) => setSearchTerm(e.target.value)}
                            />
                        </div>

                        <div className="flex gap-2 w-full sm:w-auto">
                            <Select value={selectedCategory} onValueChange={setSelectedCategory}>
                                <SelectTrigger className="w-full sm:w-[180px] bg-background/50">
                                    <SelectValue placeholder="Kategoriya" />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="all">Barchasi</SelectItem>
                                    {categories.map(c => (
                                        <SelectItem key={c.id} value={c.id.toString()}>
                                            {c.name}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>

                            <Select value={sortBy} onValueChange={setSortBy}>
                                <SelectTrigger className="w-full sm:w-[180px] bg-background/50">
                                    <SelectValue placeholder="Saralash" />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="name-asc">Nomi (A-Z)</SelectItem>
                                    <SelectItem value="price-asc">Arzonlari oldin</SelectItem>
                                    <SelectItem value="price-desc">Qimmatlari oldin</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>
                    </div>
                </CardHeader>
                <CardContent className="p-0 mt-6">
                    <Table>
                        <TableHeader className="bg-muted/30">
                            <TableRow className="hover:bg-transparent">
                                <TableHead className="pl-8 h-12">Mahsulot Nomi</TableHead>
                                <TableHead className="h-12">Shtrix Kod</TableHead>
                                <TableHead className="h-12">Kategoriya</TableHead>
                                <TableHead className="h-12">Sotish Narxi</TableHead>
                                <TableHead className="h-12">Birlik</TableHead>
                                <TableHead className="pr-8 text-right h-12">Amallar</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {isLoading ? (
                                [1, 2, 3, 4, 5].map(i => (
                                    <TableRow key={i}>
                                        <TableCell colSpan={7} className="h-12 animate-pulse bg-muted/30" />
                                    </TableRow>
                                ))
                            ) : filteredProducts.length === 0 ? (
                                <TableRow>
                                    <TableCell colSpan={7} className="h-40 text-center text-muted-foreground">
                                        Mahsulotlar topilmadi
                                    </TableCell>
                                </TableRow>
                            ) : filteredProducts.map((product) => (
                                <TableRow key={product.id} className="group hover:bg-muted/50 transition-colors border-b-border/50 odd:bg-muted/10">
                                    <TableCell className="pl-8 font-medium text-foreground">
                                        <div className="flex items-center gap-2">
                                            <Button
                                                variant="ghost"
                                                size="icon"
                                                className={cn(
                                                    "w-6 h-6 p-0 hover:bg-transparent",
                                                    product.is_favorite ? "text-amber-500 fill-amber-500" : "text-muted-foreground/30 hover:text-amber-500/50"
                                                )}
                                                onClick={() => favoriteMutation.mutate(product.id)}
                                            >
                                                <Star className="w-4 h-4" />
                                            </Button>
                                            {product.name}
                                        </div>
                                    </TableCell>
                                    <TableCell className="text-muted-foreground font-mono text-xs">{product.barcode || '-'}</TableCell>
                                    <TableCell>
                                        <Badge variant="outline" className="font-normal bg-background/50">
                                            {categories.find(c => c.id === product.category_id)?.name || 'Boshqa'}
                                        </Badge>
                                    </TableCell>
                                    <TableCell className="font-semibold text-foreground">
                                        {product.sell_price.toLocaleString()} <span className="text-[10px] text-muted-foreground font-medium uppercase">so'm</span>
                                    </TableCell>
                                    <TableCell className="text-muted-foreground">{product.unit}</TableCell>
                                    <TableCell className="pr-8 text-right">
                                        <DropdownMenu>
                                            <DropdownMenuTrigger asChild>
                                                <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-primary active:scale-95 transition-transform">
                                                    <MoreHorizontal className="w-4 h-4" />
                                                </Button>
                                            </DropdownMenuTrigger>
                                            <DropdownMenuContent align="end" className="w-40 backdrop-blur-lg bg-popover/90">
                                                <DropdownMenuLabel>Amallar</DropdownMenuLabel>
                                                <DropdownMenuSeparator />
                                                {(role === 'admin' || role === 'manager') && (
                                                    <>
                                                        <DropdownMenuItem className="gap-2 cursor-pointer" onClick={() => handleEdit(product)}>
                                                            <Edit className="w-4 h-4" /> Tahrirlash
                                                        </DropdownMenuItem>
                                                        <DropdownMenuItem
                                                            className="gap-2 cursor-pointer text-destructive focus:bg-destructive/10 focus:text-destructive"
                                                            onClick={() => {
                                                                if (confirm(`${product.name} mahsulotini o'chirib tashlamoqchimisiz?`)) {
                                                                    deleteMutation.mutate(product.id);
                                                                }
                                                            }}
                                                        >
                                                            <Trash2 className="w-4 h-4" /> O'chirish
                                                        </DropdownMenuItem>
                                                    </>
                                                )}
                                            </DropdownMenuContent>
                                        </DropdownMenu>
                                    </TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </CardContent>
            </Card>

            {filteredProducts.some(p => p.stock < threshold) && (
                <div className="bg-amber-500/10 dark:bg-amber-500/20 border border-amber-500/30 rounded-xl p-4 flex items-start gap-3 shadow-sm">
                    <AlertCircle className="w-5 h-5 text-amber-600 dark:text-amber-500 mt-0.5" />
                    <div>
                        <h4 className="font-bold text-amber-900 dark:text-amber-300">Past Qoldiq Ogohlantirishi</h4>
                        <p className="text-sm text-amber-700 dark:text-amber-400">Ba'zi mahsulotlar qoldig'i {threshold} tadan kam qolgan. Omboringizni to'ldirishingizni tavsiya qilamiz.</p>
                    </div>
                </div>
            )}
        </div>
    );
};

export default Inventory;
