<?php
/**
 * /inventory — mahsulotlar, kategoriyalar, kirimlar, ombor harakatlari.
 *
 * Eng nozik joyi — mahsulotni tahrirlash: u OPTIMISTIK QULF bilan ishlaydi.
 * Tahrirlash oynasi ochiq turganda tovar sotilgan bo'lsa, eski qoldiqni
 * qayta yozib yuborish oradagi sotuvlarni bekor qilar va omborga yolg'on
 * "tuzatish" yozuvi tushardi.
 */

declare(strict_types=1);

// --- Qo'shimcha shtrix-kodlar -------------------------------------------
//
// Bitta mahsulot bir nechta kod bilan skanerlanishi mumkin (masalan
// Agushaning har xil ta'mlari). Asosiy kod products.barcode da, qolganlari
// product_barcodes da. Kod IKKALA joy bo'yicha ham noyob bo'lishi kerak:
// aks holda kassa bitta kodni ikki xil mahsulotga olib borardi.

/** Kod kimniki: mahsulot nomi yoki null. $exceptId — o'zi hisobga olinmaydi. */
function barcode_owner(string $code, ?int $exceptId = null): ?string
{
    $ex = $exceptId ?? 0;
    $row = Db::one('SELECT name FROM products WHERE barcode = ? AND id <> ?', [$code, $ex])
        ?? Db::one(
            'SELECT p.name FROM product_barcodes pb JOIN products p ON p.id = pb.product_id
             WHERE pb.barcode = ? AND pb.product_id <> ?',
            [$code, $ex]
        );
    return $row['name'] ?? null;
}

/**
 * So'rovdan `extra_barcodes` ro'yxatini o'qiydi va tekshiradi.
 * Maydon umuman yuborilmagan bo'lsa null — ya'ni "tegma".
 */
function read_extra_barcodes(array $b, ?string $primary, ?int $productId): ?array
{
    if (!array_key_exists('extra_barcodes', $b) || $b['extra_barcodes'] === null) {
        return null;
    }
    if (!is_array($b['extra_barcodes'])) {
        fail(422, "«Qo'shimcha shtrix-kodlar» ro'yxat bo'lishi kerak.");
    }
    $codes = [];
    foreach ($b['extra_barcodes'] as $raw) {
        if (!is_string($raw) && !is_int($raw)) {
            fail(422, "Shtrix-kod matn bo'lishi kerak.");
        }
        $code = trim((string)$raw);
        if ($code === '' || $code === $primary || in_array($code, $codes, true)) {
            continue;
        }
        if (mb_strlen($code) > 30) {
            fail(422, "Shtrix-kod juda uzun (eng ko'pi 30 belgi): $code");
        }
        $owner = barcode_owner($code, $productId);
        if ($owner !== null) {
            fail(409, "Shtrix-kod $code band: \"$owner\"");
        }
        $codes[] = $code;
    }
    if (count($codes) > 100) {
        fail(422, "Bitta mahsulotga ko'pi bilan 100 ta qo'shimcha shtrix-kod.");
    }
    return $codes;
}

/** Mahsulotning qo'shimcha kodlarini to'liq almashtiradi. Tranzaksiya ichida. */
function save_extra_barcodes(int $productId, array $codes): void
{
    Db::run('DELETE FROM product_barcodes WHERE product_id = ?', [$productId]);
    foreach ($codes as $code) {
        Db::insert('product_barcodes', ['product_id' => $productId, 'barcode' => $code]);
    }
}

/** Mahsulot qatorlariga `extra_barcodes` ni qo'shadi (bitta so'rov bilan). */
function with_extra_barcodes(array $rows): array
{
    if ($rows === []) {
        return $rows;
    }
    $ids = array_map(fn($r) => (int)$r['id'], $rows);
    // Ko'p mahsulotda IN (...) SQLite parametr chegarasiga urilardi. Jadval
    // kichik (faqat qo'shimcha kodlar), shuning uchun hammasini o'qish arzon.
    $extra = count($ids) > 200
        ? Db::all('SELECT product_id, barcode FROM product_barcodes ORDER BY id')
        : Db::all('SELECT product_id, barcode FROM product_barcodes WHERE product_id IN ('
            . Db::marks($ids) . ') ORDER BY id', $ids);
    $byProduct = [];
    foreach ($extra as $e) {
        $byProduct[(int)$e['product_id']][] = $e['barcode'];
    }
    foreach ($rows as &$r) {
        $r['extra_barcodes'] = $byProduct[(int)$r['id']] ?? [];
    }
    unset($r);
    return $rows;
}

