import React, { useEffect, useRef, useState } from "react";
import { Loader2, CheckCircle2, AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";

const PHASE_TEXT = {
  boshlanmoqda: "Boshlanmoqda...",
  tekshirilmoqda: "GitHub tekshirilmoqda...",
  zahira: "Bazadan zahira nusxa olinmoqda...",
  yuklanmoqda: "Yangi kod yuklanmoqda...",
  kutubxonalar: "Kutubxonalar o'rnatilmoqda...",
  qurilmoqda: "Dastur qurilmoqda (biroz vaqt oladi)...",
  qayta_ishga_tushmoqda: "Qayta ishga tushmoqda...",
};

const authHeaders = () => ({
  Authorization: `Bearer ${localStorage.getItem("token") || ""}`,
});

/**
 * Butun ekranni yopadigan "Yangilanmoqda, kuting" oynasi.
 * Ishga tushadi: `smartkassa:update-started` hodisasi kelganda (shu kompda tugma),
 * yoki sahifa ochilganda server "updating" desa (boshqa kompda bosilgan).
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
      try {
        const res = await fetch("/system/version", { headers: authHeaders() });
        if (res.ok) {
          const v = await res.json();
          if (v.updating) {
            startedAt.current = Date.now();
            setActive(true);
          }
        }
      } catch {
        /* e'tibor bermaymiz */
      }
    })();

    return () => window.removeEventListener("smartkassa:update-started", onEvent);
  }, []);

  // Faol bo'lganда holatni so'rab turish
  useEffect(() => {
    if (!active || done) return;
    let cancelled = false;

    const loop = async () => {
      while (!cancelled) {
        try {
          const res = await fetch("/system/update-status", { headers: authHeaders() });
          if (res.ok) {
            const data = await res.json();
            if (!cancelled) setStatus(data);
            if (data.running === false && data.ok === true) {
              if (!cancelled) setDone("ok");
              setTimeout(() => window.location.reload(), 1500);
              return;
            }
            if (data.running === false && data.ok === false) {
              if (!cancelled) setDone("error");
              return;
            }
          }
        } catch {
          // backend qayta ishga tushayotgan bo'lishi mumkin
          if (!cancelled) setStatus((s) => ({ ...s, phase: "qayta_ishga_tushmoqda" }));
        }
        if (Date.now() - startedAt.current > 6 * 60 * 1000) {
          if (!cancelled) {
            setStatus({ message: "Yangilanish juda uzoq cho'zildi. Serverni tekshiring." });
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
            <p className="mt-1 text-sm text-muted-foreground">Sahifa yangilanmoqda...</p>
          </>
        ) : done === "error" ? (
          <>
            <AlertTriangle className="mx-auto h-14 w-14 text-red-500" />
            <h3 className="mt-4 text-lg font-bold">Yangilanishda xatolik</h3>
            <p className="mt-1 break-words text-sm text-muted-foreground">
              {status.message || "Noma'lum xato"}
            </p>
            <Button className="mt-5 w-full" onClick={() => window.location.reload()}>
              Sahifani yangilash
            </Button>
          </>
        ) : (
          <>
            <Loader2 className="mx-auto h-14 w-14 animate-spin text-primary" />
            <h3 className="mt-4 text-lg font-bold">Yangilanmoqda, kuting...</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              {PHASE_TEXT[status.phase] || status.message || "Iltimos kuting..."}
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
