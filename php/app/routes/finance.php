<?php
/**
 * /finance — statistika, grafiklar, xarajatlar, eksport.
 *
 * ATAYIN YASHIRISH — buni "tuzatmang":
 *   * /finance/stats menejer va kassirga totalCost va netProfit ni NOL qilib
 *     qaytaradi. Marjani faqat admin ko'radi.
 *   * menejer admin ko'rsatkichlarini ko'ra olmaydi;
 *   * kassir jim-jitlik bilan o'z id siga cheklanadi.
 *
 * TEZLIK: Python versiyasida grafiklar HAR KUN uchun alohida so'rov
 * yuborardi (7 kunlik grafik = 21 ta so'rov, 30 kunlik = 90 ta). Bu yerda
 * kunlar bitta so'rov ichida CASE bilan ajratiladi — kun soni qancha
 * bo'lishidan qat'i nazar 1 ta so'rov. Xodimlar ko'rsatkichi ham xuddi
 * shunday: har xodimga ikkita so'rov o'rniga jami ikkita so'rov.
 */

declare(strict_types=1);

// pos.php dagi CASH_METHODS bilan bir xil.
const FIN_CASH_METHODS = ['cash', 'naqd'];

/** Sotuv tannarxi: sotuv paytidagi qiymat, eski satrlar uchun joriy narx zaxira. */
const COGS_EXPR = 'SUM(si.quantity * COALESCE(si.buy_price, p.buy_price, 0))';

// =======================================================================
// GET /finance/stats
// =======================================================================
Router::get('/stats', function (): never {
    $user = Auth::user();
    if (!in_array($user['role'], ['admin', 'manager', 'cashier'], true)) {
        fail(403, 'Ruxsat berilmagan');
    }

    $employeeId = Http::qInt('employee_id');

    // Kassir faqat O'Z ko'rsatkichini ko'radi.
    if ($user['role'] === 'cashier') {
        $employeeId = (int)$user['id'];
    }
    // Menejer admin hisobotini ko'ra olmaydi.
    if ($employeeId && $user['role'] === 'manager') {
        $target = Db::one('SELECT role FROM employees WHERE id = ?', [$employeeId]);
        if ($target !== null && $target['role'] === 'admin') {
            fail(403, "Menejer admin hisobotini ko'ra olmaydi");
        }
    }

    $start = Tz::parseFilterDate(Http::q('start_date')) ?? Tz::todayStartUtc();
    $end   = Tz::parseFilterDate(Http::q('end_date'), true) ?? Tz::now();

    $empSql = $employeeId ? ' AND cashier_id = ?' : '';
    $salesParams = [$start, $end];
    if ($employeeId) {
        $salesParams[] = $employeeId;
    }

    $salesTotal = Db::num(
        "SELECT COALESCE(SUM(total_amount), 0) FROM sales
         WHERE created_at >= ? AND created_at <= ? AND status = 'completed'$empSql",
        $salesParams
    );

    // LEFT JOIN: mahsulot o'chirilgan bo'lsa ham satr TUSHIB QOLMASIN.
    // INNER JOIN da bunday satrlar tannarxdan chiqib ketardi va sof foyda
    // sun'iy oshib ko'rinardi.
    $totalCost = Db::num(
        'SELECT COALESCE(' . COGS_EXPR . ', 0) FROM sale_items si
         LEFT JOIN products p ON p.id = si.product_id
         JOIN sales s ON s.id = si.sale_id
         WHERE s.created_at >= ? AND s.created_at <= ? AND s.status = \'completed\''
        . ($employeeId ? ' AND s.cashier_id = ?' : ''),
        $salesParams
    );

    $expParams = [$start, $end];
    if ($employeeId) {
        $expParams[] = $employeeId;
    }
    $totalExpenses = Db::num(
        'SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE created_at >= ? AND created_at <= ?'
        . ($employeeId ? ' AND created_by = ?' : ''),
        $expParams
    );

    // Menejer va kassirdan marjani YASHIRAMIZ — atayin.
    if (in_array($user['role'], ['manager', 'cashier'], true)) {
        $totalCost = 0.0;
        $netProfit = 0.0;
    } else {
        $netProfit = $salesTotal - $totalCost - $totalExpenses;
    }

    $clientCount = (int)Db::val('SELECT COUNT(*) FROM clients', [], 0);

    $settings = Db::one('SELECT low_stock_threshold FROM store_settings ORDER BY id LIMIT 1');
    $threshold = (int)($settings['low_stock_threshold'] ?? 5);

    $lowStock = Db::all(
        'SELECT id, name, stock, unit, sell_price FROM products
         WHERE stock <= ? AND (is_infinite IS NULL OR is_infinite = ?)
         ORDER BY stock LIMIT 10',
        [$threshold, false]
    );

    $totalProducts = (int)Db::val('SELECT COUNT(*) FROM products', [], 0);

    Http::json([
        'dailySales'          => $salesTotal,
        'dailySalesFormatted' => number_format($salesTotal, 0, '.', ',') . " so'm",
        'totalCost'           => $totalCost,
        'totalExpenses'       => $totalExpenses,
        'netProfit'           => $netProfit,
        'netProfitFormatted'  => number_format($netProfit, 0, '.', ',') . " so'm",
        'clientCount'         => (string)$clientCount,
        'lowStock'            => (string)count($lowStock),
        'lowStockItems'       => array_map(fn($p) => [
            'id'         => Db::i($p['id']),
            'name'       => $p['name'],
            'stock'      => Db::f($p['stock']),
            'unit'       => $p['unit'] ?? 'dona',
            'sell_price' => Db::f($p['sell_price']),
        ], $lowStock),
        'totalProducts'       => (string)$totalProducts,
    ]);
});

