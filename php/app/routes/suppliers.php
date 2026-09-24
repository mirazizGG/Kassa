<?php
/**
 * /suppliers — firmalar, kirim nakladnoylari, firmaga to'lovlar.
 *
 * PUL MODELI: Supplier.balance MUSBAT bo'lsa do'kon firmaga QARZDOR.
 * Kirim balansni oshiradi, to'lov kamaytiradi.
 *
 * IKKI KISHILIK NAZORAT: har bir pul harakati BOSHQA xodimning (admin yoki
 * menejer) login-paroli bilan tasdiqlanadi. Ilgari bu tekshiruv na rolni,
 * na tasdiqlovchi boshqa odam ekanini ko'rardi — omborchi o'z amalini o'zi
 * "tasdiqlab" qo'yardi va nazorat umuman ishlamasdi.
 */

declare(strict_types=1);

// Nakladnoy fayli uchun ruxsat etilgan kengaytmalar va hajm chegarasi.
const ALLOWED_INVOICE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'webp', 'gif', 'pdf'];
const MAX_INVOICE_BYTES = 10485760; // 10 MB

/**
 * Firma bilan pul harakatini TASDIQLOVCHI xodim.
 * O'zini o'zi tasdiqlashga yo'l qo'ymaydi.
 */
function verify_confirming_employee(array $requester, ?string $username, ?string $password): array
{
    if ($username !== null && $username === $requester['username']) {
        fail(403, "Amalni o'zingiz tasdiqlay olmaysiz — menejer yoki admin tasdig'i kerak");
    }
    return Auth::verifyApprover($requester, $username, $password);
}

// =======================================================================
// GET /suppliers/
// =======================================================================
Router::get('/', function (): never {
    Auth::require(['admin', 'manager', 'warehouse'], 'Ruxsat berilmagan');
    Http::json(array_map(
        fn($r) => Shape::supplier($r),
        Db::all('SELECT * FROM suppliers ORDER BY name')
    ));
});

// =======================================================================
// POST /suppliers/
// =======================================================================
Router::post('/', function (): never {
    $user = Auth::require(['admin', 'manager', 'warehouse'], 'Ruxsat berilmagan');
    $b = Http::body();

    $name = Http::reqStr($b, 'name', 200, 'Nomi');
    $data = [
        'name'       => $name,
        'phone'      => Http::str($b, 'phone', null, 30, 'Telefon'),
        'address'    => Http::str($b, 'address', null, 300, 'Manzil'),
        'balance'    => 0.0,
        'created_at' => Tz::now(),
    ];

    $id = Db::tx(function () use ($data, $user, $name): int {
        $id = Db::insert('suppliers', $data);
        Audit::log((int)$user['id'], 'YANGI_FIRMA', "Firma qo'shildi: $name (ID: $id)");
        return $id;
    });

    Http::json(Shape::supplier(Db::one('SELECT * FROM suppliers WHERE id = ?', [$id])));
});

// =======================================================================
// POST /suppliers/receipts  (multipart: nakladnoy rasmi bilan)
// =======================================================================
Router::post('/receipts', function (): never {
    $user = Auth::require(['admin', 'manager', 'warehouse'], 'Ruxsat berilmagan');
    $f = Http::form();

    $supplierId = Http::reqInt($f, 'supplier_id', 'Firma');
    // Manfiy yoki NaN summa firma balansini qaytarib bo'lmaydigan darajada
    // buzardi (NaN butun "Firmalar" sahifasini 500 ga olib borardi).
    $totalAmount = Http::reqNum($f, 'total_amount', 'gt', 0, null, 'Summa');
    $note = Http::str($f, 'note', null, 500, 'Izoh');

    $confirming = verify_confirming_employee(
        $user,
        Http::reqStr($f, 'confirm_username', 150, 'Tasdiqlovchi login'),
        Http::reqStr($f, 'confirm_password', 200, 'Tasdiqlovchi parol')
    );

    $supplier = Db::one('SELECT * FROM suppliers WHERE id = ?', [$supplierId]);
    if ($supplier === null) {
        fail(404, 'Firma topilmadi');
    }

    $imagePath = save_invoice_image();

    Db::tx(function () use ($supplierId, $totalAmount, $imagePath, $note, $user, $supplier, $confirming): void {
        Db::insert('supply_receipts', [
            'supplier_id'   => $supplierId,
            'total_amount'  => $totalAmount,
            'invoice_image' => $imagePath,
            'date'          => Tz::now(),
            'note'          => $note,
        ]);

        // Firma balansini ATOMIK oshiramiz (qarzimiz ortadi).
        Db::run('UPDATE suppliers SET balance = balance + ? WHERE id = ?', [$totalAmount, $supplierId]);

        Audit::log((int)$user['id'], 'FIRMA_KIRIM',
            "Firma: {$supplier['name']}. Summa: $totalAmount so'm. Izoh: "
            . ($note ?? '-') . '. Tasdiqladi: @' . $confirming['username']);
    });

    $fresh = Db::one('SELECT balance FROM suppliers WHERE id = ?', [$supplierId]);
    Http::json([
        'message'     => 'Kirim muvaffaqiyatli saqlandi',
        'new_balance' => Db::f($fresh['balance']),
    ]);
});

