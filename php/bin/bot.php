<?php
/**
 * Kassa Telegram boti — do'kon kompyuterida doimiy ishlaydigan jarayon.
 *
 *     php bin/bot.php
 *
 * PHP veb-so'rovlari qisqa yashaydi, bot esa doim tinglab turishi kerak —
 * shuning uchun u alohida jarayon. Windows'da uni bot-windows/start-bot.ps1
 * ishga tushiradi va yiqilsa qayta ko'taradi. Mantiqning o'zi app/Bot.php da.
 *
 * IKKI REJIM (.env bo'yicha):
 *
 *   KASSA_API_URL berilgan — KO'PRIK (tavsiya etiladi). Bazaga ulanmaydi.
 *     Telegram xabarini serverning /bot/update ga uzatadi, har 30 soniyada
 *     /bot/tick ni chaqiradi va server qaytargan amallarni (xabar, fayl,
 *     reklama, zahira) Telegramga yetkazadi. Kerak: KASSA_API_URL,
 *     BOT_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_ADMIN_CHAT_ID.
 *
 *   KASSA_API_URL bo'sh — TO'G'RIDAN-TO'G'RI. Bot DATABASE_URL orqali
 *     bazaga o'zi ulanadi (masalan kassa shu kompyuterning o'zida bo'lsa).
 *
 * Holat logs/ ichida: bot-state.json (Telegram offset; to'g'ridan-to'g'ri
 * rejimda kunlik vazifalar va kursorlar ham), bot.lock (bitta nusxa).
 */

declare(strict_types=1);

if (PHP_SAPI !== 'cli') {
    http_response_code(403);
    exit("Bu skript faqat buyruq satridan ishlaydi.\n");
}

require dirname(__DIR__) . '/app/bootstrap.php';
require APP_DIR . '/Schema.php';
require APP_DIR . '/Backup.php';
require APP_DIR . '/Xlsx.php';
require APP_DIR . '/Telegram.php';
require APP_DIR . '/Bot.php';

// Sinov uchun: funksiyalarni tsiklsiz yuklash (define('BOT_NO_LOOP', true)).
if (defined('BOT_NO_LOOP')) {
    return;
}

set_time_limit(0);

if (!Telegram::enabled()) {
    exit("TELEGRAM_BOT_TOKEN sozlanmagan (.env). Bot ishga tushmadi.\n");
}

@mkdir(ROOT_DIR . '/logs', 0775, true);

// Bitta nusxa: ikkita bot bir tokenni tinglasa, Telegram 409 Conflict beradi.
$lock = fopen(ROOT_DIR . '/logs/bot.lock', 'c');
if ($lock === false || !flock($lock, LOCK_EX | LOCK_NB)) {
    exit("Bot allaqachon ishlayapti (logs/bot.lock band).\n");
}

$apiUrl = rtrim(trim((string)env('KASSA_API_URL')), '/');
$relay = $apiUrl !== '';

// =======================================================================
// Ko'prik: server API bilan ishlash
// =======================================================================

function curl_native_ca($ch): void
{
    // Windows'da antivirus HTTPS ni o'z sertifikati bilan tekshiradi.
    if (PHP_OS_FAMILY === 'Windows' && defined('CURLSSLOPT_NATIVE_CA')) {
        curl_setopt($ch, CURLOPT_SSL_OPTIONS, CURLSSLOPT_NATIVE_CA);
    }
}

