<?php
/**
 * Audit jurnali.
 *
 * Python'dagi `log_action(db, user_id, action, details)` ning o'rnida.
 * U yerda funksiya faqat flush qilardi — yozuv chaqiruvchi commit bilan
 * birga saqlanardi. Bu yerda ham xuddi shunday: INSERT joriy tranzaksiya
 * ichida bo'ladi, ya'ni asosiy amal bekor qilinsa jurnal yozuvi ham
 * qolmaydi (aks holda jurnalda bo'lmagan ish haqida yozuv turardi).
 *
 * Amal nomi — O'ZBEKCHA KATTA HARFLI: SAVDO, VOZVRAT, TASDIQ_XATO...
 */

declare(strict_types=1);

final class Audit
{
    public static function log(?int $userId, string $action, string $details = ''): void
    {
        try {
            Db::insert('audit_logs', [
                'user_id'    => $userId,
                'action'     => mb_substr($action, 0, 100),
                'details'    => mb_substr($details, 0, 2000),
                'created_at' => Tz::now(),
            ]);
        } catch (Throwable $e) {
            // Jurnal yozilmagani uchun savdo to'xtamasin — lekin izsiz ham
            // qolmasin: server jurnaliga tushadi.
            error_log('[kassa] audit yozilmadi: ' . $e->getMessage());
        }
    }
}
