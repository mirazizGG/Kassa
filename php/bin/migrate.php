<?php
/**
 * Ma'lumotlarni ESKI (Python) bazadan YANGI bazaga ko'chirish.
 *
 * Manba: SQLite fayli (backend/market.db) yoki PostgreSQL manzili.
 * Manzil: .env dagi DATABASE_URL (odatda MySQL).
 *
 * Ishlatish:
 *
 *     php bin/migrate.php --source "/path/to/market.db" --dry-run
 *     php bin/migrate.php --source "/path/to/market.db"
 *     php bin/migrate.php --source "postgresql://user:pass@host/db"
 *
 * XAVFSIZLIK CHORALARI (har biri haqiqiy xatoni yopadi):
 *
 *  1. Manba bazada `migrate_shift_times_to_utc` bajarilgan bo'lishi SHART.
 *     Bajarilmagan bo'lsa smena vaqtlari 5 soatga surilib ketadi.
 *  2. Manzil baza BO'SH bo'lishi shart — ustiga yozish ma'lumotni aralashtiradi.
 *  3. Jadvallar TASHQI KALIT tartibida ko'chiriladi.
 *  4. Ko'chirishdan keyin har bir jadvalning qator soni SOLISHTIRILADI.
 *  5. MySQL da AUTO_INCREMENT hisoblagichi to'g'rilanadi — busiz birinchi
 *     yangi savdo "duplicate key" bilan yiqilardi.
 */

declare(strict_types=1);

if (PHP_SAPI !== 'cli') {
    http_response_code(403);
    exit("Bu skript faqat buyruq satridan ishlaydi.\n");
}

require dirname(__DIR__) . '/app/bootstrap.php';
require APP_DIR . '/Schema.php';

// --- Argumentlar --------------------------------------------------------
$options = getopt('', ['source:', 'dry-run', 'force', 'help']);

if (isset($options['help']) || !isset($options['source'])) {
    echo <<<TXT
    Ishlatish:
      php bin/migrate.php --source <manba> [--dry-run] [--force]

      --source   SQLite fayl yo'li yoki postgresql://... manzili
      --dry-run  hech narsa yozmaydi, faqat qator sonini ko'rsatadi
      --force    manzil bazasi bo'sh bo'lmasa ham davom etadi (XAVFLI)

    TXT;
    exit(isset($options['help']) ? 0 : 1);
}

$source = (string)$options['source'];
$dryRun = isset($options['dry-run']);
$force = isset($options['force']);

echo "Kassa — ma'lumotlarni ko'chirish\n";
echo str_repeat('=', 60) . "\n";
echo 'Manba : ' . preg_replace('#://[^@]+@#', '://***@', $source) . "\n";
echo 'Manzil: ' . preg_replace('#://[^@]+@#', '://***@', (string)env('DATABASE_URL', 'sqlite')) . "\n";
echo $dryRun ? "Rejim : QURUQ PROGON (hech narsa yozilmaydi)\n" : "Rejim : HAQIQIY KO'CHIRISH\n";
echo str_repeat('=', 60) . "\n\n";

// --- Manbaga ulanish ----------------------------------------------------
try {
    if (preg_match('#^(postgres|postgresql|pgsql|mysql)://#', $source)) {
        $p = parse_url($source);
        $scheme = strtolower($p['scheme']);
        $host = $p['host'] ?? 'localhost';
        $port = isset($p['port']) ? ';port=' . $p['port'] : '';
        $db = ltrim($p['path'] ?? '', '/');
        $dsn = $scheme === 'mysql'
            ? "mysql:host=$host$port;dbname=$db;charset=utf8mb4"
            : "pgsql:host=$host$port;dbname=$db";
        $src = new PDO($dsn, $p['user'] ?? null, isset($p['pass']) ? rawurldecode($p['pass']) : null);
    } else {
        if (!is_file($source)) {
            echo "XATO: manba fayl topilmadi: $source\n";
            exit(1);
        }
        $src = new PDO('sqlite:' . $source);
    }
    $src->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
    $src->setAttribute(PDO::ATTR_DEFAULT_FETCH_MODE, PDO::FETCH_ASSOC);
} catch (Throwable $e) {
    echo "XATO: manbaga ulanib bo'lmadi — " . $e->getMessage() . "\n";
    exit(1);
}

