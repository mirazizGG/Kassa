<?php
/**
 * /sales — chek yaratish, ro'yxat, vozvrat.
 *
 * Bu fayl butun tizimning eng mas'uliyatli joyi. Tekshiruvlar TARTIBI
 * Python versiyasidan aynan ko'chirildi, chunki har biri haqiqiy xatoni
 * yopgan. Tartibni o'zgartirmang.
 *
 * BITTA ATAYIN FARQ BOR — menejer tasdig'i endi HAR QANDAY yozuvdan OLDIN
 * tekshiriladi. Python'da u savat aylanishi ICHIDA edi va tasdiq
 * muvaffaqiyatsiz bo'lganda `verify_approver` audit yozuvini saqlash uchun
 * `db.commit()` chaqirardi — bu esa O'SHA PAYTGACHA kamaytirilgan qoldiqni
 * ham saqlab qo'yardi. Ya'ni chegirma paroli noto'g'ri kiritilsa, savatning
 * birinchi mahsulotlari ombordan chiqib ketar, cheki esa yozilmasdi.
 * Endi: avval hammasi o'qiladi va tekshiriladi, keyin bitta tranzaksiyada
 * yoziladi.
 */

declare(strict_types=1);

/** Chekni javob uchun to'liq yig'adi. */
function sale_response(int $saleId): array
{
    $row = Db::one('SELECT * FROM sales WHERE id = ?', [$saleId]);
    if ($row === null) {
        fail(404, 'Sale not found');
    }
    return Shape::sales([$row])[0];
}