function product_response(int $id): never
{
    $rows = with_extra_barcodes([Db::one('SELECT * FROM products WHERE id = ?', [$id])]);
    Http::json(Shape::product($rows[0]));
}

// =======================================================================
// GET /inventory/purchase-list
// =======================================================================
Router::get('/purchase-list', function (): never {
    Auth::require(['admin', 'manager', 'warehouse'], 'Ruxsat berilmagan');

    $settings = Db::one('SELECT low_stock_threshold FROM store_settings ORDER BY id LIMIT 1');
    $threshold = max((int)($settings['low_stock_threshold'] ?? 5), 1);

    // is_infinite ni SON bilan solishtirmaymiz — PostgreSQL da bu boolean.
    $rows = Db::all(
        'SELECT * FROM products WHERE stock < ? AND is_infinite = ? ORDER BY stock ASC',
        [$threshold, false]
    );

    Http::json(array_map(function ($p) use ($threshold) {
        $stock = Db::f($p['stock']);
        $suggested = max($threshold * 2 - $stock, $threshold - $stock);
        return [
            'product_id'         => Db::i($p['id']),
            'name'               => $p['name'],
            'barcode'            => $p['barcode'] ?? null,
            'unit'               => $p['unit'] ?? 'dona',
            'stock'              => $stock,
            'minimum_stock'      => $threshold,
            'suggested_quantity' => $suggested,
            'estimated_cost'     => $suggested * Db::f($p['buy_price']),
            'priority'           => $stock <= 0 ? 'critical' : 'low',
        ];
    }, $rows));
});

// =======================================================================
// POST /inventory/supplies  — kirim
// =======================================================================
Router::post('/supplies', function (): never {
    $user = Auth::require(['admin', 'manager', 'warehouse'], 'Not enough permissions');
    $b = Http::body();

    $productId = Http::reqInt($b, 'product_id', 'Mahsulot');
    // Manfiy/NaN kirim qoldiqni ham, tannarxni ham buzardi: tannarx sotuv
    // paytida muzlatilgani uchun keyin tuzatish eski cheklarni tiklamaydi.
    $quantity = Http::reqNum($b, 'quantity', 'gt', 0, null, 'Soni');
    $buyPrice = Http::reqNum($b, 'buy_price', 'ge', 0, null, 'Kelish narxi');
    // Ixtiyoriy: yangi partiya bilan sotish narxi ham o'zgargan bo'lsa.
    // Yuborilmasa — joriy narx qoladi.
    $sellPrice = Http::num($b, 'sell_price', null, 'gt', 0, null, 'Sotish narxi');

    $product = Db::one('SELECT * FROM products WHERE id = ?', [$productId]);
    if ($product === null) {
        fail(404, 'Product not found');
    }
    $oldSell = Db::f($product['sell_price']);
    if ($sellPrice !== null && abs($sellPrice - $oldSell) < 1e-9) {
        $sellPrice = null;
    }

    $supplyId = Db::tx(function () use ($productId, $quantity, $buyPrice, $sellPrice, $oldSell, $user, $product): int {
        $supplyId = Db::insert('supplies', [
            'product_id' => $productId,
            'quantity'   => $quantity,
            'buy_price'  => $buyPrice,
            'created_at' => Tz::now(),
        ]);

        // Qoldiq va tannarxni ATOMIK yangilaymiz. Ilgari "o'qi -> qo'sh ->
        // yoz" edi: bir vaqtda kelgan ikki kirimdan biri yo'qolib ketardi.
        Db::run(
            'UPDATE products SET stock = stock + ?, buy_price = ? WHERE id = ?',
            [$quantity, $buyPrice, $productId]
        );
        if ($sellPrice !== null) {
            Db::run('UPDATE products SET sell_price = ? WHERE id = ?', [$sellPrice, $productId]);
        }

        Db::insert('stock_moves', [
            'product_id' => $productId,
            'quantity'   => $quantity,
            'type'       => 'restock',
            'reason'     => "Yangi kirim (ID: $supplyId)",
            'created_by' => $user['id'],
            'created_at' => Tz::now(),
        ]);

        Audit::log((int)$user['id'], 'OMBOR_KIRIM',
            "Mahsulot: {$product['name']}. Soni: $quantity. Narxi: $buyPrice"
            . ($sellPrice !== null ? ". Sotish narxi: $oldSell -> $sellPrice" : ''));

        return $supplyId;
    });

    Http::json(Shape::supply(Db::one('SELECT * FROM supplies WHERE id = ?', [$supplyId])));
});

