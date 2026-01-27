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
    History
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
import { cn } from "@/lib/utils";

const Inventory = () => {
    const [searchTerm, setSearchTerm] = useState('');
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

    const handleCategorySubmit = (e) => {
        e.preventDefault();
        categoryMutation.mutate(newCategoryName);
    };

    const handleSupplySubmit = (e) => {
        e.preventDefault();
        supplyMutation.mutate({
            ...supplyData,
            product_id: parseInt(supplyData.product_id),
            quantity: parseInt(supplyData.quantity),
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
        const matchesSearch = p.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
            p.barcode?.includes(searchTerm);
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



                    <Dialog open={isSupplyModalOpen} onOpenChange={setIsSupplyModalOpen}>
                        <DialogTrigger asChild>
                            <Button variant="secondary" className="gap-2 ml-2">
                                <Truck className="w-4 h-4" /> Kirim Qilish
                            </Button>
                        </DialogTrigger>
                        <DialogContent className="sm:max-w-[500px]">
                            <form onSubmit={handleSupplySubmit}>
                                <DialogHeader>
                                    <DialogTitle>Mahsulot Kirimi</DialogTitle>
                                    <DialogDescription>
                                        Omborga yangi tovar kelganda kirim qiling.
                                    </DialogDescription>
                                </DialogHeader>
                                <div className="grid gap-4 py-4">
                                    <div className="grid gap-2">
                                        <Label htmlFor="supply-product">Mahsulot</Label>
                                        <Select 
                                            value={supplyData.product_id?.toString()} 
                                            onValueChange={(val) => {
                                                const prod = products.find(p => p.id.toString() === val);
                                                setSupplyData(prev => ({ 
                                                    ...prev, 
                                                    product_id: val,
                                                    buy_price: prod ? prod.buy_price : 0
                                                }));
                                            }}
                                        >
                                            <SelectTrigger>
                                                <SelectValue placeholder="Mahsulotni tanlang..." />
                                            </SelectTrigger>
                                            <SelectContent>
                                                {products.map(p => (
                                                    <SelectItem key={p.id} value={p.id.toString()}>
                                                        {p.name}
                                                    </SelectItem>
                                                ))}
                                            </SelectContent>
                                        </Select>
                                    </div>
                                    <div className="grid gap-2">
                                        <Label htmlFor="supply-qty">Soni</Label>
                                        <Input 
                                            id="supply-qty" 
                                            type="number" 
                                            value={supplyData.quantity} 
                                            onChange={(e) => setSupplyData({...supplyData, quantity: e.target.value})} 
                                            required 
                                        />
                                    </div>
                                    <div className="grid gap-2">
                                        <Label htmlFor="supply-price">Kelish Narxi (dona)</Label>
                                        <Input 
                                            id="supply-price" 
                                            type="number" 
                                            value={supplyData.buy_price} 
                                            onChange={(e) => setSupplyData({...supplyData, buy_price: e.target.value})} 
                                            required 
                                        />
                                    </div>
                                </div>
                                <DialogFooter>
                                    <Button type="submit" disabled={supplyMutation.isPending}>
                                        {supplyMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                                        Kirim Qilish
                                    </Button>
                                </DialogFooter>
                            </form>
                        </DialogContent>
                    </Dialog>

                    <Dialog open={isHistoryOpen} onOpenChange={setIsHistoryOpen}>
                        <DialogTrigger asChild>
                            <Button variant="ghost" className="gap-2 ml-2">
                                <History className="w-4 h-4" /> Tarix
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
                                            [1,2,3].map(i => (
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
                                <div className="grid grid-cols-4 items-center gap-4">
                                    <Label htmlFor="stock" className="text-right">Qoldiq</Label>
                                    <Input id="stock" type="number" className="col-span-3" value={formData.stock} onChange={(e) => setFormData({ ...formData, stock: parseInt(e.target.value) })} required />
                                </div>
                                <div className="grid grid-cols-4 items-center gap-4">
                                    <Label htmlFor="unit" className="text-right">Birlik</Label>
                                    <Input id="unit" className="col-span-3" value={formData.unit} onChange={(e) => setFormData({ ...formData, unit: e.target.value })} placeholder="dona, kg, litr..." required />
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

            <Card className="border-none shadow-md overflow-hidden bg-card/80 backdrop-blur-xl">
                <CardHeader className="p-6 pb-0">
                    <div className="flex gap-4 items-center">
                        <div className="relative flex-1 max-w-sm">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                            <Input
                                placeholder="Nomi yoki shtrix kodi bo'yicha qidiruv..."
                                className="pl-10 bg-muted border-none ring-1 ring-border"
                                value={searchTerm}
                                onChange={(e) => setSearchTerm(e.target.value)}
                            />
                        </div>
                        
                        <Select value={selectedCategory} onValueChange={setSelectedCategory}>
                            <SelectTrigger className="w-[180px]">
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
                            <SelectTrigger className="w-[180px]">
                                <SelectValue placeholder="Saralash" />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="name-asc">Nomi (A-Z)</SelectItem>
                                <SelectItem value="price-asc">Arzonlari oldin</SelectItem>
                                <SelectItem value="price-desc">Qimmatlari oldin</SelectItem>
                                <SelectItem value="stock-asc">Kam qolganlari</SelectItem>
                                <SelectItem value="stock-desc">Ko'p qolganlari</SelectItem>
                            </SelectContent>
                        </Select>
                    </div>
                </CardHeader>
                <CardContent className="p-0 mt-6">
                    <Table>
                        <TableHeader className="bg-muted/50">
                            <TableRow>
                                <TableHead className="pl-8">Mahsulot Nomi</TableHead>
                                <TableHead>Shtrix Kod</TableHead>
                                <TableHead>Kategoriya</TableHead>
                                <TableHead>Sotish Narxi</TableHead>
                                <TableHead>Qoldiq</TableHead>
                                <TableHead>Birlik</TableHead>
                                <TableHead className="pr-8 text-right">Amallar</TableHead>
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
                                <TableRow key={product.id} className="group hover:bg-muted/50 transition-colors">
                                    <TableCell className="pl-8 font-semibold text-foreground">{product.name}</TableCell>
                                    <TableCell className="text-muted-foreground font-mono text-xs">{product.barcode || '-'}</TableCell>
                                    <TableCell>
                                        <Badge variant="outline" className="font-medium">
                                            {categories.find(c => c.id === product.category_id)?.name || 'Boshqa'}
                                        </Badge>
                                    </TableCell>
                                    <TableCell className="font-bold text-foreground">
                                        {product.sell_price.toLocaleString()} <span className="text-[10px] text-muted-foreground font-medium uppercase">so'm</span>
                                    </TableCell>
                                    <TableCell>
                                        <Badge
                                            variant={product.stock < 5 ? "destructive" : "secondary"}
                                            className={cn(
                                                "font-bold px-2 py-0.5",
                                                product.stock >= 5 && "bg-emerald-500/20 dark:bg-emerald-500/30 text-emerald-700 dark:text-emerald-400 hover:bg-emerald-500/20"
                                            )}
                                        >
                                            {product.stock}
                                        </Badge>
                                    </TableCell>
                                    <TableCell className="text-muted-foreground">{product.unit}</TableCell>
                                    <TableCell className="pr-8 text-right">
                                        <DropdownMenu>
                                            <DropdownMenuTrigger asChild>
                                                <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-primary">
                                                    <MoreHorizontal className="w-4 h-4" />
                                                </Button>
                                            </DropdownMenuTrigger>
                                            <DropdownMenuContent align="end" className="w-40">
                                                <DropdownMenuLabel>Amallar</DropdownMenuLabel>
                                                <DropdownMenuSeparator />
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
                                            </DropdownMenuContent>
                                        </DropdownMenu>
                                    </TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </CardContent>
            </Card>

            {filteredProducts.some(p => p.stock < 5) && (
                <div className="bg-amber-500/10 dark:bg-amber-500/20 border border-amber-500/30 rounded-xl p-4 flex items-start gap-3 shadow-sm">
                    <AlertCircle className="w-5 h-5 text-amber-600 dark:text-amber-500 mt-0.5" />
                    <div>
                        <h4 className="font-bold text-amber-900 dark:text-amber-300">Past Qoldiq Ogohlantirishi</h4>
                        <p className="text-sm text-amber-700 dark:text-amber-400">Ba'zi mahsulotlar qoldig'i 5 tadan kam qolgan. Omboringizni to'ldirishingizni tavsiya qilamiz.</p>
                    </div>
                </div>
            )}
        </div>
    );
};

export default Inventory;