// =======================================================================
// GET /finance/expenses-by-category
// =======================================================================
Router::get('/expenses-by-category', function (): never {
    Auth::require(['admin', 'manager'], 'Ruxsat berilmagan');

    $start = Tz::parseFilterDate(Http::q('start_date'))
        ?? (new DateTimeImmutable(Tz::now(), Tz::utcTz()))->modify('-30 days')->format('Y-m-d H:i:s.u');
    $end = Tz::parseFilterDate(Http::q('end_date'), true) ?? Tz::now();

    $rows = Db::all(
        'SELECT category, SUM(amount) AS amount FROM expenses
         WHERE created_at >= ? AND created_at <= ? GROUP BY category',
        [$start, $end]
    );

    Http::json(array_map(fn($r) => [
        'category' => $r['category'],
        'amount'   => Db::f($r['amount']),
    ], $rows));
});

// =======================================================================
// GET /finance/employee-performance
// =======================================================================
Router::get('/employee-performance', function (): never {
    $user = Auth::require(['admin', 'manager'], 'Ruxsat berilmagan');

    $start = Tz::parseFilterDate(Http::q('start_date'))
        ?? (new DateTimeImmutable(Tz::now(), Tz::utcTz()))->modify('-30 days')->format('Y-m-d H:i:s.u');
    $end = Tz::parseFilterDate(Http::q('end_date'), true) ?? Tz::now();

    // Menejer admin ko'rsatkichlarini ko'rmaydi.
    $employees = $user['role'] === 'manager'
        ? Db::all("SELECT * FROM employees WHERE role <> 'admin' ORDER BY id")
        : Db::all('SELECT * FROM employees ORDER BY id');

    // status = 'completed' SHART: qaytarilgan cheklar ham hisoblanardi,
    // ya'ni chek urib keyin bekor qilgan kassir halol ishlaganidan YUQORI
    // ko'rsatkich olardi.
    $salesRows = Db::all(
        "SELECT cashier_id, COUNT(id) AS sale_count, COALESCE(SUM(total_amount), 0) AS sale_total
         FROM sales
         WHERE created_at >= ? AND created_at <= ? AND status = 'completed'
         GROUP BY cashier_id",
        [$start, $end]
    );
    $salesBy = [];
    foreach ($salesRows as $r) {
        $salesBy[(int)$r['cashier_id']] = $r;
    }

    $taskRows = Db::all(
        "SELECT assigned_to, COUNT(id) AS total_tasks,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed_tasks
         FROM tasks GROUP BY assigned_to"
    );
    $tasksBy = [];
    foreach ($taskRows as $r) {
        $tasksBy[(int)$r['assigned_to']] = $r;
    }

    Http::json(array_map(function ($e) use ($salesBy, $tasksBy) {
        $id = (int)$e['id'];
        return [
            'id'              => $id,
            'username'        => $e['username'],
            'full_name'       => $e['full_name'] ?? null,
            'role'            => $e['role'],
            'sale_count'      => (int)($salesBy[$id]['sale_count'] ?? 0),
            'sale_total'      => Db::f($salesBy[$id]['sale_total'] ?? 0),
            'total_tasks'     => (int)($tasksBy[$id]['total_tasks'] ?? 0),
            'completed_tasks' => (int)($tasksBy[$id]['completed_tasks'] ?? 0),
        ];
    }, $employees));
});