/**
 * Nakladnoy faylini saqlaydi va URL yo'lini qaytaradi.
 *
 * Kengaytmani ilgari foydalanuvchi bergan fayl nomidan olardik va uni
 * o'zgartirmasdan saqlardik. /uploads papkasi ilovaning O'Z domenidan
 * beriladi, shuning uchun ".html" yuklab, keyin o'sha havolani ochgan
 * xodimning tokenini o'g'irlash mumkin edi. Endi faqat rasm va PDF, nomi
 * esa tasodifiy — foydalanuvchi bergan nom umuman ishlatilmaydi.
 */
function save_invoice_image(): ?string
{
    if (!isset($_FILES['image']) || ($_FILES['image']['error'] ?? UPLOAD_ERR_NO_FILE) === UPLOAD_ERR_NO_FILE) {
        return null;
    }

    $file = $_FILES['image'];
    if ($file['error'] !== UPLOAD_ERR_OK) {
        if ($file['error'] === UPLOAD_ERR_INI_SIZE || $file['error'] === UPLOAD_ERR_FORM_SIZE) {
            fail(400, 'Fayl juda katta (maksimum ' . (MAX_INVOICE_BYTES / 1048576) . ' MB)');
        }
        fail(400, 'Faylni yuklashda xatolik.');
    }

    if ($file['size'] > MAX_INVOICE_BYTES) {
        fail(400, 'Fayl juda katta (maksimum ' . (MAX_INVOICE_BYTES / 1048576) . ' MB)');
    }

    $ext = strtolower(pathinfo((string)($file['name'] ?? ''), PATHINFO_EXTENSION));
    if (!in_array($ext, ALLOWED_INVOICE_EXTENSIONS, true)) {
        fail(400, 'Nakladnoy uchun faqat rasm yoki PDF yuklash mumkin ('
            . implode(', ', ALLOWED_INVOICE_EXTENSIONS) . ')');
    }

    // Mazmunini ham tekshiramiz: kengaytmani almashtirib qo'yish oson.
    if (function_exists('finfo_open')) {
        $finfo = finfo_open(FILEINFO_MIME_TYPE);
        if ($finfo !== false) {
            $mime = (string)finfo_file($finfo, $file['tmp_name']);
            finfo_close($finfo);
            $okMimes = ['image/jpeg', 'image/png', 'image/webp', 'image/gif', 'application/pdf'];
            if (!in_array($mime, $okMimes, true)) {
                fail(400, "Fayl mazmuni rasm yoki PDF emas.");
            }
        }
    }

    $saveDir = UPLOAD_DIR . '/invoices';
    if (!is_dir($saveDir) && !@mkdir($saveDir, 0755, true) && !is_dir($saveDir)) {
        fail(500, "Fayl saqlash papkasini yaratib bo'lmadi.");
    }

    try {
        $filename = bin2hex(random_bytes(16)) . '.' . $ext;
    } catch (Throwable) {
        $filename = uniqid('inv', true) . '.' . $ext;
    }

    if (!move_uploaded_file($file['tmp_name'], "$saveDir/$filename")) {
        fail(500, "Faylni saqlab bo'lmadi.");
    }
    @chmod("$saveDir/$filename", 0644);

    return "/uploads/invoices/$filename";
}

