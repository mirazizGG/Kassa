<?php
/**
 * Zahira nusxa — cron uchun.
 *
 * PHP da fon vazifalari yo'q: jarayon so'rovdan keyin o'ladi. Shuning uchun
 * nusxani cPanel ning Cron Jobs bo'limi chaqiradi.
 *
 * cron misoli (kuniga ikki marta, 12:00 va 22:00):
 *
 *     0 12,22 * * * /usr/local/bin/php /home/FOYDALANUVCHI/kassa/bin/backup.php >> /home/FOYDALANUVCHI/kassa-backup.log 2>&1
 *
 * Skript hech qachon "yiqildi" demaydi — natijani matn bilan yozadi va
 * chiqish kodi bilan bildiradi.
 */

declare(strict_types=1);

if (PHP_SAPI !== 'cli') {
    http_response_code(403);
    exit("Bu skript faqat buyruq satridan ishlaydi.\n");
}

require dirname(__DIR__) . '/app/bootstrap.php';
require APP_DIR . '/Schema.php';
require APP_DIR . '/Backup.php';

$stamp = (new DateTimeImmutable('now', Tz::shopTz()))->format('Y-m-d H:i:s');

if (!env_bool('BACKUP_ENABLED', true)) {
    echo "[$stamp] O'TKAZILDI: BACKUP_ENABLED=false\n";
    exit(0);
}

try {
    $result = Backup::run();
    $uploads = Backup::archiveUploads();
} catch (Throwable $e) {
    echo "[$stamp] XATO: " . $e->getMessage() . "\n";
    exit(1);
}

$parts = [
    'fayl=' . $result['file'],
    'jadval=' . $result['tables'],
    'qator=' . $result['rows'],
    'hajm=' . round($result['bytes'] / 1024) . 'KB',
];
if ($uploads !== null) {
    $parts[] = 'nakladnoylar=' . $uploads;
}

// Vaqtinchalik fayllarni ham tozalab ketamiz: urinishlar hisoblagichlari
// va eskirgan kesh. Ularni hech kim boshqa tozalamaydi.
require_once APP_DIR . '/Cache.php';
$swept = RateLimit::sweep() + Cache::sweep();

// Baza statistikasini yangilaymiz — rejalashtiruvchi to'g'ri indeksni
// tanlashi uchun.
if (Backup::analyze() > 0) {
    $parts[] = 'statistika=yangilandi';
}
if ($swept > 0) {
    $parts[] = "tozalandi=$swept";
}

// Telegramga yuborish — nusxaning bazadan TASHQARIDAGI yagona joyi.
// Sozlanmagan bo'lsa jim o'tkaziladi; xato bo'lsa nusxa baribir diskda qoladi.
$exit = 0;
if (trim((string)env('TELEGRAM_BOT_TOKEN')) !== '') {
    $caption = "💾 Kassa zahira nusxasi\n"
        . "📅 $stamp\n"
        . "📊 {$result['tables']} jadval, {$result['rows']} qator, "
        . round($result['bytes'] / 1024) . ' KB';
    $err = Backup::sendTelegram($result['file'], $caption);
    if ($err === null && $uploads !== null) {
        $err = Backup::sendTelegram($uploads, "🧾 Nakladnoy rasmlari — $stamp");
    }
    if ($err === null) {
        $parts[] = 'telegram=yuborildi';
    } else {
        $parts[] = "telegram=XATO ($err)";
        $exit = 1;
    }
}

echo "[$stamp] " . ($exit === 0 ? 'OK' : 'QISMAN') . ': ' . implode(', ', $parts) . "\n";
exit($exit);
