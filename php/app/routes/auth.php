<?php
/**
 * /auth — kirish, chiqish, xodimlar, davomat.
 *
 * SESSIYA MODELI: bir foydalanuvchi — bitta faol sessiya, qat'iy.
 * JWT ichida `sid` bor va u `employees.session_token` ga TENG bo'lishi shart.
 * Sessiya tirik turganda qayta kirish 409 qaytaradi; mijoz `force=true`
 * bilan qayta uradi va bu audit jurnaliga FORCE_LOGOUT bo'lib tushadi.
 */

declare(strict_types=1);

// =======================================================================
// POST /auth/token  — kirish (form-data)
// =======================================================================
Router::post('/token', function (): never {
    // Parolni taxmin qilishni sekinlashtiramiz: bir IP dan daqiqasiga 20 ta.
    if (!RateLimit::hit('login:' . Http::clientIp(), 20, 60)) {
        fail(429, "Juda ko'p urinish. Bir daqiqadan keyin qayta urinib ko'ring.");
    }

    $f = Http::form();
    $username = trim((string)($f['username'] ?? ''));
    $password = (string)($f['password'] ?? '');
    $force = in_array(strtolower((string)($f['force'] ?? '')), ['1', 'true', 'yes', 'on'], true);

    if ($username === '' || $password === '') {
        fail(401, "Login yoki parol noto'g'ri", ['WWW-Authenticate' => 'Bearer']);
    }

    $user = Db::one('SELECT * FROM employees WHERE username = ?', [$username]);

    // Noma'lum login uchun ham parolni HISOBLAYMIZ. Aks holda javob sezilarli
    // tez qaytardi va shu farq orqali qaysi loginlar mavjudligini aniqlash
    // mumkin edi.
    if ($user === null) {
        Auth::hashPassword($password);
        fail(401, "Login yoki parol noto'g'ri", ['WWW-Authenticate' => 'Bearer']);
    }

    if (!Auth::verifyPassword($password, $user['hashed_password'])) {
        fail(401, "Login yoki parol noto'g'ri", ['WWW-Authenticate' => 'Bearer']);
    }

    if (!Db::b($user['is_active'])) {
        fail(403, 'Hisobingiz bloklangan. Iltimos, administratorga murojaat qiling.');
    }

    // "sotuvchi" roli saytga KIRMAYDI — u faqat bot orqali ishga kelish/
    // ketishni belgilash uchun mavjud.
    if ($user['role'] === 'sotuvchi') {
        fail(403, "Sotuvchi lavozimi saytga kira olmaydi. Faqat Telegram bot "
            . "orqali ishga kelish/ketishni belgilang.");
    }

    $now = Tz::now();
    $expiresAt = (new DateTimeImmutable($now, Tz::utcTz()))
        ->modify('+' . ACCESS_TOKEN_EXPIRE_MINUTES . ' minutes')
        ->format('Y-m-d H:i:s.u');

    $hasActive = !empty($user['session_token'])
        && !empty($user['session_expires_at'])
        && $user['session_expires_at'] > $now;

    if ($hasActive && !$force) {
        fail(409, 'Bu foydalanuvchi boshqa qurilmada tizimga kirgan. '
            . 'Boshqa qurilmadan chiqib, shu qurilmadan kirasizmi?');
    }

    $sessionId = Auth::newSessionId();
    $accessToken = Auth::createToken($user['username'], $sessionId);

    Db::tx(function () use ($user, $sessionId, $expiresAt, $hasActive, $force): void {
        if ($hasActive && $force) {
            // Foydalanuvchi login/parol bilan tasdiqladi — eski sessiyani
            // majburan yopamiz va buni jurnalga yozamiz.
            Audit::log(
                (int)$user['id'],
                'FORCE_LOGOUT',
                'Boshqa qurilmadagi sessiya majburan yopildi: @' . $user['username']
            );
        }
        Db::update('employees', (int)$user['id'], [
            'session_token'      => $sessionId,
            'session_expires_at' => $expiresAt,
        ]);
        Audit::log((int)$user['id'], 'LOGIN', 'Tizimga kirdi: @' . $user['username']);
    });

    Http::json([
        'access_token' => $accessToken,
        'token_type'   => 'bearer',
        'role'         => $user['role'],
        'permissions'  => $user['permissions'] ?? 'pos',
        'username'     => $user['username'],
        'user_id'      => Db::i($user['id']),
    ]);
});