/**
 * Kunlik oynalar ro'yxati: [['label' => '07.09', 'start' => ..., 'end' => ...], ...]
 */
function day_windows(int $days): array
{
    $today = new DateTimeImmutable(Tz::shopToday(), Tz::shopTz());
    $out = [];
    for ($i = $days - 1; $i >= 0; $i--) {
        $day = $today->modify("-$i day")->format('Y-m-d');
        [$s, $e] = Tz::dayBoundsUtc($day);
        $out[] = ['label' => (new DateTimeImmutable($day))->format('d.m'), 'start' => $s, 'end' => $e];
    }
    return $out;
}

/**
 * Bitta so'rovda bir nechta kunning yig'indisini oladi.
 *
 * Har kun uchun alohida so'rov yuborish o'rniga CASE ishlatamiz: 30 kunlik
 * grafik 30 ta so'rov emas, 1 ta so'rov bo'ladi.
 */
function sums_by_day(string $table, string $valueExpr, string $dateCol, array $windows,
                     string $extraWhere = '', array $extraParams = []): array
{
    if ($windows === []) {
        return [];
    }
    $parts = [];
    $params = [];
    foreach ($windows as $i => $w) {
        $parts[] = "COALESCE(SUM(CASE WHEN $dateCol >= ? AND $dateCol < ? THEN $valueExpr ELSE 0 END), 0) AS d$i";
        $params[] = $w['start'];
        $params[] = $w['end'];
    }
    $params = array_merge($params, $extraParams);

    // BUTUN oyna uchun UMUMIY chegara.
    //
    // Busiz so'rovda sana bo'yicha shart UMUMAN yo'q edi: baza barcha
    // satrlarni (200 mingdan ortiq savdo qatorini) o'qib chiqar, keyin CASE
    // ularning deyarli hammasini nolga aylantirardi. Ya'ni 30 kunlik grafik
    // ikki yillik tarixni skanerlardi. Endi indeks bo'yicha faqat kerakli
    // oraliq o'qiladi.
    $conds = [];
    if ($extraWhere !== '') {
        $conds[] = $extraWhere;
    }
    $conds[] = "$dateCol >= ? AND $dateCol < ?";
    $params[] = $windows[array_key_first($windows)]['start'];
    $params[] = $windows[array_key_last($windows)]['end'];

    $row = Db::one(
        'SELECT ' . implode(', ', $parts) . " FROM $table WHERE " . implode(' AND ', $conds),
        $params
    ) ?? [];

    $out = [];
    foreach (array_keys($windows) as $i) {
        $out[$i] = Db::f($row["d$i"] ?? 0);
    }
    return $out;
}