/** Serverning /bot/... endpointiga so'rov. Javob — massiv, xatoda istisno. */
function api_call(string $method, string $path, ?array $body = null): array
{
    $url = rtrim((string)env('KASSA_API_URL'), '/') . $path;
    $ch = curl_init($url);
    $headers = ['X-Bot-Key: ' . env('BOT_API_KEY', ''), 'Accept: application/json'];
    if ($body !== null) {
        $headers[] = 'Content-Type: application/json';
        curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($body, JSON_UNESCAPED_UNICODE));
    }
    curl_setopt_array($ch, [
        CURLOPT_CUSTOMREQUEST  => $method,
        CURLOPT_HTTPHEADER     => $headers,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_CONNECTTIMEOUT => 20,
        CURLOPT_TIMEOUT        => 120,
    ]);
    curl_native_ca($ch);
    $raw = curl_exec($ch);
    $code = (int)curl_getinfo($ch, CURLINFO_RESPONSE_CODE);
    $err = curl_error($ch);
    curl_close($ch);

    if ($raw === false) {
        throw new RuntimeException("server bilan aloqa yo'q: $err");
    }
    $data = json_decode((string)$raw, true);
    if ($code !== 200 || !is_array($data)) {
        $detail = is_array($data) ? ($data['detail'] ?? '') : substr((string)$raw, 0, 150);
        throw new RuntimeException("server javobi $code: $detail");
    }
    return $data;
}

/**
 * Serverdan API orqali zahira nusxani yuklab oladi.
 * Qaytaradi: [vaqtinchalik fayl yo'li, fayl nomi] yoki null (uploads bo'sh).
 */
function download_backup(bool $uploads): ?array
{
    $url = rtrim((string)env('KASSA_API_URL'), '/') . '/settings/backup/download' . ($uploads ? '?uploads=1' : '');
    $tmp = tempnam(sys_get_temp_dir(), 'kbk');
    $fh = fopen($tmp, 'wb');
    $name = null;
    $ch = curl_init($url);
    curl_setopt_array($ch, [
        CURLOPT_HTTPHEADER     => ['X-Bot-Key: ' . env('BOT_API_KEY', '')],
        CURLOPT_FILE           => $fh,
        CURLOPT_FOLLOWLOCATION => true,
        CURLOPT_CONNECTTIMEOUT => 20,
        CURLOPT_TIMEOUT        => 600,
        CURLOPT_HEADERFUNCTION => function ($ch, $line) use (&$name) {
            if (preg_match('/filename="([^"]+)"/i', $line, $m)) {
                $name = basename($m[1]);
            }
            return strlen($line);
        },
    ]);
    curl_native_ca($ch);
    $ok = curl_exec($ch);
    $code = (int)curl_getinfo($ch, CURLINFO_RESPONSE_CODE);
    $err = curl_error($ch);
    curl_close($ch);
    fclose($fh);

    if ($ok === false || $code !== 200) {
        $body = $code >= 400 ? substr((string)@file_get_contents($tmp), 0, 300) : '';
        @unlink($tmp);
        if ($code === 204) {
            return null;
        }
        throw new RuntimeException("server javobi $code $err $body");
    }
    return [$tmp, $name ?? ($uploads ? 'uploads.zip' : 'backup.sql.gz')];
}

/** Zahira: serverdan yuklab olib, TELEGRAM_ADMIN_CHAT_ID ga yuboradi. */
function relay_backup(): void
{
    $chat = trim((string)env('TELEGRAM_ADMIN_CHAT_ID'));
    if ($chat === '') {
        bot_log("zahira: TELEGRAM_ADMIN_CHAT_ID yo'q — o'tkazildi");
        return;
    }
    try {
        [$tmp, $name] = download_backup(false);
        $size = round(filesize($tmp) / 1024);
        $ok = Telegram::sendDocument($chat, $tmp, $name,
            "💾 <b>Kassa zahira nusxasi</b>\n📅 " . shop_now('Y-m-d H:i') . "\n📦 $size KB");
        @unlink($tmp);
        $up = download_backup(true);
        if ($up !== null) {
            if ($ok) {
                Telegram::sendDocument($chat, $up[0], $up[1], '🧾 Nakladnoy rasmlari');
            }
            @unlink($up[0]);
        }
        bot_log("zahira: $name, $size KB" . ($ok ? ' — telegramga yuborildi' : ' — telegramga YUBORILMADI'));
    } catch (Throwable $e) {
        bot_log('zahira XATO: ' . $e->getMessage());
        Telegram::send($chat, '❌ <b>Zahira nusxa olinmadi!</b>' . "\n" . h($e->getMessage()));
    }
}

