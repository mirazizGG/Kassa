<?php
/**
 * /crm — mijozlar, qarzlar, qarz to'lovlari.
 *
 * PUL MODELI: Client.balance MANFIY bo'lsa mijoz do'konga qarzdor, MUSBAT
 * bo'lsa oldindan to'lagan. Qarz to'lovi balansni OSHIRADI.
 *
 * MARSHRUT TARTIBI MUHIM: "/clients/debts" "/clients/{client_id}" dan
 * OLDIN turishi shart, aks holda "debts" so'zi id deb o'qiladi.
 */

declare(strict_types=1);

// pos.php dagi CASH_METHODS bilan bir xil bo'lishi shart: smena kassasi
// aynan shu usullardagi to'lovlarni hisoblaydi.
const CASH_PAYMENT_METHODS = ['cash', 'naqd'];

// =======================================================================
// GET /crm/clients
// =======================================================================
Router::get('/clients', function (): never {
    $user = Auth::user();
    if (!in_array($user['role'], ['admin', 'manager', 'cashier'], true)) {
        fail(403, 'Ruxsat berilmagan');
    }

    // Qidiruv ixtiyoriy — mijoz ko'p bo'lganda butun ro'yxatni tortmaslik uchun.
    $q = Http::q('search');
    if ($q !== null && $q !== '') {
        $rows = Db::all(
            'SELECT * FROM clients WHERE ' . Db::ilike('name') . ' OR ' . Db::ilike('phone')
            . ' ORDER BY name LIMIT 500',
            ["%$q%", "%$q%"]
        );
    } else {
        $rows = Db::all('SELECT * FROM clients ORDER BY id');
    }

    Http::json(array_map(fn($r) => Shape::client($r), $rows));
});

// =======================================================================
// POST /crm/clients
// =======================================================================
Router::post('/clients', function (): never {
    $user = Auth::user();
    $b = Http::body();

    // DIQQAT: balance va bonus_balance bu yerda ATAYIN qabul qilinmaydi.
    // Ilgari ular ham kirishdan olinardi — natijada istalgan xodim
    // POST /crm/clients bilan o'ziga bonus "chizib" olib, kassada pul
    // o'rnida sarflay olardi. Balans faqat sotuv va to'lov orqali o'zgaradi.
    $data = [
        'name'          => Http::reqStr($b, 'name', 200, 'Ism'),
        'phone'         => Http::str($b, 'phone', null, 30, 'Telefon'),
        'telegram_id'   => Http::int($b, 'telegram_id'),
        'debt_due_date' => Tz::parseFilterDate(Http::str($b, 'debt_due_date', null, 40)),
        'balance'       => 0.0,
        'bonus_balance' => 0.0,
        'created_at'    => Tz::now(),
    ];

    $id = Db::tx(function () use ($data, $user): int {
        $id = Db::insert('clients', $data);
        Audit::log((int)$user['id'], 'YANGI_MIJOZ',
            "Mijoz qo'shildi: {$data['name']} (Tel: " . ($data['phone'] ?? '-') . ')');
        return $id;
    });

    Http::json(Shape::client(Db::one('SELECT * FROM clients WHERE id = ?', [$id])));
});

// =======================================================================
// GET /crm/clients/debts   — "{client_id}" dan OLDIN!
// =======================================================================
Router::get('/clients/debts', function (): never {
    Auth::user();

    $rows = Db::all(
        'SELECT * FROM clients WHERE balance < 0
         ORDER BY CASE WHEN debt_due_date IS NULL THEN 1 ELSE 0 END, debt_due_date ASC'
    );

    $out = [];
    foreach ($rows as $c) {
        // KALENDAR kunlari farqi, do'kon vaqti bo'yicha. Oddiy ayirma
        // ishlatilsa, muddat kunining O'ZIDA ham natija -1 chiqib, mijozga
        // "muddati o'tgan" deb yozilardi.
        $days = Tz::daysUntil($c['debt_due_date'] ?? null);

        $status = 'no_due_date';
        if ($days !== null) {
            $status = match (true) {
                $days < 0   => 'overdue',
                $days === 0 => 'due_today',
                $days <= 3  => 'due_soon',
                default     => 'upcoming',
            };
        }

        $out[] = [
            'id'             => Db::i($c['id']),
            'name'           => $c['name'],
            'phone'          => $c['phone'] ?? null,
            'debt_amount'    => abs(Db::f($c['balance'])),
            'due_date'       => Tz::iso($c['debt_due_date'] ?? null),
            'days_until_due' => $days,
            'status'         => $status,
        ];
    }

    Http::json($out);
});