// =======================================================================
// GET /finance/profit-chart
// =======================================================================
Router::get('/profit-chart', function (): never {
    $user = Auth::require(['admin', 'manager'], 'Ruxsat berilmagan');

    $days = Http::qInt('days', 7, 1, 90) ?? 7;
    $windows = day_windows($days);

    $revenue = sums_by_day('sales', 'total_amount', 'created_at', $windows,
        "status = 'completed'");
    $expenses = sums_by_day('expenses', 'amount', 'created_at', $windows);
    $cogs = sums_by_day(
        'sale_items si LEFT JOIN products p ON p.id = si.product_id JOIN sales s ON s.id = si.sale_id',
        'si.quantity * COALESCE(si.buy_price, p.buy_price, 0)',
        's.created_at',
        $windows,
        "s.status = 'completed'"
    );

    $hideMargin = in_array($user['role'], ['manager', 'cashier'], true);

    $out = [];
    foreach ($windows as $i => $w) {
        $out[] = [
            'date'     => $w['label'],
            'revenue'  => $revenue[$i],
            // Menejerga faqat do'kon xarajatlari ko'rinadi, tannarx emas.
            'expenses' => $hideMargin ? $expenses[$i] : $expenses[$i] + $cogs[$i],
            'profit'   => $hideMargin ? 0.0 : $revenue[$i] - $cogs[$i] - $expenses[$i],
        ];
    }

    Http::json($out);
});

// =======================================================================
// GET /finance/dashboard-chart
// =======================================================================
Router::get('/dashboard-chart', function (): never {
    $user = Auth::user();

    $employeeId = Http::qInt('employee_id');
    if ($user['role'] === 'cashier') {
        $employeeId = (int)$user['id'];
    }

    $windows = day_windows(7);
    $where = "status = 'completed'";
    $params = [];
    if ($employeeId) {
        $where .= ' AND cashier_id = ?';
        $params[] = $employeeId;
    }

    $data = sums_by_day('sales', 'total_amount', 'created_at', $windows, $where, $params);

    Http::json([
        'labels' => array_map(fn($w) => $w['label'], $windows),
        'data'   => array_values($data),
    ]);
});

// =======================================================================
// GET /finance/top-products
// =======================================================================
Router::get('/top-products', function (): never {
    $user = Auth::user();
    require_once APP_DIR . '/Cache.php';

    $limit = Http::qInt('limit', 5, 1, 50) ?? 5;
    $employeeId = Http::qInt('employee_id');
    if ($user['role'] === 'cashier') {
        $employeeId = (int)$user['id'];
    }

    $where = ["s.status = 'completed'"];
    $params = [];
    if ($employeeId) {
        $where[] = 's.cashier_id = ?';
        $params[] = $employeeId;
    }
    $start = Tz::parseFilterDate(Http::q('start_date'));
    if ($start !== null) {
        $where[] = 's.created_at >= ?';
        $params[] = $start;
    }
    $end = Tz::parseFilterDate(Http::q('end_date'), true);
    if ($end !== null) {
        $where[] = 's.created_at <= ?';
        $params[] = $end;
    }

    // Bu so'rov butun tarixni guruhlaydi — sana filtri berilmasa ayniqsa
    // og'ir. Natija bir necha daqiqada sezilarli o'zgarmaydi, shuning uchun
    // keshlanadi. Pulga aloqasi yo'q: bu faqat ko'rsatish uchun ro'yxat.
    $cacheKey = 'fin-top:' . md5(implode('|', $where) . '|' . implode('|', $params) . "|$limit");

    $rows = Cache::remember($cacheKey, 300, fn() => Db::all(
        'SELECT p.name, SUM(si.quantity) AS total_qty
         FROM products p
         JOIN sale_items si ON p.id = si.product_id
         JOIN sales s ON s.id = si.sale_id
         WHERE ' . implode(' AND ', $where) . '
         GROUP BY p.id, p.name
         ORDER BY SUM(si.quantity) DESC
         LIMIT ' . $limit,
        $params
    ));

    Http::json(array_map(fn($r) => ['name' => $r['name'], 'value' => Db::f($r['total_qty'])], $rows));
});

