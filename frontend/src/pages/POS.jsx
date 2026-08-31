import React, { useState, useEffect, useRef } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import api from "../api/axios";
import { queryClient } from "../api/queryClient";
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
  Star,
  RotateCcw,
} from "lucide-react";
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
} from "@/components/ui/select";
import { cn, formatThousands, parseThousands } from "@/lib/utils.js";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { useHotkeys } from "react-hotkeys-hook";

// Tugallanmagan savdo qoralamasi. Sahifa yangilanib ketsa (masalan dastur
// yangilanganda yoki tasodifan F5 bosilsa) savat shu yerdan tiklanadi.
const POS_DRAFT_KEY = "pos-draft";
const readPosDraft = () => {
  try {
    const d = JSON.parse(localStorage.getItem(POS_DRAFT_KEY) || "{}");
    return {
      cart: Array.isArray(d.cart) ? d.cart : [],
      selectedClient: d.selectedClient ?? null,
      bonusSpent: Number(d.bonusSpent) || 0,
    };
  } catch {
    return { cart: [], selectedClient: null, bonusSpent: 0 };
  }
};
const clearPosDraft = () => {
  try {
    localStorage.removeItem(POS_DRAFT_KEY);
  } catch {
    /* jim */
  }
};

const POS = () => {
  const initialDraft = readPosDraft();
  const [searchTerm, setSearchTerm] = useState("");
  const [cart, setCart] = useState(initialDraft.cart);
  const [heldCarts, setHeldCarts] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem("held-carts") || "[]");
    } catch {
      return [];
    }
  });
  const [isHeldCartsOpen, setIsHeldCartsOpen] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState(null);
  const [isPaymentModalOpen, setIsPaymentModalOpen] = useState(false);
  const [paymentAmounts, setPaymentAmounts] = useState({
    cash: "",
    card: "",
    perevod: "",
    qarz: "",
  });
  const [selectedClient, setSelectedClient] = useState(
    initialDraft.selectedClient,
  );
  const [debtClientSearch, setDebtClientSearch] = useState("");
  const [isQuickClientOpen, setIsQuickClientOpen] = useState(false);
  const [newClient, setNewClient] = useState({ name: "", phone: "" });
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [isShiftModalOpen, setIsShiftModalOpen] = useState(false);
  const [shiftBalance, setShiftBalance] = useState("");
  const [shiftNote, setShiftNote] = useState("");
  const [isUnsoldReturnOpen, setIsUnsoldReturnOpen] = useState(false);
  const [unsoldReturn, setUnsoldReturn] = useState({
    product_id: "",
    quantity: "",
    reason: "",
  });
  const [isWeightModalOpen, setIsWeightModalOpen] = useState(false);
  const [selectedProductForWeight, setSelectedProductForWeight] =
    useState(null);
  const [weightInput, setWeightInput] = useState("");
  const [amountInput, setAmountInput] = useState("");
  const [bonusSpent, setBonusSpent] = useState(initialDraft.bonusSpent);
  const posContainerRef = useRef(null);
  const searchInputRef = useRef(null);
  const role = localStorage.getItem("role");
  const userId = localStorage.getItem("userId");

  // Fetch Active Shift
  const { data: activeShift, isLoading: isShiftLoading } = useQuery({
    queryKey: ["active-shift", userId],
    queryFn: async () => {
      const res = await api.get("/pos/shifts/active");
      return res.data;
    },
    refetchOnMount: "always",
  });

  // Auto-open shift modal if cashier has no active shift
  useEffect(() => {
    if (!isShiftLoading && !activeShift && role === "cashier") {
      // Small delay to ensure UI is ready
      const timer = setTimeout(() => setIsShiftModalOpen(true), 500);
      return () => clearTimeout(timer);
    }
  }, [activeShift, isShiftLoading, role]);
  const toggleFullscreen = () => {
    if (!document.fullscreenElement) {
      posContainerRef.current?.requestFullscreen();
      setIsFullscreen(true);
    } else {
      if (document.exitFullscreen) {
        document.exitFullscreen();
        setIsFullscreen(false);
      }
    }
  };

  const unsoldReturnMutation = useMutation({
    mutationFn: ({ productId, quantity, reason }) =>
      api.post(`/inventory/products/${productId}/return`, { quantity, reason }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["products"] });
      queryClient.invalidateQueries({ queryKey: ["stock-logs"] });
      setUnsoldReturn({ product_id: "", quantity: "", reason: "" });
      setIsUnsoldReturnOpen(false);
      toast.success("Mahsulot omborga qaytarildi");
    },
    onError: (error) =>
      toast.error(error.response?.data?.detail || "Qaytarib bo'lmadi"),
  });

  const submitUnsoldReturn = () => {
    const quantity = Number(unsoldReturn.quantity);
    if (
      !unsoldReturn.product_id ||
      !Number.isFinite(quantity) ||
      quantity <= 0 ||
      unsoldReturn.reason.trim().length < 3
    ) {
      toast.error("Mahsulot, miqdor va sababni kiriting");
      return;
    }
    unsoldReturnMutation.mutate({
      productId: unsoldReturn.product_id,
      quantity,
      reason: unsoldReturn.reason.trim(),
    });
  };
  const openShiftMutation = useMutation({
    mutationFn: (data) => api.post("/pos/shifts/open", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["active-shift"] });
      setIsShiftModalOpen(false);
      setShiftBalance("");
      setShiftNote("");
      toast.success("Smena ochildi!");
    },
    onError: (error) =>
      toast.error(error.response?.data?.detail || "Smenani ochib bo'lmadi"),
  });

  const closeShiftMutation = useMutation({
    mutationFn: (data) => api.post("/pos/shifts/close", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["active-shift"] });
      setIsShiftModalOpen(false);
      setShiftBalance("");
      setShiftNote("");
      toast.success("Smena yopildi!");
    },
    onError: (error) =>
      toast.error(error.response?.data?.detail || "Smenani yopib bo'lmadi"),
  });

  const formatCashAmount = (value) => {
    if (value === "" || value === null || value === undefined) return "";
    return String(value).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  };
  const handleShiftSubmit = () => {
    const balance = shiftBalance.trim();
    const amount = Number(balance);

    if (balance === "" || !Number.isFinite(amount) || amount < 0) {
      toast.error("Boshlang'ich balansni kiriting", {
        description: "Kassada pul bo'lmasa, 0 deb aniq yozing.",
      });
      return;
    }

    if (activeShift) {
      const expectedCash =
        activeShift.opening_balance + (activeShift.total_cash || 0);
      if (Math.abs(amount - expectedCash) > 0.01 && !shiftNote.trim()) {
        toast.error("Kassa farqi uchun sabab yozing");
        return;
      }
      closeShiftMutation.mutate({
        closing_balance: amount,
        note: shiftNote.trim() || null,
      });
    } else {
      openShiftMutation.mutate({ opening_balance: amount });
    }
  };
  // Fetch Products
  const { data: products = [] } = useQuery({
    queryKey: ["products"],
    queryFn: async () => {
      const res = await api.get("/inventory/products");
      return res.data;
    },
  });

  // Fetch Categories
  const { data: categories = [] } = useQuery({
    queryKey: ["categories"],
    queryFn: async () => {
      const res = await api.get("/inventory/categories");
      return res.data;
    },
  });

  useEffect(() => {
    localStorage.setItem("held-carts", JSON.stringify(heldCarts));
  }, [heldCarts]);

  // Tugallanmagan savdoni saqlab boramiz (yangilanish/F5 dan keyin tiklash uchun)
  useEffect(() => {
    if (cart.length === 0) {
      clearPosDraft();
      return;
    }
    try {
      localStorage.setItem(
        POS_DRAFT_KEY,
        JSON.stringify({ cart, selectedClient, bonusSpent }),
      );
    } catch {
      /* jim */
    }
  }, [cart, selectedClient, bonusSpent]);

  const favoriteMutation = useMutation({
    mutationFn: (productId) =>
      api.post(`/inventory/products/${productId}/toggle-favorite`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["products"] }),
    onError: () => toast.error("Saralangan holatni o'zgartirib bo'lmadi"),
  });
  const { data: dailySummary } = useQuery({
    queryKey: ["my-daily-summary"],
    queryFn: async () => (await api.get("/sales/my-daily-summary")).data,
  });

  const holdCurrentCart = () => {
    if (!cart.length) return;
    setHeldCarts((current) => [
      ...current,
      {
        id: `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`,
        createdAt: new Date().toISOString(),
        cart,
      },
    ]);
    setCart([]);
    setSelectedClient(null);
    toast.success("Savdo kutishga saqlandi");
  };

  const restoreHeldCart = (heldCart) => {
    if (cart.length > 0) {
      toast.error("Avval joriy savdoni saqlang!", {
        description:
          'Hozirgi mijozning savatida mahsulotlar bor. Uni "Saqlash" tugmasi bilan kutishga qo\'yib, keyin kutayotgan mijozning savdosini bajaring.',
      });
      return;
    }
    setCart(heldCart.cart);
    setHeldCarts((current) =>
      current.filter((item) => item.id !== heldCart.id),
    );
    setIsHeldCartsOpen(false);
    toast.success("Kutilayotgan savat tiklandi");
  };
  // Fetch Clients
  const { data: clients = [] } = useQuery({
    queryKey: ["clients"],
    queryFn: async () => {
      const res = await api.get("/crm/clients");
      return res.data;
    },
  });

  const quickClientMutation = useMutation({
    mutationFn: (client) => api.post("/crm/clients", client),
    onSuccess: (response) => {
      queryClient.invalidateQueries({ queryKey: ["clients"] });
      setSelectedClient(response.data.id);
      setNewClient({ name: "", phone: "" });
      setIsQuickClientOpen(false);
      toast.success("Mijoz qo'shildi va tanlandi");
    },
    onError: (error) =>
      toast.error(error.response?.data?.detail || "Mijozni qo'shib bo'lmadi"),
  });

  // Sale Mutation
  const saleMutation = useMutation({
    mutationFn: (data) => api.post("/sales/", data),
    onSuccess: () => {
      toast.success("Sotuv amalga oshirildi!");
      setCart([]);
      setIsPaymentModalOpen(false);
      setPaymentAmounts({ cash: "", card: "", perevod: "", qarz: "" });
      setBonusSpent(0);
      queryClient.invalidateQueries({ queryKey: ["products"] });
      queryClient.invalidateQueries({ queryKey: ["sales-history"] });
      queryClient.invalidateQueries({ queryKey: ["finance-stats"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard-stats"] });
      queryClient.invalidateQueries({ queryKey: ["active-shift"] });
    },
    onError: (err) => {
      const responseData = err.response?.data;
      let message = "Sotuvni amalga oshirib bo'lmadi";

      if (responseData?.detail) {
        const detail = responseData.detail;
        message =
          typeof detail === "string"
            ? detail
            : Array.isArray(detail)
              ? detail
                  .map((d) => `${d.loc?.join(".") || "error"}: ${d.msg}`)
                  .join(", ")
              : JSON.stringify(detail);
      } else if (err.message) {
        message = err.message;
      }

      toast.error("Xatolik!", { description: message });
    },
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
    if (
      (product.unit === "kg" || product.unit === "litr") &&
      forcedQuantity === null
    ) {
      setSelectedProductForWeight(product);
      setWeightInput("");
      setAmountInput("");
      setIsWeightModalOpen(true);
      return;
    }

    const quantityToAdd = forcedQuantity !== null ? forcedQuantity : 1;

    setCart((prev) => {
      const existing = prev.find((item) => item.product_id === product.id);
      if (existing) {
        /*
                if (existing.quantity + quantityToAdd > product.stock) {
                    toast.warning("Boshqa qoldiq yo'q");
                    return prev;
                }
                */
        return prev.map((item) =>
          item.product_id === product.id
            ? { ...item, quantity: item.quantity + quantityToAdd }
            : item,
        );
      }
      return [
        ...prev,
        {
          product_id: product.id,
          name: product.name,
          price: product.sell_price,
          quantity: quantityToAdd,
          max_stock: product.stock,
          unit: product.unit,
        },
      ];
    });
    setSearchTerm(""); // Clear search after adding
    searchInputRef.current?.focus();
  };

  const handleSearchChange = (event) => {
    setSearchTerm(event.target.value);
  };

  const handleSearchKeyDown = (event) => {
    if (event.key !== "Enter") return;

    const barcode = searchTerm.trim();
    const exactMatch = products.find((product) => product.barcode === barcode);
    if (!exactMatch) return;

    event.preventDefault();
    event.stopPropagation();
    addToCart(exactMatch);
  };
  const updateQuantity = (id, delta) => {
    setCart((prev) =>
      prev.map((item) => {
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
      }),
    );
  };

  const removeFromCart = (id) => {
    setCart((prev) => prev.filter((item) => item.product_id !== id));
  };

  const cartTotal = Math.round(
    cart.reduce((sum, item) => sum + item.price * item.quantity, 0),
  );
  const bonusBalance =
    clients.find((c) => c.id === selectedClient)?.bonus_balance || 0;
  const totalPaid =
    Number(paymentAmounts.cash) +
    Number(paymentAmounts.card) +
    Number(paymentAmounts.perevod) +
    Number(paymentAmounts.qarz) +
    Number(bonusSpent);

  const handlePayment = () => {
    if (!activeShift) {
      toast.info("Savdo qilish uchun avval smena oching");
      return;
    }
    setPaymentAmounts({ cash: "", card: "", perevod: "", qarz: "" });
    setBonusSpent(0);
    setIsPaymentModalOpen(true);
  };

  const handleFillRemaining = (method) => {
    // Exclude the current field we are clicking
    const otherTotal =
      Number(paymentAmounts.cash) +
      Number(paymentAmounts.card) +
      Number(paymentAmounts.perevod) +
      Number(paymentAmounts.qarz) +
      Number(bonusSpent) -
      Number(paymentAmounts[method]);
    const remaining = Math.max(0, cartTotal - otherTotal);

    setPaymentAmounts((prev) => ({
      ...prev,
      [method]: remaining,
    }));
  };

  const submitSale = () => {
    if (Number(paymentAmounts.qarz) > 0 && !selectedClient) {
      toast.error("Iltimos, mijozni tanlang!");
      return;
    }

    // Determine main payment method
    let method = "mixed";
    if (Number(paymentAmounts.cash) >= cartTotal) method = "cash";
    else if (Number(paymentAmounts.card) >= cartTotal) method = "card";
    else if (Number(paymentAmounts.perevod) >= cartTotal) method = "perevod";
    else if (Number(paymentAmounts.qarz) >= cartTotal) method = "qarz";

    const saleData = {
      total_amount: cartTotal,
      payment_method: method,
      client_id: selectedClient,
      items: cart.map((item) => ({
        product_id: item.product_id,
        quantity: item.quantity,
        price: item.price,
      })),
      // Split amounts
      cash_amount: Number(paymentAmounts.cash) || 0,
      card_amount: Number(paymentAmounts.card) || 0,
      transfer_amount: Number(paymentAmounts.perevod) || 0,
      debt_amount: Number(paymentAmounts.qarz) || 0,
      bonus_spent: Number(bonusSpent) || 0,
    };
    saleMutation.mutate(saleData);
  };

  // Filtered Products
  const filteredProducts = products
    .filter((p) => {
      const matchesSearch =
        p.name.toLowerCase().startsWith(searchTerm.toLowerCase()) ||
        p.barcode?.startsWith(searchTerm);
      const matchesCategory = selectedCategory
        ? p.category_id === selectedCategory
        : true;
      return matchesSearch && matchesCategory;
    })
    .sort((a, b) => {
      // Favorites first
      if (a.is_favorite && !b.is_favorite) return -1;
      if (!a.is_favorite && b.is_favorite) return 1;
      // Keyin alifbo bo'yicha (A-Z)
      return a.name.localeCompare(b.name, "uz");
    });

  // Shortcuts
  useHotkeys("f2", () => searchInputRef.current?.focus(), {
    preventDefault: true,
  });
  useHotkeys(
    "enter",
    (event) => {
      if (document.activeElement === searchInputRef.current) return;
      if (isShiftModalOpen) {
        event.preventDefault();
        if (
          shiftBalance.trim() !== "" &&
          !openShiftMutation.isPending &&
          !closeShiftMutation.isPending
        ) {
          handleShiftSubmit();
        }
        return;
      }
      if (isQuickClientOpen || isWeightModalOpen || isUnsoldReturnOpen) return;
      if (cart.length === 0) return;

      event.preventDefault();
      if (!isPaymentModalOpen) {
        handlePayment();
      } else if (totalPaid >= cartTotal && !saleMutation.isPending) {
        submitSale();
      }
    },
    { enableOnFormTags: ["INPUT"] },
  );

  useHotkeys(
    "esc",
    (event) => {
      event.preventDefault();
      if (isQuickClientOpen) {
        setIsQuickClientOpen(false);
      } else if (isWeightModalOpen) {
        setIsWeightModalOpen(false);
      } else if (isUnsoldReturnOpen) {
        setIsUnsoldReturnOpen(false);
      } else if (isPaymentModalOpen) {
        setIsPaymentModalOpen(false);
      } else if (isShiftModalOpen) {
        setIsShiftModalOpen(false);
      }
    },
    { enableOnFormTags: ["INPUT"] },
  );

  return (
    <div
      ref={posContainerRef}
      className={cn(
        "grid h-full w-full gap-3 overflow-hidden p-2 sm:p-3 lg:grid-cols-[minmax(0,1fr)_320px] lg:gap-3 lg:p-3 xl:grid-cols-[minmax(0,1fr)_360px]",
        isFullscreen && "h-screen bg-background p-4",
      )}
    >
      {/* Left Side - Products */}
      <div className="min-h-0 min-w-0 flex flex-col gap-3 overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-2 px-1">
          <div>
            <h1 className="text-xl font-black tracking-tight">Kassa</h1>
            <p className="text-xs text-muted-foreground">
              Qidirish uchun F2, to'lov uchun Enter
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setIsHeldCartsOpen(true)}
            >
              Kutayotgan ({heldCarts.length})
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={!cart.length}
              onClick={holdCurrentCart}
            >
              Saqlash
            </Button>
          </div>
        </div>
        <Card className="flex-1 flex flex-col overflow-hidden rounded-2xl border shadow-md bg-card/80 backdrop-blur">
          <div className="p-4 border-b flex gap-4 items-center">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                ref={searchInputRef}
                placeholder="Mahsulot qidirish (shtrix-kod yoki nom) [F2]"
                className="pl-10 h-12 text-lg"
                value={searchTerm}
                onChange={handleSearchChange}
                onKeyDown={handleSearchKeyDown}
                autoFocus
              />
            </div>
            <Button
              variant="ghost"
              size="icon"
              onClick={toggleFullscreen}
              className="h-10 w-10 rounded-lg sm:h-12 sm:w-12 sm:rounded-xl text-muted-foreground hover:bg-muted"
              title="To'liq ekran"
            >
              {isFullscreen ? (
                <Minimize2 className="h-5 w-5 sm:h-6 sm:w-6" />
              ) : (
                <Maximize2 className="h-5 w-5 sm:h-6 sm:w-6" />
              )}
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
              {categories.map((c) => (
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
            <div className="grid grid-cols-2 gap-3 pb-20 sm:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5">
              {filteredProducts.map((product) => (
                <Card
                  key={product.id}
                  className={cn(
                    "relative flex flex-col justify-between overflow-hidden rounded-xl border bg-card shadow-sm transition-all hover:-translate-y-0.5 hover:shadow-lg active:scale-[0.98]",
                  )}
                  onClick={() => addToCart(product)}
                >
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className={cn(
                      "absolute right-1.5 top-1.5 z-10 h-7 w-7 rounded-full bg-background/80 hover:bg-background",
                      product.is_favorite
                        ? "text-amber-500"
                        : "text-muted-foreground/50",
                    )}
                    title="Saralangan mahsulot"
                    onClick={(event) => {
                      event.stopPropagation();
                      favoriteMutation.mutate(product.id);
                    }}
                  >
                    <Star
                      className={cn(
                        "h-4 w-4",
                        product.is_favorite && "fill-current",
                      )}
                    />
                  </Button>
                  <div className="flex h-20 items-center justify-center bg-gradient-to-br from-primary/10 to-primary/5 p-4">
                    <div className="text-4xl font-bold text-primary/20">
                      {product.name.charAt(0).toUpperCase()}
                    </div>
                  </div>
                  <div className="space-y-2 p-3">
                    <h3 className="font-bold truncate" title={product.name}>
                      {product.name}
                    </h3>
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-black text-primary">
                        {product.sell_price.toLocaleString("de-DE")} so'm
                      </span>
                      <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] font-bold uppercase text-muted-foreground">
                        {product.unit}
                      </span>
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
      <div className="min-h-0 w-full min-w-0 flex flex-col gap-4 lg:w-auto">
        <Card className="flex-1 flex flex-col overflow-hidden rounded-2xl border shadow-xl bg-card">
          <div className="p-4 border-b bg-primary text-primary-foreground flex justify-between items-center">
            <div className="flex items-center gap-2">
              <ShoppingCart className="w-5 h-5" />
              <h2 className="font-bold text-lg">Savatcha</h2>
            </div>
            <div className="flex flex-col items-end">
              <Badge
                variant={activeShift ? "outline" : "destructive"}
                className={cn(
                  "cursor-pointer mb-1",
                  activeShift
                    ? "bg-emerald-500/20 text-white border-emerald-400"
                    : "animate-pulse",
                )}
                onClick={() => setIsShiftModalOpen(true)}
              >
                {activeShift ? "Smena Ochiq" : "Smena Yopiq"}
              </Badge>
            </div>
          </div>

          <ScrollArea className="flex-1 p-4">
            <div className="space-y-3">
              {cart.map((item) => (
                <div
                  key={item.product_id}
                  className="w-full min-w-0 overflow-hidden bg-muted/30 p-2 rounded-lg group animate-in slide-in-from-right-5 fade-in duration-300"
                >
                  <div className="min-w-0 font-medium truncate">
                    {item.name}
                  </div>
                  <div className="mt-1 flex min-w-0 items-center justify-between gap-2">
                    <div className="min-w-0 truncate text-sm text-muted-foreground">
                      {item.price.toLocaleString("de-DE")} x {item.quantity} ={" "}
                      {Math.round(item.price * item.quantity).toLocaleString(
                        "de-DE",
                      )}
                    </div>
                    <div className="flex shrink-0 items-center gap-1 rounded-md border bg-background shadow-sm">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-10 w-10 shrink-0 rounded-none rounded-l-md hover:bg-destructive/10 hover:text-destructive"
                        onClick={() =>
                          item.quantity > 1
                            ? updateQuantity(item.product_id, -1)
                            : removeFromCart(item.product_id)
                        }
                      >
                        {item.quantity === 1 ? (
                          <Trash2 className="w-5 h-5" />
                        ) : (
                          <Minus className="w-4 h-4" />
                        )}
                      </Button>
                      <div className="min-w-[56px] select-none px-1 text-center text-base font-bold">
                        {Math.round(item.price * item.quantity).toLocaleString(
                          "de-DE",
                        )}
                      </div>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-10 w-10 shrink-0 rounded-none rounded-r-md"
                        onClick={() => updateQuantity(item.product_id, 1)}
                      >
                        <Plus className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>
                </div>
              ))}
              {cart.length === 0 && (
                <div className="text-center py-20 text-muted-foreground opacity-50">
                  <ShoppingCart className="w-12 h-12 mx-auto mb-3" />
                  <p>Savatcha bo'sh</p>
                  <p className="text-xs mt-1">
                    Mahsulotlarni qo'shish uchun bosing yoki skanerlang
                  </p>
                </div>
              )}
            </div>
          </ScrollArea>

          <div className="space-y-4 border-t bg-muted/50 p-4">
            <div className="space-y-1">
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Jami Mahsulotlar:</span>
                <span className="font-bold">{cart.length} tur</span>
              </div>
              <div className="mt-2 flex justify-between border-t pt-3 text-2xl font-black">
                <span>Jami:</span>
                <span className="text-primary">
                  {Math.round(cartTotal).toLocaleString("de-DE")} so'm
                </span>
              </div>
            </div>

            <Button
              size="lg"
              className="h-14 w-full text-lg font-black shadow-lg shadow-emerald-500/20"
              disabled={cart.length === 0 || saleMutation.isPending}
              onClick={handlePayment}
              variant="success"
            >
              {saleMutation.isPending ? (
                <Loader2 className="mr-2 animate-spin" />
              ) : (
                <CreditCard className="mr-2" />
              )}
              To'lov Qilish (Enter)
            </Button>
          </div>
        </Card>
      </div>

      {/* Payment Modal */}
      <Dialog open={isPaymentModalOpen} onOpenChange={setIsPaymentModalOpen}>
        <DialogContent className="flex max-h-[calc(100dvh-1rem)] w-[calc(100vw-1rem)] flex-col gap-0 overflow-hidden rounded-xl border-0 p-0 shadow-2xl sm:max-w-[480px] sm:rounded-2xl">
          <DialogTitle className="sr-only">To'lov oynasi</DialogTitle>
          <DialogDescription className="sr-only">
            Savdo uchun to'lov usulini tanlang va summani kiriting.
          </DialogDescription>
          {/* Header */}
          <div className="relative flex-none overflow-hidden bg-slate-900 p-4 text-center text-white sm:p-6">
            <div className="relative z-10">
              <p className="text-slate-400 font-medium mb-1 uppercase tracking-wider text-xs">
                Jami To'lov Summasi
              </p>
              <div className="text-3xl font-bold tracking-tight sm:text-5xl">
                {cartTotal.toLocaleString("de-DE")}
              </div>
              <p className="text-slate-500 text-sm mt-1">so'm</p>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto bg-white p-4 sm:p-6">
            <div className="space-y-4">
              {/* Cash */}
              <div className="flex items-end gap-2 sm:gap-3">
                <div className="h-10 w-10 rounded-lg sm:h-12 sm:w-12 sm:rounded-xl bg-emerald-100 text-emerald-600 flex items-center justify-center shrink-0 border border-emerald-200">
                  <Banknote className="h-5 w-5 sm:h-6 sm:w-6" />
                </div>
                <div className="flex-1 space-y-1">
                  <Label className="text-xs text-muted-foreground font-bold uppercase tracking-wide">
                    Naqd Pul
                  </Label>
                  <Input
                    type="text"
                    inputMode="numeric"
                    placeholder="0"
                    className="h-10 border-slate-200 text-base font-bold sm:text-lg focus-visible:ring-emerald-500"
                    value={formatThousands(paymentAmounts.cash)}
                    onChange={(e) =>
                      setPaymentAmounts((prev) => ({
                        ...prev,
                        cash: parseThousands(e.target.value),
                      }))
                    }
                    onFocus={(e) => e.target.select()}
                    autoFocus
                  />
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  className="h-10 px-3 bg-emerald-50 text-emerald-700 border-emerald-200 hover:bg-emerald-100 hover:text-emerald-800 font-semibold self-end"
                  onClick={() => handleFillRemaining("cash")}
                >
                  Jami
                </Button>
              </div>

              {/* Card */}
              <div className="flex items-end gap-2 sm:gap-3">
                <div className="h-10 w-10 rounded-lg sm:h-12 sm:w-12 sm:rounded-xl bg-blue-100 text-blue-600 flex items-center justify-center shrink-0 border border-blue-200">
                  <CreditCard className="h-5 w-5 sm:h-6 sm:w-6" />
                </div>
                <div className="flex-1 space-y-1">
                  <Label className="text-xs text-muted-foreground font-bold uppercase tracking-wide">
                    Karta (Terminal)
                  </Label>
                  <Input
                    type="text"
                    inputMode="numeric"
                    placeholder="0"
                    className="h-10 border-slate-200 text-base font-bold sm:text-lg focus-visible:ring-blue-500"
                    value={formatThousands(paymentAmounts.card)}
                    onChange={(e) =>
                      setPaymentAmounts((prev) => ({
                        ...prev,
                        card: parseThousands(e.target.value),
                      }))
                    }
                    onFocus={(e) => e.target.select()}
                  />
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  className="h-10 px-3 bg-blue-50 text-blue-700 border-blue-200 hover:bg-blue-100 hover:text-blue-800 font-semibold self-end"
                  onClick={() => handleFillRemaining("card")}
                >
                  Jami
                </Button>
              </div>

              {/* Perevod */}
              <div className="flex items-end gap-2 sm:gap-3">
                <div className="h-10 w-10 rounded-lg sm:h-12 sm:w-12 sm:rounded-xl bg-purple-100 text-purple-600 flex items-center justify-center shrink-0 border border-purple-200">
                  <Smartphone className="h-5 w-5 sm:h-6 sm:w-6" />
                </div>
                <div className="flex-1 space-y-1">
                  <Label className="text-xs text-muted-foreground font-bold uppercase tracking-wide">
                    Perevod
                  </Label>
                  <Input
                    type="text"
                    inputMode="numeric"
                    placeholder="0"
                    className="h-10 border-slate-200 text-base font-bold sm:text-lg focus-visible:ring-purple-500"
                    value={formatThousands(paymentAmounts.perevod)}
                    onChange={(e) =>
                      setPaymentAmounts((prev) => ({
                        ...prev,
                        perevod: parseThousands(e.target.value),
                      }))
                    }
                    onFocus={(e) => e.target.select()}
                  />
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  className="h-10 px-3 bg-purple-50 text-purple-700 border-purple-200 hover:bg-purple-100 hover:text-purple-800 font-semibold self-end"
                  onClick={() => handleFillRemaining("perevod")}
                >
                  Jami
                </Button>
              </div>

              {/* Bonus Selection (New) */}
              {selectedClient && bonusBalance > 0 && (
                <div className="flex items-center gap-3 animate-in fade-in slide-in-from-left-2">
                  <div className="h-10 w-10 rounded-lg sm:h-12 sm:w-12 sm:rounded-xl bg-orange-100 text-orange-600 flex items-center justify-center shrink-0 border border-orange-200">
                    <Star className="w-6 h-6 fill-orange-500" />
                  </div>
                  <div className="flex-1 space-y-1">
                    <Label className="text-xs text-muted-foreground font-bold uppercase tracking-wide">
                      Bonuslatish (Mavjud: {bonusBalance})
                    </Label>
                    <Input
                      type="text"
                      inputMode="numeric"
                      placeholder="0"
                      max={bonusBalance}
                      className="h-10 border-slate-200 text-base font-bold sm:text-lg focus-visible:ring-orange-500"
                      value={formatThousands(bonusSpent)}
                      onFocus={(e) => e.target.select()}
                      onChange={(e) => {
                        const val = Math.min(
                          bonusBalance,
                          parseFloat(parseThousands(e.target.value)) || 0,
                        );
                        setBonusSpent(val);
                      }}
                    />
                  </div>
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-10 px-3 bg-orange-50 text-orange-700 border-orange-200 hover:bg-orange-100 hover:text-orange-800 font-semibold self-end"
                    onClick={() => {
                      const otherTotal =
                        Number(paymentAmounts.cash) +
                        Number(paymentAmounts.card) +
                        Number(paymentAmounts.perevod) +
                        Number(paymentAmounts.qarz);
                      const needed = Math.max(0, cartTotal - otherTotal);
                      setBonusSpent(Math.min(bonusBalance, needed));
                    }}
                  >
                    Jami
                  </Button>
                </div>
              )}

              {/* Debt */}
              <div className="flex items-end gap-2 sm:gap-3">
                <div className="h-10 w-10 rounded-lg sm:h-12 sm:w-12 sm:rounded-xl bg-amber-100 text-amber-600 flex items-center justify-center shrink-0 border border-amber-200">
                  <HandCoins className="h-5 w-5 sm:h-6 sm:w-6" />
                </div>
                <div className="flex-1 space-y-1">
                  <Label className="text-xs text-muted-foreground font-bold uppercase tracking-wide">
                    Nasiya (Qarz)
                  </Label>
                  <Input
                    type="text"
                    inputMode="numeric"
                    placeholder="0"
                    className="h-10 border-slate-200 text-base font-bold sm:text-lg focus-visible:ring-amber-500"
                    value={formatThousands(paymentAmounts.qarz)}
                    onChange={(e) => {
                      const qarz = parseThousands(e.target.value);
                      setPaymentAmounts((prev) => ({ ...prev, qarz }));
                      if (!qarz || Number(qarz) <= 0) {
                        setSelectedClient(null);
                        setBonusSpent(0);
                      }
                    }}
                    onFocus={(e) => e.target.select()}
                  />
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  className="h-10 px-3 bg-amber-50 text-amber-700 border-amber-200 hover:bg-amber-100 hover:text-amber-800 font-semibold self-end"
                  onClick={() => handleFillRemaining("qarz")}
                >
                  Jami
                </Button>
              </div>
            </div>

            {/* Mijoz faqat nasiya savdosida tanlanadi. */}
            {Number(paymentAmounts.qarz) > 0 && (
              <div className="space-y-4">
                <div className="p-4 bg-slate-50 rounded-xl border border-slate-100">
                  <div className="flex justify-between items-center mb-2 gap-2">
                    <Label className="text-sm font-medium text-slate-900">
                      Nasiyaga mijozni tanlang
                    </Label>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      className="h-8 gap-1 shrink-0"
                      onClick={() => setIsQuickClientOpen(true)}
                    >
                      <Plus className="h-4 w-4" /> Qo'shish
                    </Button>
                  </div>
                  {selectedClient ? (
                    <div className="flex h-11 items-center justify-between rounded-md border border-slate-200 bg-white px-3">
                      <span className="text-sm font-medium">
                        {clients.find((c) => c.id === selectedClient)?.name}
                      </span>
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        className="h-7 px-2 text-xs"
                        onClick={() => {
                          setSelectedClient(null);
                          setDebtClientSearch("");
                        }}
                      >
                        O'zgartirish
                      </Button>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      <div className="relative">
                        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                        <Input
                          className="h-11 border-slate-200 bg-white pl-9"
                          placeholder="Mijoz ismi yoki telefon orqali qidirish..."
                          value={debtClientSearch}
                          onChange={(e) => setDebtClientSearch(e.target.value)}
                        />
                      </div>
                      <ScrollArea className="h-[160px] rounded-md border border-slate-200 bg-white">
                        <div className="p-1">
                          {clients
                            .filter(
                              (c) =>
                                c.name
                                  .toLowerCase()
                                  .includes(debtClientSearch.toLowerCase()) ||
                                c.phone?.includes(debtClientSearch),
                            )
                            .map((c) => (
                              <button
                                type="button"
                                key={c.id}
                                onClick={() => {
                                  setSelectedClient(c.id);
                                  setDebtClientSearch("");
                                }}
                                className="flex w-full items-center justify-between rounded-md px-2 py-2 text-left text-sm hover:bg-slate-100"
                              >
                                <span className="font-medium">{c.name}</span>
                                {c.phone && (
                                  <span className="text-xs text-muted-foreground">
                                    {c.phone}
                                  </span>
                                )}
                              </button>
                            ))}
                          {clients.filter(
                            (c) =>
                              c.name
                                .toLowerCase()
                                .includes(debtClientSearch.toLowerCase()) ||
                              c.phone?.includes(debtClientSearch),
                          ).length === 0 && (
                            <p className="py-6 text-center text-sm text-muted-foreground">
                              Mijoz topilmadi
                            </p>
                          )}
                        </div>
                      </ScrollArea>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Summary & Actions */}
            <div className="pt-4 border-t border-slate-100 space-y-4">
              <div className="flex justify-between items-center bg-slate-50 p-4 rounded-xl">
                <div className="flex flex-col">
                  <span className="text-sm font-medium text-slate-500">
                    Kassada to'lanmoqda:
                  </span>
                  <span
                    className={cn(
                      "text-2xl font-bold",
                      totalPaid >= cartTotal
                        ? "text-emerald-600"
                        : "text-slate-800",
                    )}
                  >
                    {totalPaid.toLocaleString("de-DE")}
                  </span>
                </div>
                {totalPaid >= cartTotal ? (
                  <div className="text-right">
                    <span className="text-xs text-slate-500 block uppercase font-bold">
                      Qaytim
                    </span>
                    <span className="text-xl font-bold text-emerald-600">
                      {(totalPaid - cartTotal).toLocaleString("de-DE")}
                    </span>
                  </div>
                ) : (
                  <div className="text-right">
                    <span className="text-xs text-slate-500 block uppercase font-bold">
                      Yana kerak
                    </span>
                    <span className="text-xl font-bold text-rose-500">
                      {(cartTotal - totalPaid).toLocaleString("de-DE")}
                    </span>
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
                      : "bg-slate-200 text-slate-400 cursor-not-allowed shadow-none",
                  )}
                >
                  {saleMutation.isPending && (
                    <Loader2 className="mr-2 animate-spin" />
                  )}
                  {totalPaid >= cartTotal
                    ? "To'lovni Tasdiqlash"
                    : "Summa yetarli emas"}
                </Button>
              </div>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={isQuickClientOpen} onOpenChange={setIsQuickClientOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Yangi mijoz qo'shish</DialogTitle>
            <DialogDescription>
              Nasiyaga rasmiylashtirish uchun mijoz ma'lumotini kiriting.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label htmlFor="quick-client-name">Ismi</Label>
              <Input
                id="quick-client-name"
                value={newClient.name}
                onChange={(event) =>
                  setNewClient((current) => ({
                    ...current,
                    name: event.target.value,
                  }))
                }
                placeholder="Masalan: Ali Valiyev"
                autoFocus
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="quick-client-phone">Telefon (ixtiyoriy)</Label>
              <Input
                id="quick-client-phone"
                type="tel"
                value={newClient.phone}
                onChange={(event) =>
                  setNewClient((current) => ({
                    ...current,
                    phone: event.target.value,
                  }))
                }
                placeholder="998901234567"
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setIsQuickClientOpen(false)}
            >
              Bekor qilish
            </Button>
            <Button
              disabled={quickClientMutation.isPending || !newClient.name.trim()}
              onClick={() =>
                quickClientMutation.mutate({
                  name: newClient.name.trim(),
                  phone: newClient.phone.trim() || null,
                })
              }
            >
              {quickClientMutation.isPending && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              Mijozni qo'shish
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={isHeldCartsOpen} onOpenChange={setIsHeldCartsOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Kutilayotgan savatlar</DialogTitle>
            <DialogDescription>
              Saqlangan savatni tanlab, savdoni davom ettiring.
            </DialogDescription>
          </DialogHeader>
          <div className="max-h-80 space-y-2 overflow-y-auto">
            {heldCarts.length === 0 ? (
              <p className="py-6 text-center text-sm text-muted-foreground">
                Saqlangan savat yo'q
              </p>
            ) : (
              heldCarts.map((heldCart, index) => (
                <div
                  key={heldCart.id}
                  className="flex items-center justify-between gap-3 rounded-lg border p-3"
                >
                  <div className="min-w-0">
                    <p className="font-semibold">Savatcha #{index + 1}</p>
                    <p className="text-xs text-muted-foreground">
                      {heldCart.cart.length} tur mahsulot
                    </p>
                    <p className="truncate text-[11px] text-muted-foreground/80">
                      {heldCart.cart.map((item) => item.name).join(", ")}
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <Button size="sm" onClick={() => restoreHeldCart(heldCart)}>
                      Davom ettirish
                    </Button>
                    <Button
                      size="icon"
                      variant="ghost"
                      onClick={() =>
                        setHeldCarts((current) =>
                          current.filter((item) => item.id !== heldCart.id),
                        )
                      }
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ))
            )}
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={isWeightModalOpen} onOpenChange={setIsWeightModalOpen}>
        <DialogContent className="sm:max-w-[420px] p-0 overflow-hidden border-none shadow-2xl">
          <DialogHeader className="p-4 bg-primary text-primary-foreground">
            <DialogTitle className="text-xl font-black flex items-center justify-between uppercase tracking-tighter">
              {selectedProductForWeight?.name}
              <Badge
                variant="outline"
                className="text-sm py-0.5 px-2 border-primary-foreground/30 text-primary-foreground font-mono"
              >
                {selectedProductForWeight?.sell_price.toLocaleString("de-DE")} s
                / {selectedProductForWeight?.unit}
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
                  type="text"
                  inputMode="numeric"
                  value={formatThousands(amountInput)}
                  onFocus={(e) => e.target.select()}
                  onChange={(e) => {
                    const val = parseThousands(e.target.value);
                    setAmountInput(val);
                    if (val && selectedProductForWeight) {
                      const calcWeight = (
                        parseFloat(val) / selectedProductForWeight.sell_price
                      ).toFixed(5);
                      setWeightInput(calcWeight);
                    } else {
                      setWeightInput("");
                    }
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && weightInput > 0) {
                      addToCart(
                        selectedProductForWeight,
                        parseFloat(weightInput),
                      );
                      setIsWeightModalOpen(false);
                    }
                  }}
                  placeholder="0"
                  className="text-[60px] h-24 font-bold border-2 border-primary/10 focus:border-primary shadow-inner text-center bg-muted/10 rounded-2xl transition-all leading-none p-0"
                  autoFocus
                  style={{ fontSize: "60px" }}
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

      <Dialog open={isUnsoldReturnOpen} onOpenChange={setIsUnsoldReturnOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Mahsulotni omborga qaytarish</DialogTitle>
            <DialogDescription>
              Savdo chekisiz qaytgan mahsulotni qoldiqqa qo'shadi. Sabab audit
              jurnaliga yoziladi.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-2">
            <div className="grid gap-2">
              <Label>Mahsulot</Label>
              <Select
                value={unsoldReturn.product_id}
                onValueChange={(value) =>
                  setUnsoldReturn({ ...unsoldReturn, product_id: value })
                }
              >
                <SelectTrigger>
                  <SelectValue placeholder="Mahsulotni tanlang" />
                </SelectTrigger>
                <SelectContent>
                  {products.map((product) => (
                    <SelectItem key={product.id} value={String(product.id)}>
                      {product.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label>Miqdor</Label>
              <Input
                type="number"
                min="0.001"
                value={unsoldReturn.quantity}
                onChange={(event) =>
                  setUnsoldReturn({
                    ...unsoldReturn,
                    quantity: event.target.value,
                  })
                }
                placeholder="1"
              />
            </div>
            <div className="grid gap-2">
              <Label>Sabab</Label>
              <Input
                value={unsoldReturn.reason}
                onChange={(event) =>
                  setUnsoldReturn({
                    ...unsoldReturn,
                    reason: event.target.value,
                  })
                }
                placeholder="Masalan: xaridor olib kelib qaytardi"
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setIsUnsoldReturnOpen(false)}
            >
              Bekor qilish
            </Button>
            <Button
              onClick={submitUnsoldReturn}
              disabled={unsoldReturnMutation.isPending}
            >
              Omborga qo'shish
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      {/* Shift Modal */}
      <Dialog open={isShiftModalOpen} onOpenChange={setIsShiftModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {activeShift ? "Smenani Yopish" : "Yangi Smena Ochish"}
            </DialogTitle>
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
                  <span className="font-bold">
                    {activeShift.opening_balance?.toLocaleString("de-DE")} so'm
                  </span>
                </div>
                <div className="flex justify-between text-sm text-emerald-600">
                  <span>Naqd savdo:</span>
                  <span className="font-bold">
                    +{activeShift.total_cash?.toLocaleString("de-DE") || 0} so'm
                  </span>
                </div>
                <div className="flex justify-between text-sm text-blue-600">
                  <span>Karta (terminal):</span>
                  <span className="font-bold">
                    {activeShift.total_card?.toLocaleString("de-DE") || 0} so'm
                  </span>
                </div>
                <div className="flex justify-between text-sm text-violet-600">
                  <span>Perevod:</span>
                  <span className="font-bold">
                    {activeShift.total_transfer?.toLocaleString("de-DE") || 0}{" "}
                    so'm
                  </span>
                </div>
                <div className="flex justify-between text-sm text-amber-600">
                  <span>Nasiya (qarz):</span>
                  <span className="font-bold">
                    {activeShift.total_debt?.toLocaleString("de-DE") || 0} so'm
                  </span>
                </div>
                <div className="mt-3 rounded-md border bg-background/70 px-3 py-2 text-xs text-muted-foreground">
                  Bugun:{" "}
                  <span className="font-bold text-foreground">
                    {dailySummary?.sales_count || 0} savdo
                  </span>
                  <span className="ml-2">
                    N:{" "}
                    {(dailySummary?.cash_amount || 0).toLocaleString("de-DE")}
                  </span>
                  <span className="ml-2">
                    T:{" "}
                    {(dailySummary?.card_amount || 0).toLocaleString("de-DE")}
                  </span>
                  <span className="ml-2">
                    P:{" "}
                    {(dailySummary?.transfer_amount || 0).toLocaleString(
                      "de-DE",
                    )}
                  </span>
                  <span className="ml-2">
                    Q:{" "}
                    {(dailySummary?.debt_amount || 0).toLocaleString("de-DE")}
                  </span>
                </div>
                <div className="border-t pt-2 flex justify-between font-bold text-lg">
                  <span>Kassada bo'lishi kerak:</span>
                  <span>
                    {(
                      activeShift.opening_balance +
                      (activeShift.total_cash || 0)
                    ).toLocaleString("de-DE")}{" "}
                    so'm
                  </span>
                </div>
              </div>
            )}
            <div className="space-y-2">
              <Label>
                {activeShift
                  ? "Haqiqiy naqd pul (Kassadagi)"
                  : "Boshlang'ich balans"}
              </Label>
              <Input
                type="text"
                inputMode="numeric"
                value={formatCashAmount(shiftBalance)}
                onChange={(e) =>
                  setShiftBalance(e.target.value.replace(/\D/g, ""))
                }
                placeholder="0"
                autoFocus
              />
            </div>{" "}
            {activeShift &&
              shiftBalance !== "" &&
              Math.abs(
                Number(shiftBalance) -
                  (activeShift.opening_balance + (activeShift.total_cash || 0)),
              ) > 0.01 && (
                <div className="space-y-2 rounded-lg border border-amber-300 bg-amber-50 p-3 dark:border-amber-900 dark:bg-amber-950/30">
                  <Label htmlFor="shift-note">Farq sababi</Label>
                  <Input
                    id="shift-note"
                    value={shiftNote}
                    onChange={(e) => setShiftNote(e.target.value)}
                    placeholder="Masalan: mayda xarajat yoki sanashdagi farq"
                  />
                </div>
              )}
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setIsShiftModalOpen(false)}
            >
              Bekor qilish
            </Button>
            <Button
              onClick={handleShiftSubmit}
              disabled={
                openShiftMutation.isPending ||
                closeShiftMutation.isPending ||
                shiftBalance.trim() === ""
              }
            >
              {(openShiftMutation.isPending ||
                closeShiftMutation.isPending) && (
                <Loader2 className="mr-2 animate-spin h-4 w-4" />
              )}
              {activeShift ? "Smenani Yakunlash" : "Smenani Boshlash"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default POS;
