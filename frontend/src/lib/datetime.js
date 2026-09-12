import { format as formatDateFns } from "date-fns";

/**
 * Server hamma vaqtni UTC da, lekin mintaqa belgisiSIZ qaytaradi:
 * "2026-09-07T14:30:00". JavaScript bunday satrni LOKAL vaqt deb o'qiydi,
 * shuning uchun Toshkentda vaqt 5 soatga surilib ko'rinardi.
 *
 * Ilgari bu tuzatish ba'zi sahifalarda qo'lda ("Z" qo'shish orqali) bor edi,
 * ba'zilarida esa yo'q — natijada Moliya, Ombor, Firmalar va Xodimlar
 * sahifalarida vaqt noto'g'ri chiqardi. Endi barcha sahifalar shu yagona
 * funksiyadan foydalanadi.
 */
export function parseServerDate(value) {
  if (!value) return null;
  if (value instanceof Date) return value;

  const raw = String(value);
  const hasZone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(raw);
  const parsed = new Date(hasZone ? raw : `${raw}Z`);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

/** Serverdan kelgan vaqtni ko'rsatish uchun formatlaydi. */
export function formatDateTime(value, pattern = "dd.MM.yyyy HH:mm", fallback = "-") {
  const parsed = parseServerDate(value);
  if (!parsed) return fallback;
  try {
    return formatDateFns(parsed, pattern);
  } catch {
    return fallback;
  }
}
