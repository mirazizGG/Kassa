<?php
/**
 * /audit — tizim amallari tarixi. FAQAT ADMIN uchun (ikkala endpoint ham).
 *
 * SAHIFALASH HAQIQIY: javob X-Total-Count sarlavhasini beradi va `limit`
 * 500 bilan cheklanadi. Ilgari sahifa limit/offset ni umuman yubormasdi,
 * standart 100 ta qatorni olardi va o'sha sonni "hammasi" deb ko'rsatardi —
 * ya'ni jurnal kerak bo'lgan YAGONA paytda, tekshiruv vaqtida, u jimgina
 * qirqilib, hech narsa tushirib qoldirilmagandek ko'rinardi.
 */

declare(strict_types=1);

/** Ikkala endpoint uchun umumiy filtr. */
function audit_filter(): array
{
    $where = ['1=1'];
    $params = [];

    $employeeId = Http::qInt('employee_id');
    if ($employeeId) {
        $where[] = 'user_id = ?';
        $params[] = $employeeId;
    }

    $action = Http::q('action');
    if ($action !== null) {
        $where[] = 'action = ?';
        $params[] = $action;
    }

    $search = Http::q('search');
    if ($search !== null && $search !== '') {
        // Registrga sezgir bo'lmagan qidiruv — PostgreSQL da oddiy LIKE
        // hech narsa topmasdi.
        $where[] = Db::ilike('details');
        $params[] = "%$search%";
    }

    // Sana chegaralari DO'KON kuni bo'yicha.
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

    return [implode(' AND ', $where), $params];
}

// =======================================================================
// GET /audit/logs
// =======================================================================
Router::get('/logs', function (): never {
    Auth::require(['admin'], 'Ruxsat berilmagan');

    [$whereSql, $params] = audit_filter();

    $limit = Http::qInt('limit', 100, 1, 500) ?? 100;
    $offset = max(0, Http::qInt('offset', 0) ?? 0);

    // Jami sonni qisqa muddat keshlaymiz.
    //
    // Sabab: qidiruv "%matn%" ko'rinishida bo'lgani uchun indeks yordam
    // bermaydi — baza 150 mingdan ortiq yozuvni o'qib chiqadi. Sahifa esa
    // o'zi yangilanib turadi, ya'ni bu skanerlash takrorlanaveradi.
    // QATORLARNING O'ZI har doim jonli o'qiladi; keshda faqat SON turadi va
    // u yarim daqiqadan ko'proq eskirmaydi.
    require_once APP_DIR . '/Cache.php';
    $countKey = 'audit-count:' . md5($whereSql . '|' . implode('|', array_map('strval', $params)));
    $total = (int)Cache::remember(
        $countKey,
        30,
        fn() => (int)Db::val("SELECT COUNT(*) FROM audit_logs WHERE $whereSql", $params, 0)
    );
    header('X-Total-Count: ' . $total);
    header('Access-Control-Expose-Headers: X-Total-Count');

    $rows = Db::all(
        "SELECT * FROM audit_logs WHERE $whereSql
         ORDER BY created_at DESC, id DESC LIMIT $limit OFFSET $offset",
        $params
    );

    $users = Shape::lookup('employees', array_column($rows, 'user_id'));

    Http::json(array_map(function ($r) use ($users) {
        $u = $users[(int)($r['user_id'] ?? 0)] ?? null;
        return [
            'id'         => Db::i($r['id']),
            'user_id'    => Db::i($r['user_id'] ?? 0),
            'user'       => Shape::employee($u),
            'action'     => $r['action'] ?? '',
            'details'    => (string)($r['details'] ?? ''),
            'created_at' => Tz::iso($r['created_at']),
        ];
    }, $rows));
});

// =======================================================================
// GET /audit/export-excel
// =======================================================================
Router::get('/export-excel', function (): never {
    Auth::require(['admin'], 'Ruxsat berilmagan');
    require_once APP_DIR . '/Xlsx.php';

    [$whereSql, $params] = audit_filter();

    $rows = Db::all(
        "SELECT * FROM audit_logs WHERE $whereSql ORDER BY created_at DESC, id DESC LIMIT 50000",
        $params
    );
    $users = Shape::lookup('employees', array_column($rows, 'user_id'));

    $data = array_map(function ($r) use ($users) {
        $username = $users[(int)($r['user_id'] ?? 0)]['username'] ?? ('ID: ' . ($r['user_id'] ?? '-'));
        return [
            Db::i($r['id']),
            Tz::parse($r['created_at'])?->setTimezone(Tz::shopTz())->format('d.m.Y H:i:s') ?? '',
            // csv_safe: "=" bilan boshlangan katak Excel'da FORMULA bo'lib
            // bajariladi — hisobotni ochgan admin kompyuterida.
            Xlsx::safe($username),
            Xlsx::safe($r['action'] ?? ''),
            Xlsx::safe($r['details'] ?? ''),
        ];
    }, $rows);

    Xlsx::download(
        ['ID', 'Sana', 'Xodim', 'Amal', 'Tafsilotlar'],
        $data,
        'audit_' . date('Ymd') . '.xlsx',
        'AuditLog'
    );
});