// --- 1-tekshiruv: vaqt migratsiyasi -------------------------------------
// Bajarilmagan bo'lsa smena vaqtlari server lokal vaqtida yozilgan bo'ladi
// va ko'chirilgandan keyin 5 soatga surilib ketadi.
try {
    // Python versiyasi yozuvni SHIFT_UTC_MIGRATION = "2026_09_shift_times_to_utc"
    // nomi bilan qo'ygan; funksiya nomi (migrate_shift_times_to_utc) ham
    // qabul qilinadi. Ilgari faqat funksiya nomi qidirilardi va migratsiyasi
    // bajarilgan haqiqiy baza ham rad etilardi.
    $marker = $src->prepare("SELECT COUNT(*) FROM schema_migrations WHERE name IN (?, ?)");
    $marker->execute(['2026_09_shift_times_to_utc', 'migrate_shift_times_to_utc']);
    $applied = (int)$marker->fetchColumn() > 0;
} catch (Throwable) {
    $applied = false;
}

$hasShifts = false;
try {
    $hasShifts = (int)$src->query('SELECT COUNT(*) FROM shifts')->fetchColumn() > 0;
} catch (Throwable) {
    // jadval yo'q — muammo emas
}

if ($hasShifts && !$applied && !$force) {
    echo "XATO: manba bazada 'migrate_shift_times_to_utc' bajarilmagan.\n\n";
    echo "  Ya'ni smena vaqtlari hali UTC ga o'tkazilmagan va ko'chirilsa\n";
    echo "  5 soatga surilib ketadi.\n\n";
    echo "  Nima qilish kerak: do'kon kompyuterida eski dasturni YANGI versiya\n";
    echo "  bilan bir marta ishga tushiring (u vaqtlarni o'zi o'giradi), keyin\n";
    echo "  bazadan nusxa olib, shu skriptni qayta chaqiring.\n";
    exit(1);
}
echo $applied ? "Vaqt migratsiyasi: bajarilgan ✓\n\n" : "Vaqt migratsiyasi: smena yo'q, tekshirish shart emas\n\n";

// --- Manzil sxemasi -----------------------------------------------------
if (!$dryRun) {
    echo "Manzil sxemasi tayyorlanmoqda...\n";
    Schema::createAll(false);
    echo "  tayyor.\n\n";
}

$tables = array_keys(Schema::tables());

// --- 2-tekshiruv: manzil bo'shmi ----------------------------------------
if (!$dryRun && !$force) {
    $nonEmpty = [];
    foreach ($tables as $t) {
        try {
            $n = (int)Db::val('SELECT COUNT(*) FROM ' . Db::quoteId($t), [], 0);
            // store_settings va employees da setup.php yaratgan boshlang'ich
            // satrlar bo'lishi mumkin — ular ko'chirishga xalaqit qilmaydi.
            if ($n > 0 && !in_array($t, ['store_settings', 'employees', 'schema_migrations'], true)) {
                $nonEmpty[] = "$t ($n)";
            }
        } catch (Throwable) {
        }
    }
    if ($nonEmpty !== []) {
        echo "XATO: manzil baza bo'sh emas: " . implode(', ', $nonEmpty) . "\n";
        echo "  Ustiga ko'chirish ma'lumotni aralashtirib yuboradi.\n";
        echo "  Bo'sh bazaga ko'chiring yoki --force bilan majburlang (XAVFLI).\n";
        exit(1);
    }
    // setup.php yaratgan boshlang'ich satrlarni tozalaymiz — ular o'rniga
    // haqiqiy ma'lumot keladi.
    Db::run('DELETE FROM store_settings');
    Db::run('DELETE FROM employees');
}

// --- Ko'chirish ---------------------------------------------------------
$counts = [];
$total = 0;

echo str_pad('Jadval', 22) . str_pad('Manba', 10) . "Holat\n";
echo str_repeat('-', 60) . "\n";

