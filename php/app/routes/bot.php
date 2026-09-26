<?php
/**
 * /bot — do'kon kompyuteridagi bot ko'prigi uchun API.
 *
 * Ko'prik (bin/bot.php, KASSA_API_URL berilgan) Telegramdan xabarni oladi va
 * shu yerga yuboradi; server bazadan kerakli narsani topib, "amallar"
 * ro'yxatini qaytaradi (xabar yuborish, fayl, reklama nusxasi, zahira).
 * Ko'prik ularni Telegramga yetkazadi. Shunday qilib baza paroli do'kon
 * kompyuterida umuman bo'lmaydi va baza internetga ochilmaydi.
 *
 *   POST /bot/update  — Telegram update (JSON) -> {actions: [...]}
 *   POST /bot/tick    — jadval + ogohlantirishlar -> {actions: [...]}
 *   GET  /bot/ping    — kalit va aloqani tekshirish
 *
 * Kirish: `X-Bot-Key: <BOT_API_KEY>` (kamida 32 belgi). Kalit — botning
 * o'zi: kim bilsa, bot nomidan ish ko'ra oladi. Faqat noto'g'ri urinishlar
 * IP bo'yicha soatiga 10 ta bilan cheklanadi.
 */

declare(strict_types=1);

require_once APP_DIR . '/Schema.php';
require_once APP_DIR . '/Backup.php';
require_once APP_DIR . '/Xlsx.php';
require_once APP_DIR . '/Telegram.php';
require_once APP_DIR . '/Bot.php';

const BOT_CONV_FILE = ROOT_DIR . '/logs/bot-conv.json';

function bot_api_auth(): void
{
    $given = (string)($_SERVER['HTTP_X_BOT_KEY'] ?? '');
    $key = (string)env('BOT_API_KEY', '');
    if (strlen($key) < 32 || $given === '' || !hash_equals($key, $given)) {
        if (!RateLimit::hit('botkey:' . Http::clientIp(), 10, 3600)) {
            fail(429, "Juda ko'p urinish. Keyinroq qayta urinib ko'ring.");
        }
        fail(401, "Bot kaliti noto'g'ri");
    }
    @mkdir(ROOT_DIR . '/logs', 0775, true);
    set_time_limit(120);
}

/** Suhbat bosqichlari (ro'yxatdan o'tish, reklama) so'rovlar orasida faylda. */
function bot_conv_load(): array
{
    $raw = @file_get_contents(BOT_CONV_FILE);
    $data = $raw ? json_decode($raw, true) : null;
    return is_array($data) ? $data : [];
}

function bot_conv_save(array $conv): void
{
    file_put_contents(BOT_CONV_FILE, json_encode($conv, JSON_UNESCAPED_UNICODE), LOCK_EX);
}

// =======================================================================
// POST /bot/update
// =======================================================================
Router::post('/update', function (): never {
    bot_api_auth();
    $update = Http::body();

    Telegram::collect();
    $conv = bot_conv_load();
    try {
        handle_update($update, $conv);
    } catch (Throwable $e) {
        bot_log('server: xabarni qayta ishlashda XATO: ' . $e->getMessage());
        Telegram::take();
        $chat = $update['message']['chat']['id'] ?? null;
        if ($chat !== null) {
            Telegram::send($chat, "Kechirasiz, xatolik yuz berdi. Birozdan keyin qayta urinib ko'ring.");
        }
    }
    bot_conv_save($conv);

    Http::json(['actions' => Telegram::take()]);
});

// =======================================================================
// POST /bot/tick
// =======================================================================
Router::post('/tick', function (): never {
    bot_api_auth();

    Telegram::collect();
    $state = state_load();
    run_schedule($state);
    check_alerts($state);
    state_save($state);

    Http::json(['actions' => Telegram::take()]);
});

// =======================================================================
// GET /bot/ping
// =======================================================================
Router::get('/ping', function (): never {
    bot_api_auth();
    Http::json([
        'status'   => 'ok',
        'products' => (int)Db::val('SELECT COUNT(*) FROM products', [], 0),
        'clients'  => (int)Db::val('SELECT COUNT(*) FROM clients', [], 0),
        'time'     => shop_now('Y-m-d H:i'),
        'schedule' => [
            'report' => env('BOT_REPORT_TIME', '22:00'),
            'backup' => env('BACKUP_TIME', '22:00'),
            'debts'  => env('DEBT_REMINDER_TIME', '09:00'),
        ],
    ]);
});
