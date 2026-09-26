<?php
/**
 * Kassa Telegram boti — mantiq (menyular, hisobot, eslatma, ogohlantirish).
 *
 * Ikki joyda ishlaydi:
 *   - bin/bot.php (to'g'ridan-to'g'ri rejim) — do'kon kompyuteri bazaga
 *     o'zi ulanadi, xabarlarni o'zi yuboradi;
 *   - app/routes/bot.php (server rejimi) — /bot/update va /bot/tick. Bu
 *     yerda Telegram::collect() yoqilgan: xabarlar yuborilmaydi, "amallar"
 *     ro'yxatiga yig'iladi va javobda do'kon kompyuteridagi ko'prikka
 *     qaytariladi. Baza paroli do'kon kompyuterida umuman turmaydi.
 *
 * Holat: logs/bot-state.json (kunlik vazifalar, ogohlantirish kursorlari),
 * server rejimida suhbat bosqichlari ham logs/bot-conv.json da.
 */

declare(strict_types=1);

const STATE_FILE = ROOT_DIR . '/logs/bot-state.json';

// Tugma matnlari
const B_BALANCE   = '💰 Balansim';
const B_BONUS     = '🎁 Bonuslarim';
const B_IN        = '🎬 Ishga kelish';
const B_OUT       = '🛑 Ishdan ketish';
const B_REPORT    = '📊 Bugungi hisobot';
const B_WHO       = '👥 Kim ishda?';
const B_DATA      = "📦 Ma'lumotlar";
const B_BROADCAST = '📢 Reklama yuborish';

// =======================================================================
// Holat
// =======================================================================

function state_load(): array
{
    $raw = @file_get_contents(STATE_FILE);
    $data = $raw ? json_decode($raw, true) : null;
    return is_array($data) ? $data : [];
}

function state_save(array $state): void
{
    $tmp = STATE_FILE . '.tmp';
    file_put_contents($tmp, json_encode($state, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE));
    @rename($tmp, STATE_FILE);
}

// =======================================================================
// Yordamchilar
// =======================================================================

