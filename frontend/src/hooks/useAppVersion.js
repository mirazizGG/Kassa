import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import api from "../api/axios";

/**
 * Serverdagi dastur versiyasini kuzatib turadi.
 * - Boshqa kompyuterda "Yangilash" bosilib, server yangilangач,
 *   bu oyna ham buni sezib avtomatik qayta yuklanadi.
 * - `updating` — hozir yangilanish ketyaptimi (barcha oynalarda "kuting" ko'rsatish uchun).
 */
export function useAppVersion({ pollMs = 60000 } = {}) {
  const firstCommit = useRef(null);
  const [updating, setUpdating] = useState(false);
  const [reloadSoon, setReloadSoon] = useState(false);

  useEffect(() => {
    let stop = false;
    let timer;

    const tick = async () => {
      try {
        const { data } = await api.get("/system/version");
        if (stop) return;
        setUpdating(Boolean(data.updating));
        if (firstCommit.current == null) {
          firstCommit.current = data.commit;
        } else if (data.commit !== firstCommit.current && data.commit !== "?") {
          // Versiya o'zgardi — foydalanuvchini ogohlantirib, sahifani yangilaymiz.
          // Tugallanmagan savdo POS'da localStorage'ga saqlanadi va tiklanadi.
          setReloadSoon(true);
          toast.info("Yangi versiya o'rnatildi", {
            description: "Sahifa hozir yangilanadi...",
            duration: 4000,
          });
          setTimeout(() => window.location.reload(), 4000);
          return; // pollingni to'xtatamiz
        }
      } catch {
        /* tarmoq xatosi — keyingi urinishda qayta tekshiriladi */
      }
      if (!stop) timer = setTimeout(tick, pollMs);
    };

    tick();
    return () => {
      stop = true;
      clearTimeout(timer);
    };
  }, [pollMs]);

  return { updating, reloadSoon };
}