// =======================================================================
// GET /finance/expenses
// =======================================================================
Router::get('/expenses', function (): never {
    $user = Auth::user();

    $employeeId = Http::qInt('employee_id');
    if ($user['role'] === 'cashier') {
        $employeeId = (int)$user['id'];
    }

    $where = ['1=1'];
    $params = [];
    if ($employeeId) {
        $where[] = 'created_by = ?';
        $params[] = $employeeId;
    }
    $category = Http::q('category');
    if ($category !== null) {
        $where[] = 'category = ?';
        $params[] = $category;
    }
    $start = Tz::parseFilterDate(Http::q('start_date'));
    if ($start !== null) {
        $where[] = 'created_at >= ?';
        $params[] = $start;
    }
    $end = Tz::parseFilterDate(Http::q('end_date'), true);
    if ($end !== null) {
        $where[] = 'created_at <= ?';
        $params[] = $end;
    }

    $rows = Db::all(
        'SELECT * FROM expenses WHERE ' . implode(' AND ', $where)
        . ' ORDER BY created_at DESC, id DESC LIMIT 1000',
        $params
    );

    $creators = Shape::lookup('employees', array_column($rows, 'created_by'));
    Http::json(array_map(
        fn($r) => Shape::expense($r, $creators[(int)($r['created_by'] ?? 0)] ?? null),
        $rows
    ));
});

// =======================================================================
// POST /finance/expenses
// =======================================================================
Router::post('/expenses', function (): never {
    $user = Auth::require(['admin', 'manager', 'cashier'], 'Ruxsat berilmagan');
    $b = Http::body();

    $reason = Http::reqStr($b, 'reason', 300, 'Izoh');
    $category = Http::str($b, 'category', 'Boshqa', 100, 'Kategoriya') ?? 'Boshqa';
    $amount = Http::reqNum($b, 'amount', 'gt', 0, null, 'Xarajat summasi');
    $method = Http::str($b, 'payment_method', 'cash', 40, "To'lov usuli") ?? 'cash';

    // Xarajatni ochiq smenaga BOG'LAYMIZ. Shusiz kassadan chiqqan naqd pul
    // smena hisobiga umuman kirmasdi va kassir har kuni tushuntirib
    // bo'lmaydigan kamomadda qolardi — natijada kamomad signali kundalik
    // shovqinga aylanib, HAQIQIY kamomadni yashirardi.
    $shift = Db::one(
        "SELECT id FROM shifts WHERE cashier_id = ? AND status = 'open' ORDER BY id DESC",
        [$user['id']]
    );

    $id = Db::tx(function () use ($reason, $category, $amount, $method, $user, $shift): int {
        $id = Db::insert('expenses', [
            'reason'         => $reason,
            'category'       => $category,
            'amount'         => $amount,
            'payment_method' => $method,
            'created_at'     => Tz::now(),
            'created_by'     => $user['id'],
            'shift_id'       => $shift ? (int)$shift['id'] : null,
        ]);
        Audit::log((int)$user['id'], 'YANGI_XARAJAT',
            'Xarajat: ' . number_format($amount, 0, '.', ',') . " so'm ($category). Izoh: $reason");
        return $id;
    });

    Http::json(Shape::expense(Db::one('SELECT * FROM expenses WHERE id = ?', [$id]), $user));
});

