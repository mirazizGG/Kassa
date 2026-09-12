import { clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs) {
  return twMerge(clsx(inputs))
}

// Formats a raw digit string/number for display with "." as the thousands separator (e.g. 5000 -> "5.000")
export function formatThousands(value) {
  if (value === "" || value === null || value === undefined) return ""
  return String(value).replace(/\B(?=(\d{3})+(?!\d))/g, ".")
}

// Strips everything but digits, for use in onChange handlers of money inputs
export function parseThousands(value) {
  return String(value ?? "").replace(/\D/g, "")
}

/**
 * HTML ga qo'yiladigan matnni xavfsizlantiradi.
 *
 * Chek chop etishda mahsulot nomi document.write ga TO'G'RIDAN-TO'G'RI
 * qo'yilardi. Mahsulot nomini o'zgartira oladigan har kim (admin, menejer,
 * omborchi) u yerga `<img src=x onerror=...>` yozib qo'yishi mumkin edi, va
 * shu chekni chop etgan odamning tokeni localStorage'dan o'g'irlanardi —
 * ya'ni omborchi admin huquqiga ko'tarilardi.
 */
export function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}