// =======================================================================
// POST /suppliers/payments
// =======================================================================
Router::post('/payments', function (): never {
    $user = Auth::require(['admin', 'manager', 'warehouse'], 'Ruxsat berilmagan');
    $f = Http::form();

    $supplierId = Http::reqInt($f, 'supplier_id', 'Firma');
    $amount = Http::reqNum($f, 'amount', 'gt', 0, null, 'Summa');
    $method = Http::str($f, 'payment_method', 'cash', 40, "To'lov usuli") ?? 'cash';
    $note = Http::str($f, 'note', null, 500, 'Izoh');

    $confirming = verify_confirming_employee(
        $user,
        Http::reqStr($f, 'confirm_username', 150, 'Tasdiqlovchi login'),
        Http::reqStr($f, 'confirm_password', 200, 'Tasdiqlovchi parol')
    );

    $supplier = Db::one('SELECT * FROM suppliers WHERE id = ?', [$supplierId]);
    if ($supplier === null) {
        fail(404, 'Firma topilmadi');
    }

    Db::tx(function () use ($supplierId, $amount, $method, $note, $user, $supplier, $confirming): void {
        Db::insert('supplier_payments', [
            'supplier_id'    => $supplierId,
            'amount'         => $amount,
            'payment_method' => $method,
            'date'           => Tz::now(),
            'note'           => $note,
        ]);

        // Firma balansini ATOMIK kamaytiramiz (qarzimiz kamayadi).
        Db::run('UPDATE suppliers SET balance = balance - ? WHERE id = ?', [$amount, $supplierId]);

        Audit::log((int)$user['id'], 'FIRMA_TOLOV',
            "Firma: {$supplier['name']}. Summa: $amount so'm. Usul: $method. Izoh: "
            . ($note ?? '-') . '. Tasdiqladi: @' . $confirming['username']);
    });

    $fresh = Db::one('SELECT balance FROM suppliers WHERE id = ?', [$supplierId]);
    Http::json([
        'message'     => "To'lov muvaffaqiyatli saqlandi",
        'new_balance' => Db::f($fresh['balance']),
    ]);
});

// =======================================================================
// GET /suppliers/{supplier_id}/history
// =======================================================================
Router::get('/{supplier_id}/history', function (array $p): never {
    Auth::require(['admin', 'manager', 'warehouse'], 'Ruxsat berilmagan');
    $supplierId = Router::id($p, 'supplier_id');

    $receipts = Db::all(
        'SELECT * FROM supply_receipts WHERE supplier_id = ? ORDER BY date DESC, id DESC LIMIT 1000',
        [$supplierId]
    );
    $payments = Db::all(
        'SELECT * FROM supplier_payments WHERE supplier_id = ? ORDER BY date DESC, id DESC LIMIT 1000',
        [$supplierId]
    );

    $history = [];
    foreach ($receipts as $r) {
        $history[] = [
            'type'   => 'receipt',
            'id'     => Db::i($r['id']),
            'amount' => Db::f($r['total_amount']),
            'date'   => Tz::iso($r['date']),
            'image'  => $r['invoice_image'] ?? null,
            'note'   => $r['note'] ?? null,
            '_sort'  => (string)$r['date'],
        ];
    }
    foreach ($payments as $r) {
        $history[] = [
            'type'   => 'payment',
            'id'     => Db::i($r['id']),
            'amount' => Db::f($r['amount']),
            'date'   => Tz::iso($r['date']),
            'method' => $r['payment_method'],
            'note'   => $r['note'] ?? null,
            '_sort'  => (string)$r['date'],
        ];
    }

    usort($history, fn($a, $b) => strcmp($b['_sort'], $a['_sort']));
    foreach ($history as &$h) {
        unset($h['_sort']);
    }

    Http::json($history);
});
