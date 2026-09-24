<?php
/**
 * /pos — FAQAT smenalar (ochish, yopish, faol smena, tarix).
 *
 * Chek bilan bog'liq hamma narsa sales.php da. Bu ajratish Python
 * versiyasidan ko'chirildi va shunday qolishi kerak.
 *
 * KASSA HISOBI FORMULASI:
 *
 *   kutilgan = boshlang'ich
 *            + smena oynasidagi sof naqd sotuv
 *            + shu smenaga tamg'alangan naqd qarz to'lovlari
 *            - shu smenaga tamg'alangan naqd xarajatlar
 *            - shu smenada kassadan berilgan naqd vozvratlar
 */

declare(strict_types=1);

const CASH_METHODS = ['cash', 'naqd'];

/**
 * Smena hisobini JONLI hisoblaydi.
 *
 * Bu YAGONA hisoblash joyi. Ilgari aynan shu formula uch joyda takrorlangan
 * edi (tarix, faol smena, yopish) va ular bir-biridan farq qila boshlagan —
 * frontend kassirga bir raqamni, server boshqasini ko'rsatardi.
 *
 * BITTA SO'ROV. Avval to'rtta alohida so'rov ketardi (savdolar, naqd qarz
 * to'lovlari, naqd xarajatlar, naqd vozvratlar). Kassa sahifasi bu hisobni
 * muntazam so'rab turadi, shuning uchun to'rt marta borish o'rniga uchtasi
 * SELECT ichidagi kichik so'rovga aylantirildi — natija bir xil, bazaga
 * borish esa bitta.
 */
function compute_shift_totals(array $shift): array
{
    $shiftId  = (int)$shift['id'];
    $cashier  = (int)$shift['cashier_id'];
    $openedAt = $shift['opened_at'];
    $closedAt = $shift['closed_at'] ?? null;

    $params = [];

    // 1) Naqd qarz to'lovlari — smenaga tamg'alangan.
    $params[] = $shiftId;

    // 2) Kassadan naqd chiqqan xarajatlar.
    //
    // Ilgari xarajatlar smena hisobiga umuman kirmasdi. Kassir kassadan pul
    // olib biror narsa sotib olsa, yopilishda kassa aynan shu summaga kam
    // chiqar va undan har safar tushuntirish xati talab qilinardi. Natijada
    // kamomad signali kundalik shovqinga aylanib, HAQIQIY kamomadni yashirardi.
    $params[] = $shiftId;

    // 3) Shu smenada kassadan CHIQARIB berilgan naqd vozvratlar.
    //
    // Faqat BOSHQA smenaga tegishli sotuvlar hisoblanadi. Agar sotuv ham,
    // vozvrat ham shu smenada bo'lsa, sotuv 'refunded' bo'lgani uchun
    // quyidagi "completed" yig'indisidan allaqachon chiqib ketgan — ikkinchi
    // marta ayirsak, kassa IKKI BAROBAR kam ko'rinardi.
    //
    // Ahamiyatli holat — KECHAGI chekni bugun qaytarish: pul bugungi
    // yashikdan chiqadi, bugungi oyna esa o'sha sotuvni hech qachon o'z
    // ichiga olmagan.
    $refundWindow = 'cashier_id = ? AND created_at >= ?';
    $params[] = $shiftId;
    $params[] = $cashier;
    $params[] = $openedAt;
    if ($closedAt !== null) {
        $refundWindow .= ' AND created_at <= ?';
        $params[] = $closedAt;
    }

    // 4) Asosiy so'rov: smena oynasidagi tugallangan savdolar.
    $params[] = $cashier;
    $params[] = $openedAt;
    $winExtra = '';
    if ($closedAt !== null) {
        $winExtra = ' AND created_at <= ?';
        $params[] = $closedAt;
    }

    $t = Db::one(
        "SELECT
            COALESCE(SUM(total_amount - card_amount - transfer_amount
                         - debt_amount - bonus_spent), 0) AS total_cash,
            COALESCE(SUM(card_amount), 0)     AS total_card,
            COALESCE(SUM(transfer_amount), 0) AS total_transfer,
            COALESCE(SUM(debt_amount), 0)     AS total_debt,
            (SELECT COALESCE(SUM(amount), 0) FROM payments
              WHERE shift_id = ? AND payment_method IN ('cash', 'naqd')) AS debt_cash,
            (SELECT COALESCE(SUM(amount), 0) FROM expenses
              WHERE shift_id = ? AND payment_method IN ('cash', 'naqd')) AS cash_expenses,
            (SELECT COALESCE(SUM(cash_amount), 0) FROM sales
              WHERE refund_shift_id = ? AND status = 'refunded'
                AND NOT ($refundWindow)) AS cash_refunds
         FROM sales
         WHERE cashier_id = ? AND created_at >= ? AND status = 'completed'$winExtra",
        $params
    ) ?? [];

    $totalCash = Db::f($t['total_cash'] ?? 0);
    $debtCash  = Db::f($t['debt_cash'] ?? 0);
    $expenses  = Db::f($t['cash_expenses'] ?? 0);
    $refunds   = Db::f($t['cash_refunds'] ?? 0);

    return [
        'total_cash'     => $totalCash,
        'total_card'     => Db::f($t['total_card'] ?? 0),
        'total_transfer' => Db::f($t['total_transfer'] ?? 0),
        'total_debt'     => Db::f($t['total_debt'] ?? 0),
        'total_expenses' => $expenses,
        'total_refunds'  => $refunds,
        // Kassada bo'lishi kerak =
        //   boshlang'ich + naqd sotuv + naqd qarz to'lovi
        //   - naqd xarajat - naqd vozvrat
        'expected_cash'  => Db::f($shift['opening_balance']) + $totalCash + $debtCash - $expenses - $refunds,
    ];
}