// =======================================================================
// GET /crm/clients/{client_id}/history
// =======================================================================
Router::get('/clients/{client_id}/history', function (array $p): never {
    Auth::user();
    $clientId = Router::id($p, 'client_id');

    $client = Db::one('SELECT * FROM clients WHERE id = ?', [$clientId]);
    if ($client === null) {
        fail(404, 'Mijoz topilmadi');
    }

    $sales = Db::all(
        'SELECT * FROM sales WHERE client_id = ? ORDER BY created_at DESC, id DESC LIMIT 500',
        [$clientId]
    );

    // Mahsulot nomlarini bitta so'rov bilan olamiz (N+1 yo'q).
    $saleIds = array_map(fn($s) => (int)$s['id'], $sales);
    $itemsBySale = [];
    if ($saleIds !== []) {
        $itemRows = Db::all(
            'SELECT si.sale_id, si.quantity, si.price, p.name
             FROM sale_items si LEFT JOIN products p ON p.id = si.product_id
             WHERE si.sale_id IN (' . Db::marks($saleIds) . ') ORDER BY si.id',
            $saleIds
        );
        foreach ($itemRows as $ir) {
            $itemsBySale[(int)$ir['sale_id']][] = [
                'name'     => $ir['name'] ?? "Mahsulot o'chirilgan",
                'quantity' => Db::f($ir['quantity']),
                'price'    => Db::f($ir['price']),
            ];
        }
    }

    $cashiers = Shape::lookup('employees', array_column($sales, 'cashier_id'));

    $payments = Db::all(
        'SELECT * FROM payments WHERE client_id = ? ORDER BY created_at DESC, id DESC LIMIT 500',
        [$clientId]
    );
    $payEmployees = Shape::lookup('employees', array_column($payments, 'created_by'));

    Http::json([
        'client' => [
            'id'            => Db::i($client['id']),
            'name'          => $client['name'],
            'balance'       => Db::f($client['balance']),
            'debt_due_date' => Tz::iso($client['debt_due_date'] ?? null),
        ],
        'sales' => array_map(fn($s) => [
            'id'           => Db::i($s['id']),
            'created_at'   => Tz::iso($s['created_at']),
            'total_amount' => Db::f($s['total_amount']),
            'debt_amount'  => Db::f($s['debt_amount']),
            'status'       => $s['status'],
            'cashier'      => $cashiers[(int)($s['cashier_id'] ?? 0)]['username'] ?? null,
            'items'        => $itemsBySale[(int)$s['id']] ?? [],
        ], $sales),
        'payments' => array_map(fn($p) => [
            'id'             => Db::i($p['id']),
            'created_at'     => Tz::iso($p['created_at']),
            'amount'         => Db::f($p['amount']),
            'payment_method' => $p['payment_method'],
            'note'           => $p['note'] ?? null,
            'employee'       => $payEmployees[(int)($p['created_by'] ?? 0)]['username'] ?? null,
        ], $payments),
    ]);
});

// =======================================================================
// GET /crm/clients/{client_id}
// =======================================================================
Router::get('/clients/{client_id}', function (array $p): never {
    Auth::user();
    $client = Db::one('SELECT * FROM clients WHERE id = ?', [Router::id($p, 'client_id')]);
    if ($client === null) {
        fail(404, 'Client not found');
    }
    Http::json(Shape::client($client));
});

