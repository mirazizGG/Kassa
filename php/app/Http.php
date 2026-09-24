<?php
/**
 * So'rov/javob bilan ishlash va kirish ma'lumotlarini tekshirish.
 *
 * SHARTNOMA: frontend har doim {"detail": "..."} kutadi (axios interceptor va
 * 23 ta sahifa `data?.detail` ni o'qiydi). Shuning uchun ISTALGAN xato shu
 * ko'rinishda qaytadi — HTML sahifa yoki massiv frontend'ni sindiradi.
 *
 * Python versiyasida 422 xatosi massiv qaytarardi (Pydantic uslubi) va
 * interfeysda o'qib bo'lmaydigan narsa ko'rinardi. Bu yerda 422 ham
 * o'zbekcha MATN qaytaradi — foydalanuvchi uchun tushunarli.
 */

declare(strict_types=1);

/** HTTP holati bilan tashlanadigan xato. */
class HttpError extends Exception
{
    public array $headers;

    public function __construct(int $status, string $detail, array $headers = [])
    {
        parent::__construct($detail, $status);
        $this->headers = $headers;
    }
}

function fail(int $status, string $detail, array $headers = []): never
{
    throw new HttpError($status, $detail, $headers);
}

final class Http
{
    private static ?array $body = null;

    // --- Javob ----------------------------------------------------------

    public static function json(mixed $data, int $status = 200, array $headers = []): never
    {
        // JSON_PRESERVE_ZERO_FRACTION: 1000.0 "1000.0" bo'lib qolsin —
        // Python/Pydantic ham shunday qaytarardi, frontend son kutadi.
        $body = json_encode(
            $data,
            JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_PRESERVE_ZERO_FRACTION
        );

        if (headers_sent()) {
            echo $body;
            exit;
        }

        foreach ($headers as $k => $v) {
            header("$k: $v");
        }

        // ETag / 304 bu yerda ATAYIN YO'Q.
        //
        // Sinab ko'rildi va o'lchandi: foyda bermaydi. Sabab — brauzer
        // `Authorization` sarlavhasi bilan ketgan javobni keshda SAQLAMAYDI
        // (RFC 7234), ya'ni keyingi so'rovda `If-None-Match` ni yubormaydi.
        // API ga BARCHA so'rovlar esa aynan shu sarlavha bilan ketadi.
        //
        // `Cache-Control: public` qo'yish brauzerni ko'ndirardi, lekin
        // o'rtadagi kesh (proksi, CDN) kassirning savdo tarixini saqlab,
        // keyin boshqa odamga berib qo'yishi mumkin. Kassa uchun bu
        // qabul qilib bo'lmaydigan narx.
        //
        // Javobni takroran tortmaslikni frontend O'ZI hal qiladi:
        // TanStack Query natijani 5 daqiqa saqlaydi (queryClient.jsx).
        // Server tomonda esa ETag faqat ZARAR qilardi — 700 KB javob uchun
        // md5 hisoblash bir necha millisekund, foydasi esa nol.

        http_response_code($status);
        header('Content-Type: application/json; charset=utf-8');
        // Content-Length ATAYIN qo'yilmaydi: siqish yoqilgan bo'lsa
        // (zlib.output_compression yoki mod_deflate) javob hajmi
        // o'zgaradi va qo'lda yozilgan uzunlik javobni buzadi.
        echo $body;
        exit;
    }

    public static function fail(int $status, string $detail, array $headers = []): never
    {
        self::json(['detail' => $detail], $status, $headers);
    }

    public static function noContent(): never
    {
        http_response_code(204);
        exit;
    }

    // --- So'rov tanasi --------------------------------------------------

    /** JSON tanasi. Bo'sh bo'lsa — bo'sh massiv. */
    public static function body(): array
    {
        if (self::$body !== null) {
            return self::$body;
        }
        $raw = file_get_contents('php://input');
        if ($raw === false || trim($raw) === '') {
            return self::$body = [];
        }
        $ct = $_SERVER['CONTENT_TYPE'] ?? '';
        if (str_contains($ct, 'application/x-www-form-urlencoded')
            || str_contains($ct, 'multipart/form-data')) {
            return self::$body = $_POST;
        }
        $parsed = json_decode($raw, true);
        if (!is_array($parsed)) {
            fail(422, "So'rov tanasi noto'g'ri formatda (JSON kutilgan).");
        }
        return self::$body = $parsed;
    }

    /** Form maydonlari (login va tasdiqlash shu ko'rinishda keladi). */
    public static function form(): array
    {
        if (!empty($_POST)) {
            return $_POST;
        }
        return self::body();
    }

    // --- Tekshirish -----------------------------------------------------
    // Python tomonida bular Pydantic cheklovlari edi: allow_inf_nan=False,
    // gt=0, ge=0. NaN bir paytlar tekshiruvdan o'tib, REAL ustunga NULL
    // bo'lib tushar va keyin har bir ro'yxat endpointini 500 qilardi.