/**
 * Yopilgan smena uchun MUZLATILGAN qiymatlar, ochiq smena uchun jonli hisob.
 *
 * Yopilgan smenani qayta hisoblash mumkin emas: keyinroq qilingan vozvrat
 * kassir IMZOLAGAN raqamni o'zgartirib yuborardi va hisobotdagi son bilan
 * qog'ozdagi son bir-biriga mos kelmay qolardi.
 */
function totals_for_display(array $shift): array
{
    if ($shift['status'] === 'closed' && $shift['expected_cash'] !== null) {
        return [
            'total_cash'      => Db::f($shift['total_cash']),
            'total_card'      => Db::f($shift['total_card']),
            'total_transfer'  => Db::f($shift['total_transfer']),
            'total_debt'      => Db::f($shift['total_debt']),
            'total_expenses'  => Db::f($shift['total_expenses']),
            'total_refunds'   => Db::f($shift['total_refunds']),
            'expected_cash'   => Db::f($shift['expected_cash']),
            'cash_difference' => Db::fn($shift['cash_difference']),
        ];
    }
    $t = compute_shift_totals($shift);
    $t['cash_difference'] = Db::fn($shift['cash_difference'] ?? null);
    return $t;
}

// =======================================================================
// GET /pos/shifts/history
// =======================================================================
Router::get('/shifts/history', function (): never {
    $user = Auth::user();

    $limit  = Http::qInt('limit', 50, 1, 500) ?? 50;
    $offset = max(0, Http::qInt('offset', 0) ?? 0);

    $where = ['1=1'];
    $params = [];

    if (!in_array($user['role'], ['admin', 'manager'], true)) {
        $where[] = 'cashier_id = ?';
        $params[] = (int)$user['id'];
    } else {
        $employeeId = Http::qInt('employee_id');
        if ($employeeId) {
            $where[] = 'cashier_id = ?';
            $params[] = $employeeId;
        }
    }

    // Foydalanuvchi DO'KON kunini tanlaydi, bazada esa UTC turadi.
    $startDate = Http::q('start_date');
    if ($startDate !== null) {
        $v = Tz::parseFilterDate($startDate);
        if ($v !== null) {
            $where[] = 'opened_at >= ?';
            $params[] = $v;
        }
    }
    $endDate = Http::q('end_date');
    if ($endDate !== null) {
        $v = Tz::parseFilterDate($endDate, true);
        if ($v !== null) {
            $where[] = 'opened_at <= ?';
            $params[] = $v;
        }
    }

    $rows = Db::all(
        'SELECT * FROM shifts WHERE ' . implode(' AND ', $where)
        . " ORDER BY opened_at DESC, id DESC LIMIT $limit OFFSET $offset",
        $params
    );

    $cashiers = Shape::lookup('employees', array_column($rows, 'cashier_id'));

    Http::json(array_map(
        fn($r) => Shape::shift($r, totals_for_display($r), $cashiers[(int)$r['cashier_id']] ?? null),
        $rows
    ));
});

