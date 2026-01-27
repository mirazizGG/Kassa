import React, { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import api from '../api/axios';
import { Search, Plus, Minus, X, Loader2 } from 'lucide-react';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";

const POS = () => {
  const [searchTerm, setSearchTerm] = useState('');
  const [cart, setCart] = useState([]);
  const [paymentMethod, setPaymentMethod] = useState('cash');

  const { data: products = [], isLoading: productsLoading } = useQuery({
    queryKey: ['products', searchTerm],
    queryFn: async () => {
      const res = await api.get('/inventory/products', {
        params: searchTerm ? { query: searchTerm } : {}
      });
      return res.data;
    }
  });

  const addToCart = (product) => {
    if (product.stock <= 0) {
      toast.error("Mahsulot qolmagan!");
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

  const clearCart = () => {
    setCart([]);
  };

  const total = cart.reduce((sum, item) => sum + (item.price * item.quantity), 0);

  const saleMutation = useMutation({
    mutationFn: (saleData) => api.post('/pos/sales', saleData),
    onSuccess: () => {
      toast.success("Sotuv yakunlandi!", {
        description: `${total.toLocaleString()} so'm`
      });
      setCart([]);
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
      client_id: null,
      items: cart.map(item => ({
        product_id: item.product_id,
        quantity: item.quantity,
        price: item.price
      }))
    });
  };

  const filteredProducts = searchTerm
    ? products.filter(p =>
        p.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        p.barcode?.includes(searchTerm)
      )
    : products;

  return (
    <div className="flex h-[calc(100vh-5rem)] gap-4">
      {/* Products Section - Left Side */}
      <div className="flex-1 flex flex-col">
        {/* Search Bar */}
        <div className="mb-4">
          <div className="relative">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
            <Input
              placeholder="Mahsulot qidirish..."
              className="pl-12 h-14 text-lg"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              autoFocus
            />
          </div>
        </div>

        {/* Products Grid */}
        <div className="flex-1 overflow-y-auto">
          {productsLoading ? (
            <div className="grid grid-cols-3 gap-3">
              {[1, 2, 3, 4, 5, 6].map(i => (
                <div key={i} className="h-32 bg-muted animate-pulse rounded-lg" />
              ))}
            </div>
          ) : filteredProducts.length === 0 ? (
            <div className="flex items-center justify-center h-full text-muted-foreground">
              <div className="text-center">
                <p className="text-lg font-medium">Mahsulot topilmadi</p>
                <p className="text-sm">Boshqa nom bilan qidiring</p>
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-3 gap-3 pb-4">
              {filteredProducts.map(product => (
                <button
                  key={product.id}
                  onClick={() => addToCart(product)}
                  disabled={product.stock <= 0}
                  className="bg-card hover:bg-accent border-2 border-transparent hover:border-primary rounded-lg p-4 text-left transition-all disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:border-transparent h-32 flex flex-col justify-between"
                >
                  <div>
                    <h3 className="font-bold text-base mb-1 line-clamp-2">{product.name}</h3>
                    <p className="text-2xl font-black text-primary">
                      {product.sell_price.toLocaleString()}
                    </p>
                  </div>
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-muted-foreground">
                      {product.stock} {product.unit}
                    </span>
                    <Plus className="w-5 h-5 text-primary" />
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Cart Section - Right Side */}
      <div className="w-[420px] bg-card border rounded-lg flex flex-col">
        {/* Cart Header */}
        <div className="p-4 border-b">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-bold">Savatcha</h2>
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">{cart.length} ta</span>
              {cart.length > 0 && (
                <Button variant="ghost" size="sm" onClick={clearCart}>
                  Tozalash
                </Button>
              )}
            </div>
          </div>
        </div>

        {/* Cart Items */}
        <div className="flex-1 overflow-y-auto p-4 space-y-2">
          {cart.length === 0 ? (
            <div className="flex items-center justify-center h-full text-center text-muted-foreground">
              <div>
                <p className="text-lg font-medium mb-1">Savat bo'sh</p>
                <p className="text-sm">Mahsulot tanlang</p>
              </div>
            </div>
          ) : (
            cart.map(item => (
              <div key={item.product_id} className="bg-muted/50 rounded-lg p-3">
                <div className="flex items-start justify-between mb-2">
                  <div className="flex-1 pr-2">
                    <h4 className="font-semibold text-sm line-clamp-1">{item.name}</h4>
                    <p className="text-xs text-muted-foreground">
                      {item.price.toLocaleString()} so'm
                    </p>
                  </div>
                  <button
                    onClick={() => removeFromCart(item.product_id)}
                    className="text-muted-foreground hover:text-destructive p-1"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 bg-background rounded-md">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => updateQuantity(item.product_id, -1)}
                      className="h-8 w-8 p-0"
                    >
                      <Minus className="w-4 h-4" />
                    </Button>
                    <span className="font-bold min-w-[2rem] text-center">
                      {item.quantity}
                    </span>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => updateQuantity(item.product_id, 1)}
                      className="h-8 w-8 p-0"
                    >
                      <Plus className="w-4 h-4" />
                    </Button>
                  </div>
                  <span className="font-bold text-lg">
                    {(item.price * item.quantity).toLocaleString()}
                  </span>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Cart Footer - Payment & Checkout */}
        <div className="border-t p-4 space-y-4">
          {/* Payment Method */}
          <div>
            <label className="text-xs font-semibold text-muted-foreground uppercase mb-2 block">
              To'lov turi
            </label>
            <div className="grid grid-cols-3 gap-2">
              <Button
                variant={paymentMethod === 'cash' ? "default" : "outline"}
                onClick={() => setPaymentMethod('cash')}
                className="h-12 font-semibold"
              >
                Naqd
              </Button>
              <Button
                variant={paymentMethod === 'card' ? "default" : "outline"}
                onClick={() => setPaymentMethod('card')}
                className="h-12 font-semibold"
              >
                Karta
              </Button>
              <Button
                variant={paymentMethod === 'debt' ? "default" : "outline"}
                onClick={() => setPaymentMethod('debt')}
                className="h-12 font-semibold"
              >
                Nasiya
              </Button>
            </div>
          </div>

          {/* Total */}
          <div className="bg-primary/10 rounded-lg p-4">
            <div className="flex items-baseline justify-between">
              <span className="text-sm font-semibold text-muted-foreground">JAMI:</span>
              <div className="text-right">
                <span className="text-3xl font-black text-primary">
                  {total.toLocaleString()}
                </span>
                <span className="text-sm font-bold text-muted-foreground ml-1">so'm</span>
              </div>
            </div>
          </div>

          {/* Checkout Button */}
          <Button
            onClick={handleCheckout}
            disabled={cart.length === 0 || saleMutation.isPending}
            className="w-full h-14 text-lg font-bold"
            size="lg"
          >
            {saleMutation.isPending ? (
              <>
                <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                Yuklanmoqda...
              </>
            ) : (
              "Sotuvni Yakunlash"
            )}
          </Button>
        </div>
      </div>
    </div>
  );
};

export default POS;