// =======================================================================
// POST /auth/logout
// =======================================================================
Router::post('/logout', function (): never {
    $user = Auth::user();
    Db::tx(function () use ($user): void {
        // session_token ni NULL qilamiz. get_current_user solishtiruvni
        // SHARTSIZ bajargani uchun chiqib ketilgan token DARHOL ishlamay
        // qoladi. Ilgari shart `if user.session_token and ...` edi va NULL
        // "yolg'on" bo'lgani uchun tekshiruv butunlay o'tkazib yuborilardi.
        Db::update('employees', (int)$user['id'], [
            'session_token'      => null,
            'session_expires_at' => null,
        ]);
        Audit::log((int)$user['id'], 'LOGOUT', 'Tizimdan chiqdi: @' . $user['username']);
    });
    Http::json(['status' => 'success']);
});

// =======================================================================
// POST /auth/employees
// =======================================================================
Router::post('/employees', function (): never {
    $current = Auth::require(['admin', 'manager'], 'Only admins and managers can create employees');
    $b = Http::body();

    $username = Http::reqStr($b, 'username', 150, 'Login');
    $password = Http::reqStr($b, 'password', 200, 'Parol');
    $role = Http::reqStr($b, 'role', 40, 'Lavozim');

    if (!in_array($role, ['admin', 'manager', 'cashier', 'warehouse', 'sotuvchi'], true)) {
        fail(422, "Lavozim noto'g'ri.");
    }
    if ($current['role'] === 'manager' && $role !== 'cashier') {
        fail(403, 'Menejer faqat kassir yarata oladi');
    }
    // Yangi admin qo'shishni faqat BOSH admin qila oladi.
    if ($role === 'admin' && $current['username'] !== PRIMARY_ADMIN_USERNAME) {
        fail(403, "Yangi admin qo'shishni faqat bosh admin qila oladi");
    }

    if (Db::one('SELECT id FROM employees WHERE username = ?', [$username]) !== null) {
        fail(400, 'Bu login band. Boshqasini tanlang.');
    }

    $id = Db::tx(function () use ($b, $current, $username, $password, $role): int {
        $id = Db::insert('employees', [
            'username'        => $username,
            'hashed_password' => Auth::hashPassword($password),
            'role'            => $role,
            'permissions'     => Http::str($b, 'permissions', 'pos', 200),
            'is_active'       => true,
            'full_name'       => Http::str($b, 'full_name', null, 200),
            'phone'           => Http::str($b, 'phone', null, 30),
            'address'         => Http::str($b, 'address', null, 300),
            'passport'        => Http::str($b, 'passport', null, 50),
            'notes'           => Http::str($b, 'notes', null, 1000),
        ]);
        Audit::log((int)$current['id'], 'YANGI_XODIM', "Xodim yaratildi: $username (Rol: $role)");
        return $id;
    });

    Http::json(Shape::employee(Db::one('SELECT * FROM employees WHERE id = ?', [$id])));
});

// =======================================================================
// GET /auth/employees
// =======================================================================
Router::get('/employees', function (): never {
    $current = Auth::user();
    if (!in_array($current['role'], ['admin', 'manager', 'cashier'], true)) {
        fail(403, 'Ruxsat berilmagan');
    }

    // Menejer admin qatorlarini KO'RMAYDI, kassir esa faqat o'zini —
    // bu atayin yashirish, xato emas.
    if ($current['role'] === 'manager') {
        $rows = Db::all("SELECT * FROM employees WHERE role <> 'admin' ORDER BY id");
    } elseif ($current['role'] === 'cashier') {
        $rows = Db::all('SELECT * FROM employees WHERE id = ?', [(int)$current['id']]);
    } else {
        $rows = Db::all('SELECT * FROM employees ORDER BY id');
    }

    Http::json(array_map(fn($r) => Shape::employee($r), $rows));
});

