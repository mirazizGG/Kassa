<?php
/**
 * Bot sozlamalarini tekshirish: server API (yoki baza) va Telegram bilan aloqa.
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
$api = rtrim(trim((string)env('KASSA_API_URL')), '/');

echo 'PHP: ' . PHP_VERSION . "\n";
$need = ['curl', 'openssl', 'mbstring'];
if ($api === '') {
    $need[] = 'pdo_mysql';
    $need[] = 'zip';
}
foreach ($need as $ext) {
    if (!extension_loaded($ext)) {
        echo "  XATO: PHP kengaytmasi yo'q: $ext\n";
        $ok = false;
    }
}

if ($api !== '') {
    echo "Rejim: ko'prik — server API orqali ($api)\n";
    if (strlen((string)env('BOT_API_KEY', '')) < 32) {
        echo "  XATO: BOT_API_KEY yo'q yoki 32 belgidan qisqa\n";
        $ok = false;
    } else {
        $ch = curl_init("$api/bot/ping");
        curl_setopt_array($ch, [
            CURLOPT_HTTPHEADER     => ['X-Bot-Key: ' . env('BOT_API_KEY'), 'Accept: application/json'],
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT        => 20,
        ]);
        if (PHP_OS_FAMILY === 'Windows' && defined('CURLSSLOPT_NATIVE_CA')) {
            curl_setopt($ch, CURLOPT_SSL_OPTIONS, CURLSSLOPT_NATIVE_CA);
        }
        $raw = curl_exec($ch);
        $code = (int)curl_getinfo($ch, CURLINFO_RESPONSE_CODE);
        $err = curl_error($ch);
        curl_close($ch);
        $data = json_decode((string)$raw, true);
        if ($code === 200 && ($data['status'] ?? '') === 'ok') {
            echo "  OK (server: {$data['products']} mahsulot, {$data['clients']} mijoz, vaqt {$data['time']})\n";
            $s = $data['schedule'] ?? [];
            echo '  Jadval (serverda): hisobot ' . ($s['report'] ?? '?') . ', zahira ' . ($s['backup'] ?? '?')
                . ', qarz eslatmasi ' . ($s['debts'] ?? '?') . "\n";
        } elseif ($code === 401) {
            echo "  XATO: server kalitni qabul qilmadi — BOT_API_KEY serverdagi .env bilan bir xil emas\n";
            $ok = false;
        } elseif ($code === 404 || (is_string($raw) && str_contains($raw, '<html'))) {
            echo "  XATO: serverda /bot API yo'q — serverdagi kassa kodini yangilang\n";
            $ok = false;
        } else {
            echo "  XATO: server javob bermadi ($code $err)\n";
            $ok = false;
        }
    }
} else {
    $url = (string)env('DATABASE_URL', '');
    echo "Rejim: to'g'ridan-to'g'ri baza — " . preg_replace('#://[^@]+@#', '://***@', $url) . "\n";
    try {
        $products = (int)Db::val('SELECT COUNT(*) FROM products', [], 0);
        $clients = (int)Db::val('SELECT COUNT(*) FROM clients', [], 0);
        echo "  OK ($products mahsulot, $clients mijoz)\n";
    } catch (Throwable $e) {
        echo "  XATO: bazaga ulanib bo'lmadi — DATABASE_URL ni tekshiring\n";
        $ok = false;
    }
    echo 'Jadval: hisobot ' . env('BOT_REPORT_TIME', '22:00') . ', zahira ' . env('BACKUP_TIME', '22:00')
        . ', qarz eslatmasi ' . env('DEBT_REMINDER_TIME', '09:00') . "\n";
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

echo $ok ? "\nHammasi joyida.\n" : "\nMUAMMO BOR — yuqoridagi XATO qatorlarini tuzating.\n";
exit($ok ? 0 : 1);
