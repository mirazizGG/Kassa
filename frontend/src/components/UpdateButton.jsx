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
import { UPDATE_INITIATOR_KEY } from "./UpdateOverlay";

/**
 * "Dasturni yangilash" boshqaruvi. Barcha xodimlarga ko'rinadi, lekin faqat
 * server `.env` da ALLOW_SELF_UPDATE=true bo'lsagina.
 *
 * variant="sidebar"   -> menyu pastidagi ozoda tugma (admin/menejer/omborchi)
 * variant="floating"  -> kichik doira, o'ng-yuqorida (kassir)
 */
export default function UpdateButton({ variant = "sidebar", expanded = true }) {
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
      localStorage.setItem(UPDATE_INITIATOR_KEY, "1");
      setConfirmOpen(false);
      window.dispatchEvent(new Event("smartkassa:update-started"));
    } catch (err) {
      if (err.response?.status === 409) {
        localStorage.setItem(UPDATE_INITIATOR_KEY, "1");
        setConfirmOpen(false);
        window.dispatchEvent(new Event("smartkassa:update-started"));
      } else {
        toast.error("Xatolik", {
          description:
            err.response?.data?.detail || "Yangilanishni boshlab bo'lmadi",
        });
      }
    } finally {
      setStarting(false);
    }
  };

  if (!enabled) return null;

  const label = available
    ? `Yangilanish bor${behind ? ` (${behind})` : ""}`
    : "Dasturni yangilash";

  const trigger =
    variant === "floating" ? (
      <button
        type="button"
        onClick={() => setConfirmOpen(true)}
        title={label}
        className={`fixed right-3 top-3 z-[60] flex items-center gap-2 rounded-full border bg-card/90 backdrop-blur px-2.5 py-2 text-xs font-semibold shadow-md transition-all hover:scale-105 ${
          available
            ? "border-amber-400 text-amber-600 dark:text-amber-400 pr-3"
            : "text-muted-foreground"
        }`}
      >
        <RefreshCw
          className={`h-4 w-4 ${available ? "animate-[spin_3s_linear_infinite]" : ""}`}
        />
        {available && <span>{label}</span>}
      </button>
    ) : (
      <button
        type="button"
        onClick={() => setConfirmOpen(true)}
        title={label}
        className={`group relative flex w-full items-center gap-3 rounded-xl px-3 py-2 text-sm font-medium transition-colors ${
          expanded ? "" : "justify-center px-0"
        } ${
          available
            ? "bg-amber-50 text-amber-700 hover:bg-amber-100 dark:bg-amber-950/30 dark:text-amber-400"
            : "text-muted-foreground hover:bg-muted"
        }`}
      >
        <span className="relative flex h-5 w-5 shrink-0 items-center justify-center">
          <RefreshCw className="h-[18px] w-[18px]" />
          {available && (
            <span className="absolute -right-1 -top-1 h-2 w-2 rounded-full bg-amber-500 ring-2 ring-card" />
          )}
        </span>
        {expanded && <span className="truncate">{label}</span>}
        {!expanded && (
          <span className="pointer-events-none absolute left-16 z-50 ml-2 whitespace-nowrap rounded-md border bg-popover px-2 py-1 text-sm text-popover-foreground opacity-0 shadow-md transition-opacity group-hover:opacity-100">
            {label}
          </span>
        )}
      </button>
    );

  return (
    <>
      {trigger}

      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Dasturni yangilash</DialogTitle>
            <DialogDescription>
              Yangilanish <b>30–60 soniya</b> davom etadi va shu vaqtda savdo
              qilib bo'lmaydi. Boshqa kompyuterlarda savdo shu payt uzilib
              qolishi mumkin, lekin "kuting" oynasi faqat sizga chiqadi.
              <br />
              <br />
              Savdo gavjum bo'lmagan vaqtda bajaring. Hozir davom etilsinmi?
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setConfirmOpen(false)}
              disabled={starting}
            >
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