// =======================================================================
// POST /sales/  — yangi chek
// =======================================================================
Router::post('/', function (): never {
    $user = Auth::user();

    // Ombochi (warehouse) sotmaydi — u faqat ombor va firmalar bilan ishlaydi.
    if (!in_array($user['role'], ['admin', 'manager', 'cashier'], true)) {
        fail(403, 'Ruxsat berilmagan');
    }

    $b = Http::body();

    $activeShift = Db::one(
        "SELECT * FROM shifts WHERE cashier_id = ? AND status = 'open' ORDER BY id DESC",
        [$user['id']]
    );
    if ($activeShift === null) {
        fail(400, 'Savdo qilish uchun avval smenani oching');
    }

    // --- Takroriy yuborishdan himoya ------------------------------------
    // Kassir "To'lash" ni ikki marta bossa yoki so'rov timeout bo'lib qayta
    // ketsa, ilgari IKKITA chek yozilardi: ombordan tovar ikki marta
    // yechilar, kassaga ikki marta pul tushgandek ko'rinardi.
    $idemKey = Http::str($b, 'idempotency_key', null, 64);
    if ($idemKey !== null) {
        $already = Db::one('SELECT id FROM sales WHERE idempotency_key = ?', [$idemKey]);
        if ($already !== null) {
            Http::json(sale_response((int)$already['id']));
        }
    }

    // --- Kirish ma'lumotlari --------------------------------------------
    $totalAmount   = Http::reqNum($b, 'total_amount', 'gt', 0, null, 'Chek summasi');
    $paymentMethod = Http::reqStr($b, 'payment_method', 40, "To'lov usuli");
    $clientId      = Http::int($b, 'client_id');
    $cashAmount    = Http::num($b, 'cash_amount', 0.0, 'ge', 0, null, 'Naqd') ?? 0.0;
    $cardAmount    = Http::num($b, 'card_amount', 0.0, 'ge', 0, null, 'Karta') ?? 0.0;
    $transferAmt   = Http::num($b, 'transfer_amount', 0.0, 'ge', 0, null, "O'tkazma") ?? 0.0;
    $debtAmount    = Http::num($b, 'debt_amount', 0.0, 'ge', 0, null, 'Nasiya') ?? 0.0;
    $bonusSpent    = Http::num($b, 'bonus_spent', 0.0, 'ge', 0, null, 'Bonus') ?? 0.0;

    $items = $b['items'] ?? null;
    if (!is_array($items) || $items === []) {
        fail(422, "Savat bo'sh — hech bo'lmasa bitta mahsulot kerak.");
    }

    // --- Nasiya/bonus MIJOZSIZ bo'lishi mumkin emas ----------------------
    //
    // Ilgari `debt_amount > 0` va `client_id = null` bilan kelgan so'rov
    // o'tib ketardi: tovar ombordan chiqadi, tushum hisobga olinadi, smena
    // kassasi tiyinigacha to'g'ri keladi — va qarz HECH KIMDA paydo
    // bo'lmaydi. Uni aniqlaydigan birorta hisobot yo'q edi.
    if (($debtAmount > 0 || $bonusSpent > 0) && !$clientId) {
        fail(400, 'Nasiya yoki bonus uchun mijozni tanlang');
    }

    // Mijozni SHU YERDA, hech narsa yozilmasidan oldin tekshiramiz. Ilgari
    // tekshiruv chek yozilgandan keyin turardi, shuning uchun noma'lum id
    // tushunarsiz IntegrityError (500) bo'lib chiqardi.
    $client = null;
    if ($clientId) {
        $client = Db::one('SELECT * FROM clients WHERE id = ?', [$clientId]);
        if ($client === null) {
            fail(404, 'Mijoz topilmadi');
        }
    }

    // --- 1-BOSQICH: faqat O'QISH va tekshirish ---------------------------
    $wanted = [];
    foreach ($items as $it) {
        if (!is_array($it)) {
            fail(422, "Savat elementi noto'g'ri formatda.");
        }
        $wanted[] = Http::reqInt($it, 'product_id', 'Mahsulot');
    }
    $products = Shape::lookup('products', $wanted);

    $lines = [];
    $needsApproval = false;
    $computedTotal = 0.0;

    foreach ($items as $it) {
        $pid = (int)$it['product_id'];
        $product = $products[$pid] ?? null;
        if ($product === null) {
            fail(404, "Product $pid not found");
        }

        $qty = Http::reqNum($it, 'quantity', 'gt', 0, null, 'Miqdor');
        $price = Http::reqNum($it, 'price', 'gt', 0, null, 'Narx');

        if ($price < (float)$product['sell_price']) {
            $needsApproval = true;
        }

        $infinite = Db::b($product['is_infinite']);
        if (!$infinite && (float)$product['stock'] < $qty) {
            fail(400, "Mahsulot yetarli emas: {$product['name']}. Mavjud: "
                . rtrim(rtrim(number_format((float)$product['stock'], 3, '.', ''), '0'), '.'));
        }

        $computedTotal += $qty * $price;
        $lines[] = [
            'product_id' => $pid,
            'name'       => $product['name'],
            'quantity'   => $qty,
            'price'      => $price,
            'buy_price'  => (float)$product['buy_price'],
            'infinite'   => $infinite,
        ];
    }

    // Chek summasi mahsulotlar yig'indisiga mos kelishi shart (1 so'mgacha xato ruxsat).
    if (abs($computedTotal - $totalAmount) > 1) {
        fail(400, "Chek summasi mahsulotlarga mos emas. Hisoblangan: "
            . number_format($computedTotal, 0, '.', ',') . ', kelgan: '
            . number_format($totalAmount, 0, '.', ','));
    }

    // To'lov qismlari chek summasidan OSHMASLIGI kerak.
    $nonCash = $cardAmount + $transferAmt + $debtAmount + $bonusSpent;
    if ($nonCash - $totalAmount > 1) {
        fail(400, "Naqd bo'lmagan to'lovlar chek summasidan oshib ketdi");
    }

    // Qolgan qismini naqd qoplashi kerak.
    //
    // DIQQAT — bu yerda jiddiy xato bor edi. Tekshiruv `if cash_amount and ...`
    // ko'rinishida edi: cash_amount = 0 bo'lsa shart umuman bajarilmasdi.
    // Ya'ni 100 000 so'mlik chek 30 000 karta va 0 naqd bilan "to'liq
    // to'langan" deb qabul qilinar, keyin qolgan 70 000 "naqd olindi" deb
    // yozilardi. Natija: kassada bo'lmagan pul hisobga tushib, smena
    // yopilishida tushuntirib bo'lmaydigan kamomad chiqardi.
    $requiredCash = $totalAmount - $nonCash;
    if ($requiredCash > 1 && $cashAmount + 1 < $requiredCash) {
        fail(400, "To'lovlar yig'indisi chek summasidan kam. Yana "
            . number_format($requiredCash - $cashAmount, 0, '.', ',') . " so'm kerak.");
    }

    // --- 2-BOSQICH: menejer tasdig'i (tranzaksiyadan TASHQARIDA) ---------
    // Muvaffaqiyatsiz urinish audit jurnaliga tushishi SHART, shuning uchun
    // u yozuvlar boshlangunicha, alohida bajariladi.
    if ($needsApproval) {
        $mu = Http::str($b, 'manager_username', null, 150);
        $mp = Http::str($b, 'manager_password', null, 200);
        if ($mu === null || $mp === null) {
            fail(403, "Chegirma uchun menejer tasdig'i kerak");
        }
        Auth::verifyApprover($user, $mu, $mp);
    }

    // Xaridor bergan naqd qaytim bilan bo'lishi mumkin; kassada QOLADIGAN
    // sof summani saqlaymiz. Smena hisobi aynan shunga tayanadi.
    $netCash = max(0.0, $totalAmount - $cardAmount - $transferAmt - $debtAmount - $bonusSpent);

    // --- 3-BOSQICH: yozish ----------------------------------------------
    try {
        $saleId = Db::tx(function () use (
            $lines, $user, $clientId, $client, $totalAmount, $paymentMethod,
            $netCash, $cardAmount, $transferAmt, $debtAmount, $bonusSpent, $idemKey
        ): int {
            // Qoldiqni ATOMIK kamaytiramiz (cheksiz qoldiqlilar kamaymaydi).
            // Yuqoridagi tekshiruv faqat chiroyli xabar uchun; haqiqiy himoya —
            // shu shartli UPDATE. Ilgari bu "o'qi -> ayir -> yoz" edi: SQLite
            // yozuvlarni navbatga qo'ygani uchun muammo kam ko'rinardi,
            // PostgreSQL/MySQL parallel yozadi va ikki kassa oxirgi donani
            // sotib yubora olardi.
            foreach ($lines as $ln) {
                if ($ln['infinite']) {
                    continue;
                }
                $ok = Db::run(
                    'UPDATE products SET stock = stock - ? WHERE id = ? AND stock >= ?',
                    [$ln['quantity'], $ln['product_id'], $ln['quantity']]
                );
                if ($ok === 0) {
                    fail(409, "Mahsulot yetarli emas: {$ln['name']}. "
                        . "Qoldiq siz tanlaganingizdan keyin o'zgardi — savatni yangilang.");
                }
            }

            $bonusEarned = 0.0;

            $saleId = Db::insert('sales', [
                'created_at'      => Tz::now(),
                'total_amount'    => $totalAmount,
                'payment_method'  => $paymentMethod,
                'cashier_id'      => $user['id'],
                'client_id'       => $clientId,
                'status'          => 'completed',
                'cash_amount'     => $netCash,
                'card_amount'     => $cardAmount,
                'transfer_amount' => $transferAmt,
                'debt_amount'     => $debtAmount,
                'bonus_earned'    => 0.0,
                'bonus_spent'     => 0.0,
                'idempotency_key' => $idemKey,
            ]);

            foreach ($lines as $ln) {
                Db::insert('sale_items', [
                    'sale_id'    => $saleId,
                    'product_id' => $ln['product_id'],
                    'quantity'   => $ln['quantity'],
                    'price'      => $ln['price'],
                    // Tannarxni sotuv paytida MUZLATIB qo'yamiz: keyin kirim
                    // narxi o'zgarsa, o'tmishdagi foyda surilib ketmasin.
                    'buy_price'  => $ln['buy_price'],
                ]);
                Db::insert('stock_moves', [
                    'product_id' => $ln['product_id'],
                    'quantity'   => -$ln['quantity'],
                    'type'       => 'sale',
                    'reason'     => "Sotuv (Chek ID: $saleId)",
                    'created_by' => $user['id'],
                    'created_at' => Tz::now(),
                ]);
            }

            // --- Mijoz balansi va bonuslar ---------------------------------
            if ($client !== null) {
                $settings = Db::one('SELECT * FROM store_settings ORDER BY id LIMIT 1');
                $bonusPercent = $settings ? (float)$settings['bonus_percentage'] : 1.0;
                $reminderDays = $settings ? (int)$settings['debt_reminder_days'] : 3;

                // Bonus faqat qarzga YOZILMAGAN qismdan hisoblanadi.
                $paidAmount = $totalAmount - $debtAmount;
                $bonusEarned = $paidAmount > 0 ? ($paidAmount * $bonusPercent) / 100 : 0.0;

                // Sarflangan bonusni ATOMIK va SHARTLI yechamiz. Ilgari
                // "tekshir -> ayir" edi: ikki parallel sotuv bir xil bonusni
                // ikki marta sarflab, balansni minusga tushira olardi.
                if ($bonusSpent > 0) {
                    $ok = Db::run(
                        'UPDATE clients SET bonus_balance = bonus_balance - ?
                         WHERE id = ? AND bonus_balance >= ?',
                        [$bonusSpent, $clientId, $bonusSpent]
                    );
                    if ($ok === 0) {
                        fail(400, 'Bonus balansi yetarli emas');
                    }
                    Db::update('sales', $saleId, ['bonus_spent' => $bonusSpent]);
                }

                $sets = [];
                $params = [];
                if ($debtAmount > 0) {
                    $sets[] = 'balance = balance - ?';
                    $params[] = $debtAmount;

                    // Qarz muddatini SHU YERDA qo'yamiz.
                    //
                    // Ilgari debt_due_date faqat CRM oynasidan qo'lda
                    // kiritilardi: sotuv uni qo'ymasdi, to'lov esa
                    // tozalamasdi. Natijada bot doimiy mijozga kechagi qarz
                    // uchun "muddati o'tgan" deb yozar, muddati haqiqatan
                    // o'tganlar esa NULL bilan qolib, umuman xabar olmasdi.
                    //
                    // Mavjud muddat kelajakda bo'lsa — tegmaymiz (mijoz bilan
                    // kelishilgan sana buzilmasin).
                    $currentDue = $client['debt_due_date'] ?? null;
                    $dueShopDate = Tz::shopDate($currentDue);
                    if ($dueShopDate === null || $dueShopDate < Tz::shopToday()) {
                        $days = max($reminderDays, 1);
                        $sets[] = 'debt_due_date = ?';
                        $params[] = (new DateTimeImmutable(Tz::now(), Tz::utcTz()))
                            ->modify("+$days day")->format('Y-m-d H:i:s.u');
                    }
                }
                if ($bonusEarned > 0) {
                    Db::update('sales', $saleId, ['bonus_earned' => $bonusEarned]);
                    $sets[] = 'bonus_balance = bonus_balance + ?';
                    $params[] = $bonusEarned;
                }
                if ($sets !== []) {
                    $params[] = $clientId;
                    Db::run('UPDATE clients SET ' . implode(', ', $sets) . ' WHERE id = ?', $params);
                }
            }

            Audit::log(
                (int)$user['id'],
                'YANGI_SOTUV',
                'Summa: ' . number_format($totalAmount, 0, '.', ',') . " so'm. "
                . "Usul: $paymentMethod. Chek ID: $saleId"
            );

            return $saleId;
        });
    } catch (PDOException $e) {
        // Ikkita bir xil kalitli so'rov bir vaqtda kelgan bo'lsa, noyob
        // indeks ikkinchisini to'xtatadi. Bu xato emas — birinchisining
        // natijasini qaytaramiz.
        if ($idemKey !== null && self_is_duplicate($e)) {
            $existing = Db::one('SELECT id FROM sales WHERE idempotency_key = ?', [$idemKey]);
            if ($existing !== null) {
                Http::json(sale_response((int)$existing['id']));
            }
        }
        throw $e;
    }

    // Zahira nusxa bu yerda OLINMAYDI. Har sotuvdan keyin nusxa olish
    // eski nusxalarni tozalash funksiyasini ishga tushirib, saqlash
    // oynasini "oxirgi 30 ta sotuv" ga qisqartirar va kunlik nusxalarni
    // tushlikkacha o'chirib yuborardi.

    Http::json(sale_response($saleId));
});