// =======================================================================
// PATCH /crm/clients/{client_id}
// =======================================================================
Router::patch('/clients/{client_id}', function (array $p): never {
    $user = Auth::require(['admin', 'manager'], 'Ruxsat berilmagan');
    $clientId = Router::id($p, 'client_id');
    $b = Http::body();

    $client = Db::one('SELECT * FROM clients WHERE id = ?', [$clientId]);
    if ($client === null) {
        fail(404, 'Client not found');
    }

    // Faqat kelgan maydonlar. Balans bu yerda ham o'zgarmaydi.
    $data = [];
    if (array_key_exists('name', $b)) {
        $data['name'] = Http::reqStr($b, 'name', 200, 'Ism');
    }
    if (array_key_exists('phone', $b)) {
        $data['phone'] = Http::str($b, 'phone', null, 30, 'Telefon');
    }
    if (array_key_exists('telegram_id', $b)) {
        $data['telegram_id'] = Http::int($b, 'telegram_id');
    }
    if (array_key_exists('debt_due_date', $b)) {
        $data['debt_due_date'] = Tz::parseFilterDate(Http::str($b, 'debt_due_date', null, 40));
    }

    Db::tx(function () use ($data, $clientId, $user, $client): void {
        if ($data !== []) {
            Db::update('clients', $clientId, $data);
        }
        Audit::log((int)$user['id'], 'MIJOZ_TAHRIR',
            "Mijoz tahrirlandi: {$client['name']} (ID: $clientId)");
    });

    Http::json(Shape::client(Db::one('SELECT * FROM clients WHERE id = ?', [$clientId])));
});

// =======================================================================
// DELETE /crm/clients/{client_id}
// =======================================================================
Router::delete('/clients/{client_id}', function (array $p): never {
    $user = Auth::require(['admin'], "Faqat admin mijozlarni o'chira oladi");
    $clientId = Router::id($p, 'client_id');

    $client = Db::one('SELECT * FROM clients WHERE id = ?', [$clientId]);
    if ($client === null) {
        fail(404, 'Client not found');
    }
    if (abs(Db::f($client['balance'])) > 0.0000001) {
        fail(400, "Qarzi yoki balansi bor mijozni o'chirib bo'lmaydi");
    }

    // Tarixga bog'langan mijozni ham o'chirib bo'lmaydi: sotuv va to'lov
    // satrlari yetim qolardi.
    $sales = (int)Db::val('SELECT COUNT(*) FROM sales WHERE client_id = ?', [$clientId], 0);
    if ($sales > 0) {
        fail(409, "Bu mijozda $sales ta savdo tarixi bor — o'chirib bo'lmaydi.");
    }
    $pays = (int)Db::val('SELECT COUNT(*) FROM payments WHERE client_id = ?', [$clientId], 0);
    if ($pays > 0) {
        fail(409, "Bu mijozda $pays ta to'lov tarixi bor — o'chirib bo'lmaydi.");
    }

    Db::tx(function () use ($clientId, $user, $client): void {
        Db::delete('clients', $clientId);
        Audit::log((int)$user['id'], 'MIJOZ_OCHIRILDI',
            "Mijoz o'chirildi: {$client['name']} (ID: $clientId)");
    });

    Http::json(['message' => 'Client deleted']);
});

// =======================================================================
// DELETE /crm/payments/{payment_id}
// =======================================================================
Router::delete('/payments/{payment_id}', function (array $p): never {
    // Xato qabul qilingan qarz to'lovini bekor qilish.
    //
    // Ilgari to'lovni tuzatishning HECH QANDAY yo'li yo'q edi: noto'g'ri
    // summa kiritilsa yoki to'lov boshqa mijozga yozilsa, mijoz balansi
    // abadiy noto'g'ri qolardi.
    $user = Auth::require(['admin'], "Faqat admin to'lovni bekor qila oladi");
    $paymentId = Router::id($p, 'payment_id');

    $reason = Http::q('reason');
    if ($reason === null || mb_strlen($reason) < 3 || mb_strlen($reason) > 300) {
        fail(422, "Bekor qilish sababini yozing (3-300 belgi).");
    }

    $payment = Db::one('SELECT * FROM payments WHERE id = ?', [$paymentId]);
    if ($payment === null) {
        fail(404, "To'lov topilmadi");
    }

    $client = Db::one('SELECT * FROM clients WHERE id = ?', [(int)$payment['client_id']]);

    // Yopilgan smenaga tegishli bo'lsa — operatorni OGOHLANTIRAMIZ.
    // Smenaning o'z hisobi muzlatilgan holicha qoladi (kassir imzolagan
    // raqam tarixiy hujjat), lekin moliya hisobotlari o'zgaradi.
    $note = '';
    if (!empty($payment['shift_id'])) {
        $shift = Db::one('SELECT id, status FROM shifts WHERE id = ?', [(int)$payment['shift_id']]);
        if ($shift !== null && $shift['status'] === 'closed') {
            $note = " DIQQAT: yopilgan smena #{$shift['id']} da qabul qilingan edi.";
        }
    }

    Db::tx(function () use ($payment, $paymentId, $client, $user, $reason, $note): void {
        // Balansni teskariga qaytaramiz: to'lov balansni OSHIRGAN edi.
        Db::run(
            'UPDATE clients SET balance = balance - ? WHERE id = ?',
            [(float)$payment['amount'], (int)$payment['client_id']]
        );
        Audit::log(
            (int)$user['id'],
            'TOLOV_BEKOR_QILINDI',
            "To'lov #$paymentId bekor qilindi: "
            . number_format((float)$payment['amount'], 0, '.', ',') . " so'm, mijoz "
            . ($client['name'] ?? $payment['client_id']) . ". Sabab: $reason.$note"
        );
        Db::delete('payments', $paymentId);
    });

    $fresh = $client === null ? null
        : Db::one('SELECT balance FROM clients WHERE id = ?', [(int)$payment['client_id']]);

    Http::json([
        'message'     => "To'lov bekor qilindi",
        'new_balance' => $fresh === null ? null : Db::f($fresh['balance']),
        'warning'     => trim($note) === '' ? null : trim($note),
    ]);
});