function h(?string $s): string
{
    return htmlspecialchars((string)$s, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
}

function money(float $v): string
{
    return number_format($v, 0, '.', ' ') . " so'm";
}

function qty(float $v): string
{
    return rtrim(rtrim(number_format($v, 3, '.', ''), '0'), '.');
}

/** Bazadagi naive-UTC qiymatni do'kon vaqtida formatlaydi. */
function shop_time(?string $dbValue, string $format = 'H:i'): string
{
    $dt = Tz::parse($dbValue);
    return $dt === null ? '-' : $dt->setTimezone(Tz::shopTz())->format($format);
}

function shop_now(string $format): string
{
    return (new DateTimeImmutable('now', Tz::shopTz()))->format($format);
}

function digits(?string $phone): string
{
    return preg_replace('/\D+/', '', (string)$phone) ?? '';
}

function emp_name(?array $e): string
{
    if ($e === null) {
        return "O'chirilgan xodim";
    }
    return (string)($e['full_name'] ?: $e['username']);
}

function find_employee(int $tgId): ?array
{
    return Db::one('SELECT * FROM employees WHERE telegram_id = ?', [$tgId]);
}

function find_client(int $tgId): ?array
{
    return Db::one('SELECT * FROM clients WHERE telegram_id = ?', [$tgId]);
}

/** Telefon raqami (oxirgi 9 raqam) bo'yicha xodim. Yozilish shakli muhim emas. */
function employee_by_phone(string $phone): ?array
{
    $tail = substr(digits($phone), -9);
    if (strlen($tail) < 9) {
        return null;
    }
    foreach (Db::all('SELECT * FROM employees WHERE phone IS NOT NULL') as $e) {
        if (substr(digits($e['phone']), -9) === $tail) {
            return $e;
        }
    }
    return null;
}

function attendance_status(int $employeeId): string
{
    $last = Db::one(
        'SELECT status FROM attendance WHERE employee_id = ? ORDER BY created_at DESC, id DESC LIMIT 1',
        [$employeeId]
    );
    return ($last['status'] ?? 'out') === 'in' ? 'in' : 'out';
}

function is_admin_chat(int $tgId): bool
{
    $emp = find_employee($tgId);
    if ($emp !== null && $emp['role'] === 'admin' && Db::b($emp['is_active'])) {
        return true;
    }
    return (string)$tgId === trim((string)env('TELEGRAM_ADMIN_CHAT_ID'));
}

/** Hisobot va ogohlantirishlar oluvchilari: bog'langan faol adminlar + .env dagi chat. */
function admin_chats(): array
{
    $ids = array_map(
        fn($r) => (string)$r['telegram_id'],
        Db::all(
            "SELECT telegram_id FROM employees WHERE role = 'admin' AND is_active = ? AND telegram_id IS NOT NULL",
            [true]
        )
    );
    $env = trim((string)env('TELEGRAM_ADMIN_CHAT_ID'));
    if ($env !== '') {
        $ids[] = $env;
    }
    return array_values(array_unique($ids));
}

function notify_admins(string $html): void
{
    foreach (admin_chats() as $chat) {
        Telegram::send($chat, $html);
    }
}

function menu_for(string $role, string $attendance = 'out'): array
{
    return match ($role) {
        'client' => Telegram::keyboard([[B_BALANCE], [B_BONUS]]),
        'admin'  => Telegram::keyboard([[B_REPORT], [B_WHO, B_DATA], [B_BROADCAST]]),
        default  => Telegram::keyboard([[$attendance === 'in' ? B_OUT : B_IN]]),
    };
}

function store_settings(): array
{
    return Db::one('SELECT * FROM store_settings ORDER BY id LIMIT 1') ?? [];
}

// =======================================================================
// Suhbat (xabarlarni qayta ishlash)
// =======================================================================

function handle_update(array $update, array &$conv): void
{
    $msg = $update['message'] ?? null;
    if (!is_array($msg) || ($msg['chat']['type'] ?? '') !== 'private') {
        return;
    }
    $chatId = (int)$msg['chat']['id'];
    $fromId = (int)($msg['from']['id'] ?? 0);
    $text = trim((string)($msg['text'] ?? ''));
    $step = $conv[$chatId]['step'] ?? null;

    if ($text === '/cancel') {
        unset($conv[$chatId]);
        Telegram::send($chatId, 'Bekor qilindi.', main_menu($fromId));
        return;
    }
    if ($text === '/start' || str_starts_with($text, '/start ')) {
        unset($conv[$chatId]);
        cmd_start($chatId, $fromId, $conv);
        return;
    }

    // --- Bosqichli suhbatlar -------------------------------------------
    if ($step === 'contact') {
        on_contact($chatId, $fromId, $msg, $conv);
        return;
    }
    if ($step === 'name') {
        on_name($chatId, $fromId, $text, $conv);
        return;
    }
    if ($step === 'broadcast') {
        unset($conv[$chatId]);
        do_broadcast($chatId, $fromId, $msg);
        return;
    }

    // --- Tugmalar ------------------------------------------------------
    match ($text) {
        B_BALANCE   => on_balance($chatId, $fromId),
        B_BONUS     => on_bonus($chatId, $fromId),
        B_IN        => on_attendance($chatId, $fromId, 'in'),
        B_OUT       => on_attendance($chatId, $fromId, 'out'),
        B_REPORT    => is_admin_chat($fromId) ? Telegram::send($chatId, build_daily_report(Tz::shopToday())) : null,
        B_WHO       => is_admin_chat($fromId) ? Telegram::send($chatId, who_is_working()) : null,
        B_DATA      => is_admin_chat($fromId) ? send_data_files($chatId) : null,
        B_BROADCAST => start_broadcast($chatId, $fromId, $conv),
        default     => Telegram::send($chatId, 'Menyudagi tugmalardan foydalaning. Menyu: /start'),
    };
}

function main_menu(int $tgId): ?array
{
    $emp = find_employee($tgId);
    if ($emp !== null) {
        return menu_for($emp['role'], attendance_status((int)$emp['id']));
    }
    if (is_admin_chat($tgId)) {
        return menu_for('admin');
    }
    return find_client($tgId) !== null ? menu_for('client') : null;
}

function cmd_start(int $chatId, int $tgId, array &$conv): void
{
    $emp = find_employee($tgId);
    if ($emp !== null) {
        if (!Db::b($emp['is_active'])) {
            Telegram::send($chatId, "Hisobingiz bloklangan. Admin bilan bog'laning.");
            return;
        }
        Telegram::send($chatId, 'Salom, <b>' . h(emp_name($emp)) . '</b>! 👋',
            menu_for($emp['role'], attendance_status((int)$emp['id'])));
        return;
    }
    if (is_admin_chat($tgId)) {
        Telegram::send($chatId, 'Salom! 👋 Admin menyusi:', menu_for('admin'));
        return;
    }
    $client = find_client($tgId);
    if ($client !== null) {
        // Xodim botga telefoni saytga yozilmasidan OLDIN kirgan bo'lsa, mijoz
        // bo'lib qolgan. Admin keyin telefonini qo'shgan bo'lsa — endi
        // xodimga o'tkazamiz. Faqat hali hech kimga bog'lanmagan xodim:
        // boshqa odamning bog'langan hisobini tortib olib bo'lmasin.
        $e = employee_by_phone((string)$client['phone']);
        if ($e !== null && empty($e['telegram_id'])) {
            Db::tx(function () use ($e, $client, $tgId): void {
                Db::run('UPDATE clients SET telegram_id = NULL WHERE id = ?', [(int)$client['id']]);
                Db::run('UPDATE employees SET telegram_id = ?, full_name = COALESCE(full_name, ?) WHERE id = ?',
                    [$tgId, $client['name'], (int)$e['id']]);
            });
            bot_log("mijoz xodimga o'tkazildi: {$e['username']} <- $tgId");
            $e = find_employee($tgId);
            if (!Db::b($e['is_active'])) {
                Telegram::send($chatId, "Hisobingiz bloklangan. Admin bilan bog'laning.");
                return;
            }
            Telegram::send($chatId,
                'Siz tizimda xodim sifatida tanildingiz: <b>' . h(emp_name($e)) . "</b> ✅\n"
                . 'Endi bot orqali ish vaqtingizni belgilashingiz mumkin.',
                menu_for($e['role'], attendance_status((int)$e['id'])));
            return;
        }
        Telegram::send($chatId, 'Salom, <b>' . h($client['name']) . "</b>! 👋\nDo'konimizga xush kelibsiz.",
            menu_for('client'));
        return;
    }

    $conv[$chatId] = ['step' => 'contact'];
    Telegram::send(
        $chatId,
        "Assalomu alaykum! Do'konimizga xush kelibsiz.\nRo'yxatdan o'tish uchun telefon raqamingizni yuboring.",
        [
            'keyboard'          => [[['text' => '📱 Telefon raqamni yuborish', 'request_contact' => true]]],
            'resize_keyboard'   => true,
            'one_time_keyboard' => true,
        ]
    );
}

function on_contact(int $chatId, int $tgId, array $msg, array &$conv): void
{
    $contact = $msg['contact'] ?? null;
    if (!is_array($contact)) {
        Telegram::send($chatId, "Iltimos, pastdagi <b>tugma</b> orqali raqamingizni yuboring.");
        return;
    }
    // Faqat O'Z raqami: aks holda istalgan kishi boshqa odamning (masalan
    // adminning) kontaktini yuborib, o'sha xodim sifatida tanilib qolardi.
    if ((int)($contact['user_id'] ?? 0) !== $tgId) {
        Telegram::send($chatId, "Iltimos, pastdagi <b>tugma</b> orqali o'zingizning raqamingizni yuboring. "
            . "Boshqa odamning kontaktini qabul qila olmaymiz.");
        return;
    }
    $phone = (string)$contact['phone_number'];
    if (!str_starts_with($phone, '+')) {
        $phone = '+' . $phone;
    }
    $conv[$chatId] = ['step' => 'name', 'phone' => $phone];
    Telegram::send($chatId,
        "Rahmat! Endi iltimos, <b>Ism va Familiyangizni</b> to'liq yozib yuboring (Masalan: Eshmat Toshmatov):",
        Telegram::removeKeyboard());
}

function on_name(int $chatId, int $tgId, string $name, array &$conv): void
{
    if (mb_strlen($name) < 3 || mb_strlen($name) > 100 || str_starts_with($name, '/')) {
        Telegram::send($chatId, "Iltimos, ismingizni to'liqroq yozing.");
        return;
    }
    $phone = (string)$conv[$chatId]['phone'];
    $tail = substr(digits($phone), -9);
    unset($conv[$chatId]);

    // 1. Xodimmi? — telefonning oxirgi 9 raqami bo'yicha.
    $e = employee_by_phone($phone);
    if ($e !== null) {
        Db::run('UPDATE employees SET telegram_id = NULL WHERE telegram_id = ?', [$tgId]);
        Db::run('UPDATE employees SET telegram_id = ?, full_name = ? WHERE id = ?', [$tgId, $name, (int)$e['id']]);
        bot_log("xodim bog'landi: {$e['username']} <- $tgId");
        Telegram::send($chatId,
            'Siz tizimda xodim sifatida tanildingiz: <b>' . h($name) . "</b> ✅\n"
            . 'Endi bot orqali ish vaqtingizni belgilashingiz mumkin.',
            menu_for($e['role'], attendance_status((int)$e['id'])));
        return;
    }

    // 2. Mijoz: mavjud bo'lsa bog'laymiz, bo'lmasa yaratamiz.
    $client = null;
    foreach (Db::all('SELECT id, phone FROM clients WHERE phone IS NOT NULL') as $c) {
        if ($tail !== '' && substr(digits($c['phone']), -9) === $tail) {
            $client = $c;
            break;
        }
    }
    Db::run('UPDATE clients SET telegram_id = NULL WHERE telegram_id = ?', [$tgId]);
    if ($client !== null) {
        Db::run('UPDATE clients SET name = ?, telegram_id = ? WHERE id = ?', [$name, $tgId, (int)$client['id']]);
    } else {
        Db::insert('clients', [
            'name'          => $name,
            'phone'         => $phone,
            'telegram_id'   => $tgId,
            'balance'       => 0,
            'bonus_balance' => 0,
            'created_at'    => Tz::now(),
        ]);
    }
    bot_log("mijoz ro'yxatdan o'tdi: $name ($phone)");
    Telegram::send($chatId, "Tabriklaymiz! Siz muvaffaqiyatli ro'yxatdan o'tdingiz. ✅", menu_for('client'));
}

function on_balance(int $chatId, int $tgId): void
{
    $c = find_client($tgId);
    if ($c === null) {
        Telegram::send($chatId, "Siz hali ro'yxatdan o'tmagansiz. /start ni bosing.");
        return;
    }
    $bal = Db::f($c['balance']);
    $text = '👤 <b>' . h($c['name']) . "</b>\n\n💰 Sizning balansingiz: <b>" . money($bal) . '</b>';
    if ($bal < 0) {
        $text .= "\n\n🔴 Sizda qarzdorlik bor!";
        if (!empty($c['debt_due_date'])) {
            $text .= "\n📅 To'lov muddati: <b>" . shop_time($c['debt_due_date'], 'd.m.Y') . '</b>';
        }
    } elseif ($bal > 0) {
        $text .= "\n\n🟢 Sizda oldindan to'lov bor.";
    }
    Telegram::send($chatId, $text);
}

function on_bonus(int $chatId, int $tgId): void
{
    $c = find_client($tgId);
    if ($c === null) {
        Telegram::send($chatId, "Siz hali ro'yxatdan o'tmagansiz. /start ni bosing.");
        return;
    }
    Telegram::send($chatId,
        "🎁 <b>Sizning bonuslaringiz</b>\n\n✨ Mavjud bonus: <b>" . money(Db::f($c['bonus_balance'])) . "</b>\n\n"
        . "💡 <i>Har bir xaridingizdan bonuslar yig'iladi va ularni keyingi xaridlar uchun ishlatishingiz mumkin!</i>");
}

function on_attendance(int $chatId, int $tgId, string $status): void
{
    $emp = find_employee($tgId);
    if ($emp === null || !Db::b($emp['is_active'])) {
        Telegram::send($chatId, "Siz xodimlar ro'yxatida yo'qsiz!");
        return;
    }
    $current = attendance_status((int)$emp['id']);
    if ($status === $current) {
        Telegram::send($chatId,
            $status === 'in' ? 'Siz allaqachon ishdasiz! 😅' : "Siz hali ishga kelmagansiz-ku? 🤔",
            menu_for($emp['role'], $current));
        return;
    }
    Db::insert('attendance', [
        'employee_id' => (int)$emp['id'],
        'status'      => $status,
        'created_at'  => Tz::now(),
    ]);
    $name = emp_name($emp);
    $time = shop_now('H:i');
    Telegram::send($chatId,
        $status === 'in'
            ? 'Xush kelibsiz, <b>' . h($name) . "</b>! Ish boshlandi. 🚀\nVaqt: $time"
            : 'Yaxshi dam oling, <b>' . h($name) . "</b>! Ish yakunlandi. ✅\nVaqt: $time",
        menu_for($emp['role'], $status));

    if (env_bool('BOT_NOTIFY_ATTENDANCE', true)) {
        notify_admins(($status === 'in' ? '🎬 ' : '🛑 ') . '<b>' . h($name) . '</b> '
            . ($status === 'in' ? 'ishga keldi' : 'ishdan ketdi') . " — $time");
    }
}

function who_is_working(): string
{
    $cutoff = (new DateTimeImmutable('-5 minutes', Tz::utcTz()))->format('Y-m-d H:i:s.u');
    $openShifts = [];
    foreach (Db::all("SELECT cashier_id, opened_at FROM shifts WHERE status = 'open' AND cashier_id IS NOT NULL") as $s) {
        $openShifts[(int)$s['cashier_id']] = $s['opened_at'];
    }

    $lines = [];
    foreach (Db::all('SELECT * FROM employees WHERE is_active = ? ORDER BY id', [true]) as $e) {
        $id = (int)$e['id'];
        $last = Db::one(
            'SELECT status, created_at FROM attendance WHERE employee_id = ? ORDER BY created_at DESC, id DESC LIMIT 1',
            [$id]
        );
        $in = ($last['status'] ?? '') === 'in';
        $online = !empty($e['session_token']) && ($e['last_seen_at'] ?? '') !== '' && $e['last_seen_at'] >= $cutoff;
        $onShift = isset($openShifts[$id]);
        if (!$in && !$online && !$onShift) {
            continue;
        }
        $tags = [];
        if ($in) {
            $tags[] = '🎬 ' . shop_time($last['created_at']) . ' dan beri';
        }
        if ($onShift) {
            $tags[] = '🟠 smena ochiq (' . shop_time($openShifts[$id]) . ')';
        }
        if ($online) {
            $tags[] = '🟢 saytda';
        }
        $lines[] = '👤 <b>' . h(emp_name($e)) . "</b>\n     " . implode(' · ', $tags);
    }

    return $lines === []
        ? '📭 Hozirda hech kim ishda emas.'
        : "👥 <b>Hozirda ishda:</b>\n\n" . implode("\n", $lines);
}

function start_broadcast(int $chatId, int $tgId, array &$conv): void
{
    if (!is_admin_chat($tgId)) {
        Telegram::send($chatId, "Kechirasiz, bu bo'lim faqat adminlar uchun!");
        return;
    }
    $conv[$chatId] = ['step' => 'broadcast'];
    Telegram::send($chatId,
        "📢 <b>Reklama xabari yuborish bo'limi</b>\n\n"
        . "Xabar matnini yuboring (rasm yoki video bilan ham bo'ladi).\n"
        . "Yuborgan narsangiz botdan ro'yxatdan o'tgan barcha mijozlarga yetib boradi.\n\n"
        . "<i>Bekor qilish uchun /cancel deb yozing.</i>",
        Telegram::removeKeyboard());
}

function do_broadcast(int $chatId, int $tgId, array $msg): void
{
    if (!is_admin_chat($tgId)) {
        return;
    }
    $clients = Db::all('SELECT telegram_id FROM clients WHERE telegram_id IS NOT NULL');
    Telegram::send($chatId, 'Xabar yuborish boshlandi (' . count($clients) . ' ta mijoz)... ⏳');
    $sent = 0;
    foreach ($clients as $c) {
        // copyMessage — matn, rasm, video: hammasini asl ko'rinishida.
        if (Telegram::copy($c['telegram_id'], $chatId, (int)$msg['message_id'])) {
            $sent++;
        }
        if (!Telegram::collecting()) {
            usleep(60000); // Telegram cheklovi: sekundiga ~30 xabar
        }
    }
    Telegram::send($chatId, "Tayyor! ✅\nXabar $sent ta mijozga yuborildi.", menu_for('admin'));
}

// =======================================================================
// Admin: Ma'lumotlar (Excel)
// =======================================================================

function send_data_files(int|string $chatId): void
{
    Telegram::send($chatId, 'Tayyorlanmoqda... ⏳');
    $stamp = shop_now('Ymd_Hi');

    $cats = [];
    foreach (Db::all('SELECT id, name FROM categories') as $c) {
        $cats[(int)$c['id']] = $c['name'];
    }
    $products = Db::all('SELECT * FROM products ORDER BY name');
    Telegram::sendDocument($chatId, Xlsx::build(
        ['Nomi', 'Shtrix kod', 'Kategoriya', 'Kelish narxi', 'Sotish narxi', 'Qoldiq', 'Birlik'],
        array_map(fn($p) => [
            $p['name'], $p['barcode'] ?: '-', $cats[(int)($p['category_id'] ?? 0)] ?? '-',
            Db::f($p['buy_price']), Db::f($p['sell_price']),
            Db::b($p['is_infinite']) ? '∞' : Db::f($p['stock']), $p['unit'] ?? 'dona',
        ], $products),
        'Ombor'
    ), "ombor_$stamp.xlsx", '📦 Ombor (' . count($products) . ' ta mahsulot)', true);

    $suppliers = Db::all('SELECT * FROM suppliers ORDER BY name');
    Telegram::sendDocument($chatId, Xlsx::build(
        ['Nomi', 'Telefon', 'Manzil', 'Balans (qarzimiz)'],
        array_map(fn($s) => [$s['name'], $s['phone'] ?: '-', $s['address'] ?: '-', Db::f($s['balance'])], $suppliers),
        'Firmalar'
    ), "firmalar_$stamp.xlsx", '🚚 Firmalar (' . count($suppliers) . ' ta)', true);

    $clients = Db::all('SELECT * FROM clients ORDER BY name');
    Telegram::sendDocument($chatId, Xlsx::build(
        ['Ismi', 'Telefon', 'Balans', 'Bonus', 'Qarz muddati'],
        array_map(fn($c) => [
            $c['name'], $c['phone'] ?: '-', Db::f($c['balance']), Db::f($c['bonus_balance']),
            empty($c['debt_due_date']) ? '-' : shop_time($c['debt_due_date'], 'd.m.Y'),
        ], $clients),
        'Mijozlar'
    ), "mijozlar_$stamp.xlsx", '👤 Mijozlar (' . count($clients) . ' ta)', true);

    // Bugungi cheklar — kassir ustuni bilan, bitta varaqda.
    [$start, $end] = Tz::dayBoundsUtc(Tz::shopToday());
    $sales = Db::all(
        "SELECT s.*, e.full_name AS e_full, e.username AS e_user, c.name AS c_name
         FROM sales s
         LEFT JOIN employees e ON e.id = s.cashier_id
         LEFT JOIN clients c ON c.id = s.client_id
         WHERE s.created_at >= ? AND s.created_at < ? AND s.status = 'completed'
         ORDER BY s.created_at",
        [$start, $end]
    );
    $items = [];
    if ($sales !== []) {
        $ids = array_map(fn($s) => (int)$s['id'], $sales);
        foreach (Db::all(
            'SELECT si.sale_id, si.quantity, COALESCE(p.name, si.product_name) AS name, p.unit
             FROM sale_items si LEFT JOIN products p ON p.id = si.product_id
             WHERE si.sale_id IN (' . Db::marks($ids) . ')',
            $ids
        ) as $it) {
            $items[(int)$it['sale_id']][] = ($it['name'] ?? 'Mahsulot') . ' (' . qty(Db::f($it['quantity'])) . ' ' . ($it['unit'] ?? '') . ')';
        }
    }
    Telegram::sendDocument($chatId, Xlsx::build(
        ['Chek №', 'Vaqt', 'Kassir', 'Mijoz', 'Mahsulotlar', "Summa (so'm)", "To'lov usuli"],
        array_map(fn($s) => [
            (int)$s['id'], shop_time($s['created_at']),
            $s['e_full'] ?: ($s['e_user'] ?: '-'), $s['c_name'] ?: '-',
            implode(', ', $items[(int)$s['id']] ?? []), Db::f($s['total_amount']), $s['payment_method'],
        ], $sales),
        'Bugungi savdo'
    ), "bugungi_savdo_$stamp.xlsx", '🧾 Bugungi cheklar (' . count($sales) . ' ta)', true);
}

// =======================================================================
// Kunlik hisobot
// =======================================================================

function build_daily_report(string $ymd): string
{
    [$start, $end] = Tz::dayBoundsUtc($ymd);
    $p = [$start, $end];

    $s = Db::one(
        "SELECT COUNT(*) AS n, COALESCE(SUM(total_amount),0) AS total,
                COALESCE(SUM(cash_amount),0) AS cash, COALESCE(SUM(card_amount),0) AS card,
                COALESCE(SUM(transfer_amount),0) AS transfer, COALESCE(SUM(debt_amount),0) AS debt,
                COALESCE(SUM(bonus_spent),0) AS bonus
         FROM sales WHERE created_at >= ? AND created_at < ? AND status = 'completed'",
        $p
    );
    $total = Db::f($s['total']);

    // Tannarx — /finance/stats dagi bilan bir xil formula.
    $cogs = Db::num(
        "SELECT COALESCE(SUM(si.quantity * COALESCE(si.buy_price, p.buy_price, 0)), 0)
         FROM sale_items si
         LEFT JOIN products p ON p.id = si.product_id
         JOIN sales s ON s.id = si.sale_id
         WHERE s.created_at >= ? AND s.created_at < ? AND s.status = 'completed'",
        $p
    );
    $expenses = Db::num('SELECT COALESCE(SUM(amount),0) FROM expenses WHERE created_at >= ? AND created_at < ?', $p);
    $net = $total - $cogs - $expenses;

    $ref = Db::one(
        'SELECT COUNT(*) AS n, COALESCE(SUM(total_amount),0) AS total FROM sales
         WHERE refunded_at >= ? AND refunded_at < ?',
        $p
    );
    $debtPaid = Db::num('SELECT COALESCE(SUM(amount),0) FROM payments WHERE created_at >= ? AND created_at < ?', $p);
    $totalDebt = Db::num('SELECT COALESCE(SUM(-balance),0) FROM clients WHERE balance < 0');

    $L = [];
    $L[] = '📊 <b>Kunlik hisobot — ' . (new DateTimeImmutable($ymd))->format('d.m.Y') . '</b>';
    $L[] = '';
    $L[] = '🧾 Cheklar: <b>' . (int)$s['n'] . ' ta</b>';
    $L[] = '💵 Savdo: <b>' . money($total) . '</b>';
    $L[] = '   • Naqd: ' . money(Db::f($s['cash']));
    $L[] = '   • Karta: ' . money(Db::f($s['card']));
    $L[] = "   • O'tkazma: " . money(Db::f($s['transfer']));
    $L[] = '   • Qarzga: ' . money(Db::f($s['debt']));
    if (Db::f($s['bonus']) > 0) {
        $L[] = '   • Bonus bilan: ' . money(Db::f($s['bonus']));
    }
    $L[] = '';
    $L[] = '📦 Tannarx: ' . money($cogs);
    $L[] = '💸 Xarajatlar: ' . money($expenses);
    $L[] = ($net >= 0 ? '📈' : '📉') . ' Sof foyda: <b>' . money($net) . '</b>';
    $L[] = '';
    if ((int)$ref['n'] > 0) {
        $L[] = '↩️ Vozvratlar: ' . (int)$ref['n'] . ' ta — ' . money(Db::f($ref['total']));
    }
    $L[] = "💰 Qarz to'lovlari: " . money($debtPaid);
    $L[] = '📒 Mijozlarning umumiy qarzi: ' . money($totalDebt);

    $cashiers = Db::all(
        "SELECT s.cashier_id, e.full_name, e.username, COUNT(*) AS n, SUM(s.total_amount) AS total
         FROM sales s LEFT JOIN employees e ON e.id = s.cashier_id
         WHERE s.created_at >= ? AND s.created_at < ? AND s.status = 'completed'
         GROUP BY s.cashier_id, e.full_name, e.username ORDER BY total DESC",
        $p
    );
    if ($cashiers !== []) {
        $L[] = '';
        $L[] = '👥 <b>Kassirlar:</b>';
        foreach ($cashiers as $c) {
            $L[] = '   • ' . h($c['full_name'] ?: ($c['username'] ?: "O'chirilgan")) . ': '
                . (int)$c['n'] . ' ta — ' . money(Db::f($c['total']));
        }
    }

    $top = Db::all(
        "SELECT COALESCE(p.name, si.product_name, 'Mahsulot') AS name, SUM(si.quantity) AS q,
                SUM(si.quantity * si.price) AS sum
         FROM sale_items si
         LEFT JOIN products p ON p.id = si.product_id
         JOIN sales s ON s.id = si.sale_id
         WHERE s.created_at >= ? AND s.created_at < ? AND s.status = 'completed'
         GROUP BY COALESCE(p.name, si.product_name, 'Mahsulot') ORDER BY sum DESC LIMIT 5",
        $p
    );
    if ($top !== []) {
        $L[] = '';
        $L[] = '🏆 <b>Eng ko\'p sotilgan:</b>';
        foreach ($top as $i => $t) {
            $L[] = '   ' . ($i + 1) . '. ' . h($t['name']) . ' — ' . qty(Db::f($t['q'])) . ' ta, ' . money(Db::f($t['sum']));
        }
    }

    $shiftIssues = Db::all(
        'SELECT s.*, e.full_name, e.username FROM shifts s LEFT JOIN employees e ON e.id = s.cashier_id
         WHERE s.closed_at >= ? AND s.closed_at < ? AND ABS(COALESCE(s.cash_difference, 0)) > 0.01',
        $p
    );
    $open = Db::all(
        "SELECT s.opened_at, e.full_name, e.username FROM shifts s LEFT JOIN employees e ON e.id = s.cashier_id
         WHERE s.status = 'open'"
    );
    if ($shiftIssues !== [] || $open !== []) {
        $L[] = '';
        $L[] = '🗂 <b>Smenalar:</b>';
        foreach ($shiftIssues as $sh) {
            $L[] = '   ⚠️ ' . h($sh['full_name'] ?: $sh['username']) . ': farq '
                . money(Db::f($sh['cash_difference'])) . ($sh['note'] ? ' — «' . h($sh['note']) . '»' : '');
        }
        foreach ($open as $o) {
            $L[] = '   🟠 ' . h($o['full_name'] ?: ($o['username'] ?: "O'chirilgan")) . ' — smena hali ochiq ('
                . shop_time($o['opened_at'], 'd.m H:i') . ' dan)';
        }
    }

    $threshold = (int)(store_settings()['low_stock_threshold'] ?? 5);
    $low = (int)Db::val(
        'SELECT COUNT(*) FROM products WHERE stock <= ? AND (is_infinite IS NULL OR is_infinite = ?)',
        [$threshold, false], 0
    );
    if ($low > 0) {
        $L[] = '';
        $L[] = "📉 Tugayotgan mahsulotlar: <b>$low ta</b> (qoldiq ≤ $threshold)";
    }

    return implode("\n", $L);
}

// =======================================================================
// Qarz eslatmalari
// =======================================================================

function send_debt_reminders(): void
{
    $days = max(0, (int)(store_settings()['debt_reminder_days'] ?? 3));
    $sent = 0;
    $overdue = [];
    foreach (Db::all(
        'SELECT * FROM clients WHERE debt_due_date IS NOT NULL AND balance < 0'
    ) as $c) {
        $left = Tz::daysUntil($c['debt_due_date']);
        if ($left === null) {
            continue;
        }
        $debt = money(abs(Db::f($c['balance'])));
        $due = shop_time($c['debt_due_date'], 'd.m.Y');
        if ($left > 0 && $left <= $days) {
            $msg = "🔔 Eslatma: <b>" . h($c['name']) . "</b>, qarzingizni to'lashga <b>$left kun</b> qoldi.\nSumma: <b>$debt</b>\nMuddat: $due";
        } elseif ($left === 0) {
            $msg = "⚠️ Diqqat: <b>" . h($c['name']) . "</b>, qarzingizni to'lash muddati <b>bugun</b>.\nSumma: <b>$debt</b>";
        } elseif ($left < 0) {
            $msg = "❗️ Qarzingiz muddati o'tgan: <b>" . h($c['name']) . "</b>.\nSumma: <b>$debt</b>\nMuddat: $due";
            $overdue[] = h($c['name']) . " — $debt (" . abs($left) . ' kun kechikkan)';
        } else {
            continue;
        }
        if (!empty($c['telegram_id']) && Telegram::send($c['telegram_id'], $msg)) {
            $sent++;
        }
    }
    bot_log("qarz eslatmalari: $sent ta yuborildi");
    if ($overdue !== []) {
        notify_admins("📒 <b>Muddati o'tgan qarzlar (" . count($overdue) . " ta):</b>\n\n• "
            . implode("\n• ", array_slice($overdue, 0, 30))
            . "\n\nBotdagi mijozlarga eslatma yuborildi: $sent ta");
    }
}

// =======================================================================
// Zahira nusxa
// =======================================================================

function run_backup(): void
{
    $chat = trim((string)env('TELEGRAM_ADMIN_CHAT_ID'));

    // Server rejimi (/bot/tick): nusxani ko'prik o'zi API orqali yuklab oladi.
    if (Telegram::collecting()) {
        Telegram::action(['type' => 'backup']);
        return;
    }

    try {
        $result = Backup::run();
        $uploads = Backup::archiveUploads();
    } catch (Throwable $e) {
        bot_log('zahira XATO: ' . $e->getMessage());
        notify_admins('❌ <b>Zahira nusxa olinmadi!</b>' . "\n" . h($e->getMessage()));
        return;
    }
    if ($chat === '') {
        bot_log("zahira olindi, lekin TELEGRAM_ADMIN_CHAT_ID yo'q — yuborilmadi");
        return;
    }
    $caption = "💾 <b>Kassa zahira nusxasi</b>\n📅 " . shop_now('Y-m-d H:i') . "\n📊 {$result['tables']} jadval, "
        . "{$result['rows']} qator, " . round($result['bytes'] / 1024) . ' KB';
    $ok = Telegram::sendDocument($chat, Backup::dir() . '/' . $result['file'], $result['file'], $caption);
    if ($ok && $uploads !== null) {
        Telegram::sendDocument($chat, Backup::dir() . '/' . $uploads, $uploads, '🧾 Nakladnoy rasmlari');
    }
    bot_log('zahira: ' . $result['file'] . ($ok ? ' — telegramga yuborildi' : ' — telegramga YUBORILMADI'));
}

// =======================================================================
// Ogohlantirishlar
// =======================================================================

/**
 * Adminga darhol boradigan ogohlantirish — faqat kamomad/ortiqcha bilan
 * yopilgan smena. Vozvrat, narxdan arzon sotuv va tugayotgan mahsulot
 * atayin yo'q: admin ularni saytdan ko'radi (2026-09-26 da so'ralgan).
 *
 * Birinchi ishga tushishda kursor "hozir" ga qo'yiladi — eski tarix yog'ilmasin.
 */
function check_alerts(array &$state): void
{
    if (!isset($state['alerts']['shift_cursor'])) {
        // Bo'sh satr emas: MySQL DATETIME ni '' bilan solishtirishni yoqtirmaydi.
        $state['alerts'] = [
            'shift_cursor' => (string)(Db::val('SELECT MAX(closed_at) FROM shifts') ?? '1970-01-01 00:00:00'),
        ];
        return;
    }
    $a = &$state['alerts'];

    foreach (Db::all(
        'SELECT s.*, e.full_name, e.username FROM shifts s LEFT JOIN employees e ON e.id = s.cashier_id
         WHERE s.closed_at IS NOT NULL AND s.closed_at > ? ORDER BY s.closed_at',
        [$a['shift_cursor']]
    ) as $sh) {
        $a['shift_cursor'] = (string)$sh['closed_at'];
        $diff = Db::f($sh['cash_difference'] ?? 0);
        if (abs($diff) <= 0.01) {
            continue;
        }
        notify_admins(($diff < 0 ? '🔴 <b>Kamomad bilan yopilgan smena</b>' : '🟡 <b>Ortiqcha pul bilan yopilgan smena</b>') . "
"
            . 'Kassir: ' . h($sh['full_name'] ?: ($sh['username'] ?? '-')) . "
"
            . 'Kutilgan: ' . money(Db::f($sh['expected_cash'] ?? 0)) . "
"
            . 'Sanalgan: ' . money(Db::f($sh['closing_balance'] ?? 0)) . "
"
            . 'Farq: <b>' . money($diff) . '</b>'
            . (!empty($sh['note']) ? "
Izoh: «" . h($sh['note']) . '»' : ''));
    }
}

// =======================================================================
// Jadval
// =======================================================================

/** Bugun hali bajarilmagan va vaqti kelgan kunlik vazifa. */
function due_today(array $state, string $key, string $time): bool
{
    return ($state['daily'][$key] ?? '') !== Tz::shopToday() && shop_now('H:i') >= $time;
}

function run_schedule(array &$state): void
{
    $jobs = [
        'report' => [env('BOT_REPORT_TIME', '22:00'), function () {
            notify_admins(build_daily_report(Tz::shopToday()));
        }],
        'backup' => [env('BACKUP_TIME', '22:00'), fn() => env_bool('BACKUP_ENABLED', true) ? run_backup() : null],
        'debts'  => [env('DEBT_REMINDER_TIME', '09:00'), fn() => send_debt_reminders()],
    ];
    foreach ($jobs as $key => [$time, $fn]) {
        if (!due_today($state, $key, (string)$time)) {
            continue;
        }
        // Avval belgilaymiz: vazifa yiqilsa ham har 30 soniyada qayta
        // urinib, adminni bir xil xabar bilan ko'mib tashlamasin.
        $state['daily'][$key] = Tz::shopToday();
        state_save($state);
        bot_log("vazifa: $key");
        try {
            $fn();
        } catch (Throwable $e) {
            bot_log("vazifa $key XATO: " . $e->getMessage());
            Db::reset();
        }
    }
}
