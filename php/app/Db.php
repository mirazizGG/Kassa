<?php
/**
 * Baza bilan ishlash: PDO ustidagi yupqa qobiq.
 *
 * NIMA UCHUN ORM YO'Q
 * -------------------
 * SQLAlchemy har so'rovda modellarni yig'ib, obyektlarga o'rab, sessiyani
 * kuzatib turadi. Kassa uchun bu ortiqcha: so'rovlar oddiy, lekin ORM
 * yuklanishi va xotirasi doimiy. Bu yerda — tayyorlangan so'rov va massiv.
 *
 * ULANISH DANGASА: PDO faqat birinchi so'rovda ochiladi. Statik fayl yoki
 * /health so'rovi bazaga umuman tegmaydi.
 *
 * MUHIM — ATOMAR YANGILANISH
 * --------------------------
 * Pul va qoldiq HECH QACHON "o'qi -> o'zgartir -> yoz" tarzida
 * yangilanmaydi. Faqat bitta SQL UPDATE, shart WHERE ichida:
 *
 *     UPDATE products SET stock = stock - ? WHERE id = ? AND stock >= ?
 *
 * rowCount() == 0 bo'lsa — kimdir bizdan oldin ulgurgan. MySQL ulanishida
 * CLIENT_FOUND_ROWS yoqilgan, ya'ni rowCount() "shart mos keldimi" degan
 * savolga javob beradi (o'zgargan qator soniga emas).
 */

declare(strict_types=1);

final class Db
{
    private static ?PDO $pdo = null;
    private static string $driver = '';

    /**
     * Ulanishni tashlab yuboradi — keyingi so'rov yangisini ochadi.
     * Faqat uzoq ishlaydigan jarayon (bin/bot.php) uchun: masofadagi MySQL
     * bo'sh turgan ulanishni uzib qo'yadi ("server has gone away").
     */
    public static function reset(): void
    {
        self::$pdo = null;
    }

    public static function pdo(): PDO
    {
        if (self::$pdo !== null) {
            return self::$pdo;
        }

        [$dsn, $user, $pass] = self::dsn();

        $options = [
            PDO::ATTR_ERRMODE            => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
            // Haqiqiy tayyorlangan so'rov. Taqlid tezroq, lekin rowCount()
            // ishonchsiz bo'lib qoladi — yuqoridagi atomar yangilanish esa
            // aynan shunga tayanadi.
            PDO::ATTR_EMULATE_PREPARES   => false,
            PDO::ATTR_STRINGIFY_FETCHES  => false,
            PDO::ATTR_PERSISTENT         => env_bool('DB_PERSISTENT', false),
        ];

        if (str_starts_with($dsn, 'mysql:')) {
            // rowCount() topilgan (mos kelgan) qatorlarni qaytarsin.
            $options[PDO::MYSQL_ATTR_FOUND_ROWS] = true;
        }

        try {
            self::$pdo = new PDO($dsn, $user, $pass, $options);
        } catch (PDOException $e) {
            // Xabarda DSN bo'ladi, DSN ichida parol bo'lishi mumkin —
            // foydalanuvchiga chiqarmaymiz, faqat jurnalga.
            error_log('[kassa] Bazaga ulanib bo\'lmadi: ' . $e->getMessage());
            // Buyruq satrida (bot, zahira) — istisno: chaqiruvchi ushlab,
            // qayta urinadi yoki "XATO" deb yozadi. Http::fail bu yerda
            // JSON chiqarib jarayonni jimgina o'ldirardi.
            if (PHP_SAPI === 'cli') {
                throw new RuntimeException("Bazaga ulanib bo'lmadi");
            }
            Http::fail(503, "Baza bilan aloqa yo'q. Biroz kutib qayta urinib ko'ring.");
        }

        self::$driver = self::$pdo->getAttribute(PDO::ATTR_DRIVER_NAME);

        if (self::$driver === 'sqlite') {
            // SQLite tashqi kalitlarni sukut bo'yicha majburlamaydi. Uni
            // yoqmasak, ishlab chiqish serverdan boshqacha ishlaydi.
            self::$pdo->exec('PRAGMA foreign_keys=ON');
            self::$pdo->exec('PRAGMA journal_mode=WAL');
            // Kassa uchun tezlikdan ko'ra ishonchlilik muhim.
            self::$pdo->exec('PRAGMA synchronous=FULL');
            self::$pdo->exec('PRAGMA busy_timeout=5000');
        }

        return self::$pdo;
    }

    public static function driver(): string
    {
        if (self::$driver === '') {
            self::pdo();
        }
        return self::$driver;
    }