// =======================================================================
// GET /pos/shifts/active
// =======================================================================
Router::get('/shifts/active', function (): never {
    $user = Auth::user();
    $shift = Db::one(
        "SELECT * FROM shifts WHERE cashier_id = ? AND status = 'open' ORDER BY id DESC",
        [$user['id']]
    );
    if ($shift === null) {
        // Python versiyasi Optional[ShiftOut] qaytarardi — ya'ni null.
        Http::json(null);
    }
    Http::json(Shape::shift($shift, compute_shift_totals($shift), $user));
});

// =======================================================================
// POST /pos/shifts/open
// =======================================================================
Router::post('/shifts/open', function (): never {
    $user = Auth::user();
    $b = Http::body();

    $opening = Http::num($b, 'opening_balance', 0.0, 'ge', 0, null, "Boshlang'ich balans") ?? 0.0;
    $note = Http::str($b, 'note', null, 1000, 'Izoh');

    // Bitta kassirda bitta ochiq smena.
    $active = Db::one(
        "SELECT id FROM shifts WHERE cashier_id = ? AND status = 'open'",
        [$user['id']]
    );
    if ($active !== null) {
        fail(400, 'Sizda allaqachon ochiq smena bor');
    }

    $shiftId = Db::tx(function () use ($user, $opening, $note): int {
        $id = Db::insert('shifts', [
            'cashier_id'      => $user['id'],
            'opening_balance' => $opening,
            'status'          => 'open',
            'opened_at'       => Tz::now(),
            'note'            => $note,
        ]);
        Audit::log(
            (int)$user['id'],
            'SMENA_OCHILDI',
            "Boshlang'ich balans: " . number_format($opening, 0, '.', ',') . " so'm"
        );
        return $id;
    });

    $shift = Db::one('SELECT * FROM shifts WHERE id = ?', [$shiftId]);
    Http::json(Shape::shift($shift, compute_shift_totals($shift), $user));
});

// =======================================================================
// POST /pos/shifts/{shift_id}/force-close
// =======================================================================
Router::post('/shifts/{shift_id}/force-close', function (array $p): never {
    // Boshqa xodimning ochiq qolgan smenasini admin yopadi.
    //
    // Ilgari smenani FAQAT uning egasi yopa olardi. Kassir smenani yopmasdan
    // ketib qolsa (kasal bo'lsa, ishdan bo'shasa yoki hisobi bloklansa),
    // smena abadiy ochiq qolardi: kutilgan kassa cheksiz o'sib borardi va
    // o'sha kassir boshqa hech qachon yangi smena ocha olmasdi.
    $user = Auth::require(['admin', 'manager'], 'Faqat admin yoki menejer yopa oladi');
    $shiftId = Router::id($p, 'shift_id');
    $b = Http::body();

    $closing = Http::num($b, 'closing_balance', 0.0, 'ge', 0, null, 'Yakuniy balans') ?? 0.0;
    $note = trim((string)($b['note'] ?? ''));

    $shift = Db::one('SELECT * FROM shifts WHERE id = ?', [$shiftId]);
    if ($shift === null) {
        fail(404, 'Smena topilmadi');
    }
    if ($shift['status'] !== 'open') {
        fail(400, 'Bu smena allaqachon yopilgan');
    }
    if ($note === '') {
        fail(400, "Boshqa xodimning smenasini yopish sababini yozing");
    }

    $closedAt = Tz::now();
    $shift['closed_at'] = $closedAt;
    $totals = compute_shift_totals($shift);
    $difference = $closing - $totals['expected_cash'];

    Db::tx(function () use ($shift, $shiftId, $user, $totals, $closing, $difference, $note, $closedAt): void {
        Db::update('shifts', $shiftId, array_merge($totals, [
            'closed_at'       => $closedAt,
            'cash_difference' => $difference,
            'closing_balance' => $closing,
            'note'            => $note,
            'closed_by'       => $user['id'],
            'status'          => 'closed',
        ]));

        $owner = Db::one('SELECT username FROM employees WHERE id = ?', [(int)$shift['cashier_id']]);
        Audit::log(
            (int)$user['id'],
            'SMENA_MAJBURIY_YOPILDI',
            'Xodim: @' . ($owner['username'] ?? $shift['cashier_id']) . '. '
            . 'Kutilgan: ' . number_format($totals['expected_cash'], 0, '.', ',') . " so'm. "
            . 'Haqiqiy: ' . number_format($closing, 0, '.', ',') . " so'm. "
            . 'Farq: ' . number_format($difference, 0, '.', ',') . " so'm. Sabab: $note"
        );
    });

    $final = Db::one('SELECT * FROM shifts WHERE id = ?', [$shiftId]);
    $cashier = Db::one('SELECT * FROM employees WHERE id = ?', [(int)$final['cashier_id']]);
    Http::json(Shape::shift($final, totals_for_display($final), $cashier));
});

