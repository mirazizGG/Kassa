<?php
/**
 * Vaqt bilan ishlashning YAGONA joyi (Python'dagi utils/timezone.py ko'chirmasi).
 *
 * Qoida butun loyiha bo'ylab bitta:
 *   * BAZADA hamma vaqt UTC va mintaqa belgisiz saqlanadi;
 *   * FOYDALANUVCHI do'kon vaqtida o'ylaydi (sukut bo'yicha Asia/Tashkent);
 *   * bu ikkisi orasidagi har qanday o'tkazish faqat shu fayl orqali bo'ladi.
 *
 * Server soati ahamiyatsiz — hosting odatda UTC da turadi va shunday bo'lgani
 * ma'qul. PHP ning o'zi bootstrap.php da UTC ga qo'yilgan.
 */

declare(strict_types=1);

final class Tz
{
    private static ?DateTimeZone $shop = null;
    private static ?DateTimeZone $utc = null;

    public static function shopTz(): DateTimeZone
    {
        if (self::$shop === null) {
            try {
                self::$shop = new DateTimeZone(SHOP_TIMEZONE);
            } catch (Throwable) {
                // Noto'g'ri sozlama dasturni yiqitmasin.
                error_log("[kassa] SHOP_TIMEZONE='" . SHOP_TIMEZONE . "' topilmadi, Asia/Tashkent ishlatiladi.");
                self::$shop = new DateTimeZone('Asia/Tashkent');
            }
        }
        return self::$shop;
    }

    public static function utcTz(): DateTimeZone
    {
        return self::$utc ??= new DateTimeZone('UTC');
    }

    // --- Bazaga yozish --------------------------------------------------

    /** Bazaga yoziladigan "hozir": UTC, mikrosekundlari bilan. */
    public static function now(): string
    {
        return (new DateTimeImmutable('now', self::utcTz()))->format('Y-m-d H:i:s.u');
    }

    /** Bazadagi satrni DateTimeImmutable ga (UTC deb) o'giradi. */
    public static function parse(?string $value): ?DateTimeImmutable
    {
        if ($value === null || $value === '') {
            return null;
        }
        // Baza 'Y-m-d H:i:s[.u]' yoki ISO ('T' bilan) qaytarishi mumkin.
        $normal = str_replace('T', ' ', trim($value));
        // Mintaqa belgisi bo'lsa kesamiz — bazada u yo'q, kelib qolsa xato.
        $normal = preg_replace('/(?:Z|[+-]\d{2}:?\d{2})$/i', '', $normal) ?? $normal;
        try {
            return new DateTimeImmutable(trim($normal), self::utcTz());
        } catch (Throwable) {
            return null;
        }
    }

    // --- Javobga chiqarish ----------------------------------------------

    /**
     * API javobi uchun ISO 8601, mintaqa belgisiSIZ — Python/FastAPI aynan
     * shunday qaytarardi. Frontend'dagi parseServerDate() shu ko'rinishga
     * moslangan: mintaqa yo'qligini ko'rib, o'zi "Z" qo'shadi.
     *
     * "T" ajratgich SHART: bo'shliqli satr ("2026-09-07 14:30:00Z") ISO-8601
     * emas va brauzerlar uni bir xil o'qimaydi.
     */
    public static function iso(?string $dbValue): ?string
    {
        $dt = self::parse($dbValue);
        if ($dt === null) {
            return null;
        }
        // Mikrosekund nolga teng bo'lsa ko'rsatmaymiz — Python isoformat() ham
        // shunday qiladi, ya'ni javob baytma-bayt bir xil bo'ladi.
        $micro = (int)$dt->format('u');
        return $micro === 0
            ? $dt->format('Y-m-d\TH:i:s')
            : $dt->format('Y-m-d\TH:i:s.u');
    }

    // --- Do'kon kuni <-> UTC oralig'i -----------------------------------

