import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import api from "../api/axios";
import { queryClient } from "../api/queryClient";
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
} from "lucide-react";
import { format } from "date-fns";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { toast } from "sonner";
import { cn, formatThousands, parseThousands } from "@/lib/utils.js";

const Inventory = () => {
  const [searchTerm, setSearchTerm] = useState("");
  const role = localStorage.getItem("role");
  const [selectedCategory, setSelectedCategory] = useState("all");
  const [sortBy, setSortBy] = useState("name-asc");
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isCategoryModalOpen, setIsCategoryModalOpen] = useState(false);
  const [newCategoryName, setNewCategoryName] = useState("");
  const [editingProduct, setEditingProduct] = useState(null);

  // Form state
  const [formData, setFormData] = useState({
    name: "",
    barcode: "",
    category_id: null,
    buy_price: "",
    sell_price: "",
    stock: 0,
    unit: "dona",
  });

  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  const [isStockLogOpen, setIsStockLogOpen] = useState(false);

  const { data: products = [], isLoading } = useQuery({
    queryKey: ["products"],
    queryFn: async () => {
      const res = await api.get("/inventory/products");
      return res.data;
    },
  });

  const { data: categories = [] } = useQuery({
    queryKey: ["categories"],
    queryFn: async () => {
      const res = await api.get("/inventory/categories");
      return res.data;
    },
  });

  const { data: supplies = [], isLoading: historyLoading } = useQuery({
    queryKey: ["supplies"],
    queryFn: async () => {
      const res = await api.get("/inventory/supplies");
      return res.data;
    },
    enabled: isHistoryOpen,
  });

  const { data: stockLogs = [], isLoading: logsLoading } = useQuery({
    queryKey: ["stock-logs"],
    queryFn: async () => {
      const res = await api.get("/inventory/logs");
      return res.data;
    },
    enabled: isStockLogOpen,
  });

  const { data: settings } = useQuery({
    queryKey: ["settings"],
    queryFn: async () => {
      const res = await api.get("/settings");
      return res.data;
    },
  });

  const { data: purchaseList = [] } = useQuery({
    queryKey: ["purchase-list"],
    queryFn: async () => {
      const res = await api.get("/inventory/purchase-list");
      return res.data;
    },
    enabled: ["admin", "manager", "warehouse"].includes(role),
  });
  const threshold = settings?.low_stock_threshold ?? 5;
  const lowStockCount = products.filter(
    (product) => product.stock < threshold,
  ).length;

  const productMutation = useMutation({
    mutationFn: (data) =>
      editingProduct
        ? api.put(`/inventory/products/${editingProduct.id}`, data)
        : api.post("/inventory/products", data),
    onSuccess: () => {
      queryClient.invalidateQueries(["products"]);
      setIsModalOpen(false);
      setEditingProduct(null);
      resetForm();
      toast.success(
        editingProduct ? "Mahsulot yangilandi" : "Yangi mahsulot qo'shildi",
      );
    },
    onError: (err) => {
      toast.error("Xatolik!", {
        description: err.response?.data?.detail || "Amalni bajarib bo'lmadi",
      });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id) => api.delete(`/inventory/products/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries(["products"]);
      toast.success("Mahsulot ochirildi");
    },
  });

  const categoryMutation = useMutation({
    mutationFn: (name) => api.post("/inventory/categories", { name }),
    onSuccess: () => {
      queryClient.invalidateQueries(["categories"]);
      setIsCategoryModalOpen(false);
      setNewCategoryName("");
      toast.success("Kategoriya yaratildi");
    },
    onError: (err) => {
      toast.error("Xatolik!", {
        description:
          err.response?.data?.detail || "Kategoriya yaratib bo'lmadi",
      });
    },
  });

  const handleCategorySubmit = (e) => {
    e.preventDefault();
    categoryMutation.mutate(newCategoryName);
  };

  const resetForm = () => {
    setFormData({
      name: "",
      barcode: "",
      category_id: null,
      buy_price: "",
      sell_price: "",
      stock: 0,
      unit: "dona",
    });
  };

  const handleEdit = (product) => {
    setEditingProduct(product);
    setFormData({
      name: product.name,
      barcode: product.barcode || "",
      category_id: product.category_id,
      buy_price: product.buy_price ? String(product.buy_price) : "",
      sell_price: product.sell_price ? String(product.sell_price) : "",
      stock: product.stock,
      unit: product.unit,
    });
    setIsModalOpen(true);
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!formData.name.trim()) {
      toast.error("Mahsulot nomini kiriting");
      return;
    }
    if (!formData.category_id) {
      toast.error("Kategoriyani tanlang");
      return;
    }
    if (!formData.barcode.trim()) {
      toast.error("Shtrix kodni kiriting");
      return;
    }
    if (!formData.buy_price || formData.buy_price <= 0) {
      toast.error("Keltirilgan narxni kiriting");
      return;
    }
    if (!formData.sell_price || formData.sell_price <= 0) {
      toast.error("Sotish narxini kiriting");
      return;
    }
    if (!formData.stock || formData.stock <= 0) {
      toast.error("Kirim sonini kiriting");
      return;
    }
    if (!formData.unit) {
      toast.error("Birlikni tanlang");
      return;
    }
    productMutation.mutate({
      ...formData,
      buy_price: Number(formData.buy_price) || 0,
      sell_price: Number(formData.sell_price) || 0,
      stock: Number(formData.stock) || 0,
    });
  };

  const filteredProducts = products
    .filter((p) => {
      const matchesSearch =
        p.name.toLowerCase().startsWith(searchTerm.toLowerCase()) ||
        p.barcode?.startsWith(searchTerm);
      const matchesCategory =
        selectedCategory === "all" ||
        p.category_id?.toString() === selectedCategory;
      return matchesSearch && matchesCategory;
    })
    .sort((a, b) => {
      switch (sortBy) {
        case "price-asc":
          return a.sell_price - b.sell_price;
        case "price-desc":
          return b.sell_price - a.sell_price;
        case "stock-asc":
          return a.stock - b.stock;
        case "stock-desc":
          return b.stock - a.stock;
        case "name-asc":
          return a.name.localeCompare(b.name);
        default:
          return 0;
      }
    });

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="min-w-0 flex-1">
          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">
            Ombor va Mahsulotlar
          </h1>
          <p className="text-muted-foreground">
            Do'kondagi barcha mahsulotlarni boshqarish
          </p>
          <div className="mt-3 flex items-center gap-2 text-sm text-muted-foreground">
            <Badge variant="outline">{products.length} mahsulot</Badge>
            {lowStockCount > 0 && (
              <Badge
                variant="outline"
                className="border-amber-300 bg-amber-50 text-amber-700 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-300"
              >
                {lowStockCount} ta past qoldiq
              </Badge>
            )}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
        <Dialog
          open={isModalOpen}
          onOpenChange={(open) => {
            setIsModalOpen(open);
            if (!open) {
              setEditingProduct(null);
              resetForm();
            }
          }}
        >
          <DialogTrigger asChild>
            <Button
              className="gap-2 shadow-lg shadow-primary/20"
              onClick={() => {
                setEditingProduct(null);
                resetForm();
              }}
            >
              <Plus className="w-4 h-4" /> Yangi Mahsulot
            </Button>
          </DialogTrigger>

          <Dialog
            open={isCategoryModalOpen}
            onOpenChange={setIsCategoryModalOpen}
          >
            <DialogTrigger asChild>
              <Button variant="outline" className="gap-2">
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
                    {categoryMutation.isPending && (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    )}
                    Yaratish
                  </Button>
                </DialogFooter>
              </form>
            </DialogContent>
          </Dialog>

          {/* Supply button removed */}

          <Dialog open={isHistoryOpen} onOpenChange={setIsHistoryOpen}>
            <DialogTrigger asChild>
              <Button variant="ghost" className="gap-2">
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
                      [1, 2, 3].map((i) => (
                        <TableRow key={i}>
                          <TableCell
                            colSpan={5}
                            className="h-12 animate-pulse bg-muted/30"
                          />
                        </TableRow>
                      ))
                    ) : supplies.length === 0 ? (
                      <TableRow>
                        <TableCell
                          colSpan={5}
                          className="text-center text-muted-foreground h-24"
                        >
                          Hozircha kirimlar yo'q
                        </TableCell>
                      </TableRow>
                    ) : (
                      supplies.map((item) => {
                        const product = products.find(
                          (p) => p.id === item.product_id,
                        );
                        return (
                          <TableRow key={item.id}>
                            <TableCell className="text-xs text-muted-foreground">
                              {format(
                                new Date(item.created_at),
                                "dd.MM.yyyy HH:mm",
                              )}
                            </TableCell>
                            <TableCell className="font-medium">
                              {product ? product.name : `#${item.product_id}`}
                            </TableCell>
                            <TableCell>{item.quantity}</TableCell>
                            <TableCell>
                              {item.buy_price.toLocaleString("de-DE")}
                            </TableCell>
                            <TableCell className="text-right font-bold">
                              {(
                                item.quantity * item.buy_price
                              ).toLocaleString("de-DE")}
                            </TableCell>
                          </TableRow>
                        );
                      })
                    )}
                  </TableBody>
                </Table>
              </div>
            </DialogContent>
          </Dialog>

          <Dialog open={isStockLogOpen} onOpenChange={setIsStockLogOpen}>
            <DialogTrigger asChild>
              <Button variant="ghost" className="gap-2">
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
                      [1, 2, 3, 4, 5].map((i) => (
                        <TableRow key={i}>
                          <TableCell
                            colSpan={6}
                            className="h-12 animate-pulse bg-muted/30"
                          />
                        </TableRow>
                      ))
                    ) : stockLogs.length === 0 ? (
                      <TableRow>
                        <TableCell
                          colSpan={6}
                          className="text-center text-muted-foreground h-24"
                        >
                          Hozircha harakatlar yo'q
                        </TableCell>
                      </TableRow>
                    ) : (
                      stockLogs.map((log) => (
                        <TableRow key={log.id} className="text-sm">
                          <TableCell className="text-xs text-muted-foreground">
                            {format(new Date(log.created_at), "dd.MM HH:mm")}
                          </TableCell>
                          <TableCell className="font-medium">
                            {log.product?.name || `#${log.product_id}`}
                          </TableCell>
                          <TableCell>
                            <Badge
                              variant="outline"
                              className={cn(
                                "capitalize font-normal",
                                log.type === "sale" &&
                                  "text-blue-500 border-blue-500/20 bg-blue-500/5",
                                log.type === "restock" &&
                                  "text-emerald-500 border-emerald-500/20 bg-emerald-500/5",
                                log.type === "refund" &&
                                  "text-orange-500 border-orange-500/20 bg-orange-500/5",
                                log.type === "adjustment" &&
                                  "text-purple-500 border-purple-500/20 bg-purple-500/5",
                              )}
                            >
                              {log.type === "sale"
                                ? "Sotuv"
                                : log.type === "restock"
                                  ? "Kirim"
                                  : log.type === "refund"
                                    ? "Vozvrat"
                                    : "To'g'rilash"}
                            </Badge>
                          </TableCell>
                          <TableCell
                            className={cn(
                              "font-black text-base",
                              log.quantity > 0
                                ? "text-emerald-600"
                                : "text-rose-600",
                            )}
                          >
                            {log.quantity > 0
                              ? `+${log.quantity?.toLocaleString("de-DE")}`
                              : log.quantity?.toLocaleString("de-DE")}
                          </TableCell>
                          <TableCell
                            className="max-w-[150px] truncate text-xs"
                            title={log.reason}
                          >
                            {log.reason || "-"}
                          </TableCell>
                          <TableCell className="text-xs">
                            {log.user?.username || "-"}
                          </TableCell>
                        </TableRow>
                      ))
                    )}
                  </TableBody>
                </Table>
              </div>
            </DialogContent>
          </Dialog>
          <DialogContent className="sm:max-w-[500px]">
            <form onSubmit={handleSubmit}>
              <DialogHeader>
                <DialogTitle>
                  {editingProduct
                    ? "Mahsulotni Tahrirlash"
                    : "Yangi Mahsulot Qo'shish"}
                </DialogTitle>
                <DialogDescription>
                  Mahsulot ma'lumotlarini to'liq kiriting. Barcha maydonlar
                  muhim.
                </DialogDescription>
              </DialogHeader>
              <div className="grid gap-4 py-4">
                <div className="grid grid-cols-4 items-center gap-4">
                  <Label htmlFor="name" className="text-right">
                    Nomi
                  </Label>
                  <Input
                    id="name"
                    className="col-span-3"
                    value={formData.name}
                    onChange={(e) =>
                      setFormData({ ...formData, name: e.target.value })
                    }
                    required
                  />
                </div>
                <div className="grid grid-cols-4 items-center gap-4">
                  <Label htmlFor="category" className="text-right">
                    Kategoriya
                  </Label>
                  <Select
                    value={formData.category_id?.toString()}
                    onValueChange={(val) =>
                      setFormData({ ...formData, category_id: parseInt(val) })
                    }
                  >
                    <SelectTrigger className="col-span-3">
                      <SelectValue placeholder="Kategoriyani tanlang" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="null">Kategoriyasiz</SelectItem>
                      {categories.map((c) => (
                        <SelectItem key={c.id} value={c.id.toString()}>
                          {c.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid grid-cols-4 items-center gap-4">
                  <Label htmlFor="new-category" className="text-right">
                    Yangi kategoriya
                  </Label>
                  <div className="col-span-3 flex gap-2">
                    <Input
                      id="new-category"
                      value={newCategoryName}
                      onChange={(e) => setNewCategoryName(e.target.value)}
                      placeholder="Masalan: Ichimliklar"
                    />
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() =>
                        categoryMutation.mutate(newCategoryName.trim())
                      }
                      disabled={
                        !newCategoryName.trim() || categoryMutation.isPending
                      }
                    >
                      Qo'shish
                    </Button>
                  </div>
                </div>
                <div className="grid grid-cols-4 items-center gap-4">
                  <Label htmlFor="barcode" className="text-right">
                    Shtrix Kod
                  </Label>
                  <Input
                    id="barcode"
                    className="col-span-3"
                    value={formData.barcode}
                    onChange={(e) =>
                      setFormData({ ...formData, barcode: e.target.value })
                    }
                    onKeyDown={(e) => {
                      if (e.key === "Enter") e.preventDefault();
                    }}
                  />
                </div>
                <div className="grid grid-cols-4 items-center gap-4">
                  <Label htmlFor="buy_price" className="text-right">
                    Keltirilgan Narx
                  </Label>
                  <Input
                    id="buy_price"
                    type="text"
                    inputMode="numeric"
                    placeholder="0"
                    className="col-span-3"
                    value={formatThousands(formData.buy_price)}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        buy_price: parseThousands(e.target.value),
                      })
                    }
                    onFocus={(e) => e.target.select()}
                    required
                  />
                </div>
                <div className="grid grid-cols-4 items-center gap-4">
                  <Label htmlFor="sell_price" className="text-right">
                    Sotish Narxi
                  </Label>
                  <Input
                    id="sell_price"
                    type="text"
                    inputMode="numeric"
                    placeholder="0"
                    className="col-span-3"
                    value={formatThousands(formData.sell_price)}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        sell_price: parseThousands(e.target.value),
                      })
                    }
                    onFocus={(e) => e.target.select()}
                    required
                  />
                </div>
                <div className="grid grid-cols-4 items-center gap-4">
                  <Label htmlFor="stock" className="text-right">
                    Kirim soni
                  </Label>
                  <Input
                    id="stock"
                    type="number"
                    min="0"
                    step="0.001"
                    className="col-span-3"
                    value={formData.stock}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        stock: Number(e.target.value) || 0,
                      })
                    }
                    onFocus={(e) => e.target.select()}
                    required
                  />
                </div>
                <div className="grid grid-cols-4 items-center gap-4">
                  <Label htmlFor="unit" className="text-right">
                    Birlik
                  </Label>
                  <Select
                    value={formData.unit}
                    onValueChange={(val) =>
                      setFormData({ ...formData, unit: val })
                    }
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
                <Button
                  type="submit"
                  disabled={productMutation.isPending}
                  className="w-full sm:w-auto"
                >
                  {productMutation.isPending && (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  )}
                  {editingProduct ? "Saqlash" : "Qo'shish"}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
        </div>
      </div>

      <Card className="overflow-hidden border shadow-sm bg-card/70 backdrop-blur-sm">
        <CardHeader className="border-b bg-muted/10 p-4">
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
              <Select
                value={selectedCategory}
                onValueChange={setSelectedCategory}
              >
                <SelectTrigger className="w-full sm:w-[180px] bg-background/50">
                  <SelectValue placeholder="Kategoriya" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Barchasi</SelectItem>
                  {categories.map((c) => (
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
        <CardContent className="p-0">
          <Table>
            <TableHeader className="bg-muted/30">
              <TableRow className="hover:bg-transparent">
                <TableHead className="pl-4 h-12">Mahsulot nomi</TableHead>
                <TableHead className="h-12">Shtrix kod</TableHead>
                <TableHead className="h-12">Kategoriya</TableHead>
                <TableHead className="h-12">Qoldiq</TableHead>
                <TableHead className="h-12">Kelish narxi</TableHead>
                <TableHead className="h-12">Sotish narxi</TableHead>
                <TableHead className="h-12">Foyda</TableHead>
                <TableHead className="h-12">Birlik</TableHead>
                <TableHead className="pr-4 text-right h-12">Amallar</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading ? (
                [1, 2, 3, 4, 5].map((i) => (
                  <TableRow key={i}>
                    <TableCell
                      colSpan={9}
                      className="h-12 animate-pulse bg-muted/30"
                    />
                  </TableRow>
                ))
              ) : filteredProducts.length === 0 ? (
                <TableRow>
                  <TableCell
                    colSpan={7}
                    className="h-40 text-center text-muted-foreground"
                  >
                    Mahsulotlar topilmadi
                  </TableCell>
                </TableRow>
              ) : (
                filteredProducts.map((product) => (
                  <TableRow
                    key={product.id}
                    className="group hover:bg-muted/50 transition-colors border-b-border/50 odd:bg-muted/10"
                  >
                    <TableCell className="pl-4 font-medium text-foreground">
                      {product.name}
                    </TableCell>
                    <TableCell className="text-muted-foreground font-mono text-xs">
                      {product.barcode || "-"}
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant="outline"
                        className="font-normal bg-background/50"
                      >
                        {categories.find((c) => c.id === product.category_id)
                          ?.name || "Boshqa"}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant="outline"
                        className={cn(
                          "font-semibold",
                          product.stock < threshold
                            ? "border-amber-300 bg-amber-50 text-amber-700 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-300"
                            : "bg-background/50",
                        )}
                      >
                        {product.stock?.toLocaleString("de-DE")} {product.unit}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {product.buy_price.toLocaleString("de-DE")} so'm
                    </TableCell>
                    <TableCell className="font-semibold text-foreground">
                      {product.sell_price.toLocaleString("de-DE")}{" "}
                      <span className="text-[10px] text-muted-foreground font-medium uppercase">
                        so'm
                      </span>
                    </TableCell>
                    <TableCell
                      className={cn(
                        "font-semibold",
                        product.sell_price - product.buy_price >= 0
                          ? "text-emerald-600"
                          : "text-rose-600",
                      )}
                    >
                      {(
                        product.sell_price - product.buy_price
                      ).toLocaleString("de-DE")}{" "}
                      so'm
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {product.unit}
                    </TableCell>
                    <TableCell className="pr-4 text-right">
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8 text-muted-foreground hover:text-primary active:scale-95 transition-transform"
                          >
                            <MoreHorizontal className="w-4 h-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent
                          align="end"
                          className="w-40 backdrop-blur-lg bg-popover/90"
                        >
                          <DropdownMenuLabel>Amallar</DropdownMenuLabel>
                          <DropdownMenuSeparator />
                          {(role === "admin" || role === "manager" || role === "warehouse") && (
                            <>
                              <DropdownMenuItem
                                className="gap-2 cursor-pointer"
                                onClick={() => handleEdit(product)}
                              >
                                <Edit className="w-4 h-4" /> Tahrirlash
                              </DropdownMenuItem>
                              {(role === "admin" || role === "manager") && (
                              <DropdownMenuItem
                                className="gap-2 cursor-pointer text-destructive focus:bg-destructive/10 focus:text-destructive"
                                onClick={() => {
                                  if (
                                    confirm(
                                      `${product.name} mahsulotini o'chirib tashlamoqchimisiz?`,
                                    )
                                  ) {
                                    deleteMutation.mutate(product.id);
                                  }
                                }}
                              >
                                <Trash2 className="w-4 h-4" /> O'chirish
                              </DropdownMenuItem>
                              )}
                            </>
                          )}
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
      {purchaseList.length > 0 && (
        <Card className="border-amber-200 bg-amber-50/50 shadow-sm dark:border-amber-900/50 dark:bg-amber-950/20">
          <CardHeader className="flex flex-row items-start justify-between gap-4 pb-3">
            <div>
              <CardTitle className="flex items-center gap-2 text-base">
                <AlertCircle className="h-5 w-5 text-amber-600" />
                Avtomatik xarid ro'yxati
              </CardTitle>
              <p className="mt-1 text-sm text-muted-foreground">
                Minimal qoldiqdan past mahsulotlar uchun tavsiya etilgan
                buyurtma.
              </p>
            </div>
            <Badge
              variant="outline"
              className="border-amber-300 text-amber-700 dark:border-amber-800 dark:text-amber-300"
            >
              {purchaseList.length} mahsulot
            </Badge>
          </CardHeader>
          <CardContent className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
            {purchaseList.map((item) => (
              <div
                key={item.product_id}
                className="rounded-lg border bg-background/70 p-3"
              >
                <div className="flex items-start justify-between gap-2">
                  <p className="font-semibold">{item.name}</p>
                  <Badge
                    variant={
                      item.priority === "critical" ? "destructive" : "outline"
                    }
                  >
                    {item.priority === "critical" ? "Tugagan" : "Kam"}
                  </Badge>
                </div>
                <div className="mt-2 flex justify-between text-sm text-muted-foreground">
                  <span>
                    Qoldiq: {item.stock} {item.unit}
                  </span>
                  <span>
                    Olish: {item.suggested_quantity} {item.unit}
                  </span>
                </div>
                <p className="mt-2 text-sm font-medium">
                  Taxminiy xarid:{" "}
                  {Math.round(item.estimated_cost).toLocaleString("de-DE")} so'm
                </p>
              </div>
            ))}
          </CardContent>
        </Card>
      )}
      {lowStockCount > 0 && (
        <div className="bg-amber-500/10 dark:bg-amber-500/20 border border-amber-500/30 rounded-xl p-4 flex items-start gap-3 shadow-sm">
          <AlertCircle className="w-5 h-5 text-amber-600 dark:text-amber-500 mt-0.5" />
          <div>
            <h4 className="font-bold text-amber-900 dark:text-amber-300">
              Past Qoldiq Ogohlantirishi
            </h4>
            <p className="text-sm text-amber-700 dark:text-amber-400">
              Ba'zi mahsulotlar qoldig'i {threshold} tadan kam qolgan.
              Omboringizni to'ldirishingizni tavsiya qilamiz.
            </p>
          </div>
        </div>
      )}
    </div>
  );
};

export default Inventory;