// =======================================================================
// PATCH /finance/expenses/{expense_id}
// =======================================================================
Router::patch('/expenses/{expense_id}', function (array $p): never {
    // Xato yozilgan xarajatni tuzatish.
    //
    // Ilgari xarajatni na tahrirlash, na o'chirish mumkin edi. Bir marta
    // noto'g'ri summa kiritilsa, u abadiy qolib, o'sha davrning sof
    // foydasini va xarajat hisobotlarini butunlay buzardi.
    $user = Auth::require(['admin', 'manager'], 'Faqat admin va menejer tuzata oladi');
    $expenseId = Router::id($p, 'expense_id');
    $b = Http::body();

    $reasonQ = Http::q('reason');
    if ($reasonQ === null || mb_strlen($reasonQ) < 3 || mb_strlen($reasonQ) > 300) {
        fail(422, 'Tuzatish sababini yozing (3-300 belgi).');
    }

    $expense = Db::one('SELECT * FROM expenses WHERE id = ?', [$expenseId]);
    if ($expense === null) {
        fail(404, 'Xarajat topilmadi');
    }

    $changes = [];
    if (array_key_exists('reason', $b) && $b['reason'] !== null) {
        $changes['reason'] = Http::reqStr($b, 'reason', 300, 'Izoh');
    }
    if (array_key_exists('category', $b) && $b['category'] !== null) {
        $changes['category'] = Http::reqStr($b, 'category', 100, 'Kategoriya');
    }
    if (array_key_exists('amount', $b) && $b['amount'] !== null) {
        $changes['amount'] = Http::reqNum($b, 'amount', 'gt', 0, null, 'Summa');
    }
    if (array_key_exists('payment_method', $b) && $b['payment_method'] !== null) {
        $changes['payment_method'] = Http::reqStr($b, 'payment_method', 40, "To'lov usuli");
    }
    if ($changes === []) {
        fail(400, "O'zgartirish uchun maydon berilmadi");
    }

    $was = number_format(Db::f($expense['amount']), 0, '.', ',') . " so'm ("
        . $expense['category'] . ', ' . $expense['payment_method'] . ')';

    Db::tx(function () use ($changes, $expenseId, $expense, $user, $was, $reasonQ): void {
        Db::update('expenses', $expenseId, $changes);
        $now = Db::one('SELECT * FROM expenses WHERE id = ?', [$expenseId]);
        Audit::log((int)$user['id'], 'XARAJAT_TUZATILDI',
            "Xarajat #$expenseId: $was -> "
            . number_format(Db::f($now['amount']), 0, '.', ',') . " so'm ("
            . $now['category'] . ', ' . $now['payment_method'] . "). Sabab: $reasonQ");
    });

    $fresh = Db::one('SELECT * FROM expenses WHERE id = ?', [$expenseId]);
    $creator = $fresh['created_by'] ? Db::one('SELECT * FROM employees WHERE id = ?', [(int)$fresh['created_by']]) : null;
    Http::json(Shape::expense($fresh, $creator));
});

// =======================================================================
// DELETE /finance/expenses/{expense_id}
// =======================================================================
Router::delete('/expenses/{expense_id}', function (array $p): never {
    $user = Auth::require(['admin', 'manager'], "Faqat admin va menejer o'chira oladi");
    $expenseId = Router::id($p, 'expense_id');

    $reasonQ = Http::q('reason');
    if ($reasonQ === null || mb_strlen($reasonQ) < 3 || mb_strlen($reasonQ) > 300) {
        fail(422, "O'chirish sababini yozing (3-300 belgi).");
    }

    $expense = Db::one('SELECT * FROM expenses WHERE id = ?', [$expenseId]);
    if ($expense === null) {
        fail(404, 'Xarajat topilmadi');
    }

    // Smena hisobi yopilishda MUZLATILGAN — u o'zgarmaydi. Lekin moliya
    // hisobotlari o'zgaradi, shuning uchun buni aniq belgilab qo'yamiz.
    $note = '';
    if (!empty($expense['shift_id'])) {
        $shift = Db::one('SELECT id, status FROM shifts WHERE id = ?', [(int)$expense['shift_id']]);
        if ($shift !== null && $shift['status'] === 'closed') {
            $note = " DIQQAT: yopilgan smena #{$shift['id']} ga tegishli edi.";
        }
    }

    Db::tx(function () use ($expense, $expenseId, $user, $reasonQ, $note): void {
        Audit::log((int)$user['id'], 'XARAJAT_OCHIRILDI',
            "Xarajat #$expenseId o'chirildi: "
            . number_format(Db::f($expense['amount']), 0, '.', ',') . " so'm ("
            . $expense['category'] . ') — ' . $expense['reason'] . ". Sabab: $reasonQ.$note");
        Db::delete('expenses', $expenseId);
    });

    Http::json([
        'message' => "Xarajat o'chirildi",
        'warning' => trim($note) === '' ? null : trim($note),
    ]);
});

