import React, { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import api from '../api/axios';
import {
  Search,
  Plus,
  Minus,
  Trash2,
  CheckCircle,
  ShoppingCart,
  User,
  CreditCard,
  Coins,
  History
} from 'lucide-react';
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from "@/components/ui/select";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

const POS = () => {
  const [searchTerm, setSearchTerm] = useState('');
  const [cart, setCart] = useState([]);
  const [paymentMethod, setPaymentMethod] = useState('cash');
  const [clientId, setClientId] = useState(null);

  const { data: products = [], isLoading: productsLoading } = useQuery({
    queryKey: ['products', searchTerm],
    queryFn: async () => {
      const res = await api.get('/inventory/products', { params: { query: searchTerm } });
      return res.data;
    },
    enabled: searchTerm.length > 0
  });

  const { data: clients = [] } = useQuery({
    queryKey: ['clients'],
    queryFn: async () => {
      const res = await api.get('/crm/clients');
      return res.data;
    }
  });

  const addToCart = (product) => {
    if (product.stock <= 0) {
      toast.error("Xatolik!", { description: "Mahsulot qolmagan." });
      return;
    }
    const existing = cart.find(item => item.product_id === product.id);
    if (existing) {
      setCart(cart.map(item =>
        item.product_id === product.id ? { ...item, quantity: item.quantity + 1 } : item
      ));
    } else {
      setCart([...cart, {
        product_id: product.id,
        name: product.name,
        price: product.sell_price,
        quantity: 1
      }]);
    }
  };

  const updateQuantity = (id, delta) => {
    setCart(cart.map(item => {
      if (item.product_id === id) {
        const newQty = Math.max(1, item.quantity + delta);
        return { ...item, quantity: newQty };
      }
      return item;
    }));
  };

  const removeFromCart = (id) => {
    setCart(cart.filter(item => item.product_id !== id));
  };

  const total = cart.reduce((sum, item) => sum + (item.price * item.quantity), 0);

  const saleMutation = useMutation({
    mutationFn: (saleData) => api.post('/pos/sales', saleData),
    onSuccess: () => {
      toast.success("Sotuv yakunlandi!", {
        description: `${total.toLocaleString()} so'm miqdorida xarid amalga oshirildi.`
      });
      setCart([]);
      setClientId(null);
    },
    onError: (error) => {
      toast.error("Xatolik!", {
        description: error.response?.data?.detail || "Sotuvni yakunlab bo'lmadi."
      });
    }
  });

  const handleCheckout = () => {
    if (cart.length === 0) return;
    saleMutation.mutate({
      total_amount: total,
      payment_method: paymentMethod,
      client_id: clientId ? parseInt(clientId) : null,
      items: cart.map(item => ({
        product_id: item.product_id,
        quantity: item.quantity,
        price: item.price
      }))
    });
  };

  return (
    <div className="flex gap-8 h-full min-h-[500px] overflow-hidden">
      <div className="flex-1 flex flex-col min-w-0">
        <div className="mb-6">
          <div className="relative">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
            <Input
              placeholder="Qidiruv..."
              className="pl-12 h-12 text-lg bg-white border-none ring-1 ring-slate-200"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
        </div>

        <div className="flex-1 overflow-y-auto pr-2">
          {productsLoading ? (
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4 animate-pulse">
              {[1, 2, 3, 4, 5, 6, 7, 8].map(i => <div key={i} className="h-40 bg-slate-100 rounded-xl" />)}
            </div>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
              {products.map(product => (
                <Card
                  key={product.id}
                  className={cn(
                    "group cursor-pointer hover:ring-2 hover:ring-primary transition-all duration-200 border-none shadow-sm overflow-hidden",
                    product.stock <= 0 && "opacity-60 cursor-not-allowed"
                  )}
                  onClick={() => addToCart(product)}
                >
                  <CardHeader className="p-4 pb-2 text-sm font-semibold truncate group-hover:text-primary transition-colors">
                    {product.name}
                  </CardHeader>
                  <CardContent className="p-4 pt-0">
                    <div className="text-lg font-bold text-slate-900 mb-2">
                      {product.sell_price.toLocaleString()} so'm
                    </div>
                    <div className="flex items-center justify-between">
                      <Badge variant={product.stock < 5 ? "destructive" : "secondary"} className="text-[10px] px-2 py-0">
                        {product.stock} {product.unit}
                      </Badge>
                      <Button size="icon" className="w-8 h-8 rounded-full opacity-0 group-hover:opacity-100 transition-opacity">
                        <Plus className="w-4 h-4" />
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="w-[400px] flex flex-col shrink-0">
        <Card className="flex-1 flex flex-col border-none shadow-xl bg-white overflow-hidden">
          <CardHeader className="bg-slate-900 text-white p-6 rounded-none">
            <div className="flex items-center justify-between">
              <CardTitle className="flex items-center gap-3 text-lg font-bold">
                <ShoppingCart className="w-5 h-5" /> Savatcha
              </CardTitle>
              <Badge variant="outline" className="text-white border-white/20">
                {cart.length} ta xarid
              </Badge>
            </div>
          </CardHeader>

          <CardContent className="flex-1 overflow-y-auto p-0">
            {cart.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-muted-foreground p-8 opacity-50">
                <ShoppingCart className="w-16 h-16 mb-4" />
                <p className="text-center font-medium">Sotuv boshlash uchun mahsulot tanlang</p>
              </div>
            ) : (
              <div className="divide-y">
                {cart.map(item => (
                  <div key={item.product_id} className="p-4 hover:bg-slate-50 transition-colors">
                    <div className="flex justify-between items-start mb-3">
                      <div>
                        <h4 className="font-semibold text-slate-900 text-sm">{item.name}</h4>
                        <p className="text-xs text-muted-foreground">{item.price.toLocaleString()} so'm</p>
                      </div>
                      <button
                        onClick={() => removeFromCart(item.product_id)}
                        className="text-slate-300 hover:text-destructive transition-colors px-2"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-1 bg-slate-100 rounded-lg p-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          className="w-7 h-7"
                          onClick={() => updateQuantity(item.product_id, -1)}
                        >
                          <Minus className="w-3 h-3" />
                        </Button>
                        <span className="w-8 text-center font-bold text-sm">{item.quantity}</span>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="w-7 h-7"
                          onClick={() => updateQuantity(item.product_id, 1)}
                        >
                          <Plus className="w-3 h-3" />
                        </Button>
                      </div>
                      <div className="font-bold text-slate-900">
                        {(item.price * item.quantity).toLocaleString()} so'm
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>

          <CardFooter className="flex flex-col p-6 bg-slate-50 border-t gap-6">
            <div className="w-full space-y-4">
              <div className="space-y-1.5">
                <label className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
                  <User className="w-3 h-3" /> Mijoz
                </label>
                <Select value={clientId || "default"} onValueChange={(v) => setClientId(v === "default" ? null : v)}>
                  <SelectTrigger className="bg-white border-slate-200 h-10">
                    <SelectValue placeholder="Umumiy xaridor" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="default">Umumiy xaridor</SelectItem>
                    {clients.map(c => (
                      <SelectItem key={c.id} value={c.id.toString()}>{c.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-1.5">
                <label className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
                  <CreditCard className="w-3 h-3" /> To'lov Turi
                </label>
                <div className="grid grid-cols-3 gap-2">
                  {[
                    { id: 'cash', label: 'Naqd', icon: Coins },
                    { id: 'card', label: 'Karta', icon: CreditCard },
                    { id: 'debt', label: 'Nasiya', icon: History }
                  ].map(method => {
                    const Icon = method.icon;
                    return (
                      <Button
                        key={method.id}
                        variant={paymentMethod === method.id ? "default" : "outline"}
                        className={cn(
                          "h-10 px-0 flex flex-col gap-0 items-center justify-center text-[10px] font-bold uppercase",
                          paymentMethod === method.id ? "bg-primary shadow-md" : "bg-white border-slate-200"
                        )}
                        onClick={() => setPaymentMethod(method.id)}
                      >
                        <Icon className="w-3 h-3 mb-0.5" />
                        {method.label}
                      </Button>
                    );
                  })}
                </div>
              </div>
            </div>

            <div className="w-full space-y-4 pt-2 border-t border-slate-200">
              <div className="flex items-baseline justify-between">
                <span className="text-sm font-semibold text-muted-foreground">Jami:</span>
                <span className="text-3xl font-black tracking-tight text-slate-900">
                  {total.toLocaleString()} <span className="text-xs font-bold uppercase text-muted-foreground">so'm</span>
                </span>
              </div>

              <Button
                className="w-full h-14 text-base font-bold uppercase tracking-widest gap-3 shadow-lg"
                disabled={cart.length === 0 || saleMutation.isPending}
                onClick={handleCheckout}
              >
                <CheckCircle className="w-5 h-5" /> Sotuvni Yakunlash
              </Button>
            </div>
          </CardFooter>
        </Card>
      </div>
    </div>
  );
};

export default POS;