/** Noyob indeks buzilishimi? Drayverlar turlicha kod beradi. */
function self_is_duplicate(PDOException $e): bool
{
    $code = $e->getCode();
    if ($code === '23000' || $code === '23505') {
        return true;
    }
    return str_contains(strtolower($e->getMessage()), 'duplicate')
        || str_contains(strtolower($e->getMessage()), 'unique');
}

// =======================================================================
// GET /sales/top-products
// =======================================================================
Router::get('/top-products', function (): never {
    Auth::user();
    require_once APP_DIR . '/Cache.php';
    $limit = Http::qInt('limit', 12, 1, 20) ?? 12;

    // Butun tarixni guruhlaydigan og'ir so'rov: ikki yillik do'konda bu 200
    // mingdan ortiq savdo satri. Ro'yxat bir necha daqiqada sezilarli
    // o'zgarmaydi, shuning uchun keshlanadi.
    //
    // Qoldiq (stock) esa keshdan OLINMAYDI — u pastda jonli o'qiladi.
    // Aks holda kassada eskirgan qoldiq ko'rinib qolardi.
    $top = Cache::remember("sales-top:$limit", 300, fn() => Db::all(
        "SELECT si.product_id AS id, SUM(si.quantity) AS sold_quantity
         FROM sale_items si
         JOIN sales s ON s.id = si.sale_id
         WHERE s.status = 'completed'
         GROUP BY si.product_id
         ORDER BY SUM(si.quantity) DESC
         LIMIT $limit"
    )) ?? [];

    if ($top === []) {
        Http::json([]);
    }

    $ids = array_map(fn($r) => (int)$r['id'], $top);
    $fresh = Shape::lookup('products', $ids);

    $rows = [];
    foreach ($top as $t) {
        $p = $fresh[(int)$t['id']] ?? null;
        if ($p === null) {
            continue;   // mahsulot o'chirilgan
        }
        $rows[] = $p + ['sold_quantity' => $t['sold_quantity']];
    }

    Http::json(array_map(fn($r) => [
        'id'            => Db::i($r['id']),
        'name'          => $r['name'],
        'barcode'       => $r['barcode'],
        'sell_price'    => Db::f($r['sell_price']),
        'stock'         => Db::f($r['stock']),
        'unit'          => $r['unit'],
        'sold_quantity' => Db::f($r['sold_quantity']),
    ], $rows));
});

