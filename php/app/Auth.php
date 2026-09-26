<?php
/**
 * Autentifikatsiya: JWT, parol, sessiya, rollar.
 *
 * ESKI PAROLLAR ISHLASHDA DAVOM ETADI
 * -----------------------------------
 * Python tomonida parollar passlib ning `pbkdf2_sha256` sxemasida saqlangan:
 *
 *     $pbkdf2-sha256$29000$<salt>$<checksum>
 *
 * Bu yerda aynan shu format o'qiladi va yoziladi. Ya'ni bazani ko'chirgandan
 * keyin har bir xodim O'Z ESKI PAROLI bilan kiradi va ikkala versiya ham
 * bir-birining hash'ini tushunadi (ko'chish davrida qulay).
 *
 * Salt va checksum passlib ning "ab64" kodlashida: oddiy base64, lekin
 * '+' o'rniga '.', to'ldiruvchi '=' esa olib tashlangan.
 */

declare(strict_types=1);

final class Auth
{
    private const PBKDF2_ROUNDS = 29000;
    private const PBKDF2_SALT_BYTES = 16;
    private const PBKDF2_DIGEST_BYTES = 32;

    private static ?array $user = null;
    private static bool $resolved = false;

    // --- passlib "ab64" kodlash -----------------------------------------

    private static function ab64Encode(string $bytes): string
    {
        return rtrim(strtr(base64_encode($bytes), '+', '.'), '=');
    }

    private static function ab64Decode(string $text): string
    {
        $std = strtr($text, '.', '+');
        $pad = strlen($std) % 4;
        if ($pad !== 0) {
            $std .= str_repeat('=', 4 - $pad);
        }
        $out = base64_decode($std, true);
        return $out === false ? '' : $out;
    }

    // --- Parol ----------------------------------------------------------

    /** passlib pbkdf2_sha256 formatidagi hash yaratadi. */
    public static function hashPassword(string $password): string
    {
        $salt = random_bytes(self::PBKDF2_SALT_BYTES);
        $digest = hash_pbkdf2(
            'sha256',
            $password,
            $salt,
            self::PBKDF2_ROUNDS,
            self::PBKDF2_DIGEST_BYTES,
            true
        );
        return '$pbkdf2-sha256$' . self::PBKDF2_ROUNDS . '$'
            . self::ab64Encode($salt) . '$' . self::ab64Encode($digest);
    }

    /** Parolni tekshiradi. Vaqt bo'yicha hujumga qarshi hash_equals. */
    public static function verifyPassword(string $password, ?string $stored): bool
    {
        if ($stored === null || $stored === '') {
            return false;
        }
        // $pbkdf2-sha256$rounds$salt$checksum  ->  ['', 'pbkdf2-sha256', ...]
        $parts = explode('$', $stored);
        if (count($parts) !== 5 || $parts[1] !== 'pbkdf2-sha256') {
            error_log('[kassa] Notanish parol formati: ' . substr($stored, 0, 20));
            return false;
        }

        $rounds = (int)$parts[2];
        if ($rounds < 1 || $rounds > 1_000_000) {
            return false;
        }
        $salt = self::ab64Decode($parts[3]);
        $expect = self::ab64Decode($parts[4]);
        if ($salt === '' || $expect === '') {
            return false;
        }

        $actual = hash_pbkdf2('sha256', $password, $salt, $rounds, strlen($expect), true);
        return hash_equals($expect, $actual);
    }

    // --- JWT (HS256) ----------------------------------------------------

    private static function b64url(string $bytes): string
    {
        return rtrim(strtr(base64_encode($bytes), '+/', '-_'), '=');
    }

    private static function b64urlDecode(string $text): string
    {
        $std = strtr($text, '-_', '+/');
        $pad = strlen($std) % 4;
        if ($pad !== 0) {
            $std .= str_repeat('=', 4 - $pad);
        }
        $out = base64_decode($std, true);
        return $out === false ? '' : $out;
    }

    public static function createToken(string $username, string $sessionId, ?int $minutes = null): string
    {
        $minutes ??= ACCESS_TOKEN_EXPIRE_MINUTES;
        $header = ['alg' => 'HS256', 'typ' => 'JWT'];
        $payload = [
            'sub' => $username,
            'sid' => $sessionId,
            'exp' => time() + $minutes * 60,
        ];
        $h = self::b64url(json_encode($header, JSON_UNESCAPED_SLASHES));
        $p = self::b64url(json_encode($payload, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE));
        $sig = self::b64url(hash_hmac('sha256', "$h.$p", SECRET_KEY, true));
        return "$h.$p.$sig";
    }