// =======================================================================
// PATCH /auth/employees/{employee_id}
// =======================================================================
Router::patch('/employees/{employee_id}', function (array $p): never {
    $current = Auth::user();
    $employeeId = Router::id($p, 'employee_id');
    $b = Http::body();

    if (!in_array($current['role'], ['admin', 'manager'], true) && (int)$current['id'] !== $employeeId) {
        fail(403, "Ruxsat berilmagan. Faqat admin va menejerlar xodimlarni o'zgartirishi mumkin.");
    }

    $target = Db::one('SELECT * FROM employees WHERE id = ?', [$employeeId]);
    if ($target === null) {
        fail(404, 'Employee not found');
    }

    // BOSH ADMIN QULFI: bu hisobni API orqali o'zgartirib bo'lmaydi.
    // Paroli faqat serverda reset_admin skripti bilan tiklanadi.
    if ($target['username'] === PRIMARY_ADMIN_USERNAME) {
        fail(403, "Bosh administrator hisobini o'zgartirib bo'lmaydi.");
    }

    // Boshqa admin hisobini faqat bosh admin tahrirlay oladi.
    if ($target['role'] === 'admin'
        && (int)$target['id'] !== (int)$current['id']
        && $current['username'] !== PRIMARY_ADMIN_USERNAME) {
        fail(403, 'Boshqa admin hisobini faqat bosh admin tahrirlay oladi');
    }

    $newRole = array_key_exists('role', $b) ? Http::str($b, 'role', null, 40, 'Lavozim') : null;
    $hasRole = $newRole !== null;

    // Admin ROLINI berishni faqat bosh admin qila oladi.
    if ($hasRole && $newRole === 'admin' && $target['role'] !== 'admin'
        && $current['username'] !== PRIMARY_ADMIN_USERNAME) {
        fail(403, 'Admin rolini faqat bosh admin bera oladi');
    }

    $hasActive = array_key_exists('is_active', $b);
    $newActive = $hasActive ? Http::bool($b, 'is_active', true) : null;

    if ($hasActive && $employeeId === (int)$current['id'] && $newActive === false) {
        fail(400, "O'zingizni o'zingiz bloklay olmaysiz");
    }
    if ($hasActive && $current['role'] === 'manager'
        && $target['role'] !== 'cashier' && (int)$target['id'] !== (int)$current['id']) {
        fail(403, 'Menejer faqat kassirlarni bloklay oladi');
    }
    if ($hasRole && $employeeId === (int)$current['id'] && $newRole !== $target['role']) {
        fail(400, "O'z rolingizni o'zingiz o'zgartira olmaysiz");
    }
    if ($current['role'] === 'manager'
        && $target['role'] !== 'cashier' && (int)$target['id'] !== (int)$current['id']) {
        fail(403, 'Menejer faqat kassirlarni tahrirlay oladi');
    }
    if ($hasRole && $current['role'] === 'manager'
        && $newRole !== 'cashier' && (int)$target['id'] !== (int)$current['id']) {
        fail(403, 'Menejer faqat kassir rolini bera oladi');
    }

    // Faqat KELGAN maydonlar o'zgaradi (PATCH semantikasi).
    $data = [];
    foreach (['username' => 150, 'permissions' => 200, 'full_name' => 200,
              'phone' => 30, 'address' => 300, 'passport' => 50, 'notes' => 1000] as $field => $max) {
        if (array_key_exists($field, $b)) {
            $data[$field] = Http::str($b, $field, null, $max, $field);
        }
    }
    if ($hasRole) {
        $data['role'] = $newRole;
    }
    if ($hasActive) {
        $data['is_active'] = $newActive;
    }

    $password = Http::str($b, 'password', null, 200, 'Parol');
    if ($password !== null) {
        $data['hashed_password'] = Auth::hashPassword($password);
        // Parol almashtirilsa, eski sessiya BEKOR bo'lsin. Aks holda parolni
        // o'g'irlagan odam parol almashtirilganidan keyin ham o'z tokeni
        // bilan 600 daqiqagacha ishlayverardi — ya'ni parolni almashtirish
        // hujumni to'xtatmasdi.
        $data['session_token'] = null;
        $data['session_expires_at'] = null;
    }

    if (isset($data['username']) && $data['username'] !== $target['username']) {
        $clash = Db::one('SELECT id FROM employees WHERE username = ? AND id <> ?',
            [$data['username'], $employeeId]);
        if ($clash !== null) {
            fail(400, 'Bu login band. Boshqasini tanlang.');
        }
    }

    Db::tx(function () use ($data, $employeeId, $current, $target): void {
        if ($data !== []) {
            Db::update('employees', $employeeId, $data);
        }
        Audit::log((int)$current['id'], 'XODIM_TAHRIRLANDI',
            "Xodim: {$target['username']} (ID: $employeeId)");
    });

    Http::json(Shape::employee(Db::one('SELECT * FROM employees WHERE id = ?', [$employeeId])));
});