    public static function isMysql(): bool
    {
        return self::driver() === 'mysql';
    }

    public static function isPgsql(): bool
    {
        return self::driver() === 'pgsql';
    }

    /** DATABASE_URL ni PDO DSN ga o'giradi. */
    private static function dsn(): array
    {
        $url = env('DATABASE_URL', '');

        if ($url === null || $url === '') {
            // Sukut: yonidagi SQLite fayli (faqat ishlab chiqish uchun).
            return ['sqlite:' . ROOT_DIR . '/market.db', null, null];
        }

        if (str_starts_with($url, 'sqlite:')) {
            $path = preg_replace('#^sqlite:(//)?#', '', $url);
            if ($path === '' || $path === null) {
                $path = ROOT_DIR . '/market.db';
            }
            return ['sqlite:' . $path, null, null];
        }

        $p = parse_url($url);
        if ($p === false || !isset($p['scheme'])) {
            Http::fail(500, 'DATABASE_URL noto\'g\'ri yozilgan.');
        }

        $scheme = strtolower($p['scheme']);
        $host   = $p['host'] ?? 'localhost';
        $port   = $p['port'] ?? null;
        $dbname = ltrim($p['path'] ?? '', '/');
        $user   = isset($p['user']) ? rawurldecode($p['user']) : null;
        $pass   = isset($p['pass']) ? rawurldecode($p['pass']) : null;

        if (in_array($scheme, ['mysql', 'mariadb'], true)) {
            $dsn = "mysql:host=$host;dbname=$dbname;charset=utf8mb4";
            if ($port) {
                $dsn = "mysql:host=$host;port=$port;dbname=$dbname;charset=utf8mb4";
            }
            $socket = env('DB_SOCKET');
            if ($socket !== null) {
                $dsn = "mysql:unix_socket=$socket;dbname=$dbname;charset=utf8mb4";
            }
            return [$dsn, $user, $pass];
        }

        if (in_array($scheme, ['postgres', 'postgresql', 'pgsql'], true)) {
            $dsn = "pgsql:host=$host;dbname=$dbname";
            if ($port) {
                $dsn = "pgsql:host=$host;port=$port;dbname=$dbname";
            }
            return [$dsn, $user, $pass];
        }

        Http::fail(500, "DATABASE_URL: '$scheme' turi qo'llab-quvvatlanmaydi.");
    }

    // --- So'rovlar ------------------------------------------------------

    public static function stmt(string $sql, array $params = []): PDOStatement
    {
        $st = self::pdo()->prepare($sql);
        // Butun sonlarni alohida bog'laymiz: MySQL da satr sifatida kelgan
        // LIMIT qiymati sintaksis xatosi beradi.
        $i = 1;
        foreach ($params as $key => $value) {
            $name = is_int($key) ? $i++ : $key;
            $type = match (true) {
                is_int($value)  => PDO::PARAM_INT,
                is_bool($value) => PDO::PARAM_BOOL,
                is_null($value) => PDO::PARAM_NULL,
                default         => PDO::PARAM_STR,
            };
            $st->bindValue($name, $value, $type);
        }
        $st->execute();
        return $st;
    }

    /** Barcha qatorlar. */
    public static function all(string $sql, array $params = []): array
    {
        return self::stmt($sql, $params)->fetchAll();
    }

    /** Birinchi qator yoki null. */
    public static function one(string $sql, array $params = []): ?array
    {
        $row = self::stmt($sql, $params)->fetch();
        return $row === false ? null : $row;
    }

    /** Birinchi ustunning birinchi qiymati. */
    public static function val(string $sql, array $params = [], mixed $default = null): mixed
    {
        $v = self::stmt($sql, $params)->fetchColumn();
        return $v === false ? $default : $v;
    }

    /** Son qaytaradigan so'rov (SUM/COUNT) — NULL bo'lsa 0.0. */
    public static function num(string $sql, array $params = []): float
    {
        return (float)(self::val($sql, $params, 0) ?? 0);
    }

    /**
     * O'zgartiruvchi so'rov. Qaytaradi: ta'sirlangan qatorlar soni.
     * Atomar yangilanishlarda natijani TEKSHIRISH shart.
     */
    public static function run(string $sql, array $params = []): int
    {
        return self::stmt($sql, $params)->rowCount();
    }