// =======================================================================
// GET /sales/my-daily-summary
// =======================================================================
Router::get('/my-daily-summary', function (): never {
    $user = Auth::user();
    // "Bugun" — DO'KON kuni. Ilgari bu yerda mintaqa qat'iy yozilgan edi va
    // SHOP_TIMEZONE sozlamasiga bo'ysunmasdi.
    [$start, $end] = Tz::dayBoundsUtc(Tz::shopToday());

    $r = Db::one(
        "SELECT COUNT(id) AS sales_count,
                COALESCE(SUM(total_amount), 0)    AS total_amount,
                COALESCE(SUM(cash_amount), 0)     AS cash_amount,
                COALESCE(SUM(card_amount), 0)     AS card_amount,
                COALESCE(SUM(transfer_amount), 0) AS transfer_amount,
                COALESCE(SUM(debt_amount), 0)     AS debt_amount
         FROM sales
         WHERE cashier_id = ? AND status = 'completed'
           AND created_at >= ? AND created_at < ?",
        [$user['id'], $start, $end]
    ) ?? [];

    Http::json([
        'sales_count'     => Db::i($r['sales_count'] ?? 0),
        'total_amount'    => Db::f($r['total_amount'] ?? 0),
        'cash_amount'     => Db::f($r['cash_amount'] ?? 0),
        'card_amount'     => Db::f($r['card_amount'] ?? 0),
        'transfer_amount' => Db::f($r['transfer_amount'] ?? 0),
        'debt_amount'     => Db::f($r['debt_amount'] ?? 0),
    ]);
});