// =======================================================================
// POST /finance/payments
// =======================================================================
Router::post('/payments', function (): never {
    $user = Auth::require(['admin', 'manager', 'cashier'], 'Ruxsat berilmagan');
    $b = Http::body();

    $clientId = Http::reqInt($b, 'client_id', 'Mijoz');
    $amount = Http::reqNum($b, 'amount', 'gt', 0, null, "To'lov summasi");
    $method = Http::str($b, 'payment_method', 'cash', 40, "To'lov usuli") ?? 'cash';
    $note = Http::str($b, 'note', null, 500, 'Izoh');

    $shift = Db::one(
        "SELECT id FROM shifts WHERE cashier_id = ? AND status = 'open' ORDER BY id DESC",
        [$user['id']]
    );

    // NAQD to'lov uchun ochiq smena SHART — crm/pay dagi bilan bir xil sabab.
    if (in_array($method, FIN_CASH_METHODS, true) && $shift === null) {
        fail(409, "Naqd to'lovni qabul qilish uchun avval smenani oching");
    }

    // Mijoz bor-yo'qligini AVVAL tekshiramiz. Ilgari to'lov yozuvi baribir
    // qo'shilardi: mavjud bo'lmagan mijoz uchun "to'lov qabul qilindi" deb
    // javob qaytar, hech kimning qarzi kamaymas, lekin smena kassasi shu
    // summaga oshib, kassirga tushunarsiz kamomad bo'lib chiqardi.
    $client = Db::one('SELECT * FROM clients WHERE id = ?', [$clientId]);
    if ($client === null) {
        fail(404, 'Mijoz topilmadi');
    }

    Db::tx(function () use ($clientId, $amount, $method, $note, $user, $shift, $client): void {
        Db::insert('payments', [
            'client_id'      => $clientId,
            'amount'         => $amount,
            'payment_method' => $method,
            'note'           => $note,
            'created_at'     => Tz::now(),
            'created_by'     => $user['id'],
            'shift_id'       => $shift ? (int)$shift['id'] : null,
        ]);
        // Balansni ATOMIK oshiramiz.
        Db::run('UPDATE clients SET balance = balance + ? WHERE id = ?', [$amount, $clientId]);
        Db::run('UPDATE clients SET debt_due_date = NULL WHERE id = ? AND balance >= 0', [$clientId]);

        Audit::log((int)$user['id'], 'MIJOZ_TOLOV',
            "Mijoz: {$client['name']}. Summa: " . number_format($amount, 0, '.', ',')
            . " so'm. Usul: $method");
    });

    Http::json(['status' => 'success', 'message' => "To'lov qabul qilindi"]);
});