    /** Do'kon vaqtidagi satrni ("2026-09-07 00:00:00") naive-UTC ga o'giradi. */
    private static function shopMomentToUtc(string $shopMoment): string
    {
        $dt = new DateTimeImmutable($shopMoment, self::shopTz());
        return $dt->setTimezone(self::utcTz())->format('Y-m-d H:i:s.u');
    }

    /** Do'kon kunining boshlanishi -> bazada solishtirish uchun naive-UTC. */
    public static function dayStartUtc(string $ymd): string
    {
        return self::shopMomentToUtc($ymd . ' 00:00:00');
    }

    /** Do'kon kunining oxiri -> bazada solishtirish uchun naive-UTC. */
    public static function dayEndUtc(string $ymd): string
    {
        return self::shopMomentToUtc($ymd . ' 23:59:59.999999');
    }

    /** Do'kon kuni uchun [boshi, keyingi kun boshi) oralig'i. */
    public static function dayBoundsUtc(string $ymd): array
    {
        $next = (new DateTimeImmutable($ymd, self::shopTz()))
            ->modify('+1 day')->format('Y-m-d');
        return [self::dayStartUtc($ymd), self::dayStartUtc($next)];
    }

    /** Do'kon bo'yicha bugungi kalendar sana, "Y-m-d". */
    public static function shopToday(): string
    {
        return (new DateTimeImmutable('now', self::shopTz()))->format('Y-m-d');
    }

    /** Do'kon bo'yicha BUGUN boshlangan payt, naive-UTC. */
    public static function todayStartUtc(): string
    {
        return self::dayStartUtc(self::shopToday());
    }

    /** Bazadagi qiymatning do'kon bo'yicha kalendar sanasi. */
    public static function shopDate(?string $dbValue): ?string
    {
        $dt = self::parse($dbValue);
        return $dt?->setTimezone(self::shopTz())->format('Y-m-d');
    }

    /**
     * Bugundan `value` sanasigacha necha KUN qolgani (do'kon vaqti bo'yicha).
     *
     * Muhim: bu KALENDAR kunlari farqi. Ilgari Python'da qarz eslatmalari
     * `(due - now).days` bilan hisoblanardi: manfiy timedelta pastga
     * yaxlitlangani uchun muddat KUNIning o'zida ham natija -1 chiqib,
     * mijozga "muddati o'tgan" deb yozilardi.
     */
    public static function daysUntil(?string $dbValue): ?int
    {
        $target = self::shopDate($dbValue);
        if ($target === null) {
            return null;
        }
        $a = new DateTimeImmutable(self::shopToday(), self::shopTz());
        $b = new DateTimeImmutable($target, self::shopTz());
        return (int)$a->diff($b)->format('%r%a');
    }

    /**
     * Foydalanuvchi bergan sanani bazada solishtirish uchun naive-UTC ga o'giradi.
     *
     * "YYYY-MM-DD" — DO'KON kalendar kuni, shuning uchun chegaralari
     * dayStartUtc/dayEndUtc orqali olinadi. Ilgari bu kod finance.py va
     * sales.py da ikki nusxa bo'lib, kunni UTC bo'yicha kesardi: "bugungi"
     * hisobot smenalar ko'rsatadigan kundan boshqa oraliqni qamrardi.
     */
    public static function parseFilterDate(?string $value, bool $endOfDay = false): ?string
    {
        if ($value === null || trim($value) === '') {
            return null;
        }
        $text = trim($value);

        if (strlen($text) <= 10) {
            $d = DateTimeImmutable::createFromFormat('!Y-m-d', $text, self::shopTz());
            if ($d === false || $d->format('Y-m-d') !== $text) {
                return null;
            }
            return $endOfDay ? self::dayEndUtc($text) : self::dayStartUtc($text);
        }

        try {
            $normal = str_replace('Z', '+00:00', $text);
            $hasZone = (bool)preg_match('/(?:[+-]\d{2}:?\d{2})$/', $normal);
            $dt = new DateTimeImmutable($normal, $hasZone ? self::utcTz() : self::utcTz());
            return $dt->setTimezone(self::utcTz())->format('Y-m-d H:i:s.u');
        } catch (Throwable) {
            return null;
        }
    }
}
