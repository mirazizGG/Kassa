import React, { useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import api from "../api/axios";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogFooter,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

/**
 * Kichik suzuvchi "Dasturni yangilash" tugmasi. Barcha xodimlarga ko'rinadi,
 * lekin faqat server `.env` da ALLOW_SELF_UPDATE=true bo'lsagina.
 * Bosilганда serverda update.ps1 ishga tushadi; UpdateOverlay "kuting" oynasini ko'rsatadi.
 */
export default function UpdateButton({ isCashier = false }) {
  const [enabled, setEnabled] = useState(false);
  const [available, setAvailable] = useState(false);
  const [behind, setBehind] = useState(0);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [starting, setStarting] = useState(false);

  useEffect(() => {
    let stop = false;
    const check = async () => {
      try {
        const { data } = await api.get("/system/update-check");
        if (stop) return;
        setEnabled(Boolean(data.enabled));
        setAvailable(Boolean(data.update_available));
        setBehind(data.behind_count || 0);
      } catch {
        /* jim */
      }
    };
    check();
    const t = setInterval(check, 5 * 60 * 1000);
    return () => {
      stop = true;
      clearInterval(t);
    };
  }, []);

  const startUpdate = async () => {
    setStarting(true);
    try {
      await api.post("/system/update");
      setConfirmOpen(false);
      window.dispatchEvent(new Event("smartkassa:update-started"));
    } catch (err) {
      const msg = err.response?.data?.detail || "Yangilanishni boshlab bo'lmadi";
      if (err.response?.status === 409) {
        // allaqachon ketyapti — overlay o'zi ko'rsatadi
        setConfirmOpen(false);
        window.dispatchEvent(new Event("smartkassa:update-started"));
      } else {
        toast.error("Xatolik", { description: msg });
      }
    } finally {
      setStarting(false);
    }
  };

  if (!enabled) return null;

  return (
    <>
      <button
        type="button"
        onClick={() => setConfirmOpen(true)}
        title="Dasturni yangilash"
        className={`fixed left-3 z-40 flex items-center gap-2 rounded-full border bg-card px-3 py-2 text-xs font-semibold shadow-lg transition-all hover:scale-105 ${
          isCashier ? "bottom-20" : "bottom-4"
        } ${available ? "border-amber-400 text-amber-600 dark:text-amber-400" : "text-muted-foreground"}`}
      >
        <RefreshCw className="h-4 w-4" />
        {available ? `Yangilanish bor${behind ? ` (${behind})` : ""}` : "Yangilash"}
        {available && (
          <span className="absolute -right-1 -top-1 h-3 w-3 animate-pulse rounded-full bg-amber-500" />
        )}
      </button>

      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Dasturni yangilash</DialogTitle>
            <DialogDescription>
              Yangilanish <b>30–60 soniya</b> davom etadi va shu vaqtda savdo
              qilib bo'lmaydi. Barcha kompyuterlar avtomatik yangilanadi.
              <br />
              <br />
              Savdo gavjum bo'lmagan vaqtda bajaring. Hozir davom etilsinmi?
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmOpen(false)} disabled={starting}>
              Bekor qilish
            </Button>
            <Button onClick={startUpdate} disabled={starting}>
              {starting ? "Boshlanmoqda..." : "Ha, yangilash"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