// =======================================================================
// GET /inventory/supplies
// =======================================================================
Router::get('/supplies', function (): never {
    Auth::require(['admin', 'manager', 'warehouse'], 'Ruxsat berilmagan');

    $productId = Http::qInt('product_id');
    $rows = $productId
        ? Db::all('SELECT * FROM supplies WHERE product_id = ? ORDER BY created_at DESC, id DESC LIMIT 1000', [$productId])
        : Db::all('SELECT * FROM supplies ORDER BY created_at DESC, id DESC LIMIT 1000');

    Http::json(array_map(fn($r) => Shape::supply($r), $rows));
});

// =======================================================================
// DELETE /inventory/supplies/{supply_id}
// =======================================================================
Router::delete('/supplies/{supply_id}', function (array $p): never {
    // Xato kiritilgan kirimni bekor qilish.
    //
    // Kirimni tuzatishning yo'li yo'q edi. Noto'g'ri tannarx kiritilsa, u
    // mahsulotga yozilib qolar va o'shandan keyingi HAR BIR sotuvning
    // tannarxi shu xato qiymatdan muzlatilardi — ya'ni keyinchalik
    // mahsulotni tuzatish ham eski cheklarni tiklamasdi.
    $user = Auth::require(['admin', 'manager'], 'Faqat admin va menejer bekor qila oladi');
    $supplyId = Router::id($p, 'supply_id');

    $reason = Http::q('reason');
    if ($reason === null || mb_strlen($reason) < 3 || mb_strlen($reason) > 300) {
        fail(422, 'Bekor qilish sababini yozing (3-300 belgi).');
    }

    $supply = Db::one('SELECT * FROM supplies WHERE id = ?', [$supplyId]);
    if ($supply === null) {
        fail(404, 'Kirim topilmadi');
    }
    $product = Db::one('SELECT * FROM products WHERE id = ?', [(int)$supply['product_id']]);
    if ($product === null) {
        fail(404, 'Mahsulot topilmadi');
    }

    $qty = Db::f($supply['quantity']);

    $restoredPrice = Db::tx(function () use ($supply, $supplyId, $product, $qty, $user, $reason): float {
        // Qoldiqni ATOMIK kamaytiramiz. Tovar allaqachon sotilgan bo'lsa,
        // qoldiqni minusga tushirmaymiz — bunday holatda bekor qilib bo'lmaydi.
        if (!Db::b($product['is_infinite'])) {
            $ok = Db::run(
                'UPDATE products SET stock = stock - ? WHERE id = ? AND stock >= ?',
                [$qty, (int)$product['id'], $qty]
            );
            if ($ok === 0) {
                fail(409, "Bekor qilib bo'lmaydi: omborda "
                    . rtrim(rtrim(number_format(Db::f($product['stock']), 3, '.', ''), '0'), '.')
                    . " qoldi, kirim esa "
                    . rtrim(rtrim(number_format($qty, 3, '.', ''), '0'), '.')
                    . ' edi. Tovar allaqachon sotilgan.');
            }
        }

        // Tannarxni shu mahsulotning OLDINGI kirimidagi qiymatga qaytaramiz.
        $previous = Db::one(
            'SELECT buy_price FROM supplies WHERE product_id = ? AND id <> ?
             ORDER BY created_at DESC, id DESC LIMIT 1',
            [(int)$supply['product_id'], $supplyId]
        );
        $restored = $previous ? Db::f($previous['buy_price']) : Db::f($product['buy_price']);
        if ($previous !== null) {
            Db::run('UPDATE products SET buy_price = ? WHERE id = ?', [$restored, (int)$product['id']]);
        }

        Db::insert('stock_moves', [
            'product_id' => (int)$product['id'],
            'quantity'   => -$qty,
            'type'       => 'adjustment',
            'reason'     => "Kirim bekor qilindi (Kirim ID: $supplyId). Sabab: $reason",
            'created_by' => $user['id'],
            'created_at' => Tz::now(),
        ]);

        Audit::log((int)$user['id'], 'KIRIM_BEKOR_QILINDI',
            "Kirim #$supplyId bekor qilindi: {$product['name']}, $qty dona, tannarx "
            . number_format(Db::f($supply['buy_price']), 0, '.', ',') . ' -> '
            . number_format($restored, 0, '.', ',') . " so'm. Sabab: $reason");

        Db::delete('supplies', $supplyId);
        return $restored;
    });

    $fresh = Db::one('SELECT stock, buy_price FROM products WHERE id = ?', [(int)$product['id']]);
    Http::json([
        'message'       => 'Kirim bekor qilindi',
        'new_stock'     => Db::f($fresh['stock']),
        'new_buy_price' => Db::f($fresh['buy_price']),
    ]);
});