// =======================================================================
// GET /sales/  — ro'yxat
// =======================================================================
Router::get('/', function (): never {
    $user = Auth::user();
    if (!in_array($user['role'], ['admin', 'manager', 'cashier'], true)) {
        fail(403, 'Ruxsat berilmagan');
    }

    $skip  = max(0, Http::qInt('skip', 0) ?? 0);
    $limit = Http::qInt('limit', 100, 1, 500) ?? 100;
    $employeeId = Http::qInt('employee_id');

    // Kassir jim-jitlik bilan O'Z savdolariga cheklanadi.
    if ($user['role'] === 'cashier') {
        $employeeId = (int)$user['id'];
    }

    $start = Tz::parseFilterDate(Http::q('start_date'));
    $end   = Tz::parseFilterDate(Http::q('end_date'), true);

    $where = ['1=1'];
    $params = [];

    if ($employeeId) {
        // Menejer admin savdolarini KO'RMAYDI — atayin yashirilgan.
        if ($user['role'] === 'manager') {
            $target = Db::one('SELECT role FROM employees WHERE id = ?', [$employeeId]);
            if ($target !== null && $target['role'] === 'admin') {
                header('X-Total-Count: 0');
                header('Access-Control-Expose-Headers: X-Total-Count');
                Http::json([]);
            }
        }
        $where[] = 's.cashier_id = ?';
        $params[] = $employeeId;
    } elseif ($user['role'] === 'manager') {
        $where[] = "s.cashier_id IN (SELECT id FROM employees WHERE role <> 'admin')";
    }

    if ($start !== null) {
        $where[] = 's.created_at >= ?';
        $params[] = $start;
    }
    if ($end !== null) {
        $where[] = 's.created_at <= ?';
        $params[] = $end;
    }
    $whereSql = implode(' AND ', $where);

    // Jami sonni sarlavhada qaytaramiz. Ilgari sahifa faqat oxirgi 100 ta
    // chekni olardi va boshqa hech narsa ko'rsatmasdi: ko'p chekli kunda
    // ertalabki savdolar ekrandan yo'qolardi — ular bilan birga VOZVRAT
    // tugmasi ham, chunki u faqat shu ro'yxatda bor.
    $total = (int)Db::val("SELECT COUNT(*) FROM sales s WHERE $whereSql", $params, 0);
    header('X-Total-Count: ' . $total);
    header('Access-Control-Expose-Headers: X-Total-Count');

    $rows = Db::all(
        "SELECT s.* FROM sales s WHERE $whereSql
         ORDER BY s.created_at DESC, s.id DESC
         LIMIT $limit OFFSET $skip",
        $params
    );

    Http::json(Shape::sales($rows));
});

