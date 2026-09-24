<?php
/**
 * /system — versiya va ilova ichidan yangilash.
 *
 * SHARED HOSTING'DA YANGILASH O'CHIRILGAN va bu ATAYIN.
 *
 * Python versiyasida bu endpoint `git pull` qilib, frontendni qayta yig'ib,
 * serverni qayta ishga tushirardi. Bundan tashqari `Login.jsx` uni HAR
 * KIRISHDA avtomatik chaqirardi — ya'ni savdo o'rtasida kirgan istalgan
 * kassir jimgina yangilanishni boshlab yuborardi va kassa bir necha
 * daqiqaga to'xtardi.
 *
 * Bu yerda endpointlar SAQLANGAN (frontend ularni chaqiradi va javob
 * bo'lmasa xato ko'rsatadi), lekin ular hech narsa BAJARMAYDI: faqat
 * "yangilash o'chirilgan" deb halol javob qaytaradi. Yangilash yangi
 * fayllarni yuklash orqali qo'lda qilinadi — do'kon yopilgandan keyin.
 */

declare(strict_types=1);

/** Yangilash umuman yoqilganmi? Shared hosting'da har doim false. */
function self_update_allowed(): bool
{
    return env_bool('ALLOW_SELF_UPDATE', false);
}

// =======================================================================
// GET /system/version
// =======================================================================
Router::get('/version', function (): never {
    Auth::user();
    Http::json([
        'current'  => APP_VERSION,
        'runtime'  => 'php-' . PHP_VERSION,
        'running'  => false,
        'enabled'  => self_update_allowed(),
    ]);
});

// =======================================================================
// GET /system/update-check
// =======================================================================
Router::get('/update-check', function (): never {
    Auth::user();
    // enabled: false — frontend "Yangilash" tugmasini umuman ko'rsatmaydi.
    Http::json([
        'enabled'          => self_update_allowed(),
        'update_available' => false,
        'behind_count'     => 0,
        'current'          => APP_VERSION,
        'message'          => self_update_allowed()
            ? 'Yangilanish topilmadi.'
            : "Ilova ichidan yangilash o'chirilgan.",
    ]);
});

// =======================================================================
// GET /system/update-status
// =======================================================================
Router::get('/update-status', function (): never {
    Auth::user();
    // ok: true + running: false — "kuting" oynasi darhol yopiladi.
    Http::json([
        'ok'      => true,
        'running' => false,
        'step'    => null,
        'message' => null,
        'current' => APP_VERSION,
    ]);
});

// =======================================================================
// POST /system/update
// =======================================================================
Router::post('/update', function (): never {
    // FAQAT ADMIN. Ilgari bu endpoint rol tekshirmasdi va Login.jsx uni
    // har kirishda avtomatik chaqirardi.
    Auth::require(['admin'], "Yangilashni faqat admin boshlashi mumkin");

    if (!self_update_allowed()) {
        fail(403, "Ilova ichidan yangilash o'chirilgan. Yangi fayllarni "
            . "qo'lda yuklang (do'kon yopilgandan keyin).");
    }

    // Yoqilgan bo'lsa ham, bu muhitda bajaradigan narsa yo'q: PHP versiyasi
    // git ham, qurish jarayonini ham boshqarmaydi.
    fail(501, "Bu serverda avtomatik yangilash qo'llab-quvvatlanmaydi.");
});