// =======================================================================
// GET /inventory/logs
// =======================================================================
Router::get('/logs', function (): never {
    Auth::require(['admin', 'manager', 'warehouse'], 'Ruxsat berilmagan');

    $productId = Http::qInt('product_id');
    $limit = Http::qInt('limit', 500, 1, 2000) ?? 500;

    $rows = $productId
        ? Db::all("SELECT * FROM stock_moves WHERE product_id = ? ORDER BY created_at DESC, id DESC LIMIT $limit", [$productId])
        : Db::all("SELECT * FROM stock_moves ORDER BY created_at DESC, id DESC LIMIT $limit");

    $products = Shape::lookup('products', array_column($rows, 'product_id'));
    Http::json(array_map(
        fn($r) => Shape::stockMove($r, $products[(int)($r['product_id'] ?? 0)] ?? null),
        $rows
    ));
});

// =======================================================================
// POST /inventory/products/{product_id}/return
// =======================================================================
Router::post('/products/{product_id}/return', function (array $p): never {
    $user = Auth::require(['admin', 'manager', 'warehouse', 'cashier'], 'Ruxsat berilmagan');
    $productId = Router::id($p, 'product_id');
    $b = Http::body();

    $quantity = Http::reqNum($b, 'quantity', 'gt', 0, null, 'Soni');
    $reason = Http::reqStr($b, 'reason', 300, 'Sabab');
    if (mb_strlen($reason) < 3) {
        fail(422, 'Sabab kamida 3 belgidan iborat bo\'lsin.');
    }

    $product = Db::one('SELECT * FROM products WHERE id = ?', [$productId]);
    if ($product === null) {
        fail(404, 'Mahsulot topilmadi');
    }

    Db::tx(function () use ($productId, $quantity, $reason, $user, $product): void {
        Db::run('UPDATE products SET stock = stock + ? WHERE id = ?', [$quantity, $productId]);
        Db::insert('stock_moves', [
            'product_id' => $productId,
            'quantity'   => $quantity,
            'type'       => 'return_unsold',
            'reason'     => "Sotuvsiz qaytarish: $reason",
            'created_by' => $user['id'],
            'created_at' => Tz::now(),
        ]);
        Audit::log((int)$user['id'], 'SOTUVSIZ_QAYTARISH',
            "Mahsulot: {$product['name']}. Soni: $quantity. Sabab: $reason");
    });

    product_response($productId);
});

// =======================================================================
// GET /inventory/products
// =======================================================================
Router::get('/products', function (): never {
    Auth::user();

    $where = ['1=1'];
    $params = [];

    $categoryId = Http::qInt('category_id');
    if ($categoryId) {
        $where[] = 'category_id = ?';
        $params[] = $categoryId;
    }

    $query = Http::q('query');
    if ($query !== null && $query !== '') {
        // Registrga sezgir bo'lmagan qidiruv. Oddiy LIKE PostgreSQL da
        // registrni hisobga oladi — serverga ko'chganda mahsulot qidiruvi
        // hech narsa topmay qo'yardi.
        $where[] = '(' . Db::ilike('name') . ' OR ' . Db::ilike('barcode')
            . ' OR id IN (SELECT product_id FROM product_barcodes WHERE ' . Db::ilike('barcode') . '))';
        $params[] = "%$query%";
        $params[] = "%$query%";
        $params[] = "%$query%";
    }
    $whereSql = implode(' AND ', $where);

    // `limit` ATAYIN majburiy emas va sukut bo'yicha YO'Q. Unga standart
    // qiymat qo'ysak, eski chaqiruvlar jimgina qirqilib qolardi: kassa yoki
    // ombor sahifasi "hammasi shu" deb ko'rsatib turgan holda katalogning
    // bir qismini yashirib qo'yardi.
    $sql = "SELECT * FROM products WHERE $whereSql ORDER BY is_favorite DESC, name";
    $limit = Http::qInt('limit');
    if ($limit !== null) {
        $limit = max(1, min($limit, 500));
        $offset = max(0, Http::qInt('offset', 0) ?? 0);
        $sql .= " LIMIT $limit OFFSET $offset";
    }

    $rows = Db::all($sql, $params);

    // COUNT ni faqat SAHIFALASH bo'lganda so'raymiz.
    //
    // `limit` berilmagan bo'lsa mijoz butun ro'yxatni oladi, ya'ni jami son
    // — bu qaytarilgan qatorlar soni. Baribir COUNT yuborish bir so'rovni
    // bekorga sarflash edi, kassa esa katalogni eng tez-tez so'raydigan
    // joy: bu har ochilishda ortiqcha bir marta bazaga borish demakdi.
    $total = $limit === null
        ? count($rows)
        : (int)Db::val("SELECT COUNT(*) FROM products WHERE $whereSql", $params, 0);

    header('X-Total-Count: ' . $total);
    header('Access-Control-Expose-Headers: X-Total-Count');

    Http::json(array_map(fn($r) => Shape::product($r), with_extra_barcodes($rows)));
});