    /** Tokenni ochadi. Imzo yoki muddat noto'g'ri bo'lsa — null. */
    public static function decodeToken(string $token): ?array
    {
        $parts = explode('.', $token);
        if (count($parts) !== 3) {
            return null;
        }
        [$h, $p, $sig] = $parts;

        $expected = self::b64url(hash_hmac('sha256', "$h.$p", SECRET_KEY, true));
        if (!hash_equals($expected, $sig)) {
            return null;
        }

        $header = json_decode(self::b64urlDecode($h), true);
        // "alg": "none" hujumi — algoritmni imzolanmagan holatga tushirish.
        if (!is_array($header) || ($header['alg'] ?? '') !== 'HS256') {
            return null;
        }

        $payload = json_decode(self::b64urlDecode($p), true);
        if (!is_array($payload)) {
            return null;
        }
        if (!isset($payload['exp']) || (int)$payload['exp'] < time()) {
            return null;
        }
        return $payload;
    }

    // --- Joriy foydalanuvchi --------------------------------------------

    private static function bearer(): ?string
    {
        $header = $_SERVER['HTTP_AUTHORIZATION']
            ?? $_SERVER['REDIRECT_HTTP_AUTHORIZATION']
            ?? '';
        if ($header === '' && function_exists('apache_request_headers')) {
            // Ba'zi Apache/CGI sozlamalarida sarlavha $_SERVER ga tushmaydi.
            foreach (apache_request_headers() as $k => $v) {
                if (strcasecmp($k, 'Authorization') === 0) {
                    $header = $v;
                    break;
                }
            }
        }
        if (stripos($header, 'Bearer ') !== 0) {
            return null;
        }
        $token = trim(substr($header, 7));
        return $token === '' ? null : $token;
    }

    /**
     * Tokendan xodimni topadi. Topilmasa 401 bilan to'xtatadi.
     * Natija so'rov davomida eslab qolinadi — baza bir marta o'qiladi.
     */
    public static function user(): array
    {
        if (self::$resolved) {
            if (self::$user === null) {
                Http::fail(401, 'Could not validate credentials', ['WWW-Authenticate' => 'Bearer']);
            }
            return self::$user;
        }
        self::$resolved = true;

        $token = self::bearer();
        if ($token === null) {
            Http::fail(401, 'Not authenticated', ['WWW-Authenticate' => 'Bearer']);
        }

        $payload = self::decodeToken($token);
        if ($payload === null || empty($payload['sub'])) {
            Http::fail(401, 'Could not validate credentials', ['WWW-Authenticate' => 'Bearer']);
        }

        $user = Db::one(
            'SELECT * FROM employees WHERE username = ?',
            [(string)$payload['sub']]
        );
        if ($user === null) {
            Http::fail(401, 'Could not validate credentials', ['WWW-Authenticate' => 'Bearer']);
        }

        if (!Db::b($user['is_active'])) {
            Http::fail(403, 'Foydalanuvchi faol emas (bloklangan)');
        }

        // Sessiya kalitini HAR DOIM solishtiramiz.
        //
        // Ilgari shart `if user.session_token and ...` edi. Chiqishda
        // session_token NULL ga o'rnatiladi va NULL "yolg'on" bo'lgani uchun
        // butun tekshiruv o'tkazib yuborilardi: chiqib ketilgan token o'z
        // muddati tugagunicha ishlayverardi — ya'ni "Chiqish" tugmasi hech
        // narsani bekor qilmasdi va parol almashtirish ham tokenni
        // o'ldirmasdi.
        $sid = (string)($payload['sid'] ?? '');
        $stored = (string)($user['session_token'] ?? '');
        if ($sid === '' || $stored === '' || !hash_equals($stored, $sid)) {
            Http::fail(
                401,
                'Sessiya yakunlangan. Qaytadan tizimga kiring.',
                ['WWW-Authenticate' => 'Bearer']
            );
        }

        $user['id'] = (int)$user['id'];

        // Oxirgi faollik — admin xodimlar ro'yxatida online/offline ko'radi.
        // Har so'rovda yozmaslik uchun daqiqasiga ko'pi bilan bir marta.
        $seen = Tz::parse($user['last_seen_at'] ?? null);
        if ($seen === null || $seen < new DateTimeImmutable('-60 seconds', new DateTimeZone('UTC'))) {
            Db::run('UPDATE employees SET last_seen_at = ? WHERE id = ?', [Tz::now(), $user['id']]);
        }

        return self::$user = $user;
    }

    /** Rol tekshiruvi. Python'dagi inline `if role not in [...]` ning o'rnida. */
    public static function require(array $roles, string $message = 'Ruxsat yo\'q'): array
    {
        $user = self::user();
        if (!in_array($user['role'], $roles, true)) {
            Http::fail(403, $message);
        }
        return $user;
    }

    public static function isPrimaryAdmin(array $user): bool
    {
        return $user['username'] === PRIMARY_ADMIN_USERNAME;
    }

