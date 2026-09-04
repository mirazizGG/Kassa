import React, { useEffect, useRef, useState } from "react";
import { Loader2, CheckCircle2, AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import api from "../api/axios";

export const UPDATE_INITIATOR_KEY = "smartkassa_update_initiator";

const PHASE_TEXT = {
  boshlanmoqda: "Boshlanmoqda...",
  tekshirilmoqda: "GitHub tekshirilmoqda...",
  zahira: "Bazadan zahira nusxa olinmoqda...",
  yuklanmoqda: "Yangi kod yuklanmoqda...",
  kutubxonalar: "Kutubxonalar o'rnatilmoqda...",
  qurilmoqda: "Dastur qurilmoqda (biroz vaqt oladi)...",
  qayta_ishga_tushmoqda: "Qayta ishga tushmoqda...",
};

/**
 * Butun ekranni yopadigan "Yangilanmoqda, kuting" oynasi.
 * Faqat yangilanishni BOSHLAGAN brauzer/akkauntda ko'rinadi (localStorage
 * bayrog'i orqali) — boshqa kassirlar sahifani shu vaqt ichida ochsa ham
 * bu oynani ko'rmaydi, backend qayta ishga tushganda ularning so'rovlari
 * bir necha soniyaga ishlamay, so'ng o'zi tiklanadi.
 */
export default function UpdateOverlay() {
  const [active, setActive] = useState(false);
  const [status, setStatus] = useState({ phase: "boshlanmoqda", message: "" });
  const [done, setDone] = useState(null); // null | "ok" | "error"
  const startedAt = useRef(0);

  // Ishga tushirish signallari
  useEffect(() => {
    const onEvent = () => {
      startedAt.current = Date.now();
      setDone(null);
      setActive(true);
    };
    window.addEventListener("smartkassa:update-started", onEvent);

    (async () => {
      if (localStorage.getItem(UPDATE_INITIATOR_KEY) !== "1") return;
      try {
        const { data: v } = await api.get("/system/version");
        if (v.updating) {
          startedAt.current = Date.now();
          setActive(true);
        } else {
          localStorage.removeItem(UPDATE_INITIATOR_KEY);
        }
      } catch {
        /* e'tibor bermaymiz */
      }
    })();

    return () =>
      window.removeEventListener("smartkassa:update-started", onEvent);
  }, []);

  // Faol bo'lganда holatni so'rab turish
  useEffect(() => {
    if (!active || done) return;
    let cancelled = false;

    const loop = async () => {
      while (!cancelled) {
        try {
          const { data } = await api.get("/system/update-status");
          if (!cancelled) setStatus(data);
          if (data.running === false && data.ok === true) {
            localStorage.removeItem(UPDATE_INITIATOR_KEY);
            if (!cancelled) setDone("ok");
            setTimeout(() => window.location.reload(), 1500);
            return;
          }
          if (data.running === false && data.ok === false) {
            localStorage.removeItem(UPDATE_INITIATOR_KEY);
            if (!cancelled) setDone("error");
            return;
          }
        } catch {
          // backend qayta ishga tushayotgan bo'lishi mumkin
          if (!cancelled)
            setStatus((s) => ({ ...s, phase: "qayta_ishga_tushmoqda" }));
        }
        if (Date.now() - startedAt.current > 6 * 60 * 1000) {
          localStorage.removeItem(UPDATE_INITIATOR_KEY);
          if (!cancelled) {
            setStatus({
              message: "Yangilanish juda uzoq cho'zildi. Serverni tekshiring.",
            });
            setDone("error");
          }
          return;
        }
        await new Promise((r) => setTimeout(r, 2000));
      }
    };

    loop();
    return () => {
      cancelled = true;
    };
  }, [active, done]);

  if (!active) return null;

  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-background/80 backdrop-blur-sm">
      <div className="w-[90%] max-w-sm rounded-2xl border bg-card p-8 text-center shadow-2xl">
        {done === "ok" ? (
          <>
            <CheckCircle2 className="mx-auto h-14 w-14 text-emerald-500" />
            <h3 className="mt-4 text-lg font-bold">Yangilandi!</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              Sahifa yangilanmoqda...
            </p>
          </>
        ) : done === "error" ? (
          <>
            <AlertTriangle className="mx-auto h-14 w-14 text-red-500" />
            <h3 className="mt-4 text-lg font-bold">Yangilanishda xatolik</h3>
            <p className="mt-1 break-words text-sm text-muted-foreground">
              {status.message || "Noma'lum xato"}
            </p>
            <Button
              className="mt-5 w-full"
              onClick={() => window.location.reload()}
            >
              Sahifani yangilash
            </Button>
          </>
        ) : (
          <>
            <Loader2 className="mx-auto h-14 w-14 animate-spin text-primary" />
            <h3 className="mt-4 text-lg font-bold">Yangilanmoqda, kuting...</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              {PHASE_TEXT[status.phase] ||
                status.message ||
                "Iltimos kuting..."}
            </p>
            <p className="mt-4 text-xs text-muted-foreground">
              Bu oynani yopmang. Bir necha soniya vaqt oladi.
            </p>
          </>
        )}
      </div>
    </div>
  );
}