// =======================================================================
// DELETE /auth/employees/{employee_id}
// =======================================================================
Router::delete('/employees/{employee_id}', function (array $p): never {
    $current = Auth::require(['admin'], 'Only admins can delete employees');
    $employeeId = Router::id($p, 'employee_id');

    if ((int)$current['id'] === $employeeId) {
        fail(400, "O'zingizni o'chira olmaysiz");
    }

    $target = Db::one('SELECT * FROM employees WHERE id = ?', [$employeeId]);
    if ($target === null) {
        fail(404, 'Employee not found');
    }
    if ($target['username'] === PRIMARY_ADMIN_USERNAME) {
        fail(400, "Bosh administratorni o'chirib bo'lmaydi");
    }
    if ($target['role'] === 'admin' && $current['username'] !== PRIMARY_ADMIN_USERNAME) {
        fail(403, "Boshqa admin hisobini faqat bosh admin o'chira oladi");
    }

    // Ishlagan xodimni O'CHIRIB BO'LMAYDI — uni BLOKLASH kerak.
    //
    // Xodim id si sotuv, smena, to'lov, xarajat va audit satrlarida turadi.
    // O'chirish bu satrlarni yetim qoldirardi: cheklarda kassir yo'qolib,
    // audit jurnali "kim qildi" degan savolga javob bera olmay qolardi.
    $guards = [
        ['sales',      'cashier_id', 'savdo'],
        ['shifts',     'cashier_id', 'smena'],
        ['payments',   'created_by', "to'lov"],
        ['expenses',   'created_by', 'xarajat'],
        ['audit_logs', 'user_id',    'audit yozuvi'],
    ];
    foreach ($guards as [$table, $col, $nomi]) {
        $count = (int)Db::val(
            'SELECT COUNT(*) FROM ' . Db::quoteId($table) . ' WHERE ' . Db::quoteId($col) . ' = ?',
            [$employeeId], 0
        );
        if ($count > 0) {
            fail(409, "Bu xodimda $count ta $nomi tarixi bor — o'chirib bo'lmaydi. "
                . "Uning o'rniga hisobni bloklang (faol emas qilib qo'ying).");
        }
    }

    Db::tx(function () use ($employeeId, $current, $target): void {
        Db::delete('employees', $employeeId);
        Audit::log((int)$current['id'], 'XODIM_OCHIRILDI',
            "Xodim o'chirildi: {$target['username']} (ID: $employeeId)");
    });

    Http::noContent();
});

// =======================================================================
// GET /auth/attendance
// =======================================================================
Router::get('/attendance', function (): never {
    Auth::require(['admin', 'manager'], 'Ruxsat berilmagan');

    $where = ['1=1'];
    $params = [];

    $employeeId = Http::qInt('employee_id');
    if ($employeeId) {
        $where[] = 'employee_id = ?';
        $params[] = $employeeId;
    }

    // Sana chegaralari DO'KON kuni bo'yicha. Python versiyasida bu yerda
    // oddiy strptime turardi, ya'ni kun UTC bo'yicha kesilardi va davomat
    // hisoboti smenalar/audit ko'rsatadigan kundan boshqa oraliqni qamrardi.
    $start = Tz::parseFilterDate(Http::q('start_date'));
    if ($start !== null) {
        $where[] = 'created_at >= ?';
        $params[] = $start;
    }
    $end = Http::q('end_date');
    if ($end !== null) {
        [, $next] = Tz::dayBoundsUtc($end);
        $where[] = 'created_at < ?';
        $params[] = $next;
    }

    $rows = Db::all(
        'SELECT * FROM attendance WHERE ' . implode(' AND ', $where)
        . ' ORDER BY created_at DESC LIMIT 1000',
        $params
    );

    $employees = Shape::lookup('employees', array_column($rows, 'employee_id'));
    Http::json(array_map(
        fn($r) => Shape::attendance($r, $employees[(int)$r['employee_id']] ?? null),
        $rows
    ));
});