    /** INSERT va yangi id. */
    public static function insert(string $table, array $data): int
    {
        $cols = array_keys($data);
        $quoted = array_map(fn($c) => self::quoteId($c), $cols);
        $marks = implode(', ', array_fill(0, count($cols), '?'));
        $sql = 'INSERT INTO ' . self::quoteId($table) . ' (' . implode(', ', $quoted) . ") VALUES ($marks)";

        if (self::isPgsql()) {
            // PostgreSQL da lastInsertId ketma-ketlik nomini talab qiladi —
            // RETURNING ishonchliroq.
            return (int)self::val($sql . ' RETURNING id', array_values($data));
        }

        self::stmt($sql, array_values($data));
        return (int)self::pdo()->lastInsertId();
    }

    /** UPDATE ... WHERE id = ?. Qaytaradi: ta'sirlangan qatorlar. */
    public static function update(string $table, int $id, array $data): int
    {
        if ($data === []) {
            return 0;
        }
        $sets = [];
        foreach (array_keys($data) as $c) {
            $sets[] = self::quoteId($c) . ' = ?';
        }
        $params = array_values($data);
        $params[] = $id;
        return self::run(
            'UPDATE ' . self::quoteId($table) . ' SET ' . implode(', ', $sets) . ' WHERE id = ?',
            $params
        );
    }

    public static function delete(string $table, int $id): int
    {
        return self::run('DELETE FROM ' . self::quoteId($table) . ' WHERE id = ?', [$id]);
    }

    // --- Tranzaksiya ----------------------------------------------------

    /**
     * Tranzaksiya ichida bajaradi. Xato bo'lsa — to'liq bekor qiladi.
     * Ichma-ich chaqirilsa ikkinchi marta tranzaksiya ochmaydi.
     */
    public static function tx(callable $fn): mixed
    {
        $pdo = self::pdo();
        if ($pdo->inTransaction()) {
            return $fn();
        }
        $pdo->beginTransaction();
        try {
            $result = $fn();
            $pdo->commit();
            return $result;
        } catch (Throwable $e) {
            if ($pdo->inTransaction()) {
                $pdo->rollBack();
            }
            throw $e;
        }
    }

    // --- Yordamchilar ---------------------------------------------------

    public static function quoteId(string $name): string
    {
        // Faqat harflar/raqamlar/pastki chiziq — qolganini rad etamiz.
        if (!preg_match('/^[A-Za-z_][A-Za-z0-9_]*$/', $name)) {
            throw new RuntimeException("Xavfli identifikator: $name");
        }
        return self::isMysql() ? "`$name`" : "\"$name\"";
    }

    /**
     * Registrga sezgir bo'lmagan qidiruv.
     *
     * Python tomonida bu .icontains() edi. Oddiy LIKE faqat SQLite da
     * registrni e'tiborsiz qoldiradi; PostgreSQL da mahsulot qidiruvi
     * jim bo'lib qolardi. MySQL ning utf8mb4_..._ci solishtiruvi bilan
     * LIKE allaqachon registrga sezgir emas.
     */
    public static function ilike(string $column): string
    {
        return match (self::driver()) {
            'pgsql' => "$column ILIKE ?",
            default => "LOWER($column) LIKE LOWER(?)",
        };
    }

    /** IN (?, ?, ?) uchun o'rin belgilari. Bo'sh ro'yxatda NULL beradi. */
    public static function marks(array $values): string
    {
        return $values === [] ? 'NULL' : implode(', ', array_fill(0, count($values), '?'));
    }

    /** Qiymatni float ga (NULL bo'lsa 0.0). Javobda son chiqishi uchun. */
    public static function f(mixed $v): float
    {
        return $v === null ? 0.0 : (float)$v;
    }

    /** NULL bo'lishi mumkin bo'lgan son. */
    public static function fn(mixed $v): ?float
    {
        return $v === null ? null : (float)$v;
    }

    public static function i(mixed $v): int
    {
        return (int)$v;
    }

    /**
     * Bazadagi mantiqiy qiymatni haqiqiy bool ga.
     *
     * Har bir baza buni boshqacha qaytaradi:
     *   MySQL/SQLite -> 0 yoki 1
     *   PostgreSQL   -> haqiqiy bool, ba'zi sozlamalarda esa 't' / 'f' satri
     *
     * Oddiy (bool) o'girish 'f' satrini ROST deb o'qiydi — chunki bo'sh
     * bo'lmagan satr har doim rost. Bu jimgina, lekin qimmat xato: 'f'
     * qaytgan is_infinite mahsulotning qoldig'ini sotuvda kamaytirmay
     * qo'yardi yoki aksincha.
     */
    public static function b(mixed $v): bool
    {
        if (is_bool($v)) {
            return $v;
        }
        if (is_string($v)) {
            $t = strtolower(trim($v));
            return $t !== '' && $t !== '0' && $t !== 'f' && $t !== 'false' && $t !== 'no';
        }
        return (bool)$v;
    }
}