// =======================================================================
// POST /crm/clients/{client_id}/pay
// =======================================================================
Router::post('/clients/{client_id}/pay', function (array $p): never {
    // Qarzni yopish — pul bilan ishlash. Ombochida smena ham bo'lmaydi,
    // ya'ni uning "to'lovi" hech qaysi kassada ko'rinmasdi.
    $user = Auth::require(['admin', 'manager', 'cashier'], 'Ruxsat berilmagan');
    $clientId = Router::id($p, 'client_id');
    $b = Http::body();

    $amount = Http::reqNum($b, 'amount', 'gt', 0, null, "To'lov summasi");
    $method = Http::str($b, 'payment_method', 'cash', 40, "To'lov usuli") ?? 'cash';
    $note = Http::str($b, 'note', null, 500, 'Izoh');

    $client = Db::one('SELECT * FROM clients WHERE id = ?', [$clientId]);
    if ($client === null) {
        fail(404, 'Mijoz topilmadi');
    }

    $shift = Db::one(
        "SELECT id FROM shifts WHERE cashier_id = ? AND status = 'open' ORDER BY id DESC",
        [$user['id']]
    );

    // NAQD to'lov uchun ochiq smena SHART.
    //
    // Ilgari smena topilmasa shift_id NULL bo'lib qolardi: pul jismonan
    // kassaga tushadi, lekin uni hech qaysi smena kutmaydi. Yopilishda
    // tushunarsiz ORTIQCHA chiqar va kassirdan tushuntirish talab qilinardi.
    if (in_array($method, CASH_PAYMENT_METHODS, true) && $shift === null) {
        fail(409, "Naqd to'lovni qabul qilish uchun avval smenani oching");
    }

    Db::tx(function () use ($clientId, $amount, $method, $note, $user, $shift, $client): void {
        // Balansni ATOMIK yangilash (qarz kamayadi, ya'ni balans oshadi).
        // "o'qi -> qo'sh -> yoz" bo'lsa, bir vaqtda kelgan ikki to'lovdan
        // biri yo'qolib ketardi va mijoz qarzi kamaymay qolardi.
        Db::run('UPDATE clients SET balance = balance + ? WHERE id = ?', [$amount, $clientId]);

        // Qarz to'liq yopilgan bo'lsa, muddatni ham TOZALAYMIZ. Aks holda
        // bot qarzi yo'q mijozga "muddati o'tgan" deb yozib turardi.
        Db::run('UPDATE clients SET debt_due_date = NULL WHERE id = ? AND balance >= 0', [$clientId]);

        Db::insert('payments', [
            'client_id'      => $clientId,
            'amount'         => $amount,
            'payment_method' => $method,
            'note'           => $note,
            'created_at'     => Tz::now(),
            'created_by'     => $user['id'],
            'shift_id'       => $shift ? (int)$shift['id'] : null,
        ]);

        Audit::log((int)$user['id'], 'MIJOZ_TOLOV',
            "Mijoz: {$client['name']}. Summa: " . number_format($amount, 0, '.', ',')
            . " so'm. Usul: $method");
    });

    $fresh = Db::one('SELECT balance FROM clients WHERE id = ?', [$clientId]);
    Http::json([
        'message'     => "To'lov qabul qilindi",
        'new_balance' => Db::f($fresh['balance']),
    ]);
});