foreach ($tables as $table) {
    try {
        $srcCount = (int)$src->query('SELECT COUNT(*) FROM ' . $table)->fetchColumn();
    } catch (Throwable) {
        echo str_pad($table, 22) . str_pad('-', 10) . "manbada yo'q, o'tkazildi\n";
        continue;
    }

    $counts[$table] = $srcCount;
    $total += $srcCount;

    if ($dryRun) {
        echo str_pad($table, 22) . str_pad((string)$srcCount, 10) . "ko'chiriladi\n";
        continue;
    }
    if ($srcCount === 0) {
        echo str_pad($table, 22) . str_pad('0', 10) . "bo'sh\n";
        continue;
    }

    // Manzil jadvalning ustunlari — manbada bo'lmagan ustun NULL qoladi.
    $targetCols = array_keys(Schema::tables()[$table]);

    // Yetim bog'lanishlar: eski SQLite tashqi kalitlarni tekshirmagan,
    // shuning uchun o'chirilgan xodim/mahsulotga ishora qiluvchi satrlar
    // bor (masalan audit_logs.user_id). Yangi baza ularni qabul qilmaydi.
    // Satrning o'zi saqlanadi, faqat mavjud bo'lmagan bog'lanish NULL qilinadi.
    // Ota jadvallar tashqi kalit tartibida OLDIN ko'chirilgan.
    $fkParents = [];
    foreach (Schema::tables()[$table] as $c => $spec) {
        if (str_starts_with($spec, 'fk:')) {
            $parent = substr($spec, 3);
            $fkParents[$c] = array_flip(array_map('intval', array_column(
                Db::all('SELECT id FROM ' . Db::quoteId($parent)), 'id'
            )));
        }
    }
    $detached = 0;

    $stmt = $src->query('SELECT * FROM ' . $table);
    $written = 0;
    $batch = [];

    Db::pdo()->beginTransaction();
    try {
        while (($row = $stmt->fetch(PDO::FETCH_ASSOC)) !== false) {
            $data = [];
            foreach ($targetCols as $c) {
                if (!array_key_exists($c, $row)) {
                    continue;
                }
                $v = $row[$c];
                // SQLite bool'ni 0/1 qilib saqlaydi — shundayligicha ketadi.
                // Vaqtni bir ko'rinishga keltiramiz: 'T' ajratgichli satr
                // MySQL DATETIME uchun ham yaroqli, lekin bir xillik yaxshi.
                if ($v !== null && str_ends_with($c, '_at') || $v !== null && in_array($c, ['date', 'due_date', 'debt_due_date'], true)) {
                    $v = str_replace('T', ' ', (string)$v);
                }
                if ($v !== null && isset($fkParents[$c]) && !isset($fkParents[$c][(int)$v])) {
                    $v = null;
                    $detached++;
                }
                $data[$c] = $v;
            }
            if ($data === []) {
                continue;
            }
            $cols = array_map(fn($c) => Db::quoteId($c), array_keys($data));
            $marks = implode(',', array_fill(0, count($data), '?'));
            Db::run('INSERT INTO ' . Db::quoteId($table) . ' (' . implode(',', $cols) . ") VALUES ($marks)",
                array_values($data));
            $written++;
        }
        Db::pdo()->commit();
    } catch (Throwable $e) {
        Db::pdo()->rollBack();
        echo str_pad($table, 22) . str_pad((string)$srcCount, 10) . 'XATO: ' . $e->getMessage() . "\n";
        exit(1);
    }

    echo str_pad($table, 22) . str_pad((string)$srcCount, 10) . "$written ta yozildi"
        . ($detached > 0 ? " ($detached ta yetim bog'lanish NULL qilindi)" : '') . "\n";
}

echo str_repeat('-', 60) . "\n";
echo "Jami: $total qator\n\n";

if ($dryRun) {
    echo "Quruq progon tugadi — hech narsa yozilmadi.\n";
    echo "Raqamlarni do'kondagi dastur ko'rsatayotgani bilan solishtiring.\n";
    exit(0);
}

// --- AUTO_INCREMENT / ketma-ketliklarni to'g'rilash ---------------------
// Busiz birinchi yangi savdo "duplicate key" bilan yiqilardi.
echo "Hisoblagichlar to'g'rilanmoqda...\n";
foreach ($tables as $table) {
    try {
        $max = (int)Db::val('SELECT COALESCE(MAX(id), 0) FROM ' . Db::quoteId($table), [], 0);
        if ($max === 0) {
            continue;
        }
        if (Db::isMysql()) {
            Db::pdo()->exec('ALTER TABLE ' . Db::quoteId($table) . ' AUTO_INCREMENT = ' . ($max + 1));
        } elseif (Db::isPgsql()) {
            Db::pdo()->exec("SELECT setval(pg_get_serial_sequence('$table', 'id'), $max)");
        }
        // SQLite AUTOINCREMENT o'zi MAX(id) dan davom ettiradi.
    } catch (Throwable $e) {
        echo "  OGOHLANTIRISH: $table — " . $e->getMessage() . "\n";
    }
}
echo "  tayyor.\n\n";

// --- Solishtirish -------------------------------------------------------
echo "Qatorlar solishtirilmoqda...\n";
$mismatch = false;
foreach ($counts as $table => $expected) {
    $actual = (int)Db::val('SELECT COUNT(*) FROM ' . Db::quoteId($table), [], 0);
    if ($actual !== $expected) {
        echo "  FARQ: $table — manbada $expected, manzilda $actual\n";
        $mismatch = true;
    }
}

if ($mismatch) {
    echo "\nKO'CHIRISHDA FARQ BOR — bazani ISHLATMANG, sababini aniqlang.\n";
    exit(1);
}

Schema::markMigration('php_port_' . date('Ymd_His'));

echo "  hammasi mos ✓\n\n";
echo "Ko'chirish muvaffaqiyatli tugadi.\n";
echo "Endi saytga eski login va parolingiz bilan kiring.\n";
exit(0);
