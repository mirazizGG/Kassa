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
