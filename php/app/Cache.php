<?php
/**
 * Kichik kesh: og'ir hisob-kitoblarni takrorlamaslik uchun.
 *
 * NIMA UCHUN KERAK
 * ----------------
 * Ba'zi so'rovlar BUTUN tarixni yig'adi — masalan "eng ko'p sotilgan
 * mahsulotlar" 200 mingdan ortiq savdo satrini guruhlaydi. Bunday javob
 * bir necha daqiqada bir marta o'zgaradi, lekin har chaqiruvda qaytadan
 * hisoblanardi.
 *
 * QAYERGA SAQLAYDI
 * ----------------
 * APCu bo'lsa — xotiraga (eng tez). Bo'lmasa — faylga. Shared hosting'da
 * APCu ko'pincha o'chirilgan, shuning uchun fayl varianti ham to'liq ishlaydi.
 *
 * NIMANI KESHLASH MUMKIN EMAS
 * ---------------------------
 * Pul va qoldiq. Savat summasi, smena kassasi, mijoz balansi — bular HAR
 * DOIM bazadan jonli o'qiladi. Kesh faqat ko'rsatish uchun mo'ljallangan
 * ro'yxatlarga va sozlamalarga tegishli, va sozlamalar o'zgarganda kesh
 * DARHOL tozalanadi (TTL kutilmaydi).
 */

declare(strict_types=1);

final class Cache
{
    private static ?bool $apcu = null;

    private static function hasApcu(): bool
    {
        if (self::$apcu === null) {
            self::$apcu = function_exists('apcu_fetch')
                && function_exists('apcu_enabled')
                && apcu_enabled();
        }
        return self::$apcu;
    }

    private static function dir(): string
    {
        $dir = ROOT_DIR . '/logs/cache';
        if (!is_dir($dir)) {
            @mkdir($dir, 0700, true);
        }
        return $dir;
    }

    private static function path(string $key): string
    {
        return self::dir() . '/' . hash('sha256', $key) . '.cache';
    }

    /** Qiymatni oladi. Yo'q yoki eskirgan bo'lsa — null. */
    public static function get(string $key): mixed
    {
        if (self::hasApcu()) {
            $ok = false;
            $v = apcu_fetch('kassa:' . $key, $ok);
            return $ok ? $v : null;
        }

        $path = self::path($key);
        $raw = @file_get_contents($path);
        if ($raw === false) {
            return null;
        }
        $data = @unserialize($raw, ['allowed_classes' => false]);
        if (!is_array($data) || !isset($data['e'], $data['v'])) {
            return null;
        }
        if ($data['e'] < time()) {
            @unlink($path);
            return null;
        }
        return $data['v'];
    }

    public static function set(string $key, mixed $value, int $ttl = 300): void
    {
        if (self::hasApcu()) {
            apcu_store('kassa:' . $key, $value, $ttl);
            return;
        }

        $path = self::path($key);
        $payload = serialize(['e' => time() + $ttl, 'v' => $value]);
        // Atomar yozish: yarim yozilgan fayl o'qilmasin.
        $tmp = $path . '.' . getmypid() . '.tmp';
        if (@file_put_contents($tmp, $payload, LOCK_EX) !== false) {
            @rename($tmp, $path);
            @chmod($path, 0600);
        }
    }

    /** Keshda bo'lsa — o'shani, bo'lmasa — hisoblab, saqlab qaytaradi. */
    public static function remember(string $key, int $ttl, callable $fn): mixed
    {
        $hit = self::get($key);
        if ($hit !== null) {
            return $hit;
        }
        $value = $fn();
        // null ni saqlamaymiz — u "yo'q" bilan chalkashadi.
        if ($value !== null) {
            self::set($key, $value, $ttl);
        }
        return $value;
    }

    public static function forget(string $key): void
    {
        if (self::hasApcu()) {
            apcu_delete('kassa:' . $key);
            return;
        }
        @unlink(self::path($key));
    }

    /** Barcha keshni tozalaydi (sozlama o'zgarganda yoki qo'lda). */
    public static function flush(): int
    {
        if (self::hasApcu()) {
            apcu_clear_cache();
            return 1;
        }
        $n = 0;
        foreach (glob(self::dir() . '/*.cache') ?: [] as $f) {
            @unlink($f);
            $n++;
        }
        return $n;
    }

    /** Eskirgan fayllarni tozalash (cron chaqiradi). */
    public static function sweep(): int
    {
        if (self::hasApcu()) {
            return 0;
        }
        $n = 0;
        $now = time();
        foreach (glob(self::dir() . '/*.cache') ?: [] as $f) {
            // Fayl yaratilganidan beri bir sutkadan ko'p o'tgan bo'lsa,
            // uning TTL si ham allaqachon tugagan.
            if ($now - (int)@filemtime($f) > 86400) {
                @unlink($f);
                $n++;
            }
        }
        return $n;
    }
}