/** Eksport uchun cheklar jadvalini yig'adi. */
function export_sales_rows(string $start, string $end): array
{
    $sales = Db::all(
        'SELECT * FROM sales WHERE created_at >= ? AND created_at <= ?
         ORDER BY created_at DESC, id DESC LIMIT 20000',
        [$start, $end]
    );
    if ($sales === []) {
        return [];
    }

    $ids = array_map(fn($s) => (int)$s['id'], $sales);
    $itemRows = Db::all(
        'SELECT si.sale_id, si.quantity, p.name, p.unit FROM sale_items si
         LEFT JOIN products p ON p.id = si.product_id
         WHERE si.sale_id IN (' . Db::marks($ids) . ') ORDER BY si.id',
        $ids
    );
    $itemsBy = [];
    foreach ($itemRows as $ir) {
        if ($ir['name'] === null) {
            continue;
        }
        $qty = rtrim(rtrim(number_format(Db::f($ir['quantity']), 3, '.', ''), '0'), '.');
        $itemsBy[(int)$ir['sale_id']][] = $ir['name'] . " ($qty " . ($ir['unit'] ?? 'dona') . ')';
    }

    $cashiers = Shape::lookup('employees', array_column($sales, 'cashier_id'));
    $clients = Shape::lookup('clients', array_column($sales, 'client_id'));

    $out = [];
    foreach ($sales as $s) {
        $out[] = [
            Db::i($s['id']),
            Tz::parse($s['created_at'])?->setTimezone(Tz::shopTz())->format('d.m.Y H:i') ?? '',
            Xlsx::safe($cashiers[(int)($s['cashier_id'] ?? 0)]['username'] ?? '-'),
            Xlsx::safe($clients[(int)($s['client_id'] ?? 0)]['name'] ?? '-'),
            Db::f($s['total_amount']),
            Xlsx::safe($s['payment_method']),
            // "Holat" ustuni ATAYIN bor. Ilgari qaytarilgan cheklar ham
            // fayllarga tushardi, lekin ularni ajratadigan ustun yo'q edi:
            // eksport dashboard bilan aynan vozvratlar summasiga farq qilar
            // va bu "pul yo'qolgan" kabi ko'rinardi.
            $s['status'] === 'refunded' ? 'Qaytarilgan' : "O'tkazilgan",
            Xlsx::safe(implode('; ', $itemsBy[(int)$s['id']] ?? [])),
        ];
    }
    return $out;
}

const EXPORT_HEADERS = ['ID', 'Sana', 'Kassir', 'Mijoz', 'Summa', "To'lov usuli", 'Holat', 'Mahsulotlar'];

// =======================================================================
// GET /finance/export-sales  (CSV)
// =======================================================================
Router::get('/export-sales', function (): never {
    Auth::require(['admin'], 'Ruxsat berilmagan');
    require_once APP_DIR . '/Xlsx.php';

    $start = Tz::parseFilterDate(Http::q('start_date'))
        ?? (new DateTimeImmutable(Tz::now(), Tz::utcTz()))->modify('-30 days')->format('Y-m-d H:i:s.u');
    $end = Tz::parseFilterDate(Http::q('end_date'), true) ?? Tz::now();

    Xlsx::downloadCsv(
        EXPORT_HEADERS,
        export_sales_rows($start, $end),
        'sotuvlar_' . date('Ymd') . '.csv'
    );
});

// =======================================================================
// GET /finance/export-sales-excel
// =======================================================================
Router::get('/export-sales-excel', function (): never {
    Auth::require(['admin'], 'Ruxsat berilmagan');
    require_once APP_DIR . '/Xlsx.php';

    $start = Tz::parseFilterDate(Http::q('start_date'))
        ?? (new DateTimeImmutable(Tz::now(), Tz::utcTz()))->modify('-30 days')->format('Y-m-d H:i:s.u');
    $end = Tz::parseFilterDate(Http::q('end_date'), true) ?? Tz::now();

    Xlsx::download(
        EXPORT_HEADERS,
        export_sales_rows($start, $end),
        'sotuvlar_' . date('Ymd') . '.xlsx',
        'Savdolar'
    );
});

// =======================================================================
// GET /finance/categories  — xarajat kategoriyalari
// =======================================================================
Router::get('/categories', function (): never {
    Auth::user();
    Http::json(array_map(
        fn($r) => ['id' => Db::i($r['id']), 'name' => $r['name']],
        Db::all('SELECT * FROM expense_categories ORDER BY name')
    ));
});
