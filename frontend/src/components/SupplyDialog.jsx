import { useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { Loader2, ScanBarcode, X } from "lucide-react";
import api from "../api/axios";
import { queryClient } from "../api/queryClient";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  cn,
  formatThousands,
  parseThousands,
  productBarcodes,
} from "@/lib/utils.js";

const priceString = (n) => (n ? String(Math.round(n)) : "");

const formatQty = (n) =>
  Number(n || 0).toLocaleString("de-DE", { maximumFractionDigits: 3 });

/**
 * Omborga kirim: mavjud mahsulotga yangi kelgan tovarni QO'SHISH.
 *
 * Ilgari buning uchun mahsulotni tahrirlab, umumiy qoldiqni qo'lda hisoblab
 * yozish kerak edi (5 ta bor + 20 ta keldi = 25). Bu kirim tarixiga
 * tushmasdi va yangi kelish narxi saqlanmasdi. Bu oyna POST
 * /inventory/supplies ni chaqiradi: server sonni qoldiqqa atomik qo'shadi,
 * narxni yangilaydi va kirim tarixiga yozadi.
 *
 * Skaner: shtrix-kod (qo'shimcha kodlar ham) skanerlanganda mahsulot o'zi
 * tanlanadi va kursor "Kelgan soni" ga o'tadi. Saqlangandan keyin oyna
 * yopilmaydi — keyingi tovarni darhol skanerlash mumkin.
 */