// =======================================================================
// POST /sales/{sale_id}/refund
// =======================================================================
Router::post('/{sale_id}/refund', function (array $p): never {
    $user = Auth::user();
    $saleId = Router::id($p, 'sale_id');
    $b = Http::body();

    // Har bir vozvrat menejer/admin tasdig'ini talab qiladi.
    // Vozvratning O'ZI rol bilan cheklanmagan — tasdiq tanada keladi.
    // verifyApprover cheklangan (5/daqiqa) va muvaffaqiyatsiz urinish
    // audit jurnaliga tushadi.
    $approver = Auth::verifyApprover(
        $user,
        Http::reqStr($b, 'manager_username', 150, 'Menejer login'),
        Http::reqStr($b, 'manager_password', 200, 'Menejer parol')
    );

    $sale = Db::one('SELECT * FROM sales WHERE id = ?', [$saleId]);
    if ($sale === null) {
        fail(404, 'Sale not found');
    }
    if ($sale['status'] === 'refunded') {
        fail(400, 'Sale already refunded');
    }

    // Vozvrat qaysi smenada bo'lganini yozib qo'yamiz: naqd pul aynan o'sha
    // smenaning kassasidan chiqadi. Smena ochiq bo'lmasa (masalan admin
    // kabinetdan qaytarsa) NULL bo'ladi — pul kassadan chiqmagan hisoblanadi.
    $refundShift = Db::one(
        "SELECT id FROM shifts WHERE cashier_id = ? AND status = 'open' ORDER BY id DESC",
        [$user['id']]
    );

    Db::tx(function () use ($sale, $saleId, $user, $approver, $refundShift): void {
        $items = Db::all(
            'SELECT si.*, p.is_infinite FROM sale_items si
             LEFT JOIN products p ON p.id = si.product_id
             WHERE si.sale_id = ?',
            [$saleId]
        );

        foreach ($items as $it) {
            if ($it['product_id'] === null) {
                continue;
            }
            // Cheksiz qoldiqli mahsulot sotuvda kamaymagan — vozvratda ham
            // oshmasligi kerak.
            if (!Db::b($it['is_infinite'])) {
                Db::run(
                    'UPDATE products SET stock = stock + ? WHERE id = ?',
                    [(float)$it['quantity'], (int)$it['product_id']]
                );
            }
            Db::insert('stock_moves', [
                'product_id' => (int)$it['product_id'],
                'quantity'   => (float)$it['quantity'],
                'type'       => 'refund',
                'reason'     => "Vozvrat (Chek ID: $saleId)",
                'created_by' => $user['id'],
                'created_at' => Tz::now(),
            ]);
        }

        // Mijoz balansi va bonuslar — bitta atomik UPDATE bilan.
        if (!empty($sale['client_id'])) {
            $sets = [];
            $params = [];
            if ((float)$sale['debt_amount'] > 0) {
                $sets[] = 'balance = balance + ?';
                $params[] = (float)$sale['debt_amount'];
            }
            $bonusDelta = (float)($sale['bonus_spent'] ?? 0) - (float)($sale['bonus_earned'] ?? 0);
            if (abs($bonusDelta) > 0.0000001) {
                $sets[] = 'bonus_balance = bonus_balance + ?';
                $params[] = $bonusDelta;
            }
            if ($sets !== []) {
                $params[] = (int)$sale['client_id'];
                Db::run('UPDATE clients SET ' . implode(', ', $sets) . ' WHERE id = ?', $params);
            }
        }

        Db::update('sales', $saleId, [
            'refunded_at'     => Tz::now(),
            'refund_shift_id' => $refundShift ? (int)$refundShift['id'] : null,
            'status'          => 'refunded',
        ]);

        Audit::log(
            (int)$user['id'],
            'VOZVRAT',
            "Savdo qaytarildi. Chek ID: $saleId. Summa: "
            . number_format((float)$sale['total_amount'], 0, '.', ',') . " so'm. "
            . 'Tasdiqladi: @' . $approver['username']
        );
    });

    Http::json(sale_response($saleId));
});
