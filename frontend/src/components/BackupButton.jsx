import { useState } from "react";
import { DownloadCloud, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import api from "../api/axios";

/**
 * "Zaxira nusxa" tugmasi. Bir bosishda baza: lokal + bulut papka + GitHub +
 * Telegram ga nusxalanadi (qaysi biri sozlangan bo'lsa).
 *
 * Backend: POST /settings/backup  (admin / menejer / omborchi).
 */
export default function BackupButton({
  variant = "outline",
  className = "",
  label = "Zaxira nusxa",
}) {
  const [loading, setLoading] = useState(false);

  const run = async () => {
    setLoading(true);
    try {
      const res = await api.post("/settings/backup");
      toast.success("Zaxira nusxa olindi", {
        description: res.data?.message || "Baza nusxalandi",
      });
    } catch (err) {
      toast.error("Xatolik", {
        description: err.response?.data?.detail || "Zaxira nusxa olib bo'lmadi",
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <Button
      type="button"
      variant={variant}
      className={`gap-2 ${className}`}
      onClick={run}
      disabled={loading}
    >
      {loading ? (
        <Loader2 className="w-4 h-4 animate-spin" />
      ) : (
        <DownloadCloud className="w-4 h-4" />
      )}
      {label}
    </Button>
  );
}
