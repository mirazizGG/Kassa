<?php
/**
 * Bot sozlamalarini tekshirish: baza va Telegram bilan aloqa.
 *
 *     php bin/bot-check.php
 *
 * O'rnatuvchi (bot-windows/install.ps1) shuni chaqiradi. Hech narsa yozmaydi.
 * Chiqish kodi: 0 — hammasi joyida, 1 — nimadir ishlamayapti.
 */

declare(strict_types=1);

if (PHP_SAPI !== 'cli') {
    http_response_code(403);
    exit("Bu skript faqat buyruq satridan ishlaydi.\n");
}

require dirname(__DIR__) . '/app/bootstrap.php';
require APP_DIR . '/Telegram.php';

$ok = true;

echo 'PHP: ' . PHP_VERSION . "\n";
foreach (['curl', 'openssl', 'mbstring', 'pdo_mysql', 'zip'] as $ext) {
    if (!extension_loaded($ext)) {
        echo "  XATO: PHP kengaytmasi yo'q: $ext\n";
        $ok = false;
    }
}

$url = (string)env('DATABASE_URL', '');
echo 'Baza: ' . preg_replace('#://[^@]+@#', '://***@', $url) . "\n";
try {
    $products = (int)Db::val('SELECT COUNT(*) FROM products', [], 0);
    $clients = (int)Db::val('SELECT COUNT(*) FROM clients', [], 0);
    $sales = (int)Db::val('SELECT COUNT(*) FROM sales', [], 0);
    echo "  OK ($products mahsulot, $clients mijoz, $sales chek)\n";
} catch (Throwable $e) {
    echo "  XATO: bazaga ulanib bo'lmadi. DATABASE_URL ni va hostingda Remote MySQL\n"
        . "  ruxsatini (shu kompyuterning IP manzili) tekshiring.\n";
    $ok = false;
}

echo "Telegram:\n";
if (!Telegram::enabled()) {
    echo "  XATO: TELEGRAM_BOT_TOKEN bo'sh\n";
    $ok = false;
} else {
    try {
        $me = Telegram::call('getMe');
        echo '  OK (@' . ($me['username'] ?? '?') . ")\n";
    } catch (Throwable $e) {
        echo '  XATO: ' . $e->getMessage() . "\n";
        $ok = false;
    }
}
if (trim((string)env('TELEGRAM_ADMIN_CHAT_ID')) === '') {
    echo "  OGOHLANTIRISH: TELEGRAM_ADMIN_CHAT_ID bo'sh — zahira nusxa yuborilmaydi\n";
}

$api = rtrim(trim((string)env('KASSA_API_URL')), '/');
if ($api !== '') {
    echo "Zahira: server API orqali ($api)\n";
    if (strlen((string)env('BACKUP_API_KEY', '')) < 32) {
        echo "  XATO: BACKUP_API_KEY yo'q yoki 32 belgidan qisqa\n";
        $ok = false;
    }
    $ch = curl_init("$api/health");
    curl_setopt_array($ch, [CURLOPT_RETURNTRANSFER => true, CURLOPT_TIMEOUT => 20]);
    if (PHP_OS_FAMILY === 'Windows' && defined('CURLSSLOPT_NATIVE_CA')) {
        curl_setopt($ch, CURLOPT_SSL_OPTIONS, CURLSSLOPT_NATIVE_CA);
    }
    curl_exec($ch);
    $code = (int)curl_getinfo($ch, CURLINFO_RESPONSE_CODE);
    $err = curl_error($ch);
    curl_close($ch);
    if ($code === 200) {
        echo "  OK (server javob berdi)\n";
    } else {
        echo "  XATO: server javob bermadi ($code $err)\n";
        $ok = false;
    }
} else {
    echo "Zahira: bazadan to'g'ridan-to'g'ri (KASSA_API_URL bo'sh)\n";
}

echo "Jadval: hisobot " . env('BOT_REPORT_TIME', '22:00') . ', zahira ' . env('BACKUP_TIME', '22:00')
    . ', qarz eslatmasi ' . env('DEBT_REMINDER_TIME', '09:00') . ' (' . SHOP_TIMEZONE . ")\n";

echo $ok ? "\nHammasi joyida.\n" : "\nMUAMMO BOR — yuqoridagi XATO qatorlarini tuzating.\n";
exit($ok ? 0 : 1);