// =======================================================================
// GET /inventory/barcode-lookup/{barcode}
// =======================================================================
Router::get('/barcode-lookup/{barcode}', function (array $p): never {
    Auth::user();
    $barcode = trim($p['barcode'] ?? '');
    if ($barcode === '' || !preg_match('/^[A-Za-z0-9-]{1,30}$/', $barcode)) {
        fail(422, "Shtrix-kod bo'sh");
    }

    // 1) Avval O'Z bazamizda qaraymiz.
    $existing = Db::one('SELECT id, name FROM products WHERE barcode = ?', [$barcode])
        ?? Db::one(
            'SELECT p.id, p.name FROM product_barcodes pb JOIN products p ON p.id = pb.product_id
             WHERE pb.barcode = ?',
            [$barcode]
        );
    if ($existing !== null) {
        Http::json([
            'found'      => true,
            'exists'     => true,
            'source'     => 'local',
            'product_id' => Db::i($existing['id']),
            'name'       => $existing['name'],
            'brand'      => null,
            'image_url'  => null,
        ]);
    }

    // 2) Keshda bormi? Python'da bu xotirada edi, PHP da jarayon o'lgani
    //    uchun faylda — internetga qayta chiqmaslik uchun.
    $cacheDir = ROOT_DIR . '/logs/barcode';
    $cacheFile = $cacheDir . '/' . preg_replace('/[^A-Za-z0-9-]/', '', $barcode) . '.json';
    if (is_file($cacheFile) && time() - filemtime($cacheFile) < 2592000) {
        $cached = json_decode((string)@file_get_contents($cacheFile), true);
        if (is_array($cached)) {
            Http::json($cached);
        }
    }

    $result = ['found' => false, 'exists' => false, 'source' => null,
               'name' => '', 'brand' => null, 'image_url' => null];

    // 3) Open Food Facts (ochiq, bepul). Internet yo'q / topilmasa —
    //    found: false qaytadi, xato bermaydi.
    $url = "https://world.openfoodfacts.org/api/v2/product/$barcode.json"
        . '?fields=product_name,product_name_ru,product_name_uz,brands,image_front_small_url,quantity';

    $raw = http_get_short($url, 6);
    if ($raw !== null) {
        $data = json_decode($raw, true);
        if (is_array($data) && ($data['status'] ?? 0) == 1) {
            $pr = $data['product'] ?? [];
            $name = trim((string)($pr['product_name_ru'] ?? $pr['product_name'] ?? $pr['product_name_uz'] ?? ''));
            $qty = trim((string)($pr['quantity'] ?? ''));
            if ($name !== '' && $qty !== '' && !str_contains(mb_strtolower($name), mb_strtolower($qty))) {
                $name = "$name $qty";
            }
            $result = [
                'found'     => $name !== '',
                'exists'    => false,
                'source'    => 'openfoodfacts',
                'name'      => $name,
                'brand'     => trim((string)($pr['brands'] ?? '')) ?: null,
                'image_url' => $pr['image_front_small_url'] ?? null,
            ];
        }
    }

    if ($result['found']) {
        if (!is_dir($cacheDir)) {
            @mkdir($cacheDir, 0700, true);
        }
        @file_put_contents($cacheFile, json_encode($result, JSON_UNESCAPED_UNICODE));
    }

    Http::json($result);
});

