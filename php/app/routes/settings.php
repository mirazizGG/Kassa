<?php
/**
 * /settings — do'kon sozlamalari va qo'lda zahira nusxa.
 *
 * Sozlamalar YAGONA satr bo'lishi kerak, lekin buni faqat kelishuv ushlab
 * turadi. Shuning uchun har joyda `ORDER BY id LIMIT 1` — tartibsiz
 * "birinchisini ol" da baza satrlar ketma-ketligini KAFOLATLAMAYDI va
 * ikkinchi satr paydo bo'lsa, sozlamalar so'rovdan so'rovga "sakrab"
 * turardi.
 */

declare(strict_types=1);

/** Sozlamalar satrini oladi, bo'lmasa yaratadi. */
function settings_row(): array
{
    $row = Db::one('SELECT * FROM store_settings ORDER BY id LIMIT 1');
    if ($row !== null) {
        return $row;
    }
    $id = Db::insert('store_settings', [
        'name'                => "Mening Do'konim",
        'low_stock_threshold' => 5,
        'bonus_percentage'    => 1.0,
        'debt_reminder_days'  => 3,
    ]);
    return Db::one('SELECT * FROM store_settings WHERE id = ?', [$id]) ?? [];
}

// =======================================================================
// GET /settings
// =======================================================================
Router::get('', function (): never {
    // Sozlamalarni BARCHA xodimlar o'qiy olishi kerak (masalan kassaga
    // low_stock_threshold va bonus foizi kerak).
    Auth::user();
    Http::json(Shape::setting(settings_row()));
});

// =======================================================================
// PUT /settings
// =======================================================================
Router::put('', function (): never {
    $user = Auth::require(['admin'], 'Ruxsat berilmagan');
    $b = Http::body();

    $current = settings_row();

    $data = [
        'name'                => Http::reqStr($b, 'name', 200, 'Do\'kon nomi'),
        'address'             => Http::str($b, 'address', null, 300, 'Manzil'),
        'phone'               => Http::str($b, 'phone', null, 30, 'Telefon'),
        'header_text'         => Http::str($b, 'header_text', null, 500, 'Chek tepasi'),
        'footer_text'         => Http::str($b, 'footer_text', null, 500, 'Chek pasti'),
        'logo_url'            => Http::str($b, 'logo_url', null, 500, 'Logotip'),
        'low_stock_threshold' => Http::int($b, 'low_stock_threshold', 5, 'Kam qoldiq chegarasi'),
        // Bonus foizi bevosita pulga aylanadi — chegarasiz qoldirib
        // bo'lmaydi. 0-100 oralig'i.
        'bonus_percentage'    => Http::num($b, 'bonus_percentage', 1.0, 'ge', 0, 100, 'Bonus foizi'),
        'debt_reminder_days'  => Http::int($b, 'debt_reminder_days', 3, 'Eslatish kunlari'),
    ];

    if ($data['low_stock_threshold'] !== null && $data['low_stock_threshold'] < 0) {
        fail(422, "«Kam qoldiq chegarasi» manfiy bo'lishi mumkin emas.");
    }
    if ($data['debt_reminder_days'] !== null
        && ($data['debt_reminder_days'] < 0 || $data['debt_reminder_days'] > 365)) {
        fail(422, "«Eslatish kunlari» 0 dan 365 gacha bo'lishi kerak.");
    }

    Db::tx(function () use ($data, $current, $user): void {
        Db::update('store_settings', (int)$current['id'], $data);
        Audit::log((int)$user['id'], 'SOZLAMALAR_OZGARDI',
            "Do'kon sozlamalari yangilandi: {$data['name']}");
    });

    Http::json(Shape::setting(Db::one('SELECT * FROM store_settings WHERE id = ?', [(int)$current['id']])));
});

// =======================================================================
// POST /settings/backup
// =======================================================================
Router::post('/backup', function (): never {
    // Admin, menejer va omborchi bosishi mumkin (kassir omborga kira olmaydi).
    $user = Auth::require(['admin', 'manager', 'warehouse'], 'Ruxsat berilmagan');

    if (!env_bool('BACKUP_ENABLED', true)) {
        fail(
            409,
            "Zahira nusxa sozlamalarda o'chirilgan (BACKUP_ENABLED=false). "
            . "Yoqish uchun .env faylini o'zgartiring."
        );
    }

    require_once APP_DIR . '/Schema.php';
    require_once APP_DIR . '/Backup.php';

    try {
        $result = Backup::run();
        $uploads = Backup::archiveUploads();
    } catch (Throwable $e) {
        error_log('[kassa] zahira xatosi: ' . $e->getMessage());
        fail(500, 'Zahira olishda xatolik: ' . $e->getMessage());
    }

    $parts = ['Baza ✓'];
    if ($uploads !== null) {
        $parts[] = 'Nakladnoylar ✓';
    }

    Db::tx(function () use ($user, $result, $parts): void {
        Audit::log((int)$user['id'], 'ZAHIRA_NUSXA',
            "Qo'lda zahira: {$result['file']} ({$result['rows']} qator). Manzillar: "
            . implode(', ', $parts));
    });

    Http::json([
        'status'   => 'success',
        'message'  => 'Zahira nusxasi olindi — ' . implode(', ', $parts),
        'filename' => $result['file'],
        'detail'   => [
            'local'   => $result['file'],
            'uploads' => $uploads,
            'tables'  => $result['tables'],
            'rows'    => $result['rows'],
            'size_kb' => (int)round($result['bytes'] / 1024),
        ],
    ]);
});