// =======================================================================
// POST /pos/shifts/close
// =======================================================================
Router::post('/shifts/close', function (): never {
    $user = Auth::user();
    $b = Http::body();

    $closing = Http::num($b, 'closing_balance', 0.0, 'ge', 0, null, 'Yakuniy balans') ?? 0.0;
    $note = trim((string)($b['note'] ?? ''));

    $shift = Db::one(
        "SELECT * FROM shifts WHERE cashier_id = ? AND status = 'open' ORDER BY id DESC",
        [$user['id']]
    );
    if ($shift === null) {
        fail(404, 'Ochiq smena topilmadi');
    }

    // Yopish vaqtini AVVAL qo'yamiz, so'ng hisoblaymiz: shunda hisob aynan
    // shu oynaga tegishli bo'ladi va keyin yozilgan sotuv unga tushmaydi.
    $closedAt = Tz::now();
    $shift['closed_at'] = $closedAt;
    $totals = compute_shift_totals($shift);
    $expected = $totals['expected_cash'];
    $difference = $closing - $expected;

    // Farq bo'lsa sabab MAJBURIY.
    if (abs($difference) > 0.01 && $note === '') {
        fail(400, 'Kassa farqi uchun sabab yozing');
    }

    Db::tx(function () use ($shift, $user, $totals, $closing, $difference, $expected, $note, $closedAt): void {
        // Hisobni MUZLATAMIZ. Ilgari u har so'rovda qayta hisoblanardi va
        // keyinroq qilingan vozvrat allaqachon yopilgan smenaning kamomadini
        // o'zgartirib yuborardi.
        Db::update('shifts', (int)$shift['id'], array_merge($totals, [
            'closed_at'       => $closedAt,
            'cash_difference' => $difference,
            'closing_balance' => $closing,
            'note'            => $note === '' ? null : $note,
            'closed_by'       => $user['id'],
            'status'          => 'closed',
        ]));

        Audit::log(
            (int)$user['id'],
            'SMENA_YOPILDI',
            'Kutilgan: ' . number_format($expected, 0, '.', ',') . " so'm "
            . "(boshlang'ich " . number_format(Db::f($shift['opening_balance']), 0, '.', ',')
            . ' + naqd sotuv ' . number_format($totals['total_cash'], 0, '.', ',')
            . ' - naqd xarajat ' . number_format($totals['total_expenses'], 0, '.', ',')
            . ' - naqd vozvrat ' . number_format($totals['total_refunds'], 0, '.', ',') . '). '
            . 'Haqiqiy: ' . number_format($closing, 0, '.', ',') . " so'm. "
            . 'Farq: ' . number_format($difference, 0, '.', ',') . " so'm. "
            . 'Sabab: ' . ($note === '' ? '-' : $note)
        );
    });

    $final = Db::one('SELECT * FROM shifts WHERE id = ?', [(int)$shift['id']]);
    Http::json(Shape::shift($final, totals_for_display($final), $user));
});