/** Qisqa tashqi so'rov. Internet yo'q bo'lsa null — xato tashlamaydi. */
function http_get_short(string $url, int $timeout): ?string
{
    if (function_exists('curl_init')) {
        $ch = curl_init($url);
        curl_setopt_array($ch, [
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT        => $timeout,
            CURLOPT_CONNECTTIMEOUT => 3,
            CURLOPT_FOLLOWLOCATION => true,
            CURLOPT_MAXREDIRS      => 2,
            CURLOPT_USERAGENT      => 'SmartKassa POS (self-hosted)',
        ]);
        $body = curl_exec($ch);
        $code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);
        return ($body !== false && $code === 200) ? (string)$body : null;
    }

    $ctx = stream_context_create(['http' => [
        'timeout' => $timeout,
        'header'  => "User-Agent: SmartKassa POS (self-hosted)\r\n",
    ]]);
    $body = @file_get_contents($url, false, $ctx);
    return $body === false ? null : $body;
}

// =======================================================================
// POST /inventory/products
// =======================================================================
Router::post('/products', function (): never {
    $user = Auth::require(['admin', 'manager', 'warehouse'], 'Not enough permissions');
    $b = Http::body();

    $name = Http::reqStr($b, 'name', 300, 'Nomi');
    $barcode = Http::str($b, 'barcode', null, 30, 'Shtrix-kod');
    $buyPrice = Http::num($b, 'buy_price', 0.0, 'ge', 0, null, 'Kelish narxi') ?? 0.0;
    $sellPrice = Http::num($b, 'sell_price', 0.0, 'ge', 0, null, 'Sotish narxi') ?? 0.0;
    $stock = Http::num($b, 'stock', 0.0, 'any', null, null, 'Qoldiq') ?? 0.0;

    // Takroriy shtrix-kod NOZIK xato bo'lishi kerak, 500 emas. Ilgari unikal
    // cheklov buzilishi ushlanmasdi va operator "Ichki server xatoligi"
    // degan tushunarsiz xabar olardi.
    if ($barcode !== null) {
        $owner = barcode_owner($barcode);
        if ($owner !== null) {
            fail(409, "Bu shtrix-kod band: \"$owner\"");
        }
    }
    $extraCodes = read_extra_barcodes($b, $barcode, null) ?? [];

    $id = Db::tx(function () use ($b, $user, $name, $barcode, $extraCodes, $buyPrice, $sellPrice, $stock): int {
        $id = Db::insert('products', [
            'name'        => $name,
            'barcode'     => $barcode,
            'buy_price'   => $buyPrice,
            'sell_price'  => $sellPrice,
            'stock'       => $stock,
            'is_infinite' => Http::bool($b, 'is_infinite'),
            'unit'        => Http::str($b, 'unit', 'dona', 20, 'Birlik'),
            'category_id' => Http::int($b, 'category_id'),
            'is_favorite' => Http::bool($b, 'is_favorite'),
        ]);
        save_extra_barcodes($id, $extraCodes);

        if ($stock > 0) {
            Db::insert('stock_moves', [
                'product_id' => $id,
                'quantity'   => $stock,
                'type'       => 'adjustment',
                'reason'     => 'Dastlabki qoldiq (mahsulot yaratilganda)',
                'created_by' => $user['id'],
                'created_at' => Tz::now(),
            ]);
        }

        Audit::log((int)$user['id'], 'YANGI_MAHSULOT',
            "Mahsulot: $name. Sklad: $stock. Narx: $sellPrice"
            . ($extraCodes ? ". Qo'shimcha kodlar: " . implode(', ', $extraCodes) : ''));
        return $id;
    });

    product_response($id);
});