    public static function newSessionId(): string
    {
        return bin2hex(random_bytes(16));
    }

    // --- Menejer tasdig'i -----------------------------------------------

    /**
     * Menejer/admin tasdig'ini tekshiradi — CHEKLOV va JURNAL bilan.
     *
     * Ilgari bu tekshiruv uch joyda takrorlangan, cheklovsiz va
     * muvaffaqiyatsiz urinishlar jurnalga YOZILMASDAN turardi. Kassir
     * kassadan turib menejer parolini xohlaganicha tez taxmin qila olardi,
     * hech qanday iz qoldirmasdan; topilgan parol esa /auth/token uchun ham
     * yaraydi, ya'ni to'liq eskalatsiya.
     */
    public static function verifyApprover(
        array $requester,
        ?string $username,
        ?string $password,
        array $roles = ['admin', 'manager']
    ): array {
        if ($username === null || $password === null || $username === '' || $password === '') {
            Http::fail(403, "Menejer tasdig'i noto'g'ri");
        }

        if (!RateLimit::hit('approve:' . $requester['id'], 5, 60)) {
            Http::fail(429, "Juda ko'p urinish. Bir daqiqadan keyin qayta urinib ko'ring.");
        }

        // Mantiqiy qiymatni SON bilan solishtirmaymiz: PostgreSQL da ustun
        // haqiqiy boolean va "is_active = 1" xato beradi
        // (operator does not exist: boolean = integer). PHP bool ni bog'lash
        // uchala bazada ham to'g'ri ishlaydi.
        $approver = Db::one(
            'SELECT * FROM employees WHERE username = ? AND is_active = ?',
            [$username, true]
        );

        if ($approver === null
            || !in_array($approver['role'], $roles, true)
            || !self::verifyPassword($password, $approver['hashed_password'])) {
            Audit::log(
                (int)$requester['id'],
                'TASDIQ_XATO',
                "Menejer tasdig'i muvaffaqiyatsiz. Kiritilgan login: '" . $username . "'"
            );
            Http::fail(403, "Menejer tasdig'i noto'g'ri");
        }

        RateLimit::clear('approve:' . $requester['id']);
        $approver['id'] = (int)$approver['id'];
        return $approver;
    }
}

/**
 * Urinishlar chegarasi.
 *
 * Python'da bu xotirada (jarayon ichida) turardi. PHP da jarayon har
 * so'rovdan keyin o'ladi, shuning uchun hisob faylda. Faqat kirish va
 * tasdiqlash yo'llarida chaqiriladi — ular kamdan-kam bo'ladi, shuning
 * uchun disk bilan ishlash umumiy yuklamaga sezilarli ta'sir qilmaydi.
 */
final class RateLimit
{
    private static function dir(): string
    {
        $dir = ROOT_DIR . '/logs/ratelimit';
        if (!is_dir($dir)) {
            @mkdir($dir, 0700, true);
        }
        return $dir;
    }

    private static function path(string $key): string
    {
        return self::dir() . '/' . hash('sha256', $key) . '.cnt';
    }

    /**
     * Urinishni qayd qiladi. Chegaradan oshsa false.
     *
     * @param int $limit  oynada ruxsat etilgan urinishlar
     * @param int $window oyna, sekundda
     */
    public static function hit(string $key, int $limit, int $window): bool
    {
        $path = self::path($key);
        $now = time();

        $fh = @fopen($path, 'c+');
        if ($fh === false) {
            // Diskka yozib bo'lmasa, kassani to'xtatib qo'ymaymiz.
            error_log('[kassa] RateLimit: faylni ochib bo\'lmadi: ' . $path);
            return true;
        }

        try {
            if (!flock($fh, LOCK_EX)) {
                return true;
            }
            $raw = stream_get_contents($fh);
            $stamps = [];
            foreach (explode(',', (string)$raw) as $s) {
                $s = (int)$s;
                if ($s > 0 && $now - $s < $window) {
                    $stamps[] = $s;
                }
            }

            if (count($stamps) >= $limit) {
                return false;
            }

            $stamps[] = $now;
            ftruncate($fh, 0);
            rewind($fh);
            fwrite($fh, implode(',', $stamps));
            fflush($fh);
            return true;
        } finally {
            flock($fh, LOCK_UN);
            fclose($fh);
        }
    }

    public static function clear(string $key): void
    {
        @unlink(self::path($key));
    }

    /** Eski fayllarni tozalash (cron chaqiradi). */
    public static function sweep(int $olderThan = 3600): int
    {
        $n = 0;
        $now = time();
        foreach (glob(self::dir() . '/*.cnt') ?: [] as $f) {
            if ($now - (int)@filemtime($f) > $olderThan) {
                @unlink($f);
                $n++;
            }
        }
        return $n;
    }
}
