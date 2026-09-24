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

    $product = Db::one('SELECT * FROM products WHERE id = ?', [$productId]);
    if ($product === null) {
        fail(404, 'Product not found');
    }

    $supplyId = Db::tx(function () use ($productId, $quantity, $buyPrice, $user, $product): int {
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

        Db::insert('stock_moves', [
            'product_id' => $productId,
            'quantity'   => $quantity,
            'type'       => 'restock',
            'reason'     => "Yangi kirim (ID: $supplyId)",
            'created_by' => $user['id'],
            'created_at' => Tz::now(),
        ]);

        Audit::log((int)$user['id'], 'OMBOR_KIRIM',
            "Mahsulot: {$product['name']}. Soni: $quantity. Narxi: $buyPrice");

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

    Http::json(Shape::product(Db::one('SELECT * FROM products WHERE id = ?', [$productId])));
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
        $where[] = '(' . Db::ilike('name') . ' OR ' . Db::ilike('barcode') . ')';
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

    Http::json(array_map(fn($r) => Shape::product($r), $rows));
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
    $existing = Db::one('SELECT id, name FROM products WHERE barcode = ?', [$barcode]);
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
        $existing = Db::one('SELECT name FROM products WHERE barcode = ?', [$barcode]);
        if ($existing !== null) {
            fail(409, "Bu shtrix-kod band: \"{$existing['name']}\"");
        }
    }

    $id = Db::tx(function () use ($b, $user, $name, $barcode, $buyPrice, $sellPrice, $stock): int {
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
            "Mahsulot: $name. Sklad: $stock. Narx: $sellPrice");
        return $id;
    });

    Http::json(Shape::product(Db::one('SELECT * FROM products WHERE id = ?', [$id])));
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
        $clash = Db::one('SELECT name FROM products WHERE barcode = ? AND id <> ?', [$barcode, $productId]);
        if ($clash !== null) {
            fail(409, "Bu shtrix-kod band: \"{$clash['name']}\"");
        }
    }

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

    Db::tx(function () use ($data, $productId, $expected, $newStock, $oldStock, $user, $product): void {
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
            "Mahsulot: {$data['name']} (ID: $productId). Sklad: $oldStock -> $newStock");
    });

    Http::json(Shape::product(Db::one('SELECT * FROM products WHERE id = ?', [$productId])));
});

// =======================================================================
// DELETE /inventory/products/{product_id}
// =======================================================================
Router::delete('/products/{product_id}', function (array $p): never {
    $user = Auth::require(['admin', 'manager'], 'Only admins and managers can delete products');
    $productId = Router::id($p, 'product_id');

    $product = Db::one('SELECT * FROM products WHERE id = ?', [$productId]);
    if ($product === null) {
        fail(404, 'Mahsulot topilmadi');
    }

    // Tarixga bog'langan mahsulotni O'CHIRIB BO'LMAYDI.
    //
    // Ilgari tekshiruv yo'q edi. Sotuv satrlari "yetim" bo'lib qolardi,
    // keyin baza o'sha id ni yangi mahsulotga qayta berib yuborardi va eski
    // cheklar boshqa tovarga ishora qila boshlardi. Bundan tashqari
    // hisobotdagi tannarx JOIN orqali olingani uchun o'chirilgan
    // mahsulotning tannarxi yo'qolib, sof foyda sun'iy ravishda oshardi.
    $sold = (int)Db::val('SELECT COUNT(*) FROM sale_items WHERE product_id = ?', [$productId], 0);
    if ($sold > 0) {
        fail(409, "Bu mahsulot $sold ta chekda ishlatilgan — o'chirib bo'lmaydi. "
            . 'Sotuvdan olib qo\'yish uchun qoldiqni 0 qiling.');
    }
    $supplied = (int)Db::val('SELECT COUNT(*) FROM supplies WHERE product_id = ?', [$productId], 0);
    if ($supplied > 0) {
        fail(409, "Bu mahsulotda $supplied ta kirim tarixi bor — o'chirib bo'lmaydi.");
    }

    Db::tx(function () use ($productId, $user, $product): void {
        // Qoldiq harakatlari tarix emas, mahsulotning o'ziga tegishli —
        // ular ketishi mumkin.
        Db::run('DELETE FROM stock_moves WHERE product_id = ?', [$productId]);
        Db::delete('products', $productId);
        Audit::log((int)$user['id'], 'DELETE_PRODUCT',
            "Mahsulot o'chirildi: {$product['name']} (ID: $productId)");
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

    Http::json(Shape::product(Db::one('SELECT * FROM products WHERE id = ?', [$productId])));
});
