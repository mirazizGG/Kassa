import React, { useState } from 'react';
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
    Loader2
} from 'lucide-react';
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
    const [isModalOpen, setIsModalOpen] = useState(false);
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

    const filteredProducts = products.filter(p =>
        p.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        p.barcode?.includes(searchTerm)
    );

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

            <Card className="border-none shadow-md overflow-hidden bg-white/80 backdrop-blur-xl">
                <CardHeader className="p-6 pb-0">
                    <div className="flex gap-4 items-center">
                        <div className="relative flex-1 max-w-sm">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                            <Input
                                placeholder="Nomi yoki shtrix kodi bo'yicha qidiruv..."
                                className="pl-10 bg-slate-50 border-none ring-1 ring-slate-200"
                                value={searchTerm}
                                onChange={(e) => setSearchTerm(e.target.value)}
                            />
                        </div>
                        <Button variant="outline" className="gap-2 border-slate-200">
                            <Filter className="w-4 h-4" /> Saralash
                        </Button>
                    </div>
                </CardHeader>
                <CardContent className="p-0 mt-6">
                    <Table>
                        <TableHeader className="bg-slate-50/50">
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
                                        <TableCell colSpan={7} className="h-12 animate-pulse bg-slate-50/30" />
                                    </TableRow>
                                ))
                            ) : filteredProducts.length === 0 ? (
                                <TableRow>
                                    <TableCell colSpan={7} className="h-40 text-center text-muted-foreground">
                                        Mahsulotlar topilmadi
                                    </TableCell>
                                </TableRow>
                            ) : filteredProducts.map((product) => (
                                <TableRow key={product.id} className="group hover:bg-slate-50/50 transition-colors">
                                    <TableCell className="pl-8 font-semibold text-slate-900">{product.name}</TableCell>
                                    <TableCell className="text-slate-500 font-mono text-xs">{product.barcode || '-'}</TableCell>
                                    <TableCell>
                                        <Badge variant="outline" className="font-medium text-slate-600 bg-slate-50 border-slate-200">
                                            {categories.find(c => c.id === product.category_id)?.name || 'Boshqa'}
                                        </Badge>
                                    </TableCell>
                                    <TableCell className="font-bold text-slate-900">
                                        {product.sell_price.toLocaleString()} <span className="text-[10px] text-muted-foreground font-medium uppercase">so'm</span>
                                    </TableCell>
                                    <TableCell>
                                        <Badge
                                            variant={product.stock < 5 ? "destructive" : "secondary"}
                                            className={cn(
                                                "font-bold px-2 py-0.5",
                                                product.stock >= 5 && "bg-emerald-100 text-emerald-700 hover:bg-emerald-100"
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
                                                    <Edit className="w-4 h-4 text-slate-500" /> Tahrirlash
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
                <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex items-start gap-3 shadow-sm">
                    <AlertCircle className="w-5 h-5 text-amber-600 mt-0.5" />
                    <div>
                        <h4 className="font-bold text-amber-900">Past Qoldiq Ogohlantirishi</h4>
                        <p className="text-sm text-amber-700">Ba'zi mahsulotlar qoldig'i 5 tadan kam qolgan. Omboringizni to'ldirishingizni tavsiya qilamiz.</p>
                    </div>
                </div>
            )}
        </div>
    );
};

export default Inventory;
