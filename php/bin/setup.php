<?php
/**
 * Bazani tayyorlash: jadvallar, indekslar va birinchi admin.
 *
 * Ishlatish (php/ papkasidan):
 *
 *     php bin/setup.php
 *
 * Skript IDEMPOTENT: qayta ishlatish xavfsiz. Sxema o'zgarganda (yangi ustun
 * qo'shilganda) ham shuni qayta ishlatish kerak — yetishmayotgan ustunlar
 * o'z-o'zidan qo'shiladi.
 */

declare(strict_types=1);

if (PHP_SAPI !== 'cli') {
    http_response_code(403);
    exit("Bu skript faqat buyruq satridan ishlaydi.\n");
}

require dirname(__DIR__) . '/app/bootstrap.php';
require APP_DIR . '/Schema.php';

echo "Kassa — bazani tayyorlash\n";
echo str_repeat('=', 50) . "\n";

// --- Papkalar -----------------------------------------------------------
foreach ([ROOT_DIR . '/logs', ROOT_DIR . '/logs/ratelimit', ROOT_DIR . '/backups',
          UPLOAD_DIR, UPLOAD_DIR . '/invoices'] as $dir) {
    if (!is_dir($dir)) {
        if (@mkdir($dir, 0700, true)) {
            echo "  papka yaratildi: " . basename($dir) . "\n";
        } else {
            echo "  OGOHLANTIRISH: papka yaratilmadi: $dir\n";
        }
    }
}

// --- Ulanish ------------------------------------------------------------
try {
    $driver = Db::driver();
} catch (Throwable $e) {
    echo "\nXATO: bazaga ulanib bo'lmadi.\n";
    echo "  " . $e->getMessage() . "\n";
    echo "\n.env dagi DATABASE_URL ni tekshiring. Masalan:\n";
    echo "  DATABASE_URL=mysql://foydalanuvchi:parol\@localhost/baza_nomi\n";
    exit(1);
}
echo "Baza: $driver\n\n";

// --- Sxema --------------------------------------------------------------
echo "Sxema tayyorlanmoqda...\n";
Schema::createAll(true);
echo "  jadval va indekslar joyida.\n\n";

// --- Birinchi admin -----------------------------------------------------
$admin = Db::one("SELECT username FROM employees WHERE role = 'admin' ORDER BY id LIMIT 1");

if ($admin !== null) {
    echo "Admin allaqachon bor: {$admin['username']} — tegilmadi.\n";
} else {
    $password = env('PRIMARY_ADMIN_PASSWORD');
    if ($password === null || $password === '') {
        if (IS_PROD) {
            echo "XATO: PRIMARY_ADMIN_PASSWORD o'rnatilmagan va bazada admin yo'q.\n";
            echo "  .env ga  PRIMARY_ADMIN_PASSWORD=<kuchli-parol>  qo'shing.\n";
            exit(1);
        }
        $password = DEV_ADMIN_PASSWORD;
        echo "  Ogohlantirish: PRIMARY_ADMIN_PASSWORD yo'q, ishlab chiqish paroli ishlatildi.\n";
    }

    Db::insert('employees', [
        'username'        => PRIMARY_ADMIN_USERNAME,
        'hashed_password' => Auth::hashPassword($password),
        'role'            => 'admin',
        'permissions'     => 'all',
        'is_active'       => 1,
    ]);
    echo "Admin yaratildi: " . PRIMARY_ADMIN_USERNAME . "\n";
}

// --- Sozlamalar satri ---------------------------------------------------
$settings = Db::one('SELECT id FROM store_settings ORDER BY id LIMIT 1');
if ($settings === null) {
    Db::insert('store_settings', [
        'name'                => "Mening Do'konim",
        'low_stock_threshold' => 5,
        'bonus_percentage'    => 1.0,
        'debt_reminder_days'  => 3,
    ]);
    echo "Do'kon sozlamalari yaratildi.\n";
}

echo "\n" . str_repeat('=', 50) . "\n";
echo "Tayyor.\n";
exit(0);