/** Server qaytargan amallarni Telegramga yetkazadi. */
function run_actions(array $actions): void
{
    foreach ($actions as $a) {
        try {
            switch ($a['type'] ?? '') {
                case 'send':
                    Telegram::send($a['chat'], (string)$a['text'], $a['keyboard'] ?? null);
                    break;
                case 'document':
                    Telegram::sendDocument($a['chat'], (string)base64_decode((string)$a['data']),
                        (string)$a['filename'], (string)($a['caption'] ?? ''), true);
                    break;
                case 'copy':
                    Telegram::copy($a['chat'], $a['from'], (int)$a['message_id']);
                    usleep(60000); // Telegram cheklovi: sekundiga ~30 xabar
                    break;
                case 'backup':
                    relay_backup();
                    break;
                default:
                    bot_log('noma\'lum amal: ' . json_encode($a));
            }
        } catch (Throwable $e) {
            bot_log('amal XATO: ' . $e->getMessage());
        }
    }
}

// =======================================================================
// Asosiy tsikl
// =======================================================================

$state = state_load();

if ($relay) {
    bot_log("bot ishga tushdi (ko'prik: $apiUrl)");
} else {
    bot_log("bot ishga tushdi (to'g'ridan-to'g'ri, baza: " . Db::driver() . ')');
}

try {
    // Webhook o'rnatilgan bo'lsa getUpdates ishlamaydi.
    Telegram::call('deleteWebhook');
    $me = Telegram::call('getMe');
    bot_log('bot: @' . ($me['username'] ?? '?'));
} catch (Throwable $e) {
    bot_log('Telegram bilan aloqa yo\'q: ' . $e->getMessage());
}

/** @var array<int, array> To'g'ridan-to'g'ri rejimda suhbat bosqichlari */
$conv = [];
$lastTick = 0;
$failures = [];

while (true) {
    // 1. Jadval va ogohlantirishlar (har 30 soniyada).
    if (time() - $lastTick >= 30) {
        $lastTick = time();
        try {
            if ($relay) {
                run_actions(api_call('POST', '/bot/tick', [])['actions'] ?? []);
            } else {
                run_schedule($state);
                check_alerts($state);
                state_save($state);
            }
        } catch (Throwable $e) {
            bot_log('jadval XATO: ' . $e->getMessage());
            if (!$relay) {
                Db::reset();
            }
        }
    }

    // 2. Telegram xabarlari (25 soniyagacha kutadi).
    try {
        $updates = Telegram::call('getUpdates', [
            'offset'          => (int)($state['offset'] ?? 0),
            'timeout'         => 25,
            'allowed_updates' => ['message'],
        ], 40);
    } catch (Throwable $e) {
        bot_log('getUpdates XATO: ' . $e->getMessage());
        if ($e->getCode() === 409) {
            bot_log("Boshqa joyda ham shu bot ishlayapti (eski server?). Uni to'xtating.");
        }
        sleep(15);
        continue;
    }

    foreach ($updates as $u) {
        $id = (int)$u['update_id'];
        try {
            if ($relay) {
                run_actions(api_call('POST', '/bot/update', $u)['actions'] ?? []);
            } else {
                handle_update($u, $conv);
            }
        } catch (Throwable $e) {
            bot_log("xabar #$id XATO: " . $e->getMessage());
            if (!$relay) {
                Db::reset();
            }
            // Server vaqtincha javob bermasa xabarni yo'qotmaymiz: offset
            // surilmaydi va keyingi aylanishda qayta uriniladi. 5 martadan
            // keyin tashlab ketamiz — bitta "buzuq" xabar botni to'xtatmasin.
            $failures[$id] = ($failures[$id] ?? 0) + 1;
            if ($failures[$id] < 5) {
                sleep(10);
                break;
            }
            bot_log("xabar #$id tashlab ketildi (5 urinish)");
        }
        unset($failures[$id]);
        $state['offset'] = $id + 1;
        state_save($state);
    }
}