// =======================================================================
// PUT /inventory/products/{product_id}
// =======================================================================
Router::put('/products/{product_id}', function (array $p): never {
    $user = Auth::require(['admin', 'manager', 'warehouse'], 'Not enough permissions');
    $productId = Router::id($p, 'product_id');
    $b = Http::body();

    $product = Db::one('SELECT * FROM products WHERE id = ?', [$productId]);
    if ($product === null) {
        fail(404, 'Product not found');
    }

    $oldStock = Db::f($product['stock']);
    $newStock = Http::num($b, 'stock', $oldStock, 'any', null, null, 'Qoldiq') ?? $oldStock;
    $expected = Http::num($b, 'expected_stock', null, 'any', null, null, 'Kutilgan qoldiq');

    // OPTIMISTIK QULF: tahrirlash oynasi ochiq turganda tovar sotilgan
    // bo'lsa, eski qoldiqni qayta yozib yubormaymiz. Ilgari forma
    // yuklangan paytdagi qiymat shunchaki ustidan yozilardi — oradagi
    // sotuvlar bekor bo'lib, omborga yolg'on "tuzatish" tushardi.
    if ($expected !== null && abs($expected - $oldStock) > 1e-9) {
        fail(409, "Qoldiq siz formani ochganingizdan keyin o'zgardi ("
            . rtrim(rtrim(number_format($expected, 3, '.', ''), '0'), '.') . ' -> '
            . rtrim(rtrim(number_format($oldStock, 3, '.', ''), '0'), '.')
            . '). Sahifani yangilab, qaytadan urinib ko\'ring.');
    }

    $barcode = Http::str($b, 'barcode', null, 30, 'Shtrix-kod');
    if ($barcode !== null && $barcode !== ($product['barcode'] ?? null)) {
        $clash = barcode_owner($barcode, $productId);
        if ($clash !== null) {
            fail(409, "Bu shtrix-kod band: \"$clash\"");
        }
    }
    // null — forma bu maydonni yubormadi, mavjud kodlarga tegmaymiz.
    $extraCodes = read_extra_barcodes($b, $barcode, $productId);

    $data = [
        'name'        => Http::reqStr($b, 'name', 300, 'Nomi'),
        'barcode'     => $barcode,
        'buy_price'   => Http::num($b, 'buy_price', Db::f($product['buy_price']), 'ge', 0, null, 'Kelish narxi'),
        'sell_price'  => Http::num($b, 'sell_price', Db::f($product['sell_price']), 'ge', 0, null, 'Sotish narxi'),
        'is_infinite' => Http::bool($b, 'is_infinite', Db::b($product['is_infinite'])),
        'unit'        => Http::str($b, 'unit', $product['unit'] ?? 'dona', 20, 'Birlik'),
        'category_id' => array_key_exists('category_id', $b) ? Http::int($b, 'category_id') : (isset($product['category_id']) ? (int)$product['category_id'] : null),
        'is_favorite' => Http::bool($b, 'is_favorite', Db::b($product['is_favorite'])),
    ];

    Db::tx(function () use ($data, $productId, $expected, $newStock, $oldStock, $user, $product, $extraCodes): void {
        // Qoldiqni ATOMIK va SHARTLI yozamiz (compare-and-swap).
        //
        // Yuqoridagi tekshiruv formani ochgan paytdagi qiymatni solishtiradi,
        // ammo tekshiruv bilan yozuv orasida ham sotuv bo'lishi mumkin.
        // Shuning uchun yozuvning O'ZI ham shartli.
        if ($expected !== null && abs($newStock - $oldStock) > 1e-9) {
            $ok = Db::run(
                'UPDATE products SET stock = ? WHERE id = ? AND stock = ?',
                [$newStock, $productId, $expected]
            );
            if ($ok === 0) {
                fail(409, "Qoldiq hozirgina o'zgardi. Sahifani yangilab, qaytadan urinib ko'ring.");
            }
        } elseif ($expected === null) {
            // expected_stock berilmagan — eski xulq: qoldiqni to'g'ridan-
            // to'g'ri yozamiz (masalan ombor inventarizatsiyasi).
            $data['stock'] = $newStock;
        }

        Db::update('products', $productId, $data);
        if ($extraCodes !== null) {
            save_extra_barcodes($productId, $extraCodes);
        }

        if (abs($newStock - $oldStock) > 1e-9) {
            Db::insert('stock_moves', [
                'product_id' => $productId,
                'quantity'   => $newStock - $oldStock,
                'type'       => 'adjustment',
                'reason'     => 'Ombor tahrirlandi (adjustment)',
                'created_by' => $user['id'],
                'created_at' => Tz::now(),
            ]);
        }

        Audit::log((int)$user['id'], 'MAHSULOT_TAHRIR',
            "Mahsulot: {$data['name']} (ID: $productId). Sklad: $oldStock -> $newStock"
            . ($extraCodes ? ". Qo'shimcha kodlar: " . implode(', ', $extraCodes) : ''));
    });

    product_response($productId);
});