const SupplyDialog = ({ open, onOpenChange, products, initialProduct }) => {
  // Holat har ochilishda noldan boshlanadi: ota komponent `key` ni
  // almashtirib, oynani qayta yaratadi.
  const [scan, setScan] = useState("");
  const [productId, setProductId] = useState(initialProduct?.id ?? null);
  const [quantity, setQuantity] = useState("");
  const [buyPrice, setBuyPrice] = useState(priceString(initialProduct?.buy_price));
  const [sellPrice, setSellPrice] = useState(
    priceString(initialProduct?.sell_price),
  );

  // Mahsulotni ro'yxatdan olamiz: saqlangandan keyin qoldiq yangilanib ko'rinadi.
  const product = products.find((p) => p.id === productId) ?? null;

  const selectProduct = (p) => {
    setProductId(p.id);
    setBuyPrice(priceString(p.buy_price));
    setSellPrice(priceString(p.sell_price));
    setQuantity("");
    setScan("");
  };

  const resetToScan = () => {
    setProductId(null);
    setQuantity("");
    setBuyPrice("");
    setSellPrice("");
    setScan("");
  };

  const matches = useMemo(() => {
    const needle = scan.trim().toLowerCase();
    if (!needle) return [];
    return products
      .filter(
        (p) =>
          p.name.toLowerCase().includes(needle) ||
          productBarcodes(p).some((code) => code.startsWith(needle)),
      )
      .slice(0, 8);
  }, [scan, products]);

  const handleScanEnter = () => {
    const code = scan.trim();
    if (!code) return;
    const exact = products.find((p) => productBarcodes(p).includes(code));
    if (exact) {
      selectProduct(exact);
    } else if (matches.length === 1) {
      selectProduct(matches[0]);
    } else if (matches.length === 0) {
      toast.error(
        `"${code}" topilmadi. Yangi mahsulot bo'lsa, "Qo'shish" orqali yarating.`,
      );
      setScan("");
    }
  };

  const supplyMutation = useMutation({
    mutationFn: (payload) => api.post("/inventory/supplies", payload),
    onSuccess: () => {
      toast.success(`${product?.name}: +${formatQty(quantity)} kirim qilindi`);
      queryClient.invalidateQueries({ queryKey: ["products"] });
      queryClient.invalidateQueries({ queryKey: ["supplies"] });
      queryClient.invalidateQueries({ queryKey: ["stock-logs"] });
      queryClient.invalidateQueries({ queryKey: ["purchase-list"] });
      resetToScan();
    },
    onError: (err) => {
      toast.error(err.response?.data?.detail || "Kirimni saqlab bo'lmadi");
    },
  });

  const qty = Number(quantity);
  const price = Number(buyPrice);
  const sell = Number(sellPrice);
  const sellChanged = product && sell > 0 && sell !== product.sell_price;

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!product) return;
    if (!qty || qty <= 0) {
      toast.error("Kelgan sonini kiriting");
      return;
    }
    if (Number.isNaN(price) || price < 0) {
      toast.error("Kelish narxini kiriting");
      return;
    }
    if (!sell || sell <= 0) {
      toast.error("Sotish narxini kiriting");
      return;
    }
    supplyMutation.mutate({
      product_id: product.id,
      quantity: qty,
      buy_price: price,
      // Faqat o'zgargan bo'lsa yuboramiz.
      ...(sellChanged ? { sell_price: sell } : {}),
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[480px]">
        <DialogHeader>
          <DialogTitle>Kirim qilish</DialogTitle>
          <DialogDescription>
            Shtrix-kodni skanerlang yoki mahsulot nomini yozing.
          </DialogDescription>
        </DialogHeader>

        {!product ? (
          <div className="space-y-2 py-2">
            <div className="relative">
              <ScanBarcode className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                autoFocus
                className="pl-9"
                placeholder="Shtrix-kod yoki nom..."
                value={scan}
                onChange={(e) => setScan(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    handleScanEnter();
                  }
                }}
              />
            </div>
            {matches.length > 0 && (
              <div className="max-h-64 overflow-auto rounded-md border">
                {matches.map((p) => (
                  <button
                    key={p.id}
                    type="button"
                    className="flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-muted"
                    onClick={() => selectProduct(p)}
                  >
                    <span className="font-medium">{p.name}</span>
                    <span className="text-xs text-muted-foreground">
                      {p.is_infinite ? "∞" : `${formatQty(p.stock)} ${p.unit}`}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4 py-2">
            <div className="flex items-start justify-between gap-2 rounded-md border bg-muted/30 p-3">
              <div>
                <div className="font-semibold">{product.name}</div>
                <div className="text-xs text-muted-foreground font-mono">
                  {productBarcodes(product).join(", ") || "-"}
                </div>
              </div>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                title="Boshqa mahsulot tanlash"
                onClick={resetToScan}
              >
                <X className="h-4 w-4" />
              </Button>
            </div>

            {product.is_infinite && (
              <p className="text-sm text-amber-600">
                Bu mahsulot cheksiz qoldiqli — sotuvda kamaymaydi, kirim
                faqat tarix va narx uchun yoziladi.
              </p>
            )}

            <div className="grid grid-cols-3 items-center gap-3">
              <Label className="text-right">Hozirgi qoldiq</Label>
              <div className="col-span-2 font-medium">
                {product.is_infinite
                  ? "∞"
                  : `${formatQty(product.stock)} ${product.unit}`}
              </div>
            </div>
            <div className="grid grid-cols-3 items-center gap-3">
              <Label htmlFor="supply_qty" className="text-right">
                Kelgan soni
              </Label>
              <Input
                id="supply_qty"
                autoFocus
                type="number"
                min="0"
                step="0.001"
                className="col-span-2"
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
                required
              />
            </div>
            <div className="grid grid-cols-3 items-center gap-3">
              <Label htmlFor="supply_price" className="text-right">
                Kelish narxi
              </Label>
              <Input
                id="supply_price"
                type="text"
                inputMode="numeric"
                className="col-span-2"
                value={formatThousands(buyPrice)}
                onChange={(e) => setBuyPrice(parseThousands(e.target.value))}
                onFocus={(e) => e.target.select()}
                required
              />
            </div>
            <div className="grid grid-cols-3 items-center gap-3">
              <Label htmlFor="supply_sell" className="text-right">
                Sotish narxi
              </Label>
              <div className="col-span-2">
                <Input
                  id="supply_sell"
                  type="text"
                  inputMode="numeric"
                  value={formatThousands(sellPrice)}
                  onChange={(e) => setSellPrice(parseThousands(e.target.value))}
                  onFocus={(e) => e.target.select()}
                  required
                />
                {sellChanged && (
                  <p className="mt-1 text-xs text-muted-foreground">
                    Eski narx: {formatThousands(Math.round(product.sell_price))}
                  </p>
                )}
                {sell > 0 && price > sell && (
                  <p className="mt-1 text-xs text-amber-600">
                    Sotish narxi kelish narxidan past — zarariga sotiladi
                  </p>
                )}
              </div>
            </div>
            {!product.is_infinite && (
              <div className="grid grid-cols-3 items-center gap-3">
                <Label className="text-right">Yangi qoldiq</Label>
                <div
                  className={cn(
                    "col-span-2 text-lg font-bold",
                    qty > 0 && "text-emerald-600",
                  )}
                >
                  {formatQty(product.stock + (qty > 0 ? qty : 0))}{" "}
                  {product.unit}
                </div>
              </div>
            )}

            <DialogFooter>
              <Button type="button" variant="outline" onClick={resetToScan}>
                Bekor
              </Button>
              <Button type="submit" disabled={supplyMutation.isPending}>
                {supplyMutation.isPending && (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                )}
                Saqlash
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
};

export default SupplyDialog;