    /**
     * Son. $min berilsa — qat'iy katta (gt) yoki teng (ge) tekshiradi.
     *
     * @param string $mode 'gt' | 'ge' | 'any'
     */
    public static function num(
        array $src,
        string $key,
        ?float $default = null,
        string $mode = 'any',
        ?float $min = null,
        ?float $max = null,
        ?string $label = null
    ): ?float {
        $label = $label ?? $key;
        $raw = $src[$key] ?? null;
        if ($raw === null || $raw === '') {
            if ($default === null && !array_key_exists($key, $src)) {
                return null;
            }
            return $default;
        }
        if (is_bool($raw) || is_array($raw)) {
            fail(422, "«{$label}» son bo'lishi kerak.");
        }
        if (!is_numeric($raw)) {
            fail(422, "«{$label}» son bo'lishi kerak.");
        }
        $v = (float)$raw;
        // is_finite: "1e999" -> INF, "nan" -> NAN. Ikkalasi ham bazani buzadi.
        if (!is_finite($v)) {
            fail(422, "«{$label}» haqiqiy son bo'lishi kerak.");
        }
        if ($min !== null) {
            if ($mode === 'gt' && $v <= $min) {
                fail(422, "«{$label}» {$min} dan katta bo'lishi kerak.");
            }
            if ($mode === 'ge' && $v < $min) {
                fail(422, "«{$label}» {$min} dan kichik bo'lmasligi kerak.");
            }
        }
        if ($max !== null && $v > $max) {
            fail(422, "«{$label}» juda katta.");
        }
        return $v;
    }

    /** Majburiy son. */
    public static function reqNum(
        array $src,
        string $key,
        string $mode = 'any',
        ?float $min = null,
        ?float $max = null,
        ?string $label = null
    ): float {
        $label = $label ?? $key;
        if (!isset($src[$key]) || $src[$key] === '') {
            fail(422, "«{$label}» ko'rsatilmagan.");
        }
        return self::num($src, $key, null, $mode, $min, $max, $label);
    }

    public static function int(array $src, string $key, ?int $default = null, ?string $label = null): ?int
    {
        $label = $label ?? $key;
        $raw = $src[$key] ?? null;
        if ($raw === null || $raw === '') {
            return $default;
        }
        if (!is_numeric($raw) || (float)$raw != (int)(float)$raw) {
            fail(422, "«{$label}» butun son bo'lishi kerak.");
        }
        return (int)$raw;
    }

    public static function reqInt(array $src, string $key, ?string $label = null): int
    {
        $label = $label ?? $key;
        $v = self::int($src, $key, null, $label);
        if ($v === null) {
            fail(422, "«{$label}» ko'rsatilmagan.");
        }
        return $v;
    }

    public static function str(
        array $src,
        string $key,
        ?string $default = null,
        int $max = 500,
        ?string $label = null
    ): ?string {
        $label = $label ?? $key;
        $raw = $src[$key] ?? null;
        if ($raw === null) {
            return $default;
        }
        if (is_array($raw) || is_bool($raw)) {
            fail(422, "«{$label}» matn bo'lishi kerak.");
        }
        $v = trim((string)$raw);
        if ($v === '') {
            return $default;
        }
        if (mb_strlen($v) > $max) {
            fail(422, "«{$label}» juda uzun (eng ko'pi {$max} belgi).");
        }
        return $v;
    }

    public static function reqStr(array $src, string $key, int $max = 500, ?string $label = null): string
    {
        $label = $label ?? $key;
        $v = self::str($src, $key, null, $max, $label);
        if ($v === null) {
            fail(422, "«{$label}» ko'rsatilmagan.");
        }
        return $v;
    }

    public static function bool(array $src, string $key, bool $default = false): bool
    {
        $raw = $src[$key] ?? null;
        if ($raw === null || $raw === '') {
            return $default;
        }
        if (is_bool($raw)) {
            return $raw;
        }
        return in_array(strtolower((string)$raw), ['1', 'true', 'yes', 'on'], true);
    }

    /** Ro'yxatdan biri bo'lishi shart. */
    public static function enum(
        array $src,
        string $key,
        array $allowed,
        ?string $default = null,
        ?string $label = null
    ): ?string {
        $label = $label ?? $key;
        $v = self::str($src, $key, $default, 60, $label);
        if ($v === null) {
            return null;
        }
        if (!in_array($v, $allowed, true)) {
            fail(422, "«{$label}» qiymati noto'g'ri.");
        }
        return $v;
    }

    // --- So'rov parametrlari (query string) -----------------------------

    public static function q(string $key, ?string $default = null): ?string
    {
        $v = $_GET[$key] ?? null;
        if ($v === null || $v === '' || is_array($v)) {
            return $default;
        }
        return trim((string)$v);
    }

    public static function qInt(string $key, ?int $default = null, ?int $min = null, ?int $max = null): ?int
    {
        $v = self::q($key);
        if ($v === null || !is_numeric($v)) {
            return $default;
        }
        $n = (int)$v;
        if ($min !== null && $n < $min) {
            $n = $min;
        }
        if ($max !== null && $n > $max) {
            $n = $max;
        }
        return $n;
    }

    public static function qBool(string $key, bool $default = false): bool
    {
        $v = self::q($key);
        if ($v === null) {
            return $default;
        }
        return in_array(strtolower($v), ['1', 'true', 'yes', 'on'], true);
    }

    /** Mijoz IP si — rate-limit kaliti uchun. */
    public static function clientIp(): string
    {
        // Faqat TRUST_PROXY_HEADERS yoqilganda sarlavhaga ishonamiz. Aks holda
        // istalgan mijoz uni O'ZI yasab, har so'rovda yangi "IP" ko'rsatib,
        // urinishlar chegarasini butunlay chetlab o'tardi.
        if (env_bool('TRUST_PROXY_HEADERS', false)) {
            $cf = $_SERVER['HTTP_CF_CONNECTING_IP'] ?? '';
            if ($cf !== '') {
                return trim($cf);
            }
            $xff = $_SERVER['HTTP_X_FORWARDED_FOR'] ?? '';
            if ($xff !== '') {
                return trim(explode(',', $xff)[0]);
            }
        }
        return $_SERVER['REMOTE_ADDR'] ?? '0.0.0.0';
    }
}