// =======================================================================
// DELETE /inventory/products/{product_id}
// =======================================================================
Router::delete('/products/{product_id}', function (array $p): never {
    $user = Auth::require(['admin', 'manager', 'warehouse'], "Mahsulotni o'chirishga ruxsat yo'q");
    $productId = Router::id($p, 'product_id');

    $product = Db::one('SELECT * FROM products WHERE id = ?', [$productId]);
    if ($product === null) {
        fail(404, 'Mahsulot topilmadi');
    }

    // Tarixga bog'langan mahsulotni faqat ADMIN o'chira oladi.
    //
    // Cheklar buzilmasligi uchun o'chirishdan oldin har bir sotuv satriga
    // mahsulot nomi va (bo'sh bo'lsa) tannarxi ko'chiriladi, keyin
    // product_id uziladi. Aks holda eski cheklarda tovar nomi yo'qolar,
    // hisobotdagi tannarx JOIN orqali olingani uchun esa sof foyda sun'iy
    // ravishda oshardi.
    $sold = (int)Db::val('SELECT COUNT(*) FROM sale_items WHERE product_id = ?', [$productId], 0);
    $supplied = (int)Db::val('SELECT COUNT(*) FROM supplies WHERE product_id = ?', [$productId], 0);
    if (($sold > 0 || $supplied > 0) && $user['role'] !== 'admin') {
        fail(409, "Bu mahsulotda tarix bor ($sold ta chek, $supplied ta kirim) — "
            . "uni faqat admin o'chira oladi.");
    }

    Db::tx(function () use ($productId, $user, $product, $sold, $supplied): void {
        Db::run(
            'UPDATE sale_items SET product_name = ?, buy_price = COALESCE(buy_price, ?), product_id = NULL
             WHERE product_id = ?',
            [$product['name'], Db::f($product['buy_price'] ?? 0), $productId]
        );
        Db::run('UPDATE supplies SET product_id = NULL WHERE product_id = ?', [$productId]);
        // Qoldiq harakatlari tarix emas, mahsulotning o'ziga tegishli —
        // ular ketishi mumkin.
        Db::run('DELETE FROM stock_moves WHERE product_id = ?', [$productId]);
        Db::run('DELETE FROM product_barcodes WHERE product_id = ?', [$productId]);
        Db::delete('products', $productId);
        Audit::log((int)$user['id'], 'DELETE_PRODUCT',
            "Mahsulot o'chirildi: {$product['name']} (ID: $productId). "
            . "Uzilgan cheklar: $sold, kirimlar: $supplied");
    });

    Http::json(['status' => 'success', 'message' => 'Product deleted']);
});

// =======================================================================
// GET /inventory/categories
// =======================================================================
Router::get('/categories', function (): never {
    Auth::user();
    Http::json(array_map(
        fn($r) => Shape::category($r),
        Db::all('SELECT * FROM categories ORDER BY name')
    ));
});

// =======================================================================
// POST /inventory/categories
// =======================================================================
Router::post('/categories', function (): never {
    $user = Auth::require(['admin', 'manager', 'warehouse'], 'Not enough permissions');
    $name = Http::reqStr(Http::body(), 'name', 100, 'Nomi');

    if (Db::one('SELECT id FROM categories WHERE name = ?', [$name]) !== null) {
        fail(409, 'Bunday kategoriya allaqachon bor.');
    }

    $id = Db::tx(function () use ($name, $user): int {
        $id = Db::insert('categories', ['name' => $name]);
        Audit::log((int)$user['id'], 'YANGI_KATEGORIYA', "Kategoriya: $name");
        return $id;
    });

    Http::json(Shape::category(Db::one('SELECT * FROM categories WHERE id = ?', [$id])));
});

// =======================================================================
// POST /inventory/products/{product_id}/toggle-favorite
// =======================================================================
Router::post('/products/{product_id}/toggle-favorite', function (array $p): never {
    Auth::require(['admin', 'manager', 'warehouse', 'cashier'], 'Not enough permissions');
    $productId = Router::id($p, 'product_id');

    $product = Db::one('SELECT * FROM products WHERE id = ?', [$productId]);
    if ($product === null) {
        fail(404, 'Product not found');
    }

    // Bitta so'rov bilan ag'daramiz — o'qib-yozish oralig'i yo'q.
    // NOT uchala bazada ham ishlaydi (MySQL/SQLite da 1/0, PostgreSQL da bool).
    Db::run('UPDATE products SET is_favorite = NOT is_favorite WHERE id = ?', [$productId]);

    product_response($productId);
});
