<?php
/**
 * Javob shakllari.
 *
 * Bu fayl — SHARTNOMA. Python'dagi Pydantic sxemalari (schemas.py) qanday
 * JSON qaytargan bo'lsa, bu yerda ham AYNAN shunday qaytadi: bir xil
 * maydonlar, bir xil turlar, bir xil tartib. Shu sabab React tomonida
 * birorta satr o'zgartirilmadi.
 *
 * Ikki narsaga alohida e'tibor:
 *
 *   1. SONLAR son bo'lib chiqishi shart. PDO ba'zi drayverlarda DOUBLE ni
 *      satr qilib qaytaradi ("1000.00"), JS esa uni qo'shganda "10001000"
 *      hosil qiladi. Shuning uchun har bir pul maydoni (float) ga o'giriladi.
 *
 *   2. VAQT mintaqa belgisiSIZ ISO 8601 bo'lishi shart
 *      ("2026-09-22T14:30:00"). Frontend'dagi parseServerDate() aynan shuni
 *      kutadi: mintaqa yo'qligini ko'rib, o'zi UTC deb o'qiydi.
 */

declare(strict_types=1);

final class Shape
{
    public static function employee(?array $r): ?array
    {
        if ($r === null) {
            return null;
        }
        return [
            'username'    => $r['username'],
            'role'        => $r['role'],
            'permissions' => $r['permissions'] ?? 'pos',
            'full_name'   => $r['full_name'] ?? null,
            'phone'       => $r['phone'] ?? null,
            'address'     => $r['address'] ?? null,
            'passport'    => $r['passport'] ?? null,
            'notes'       => $r['notes'] ?? null,
            'is_active'   => Db::b($r['is_active'] ?? 1),
            'id'          => Db::i($r['id']),
        ];
    }

    public static function product(?array $r): ?array
    {
        if ($r === null || !isset($r['id'])) {
            return null;
        }
        $out = [
            'name'        => $r['name'],
            'barcode'     => $r['barcode'] ?? null,
            'buy_price'   => Db::f($r['buy_price'] ?? 0),
            'sell_price'  => Db::f($r['sell_price'] ?? 0),
            'stock'       => Db::f($r['stock'] ?? 0),
            'is_infinite' => Db::b($r['is_infinite'] ?? 0),
            'unit'        => $r['unit'] ?? 'dona',
            'category_id' => isset($r['category_id']) ? Db::i($r['category_id']) : null,
            'is_favorite' => Db::b($r['is_favorite'] ?? 0),
            'id'          => Db::i($r['id']),
        ];
        // Qo'shimcha kodlar faqat ular YUKLANGAN javobda chiqadi. Chek
        // javobidagi mahsulotda bu kalit yo'q — kassa keshni {...eski,
        // ...yangi} bilan birlashtiradi va bo'sh ro'yxat kodlarni o'chirib
        // yuborardi.
        if (array_key_exists('extra_barcodes', $r)) {
            $out['extra_barcodes'] = array_values($r['extra_barcodes']);
        }
        return $out;
    }

    public static function client(?array $r): ?array
    {
        if ($r === null || !isset($r['id'])) {
            return null;
        }
        return [
            'name'          => $r['name'],
            'phone'         => $r['phone'] ?? null,
            'telegram_id'   => isset($r['telegram_id']) ? Db::i($r['telegram_id']) : null,
            'balance'       => Db::f($r['balance'] ?? 0),
            'bonus_balance' => Db::f($r['bonus_balance'] ?? 0),
            'debt_due_date' => Tz::iso($r['debt_due_date'] ?? null),
            'id'            => Db::i($r['id']),
            'created_at'    => Tz::iso($r['created_at'] ?? null),
        ];
    }

    public static function category(array $r): array
    {
        return ['name' => $r['name'], 'id' => Db::i($r['id'])];
    }

    public static function saleItem(array $r, ?array $product = null): array
    {
        return [
            'product_id' => isset($r['product_id']) ? Db::i($r['product_id']) : null,
            'quantity'   => Db::f($r['quantity'] ?? 0),
            'price'      => Db::f($r['price'] ?? 0),
            'id'         => Db::i($r['id']),
            'product'    => self::product($product),
        ];
    }

    /**
     * Chek. $items — allaqachon shakllantirilgan qatorlar.
     */
    public static function sale(array $r, array $items = [], ?array $cashier = null, ?array $client = null): array
    {
        return [
            'id'              => Db::i($r['id']),
            'created_at'      => Tz::iso($r['created_at'] ?? null),
            'total_amount'    => Db::f($r['total_amount'] ?? 0),
            'payment_method'  => $r['payment_method'] ?? 'cash',
            'cashier_id'      => Db::i($r['cashier_id'] ?? 0),
            'cashier'         => self::employee($cashier),
            'client_id'       => isset($r['client_id']) ? Db::i($r['client_id']) : null,
            'client'          => self::client($client),
            'status'          => $r['status'] ?? 'completed',
            'cash_amount'     => Db::f($r['cash_amount'] ?? 0),
            'card_amount'     => Db::f($r['card_amount'] ?? 0),
            'transfer_amount' => Db::f($r['transfer_amount'] ?? 0),
            'debt_amount'     => Db::f($r['debt_amount'] ?? 0),
            'bonus_earned'    => Db::f($r['bonus_earned'] ?? 0),
            'bonus_spent'     => Db::f($r['bonus_spent'] ?? 0),
            'items'           => $items,
        ];
    }

    /**
     * Smena. Hisob-kitob maydonlari CHAQIRUVCHI tomonidan beriladi —
     * ular compute_shift_totals() dan keladi va bu yerda qayta
     * hisoblanmaydi (hisoblash YAGONA joyda bo'lishi shart).
     */
    public static function shift(array $r, array $totals = [], ?array $cashier = null): array
    {
        return [
            'id'              => Db::i($r['id']),
            'cashier_id'      => Db::i($r['cashier_id'] ?? 0),
            'cashier'         => self::employee($cashier),
            'opening_balance' => Db::f($r['opening_balance'] ?? 0),
            'closing_balance' => Db::fn($r['closing_balance'] ?? null),
            'opened_at'       => Tz::iso($r['opened_at'] ?? null),
            'closed_at'       => Tz::iso($r['closed_at'] ?? null),
            'status'          => $r['status'] ?? 'open',
            'note'            => $r['note'] ?? null,
            'total_cash'      => Db::f($totals['total_cash'] ?? 0),
            'total_card'      => Db::f($totals['total_card'] ?? 0),
            'total_transfer'  => Db::f($totals['total_transfer'] ?? 0),
            'total_debt'      => Db::f($totals['total_debt'] ?? 0),
            'total_expenses'  => Db::f($totals['total_expenses'] ?? 0),
            'total_refunds'   => Db::f($totals['total_refunds'] ?? 0),
            'expected_cash'   => Db::f($totals['expected_cash'] ?? 0),
            'cash_difference' => Db::fn($totals['cash_difference'] ?? null),
            'closed_by'       => isset($r['closed_by']) ? Db::i($r['closed_by']) : null,
        ];
    }

    public static function expense(array $r, ?array $creator = null): array
    {
        return [
            'reason'         => $r['reason'],
            'category'       => $r['category'] ?? 'Boshqa',
            'amount'         => Db::f($r['amount'] ?? 0),
            'payment_method' => $r['payment_method'] ?? 'cash',
            'id'             => Db::i($r['id']),
            'created_at'     => Tz::iso($r['created_at'] ?? null),
            'created_by'     => isset($r['created_by']) ? Db::i($r['created_by']) : null,
            'creator'        => self::employee($creator),
        ];
    }

    public static function stockMove(array $r, ?array $product = null): array
    {
        return [
            'product_id' => isset($r['product_id']) ? Db::i($r['product_id']) : null,
            'quantity'   => Db::f($r['quantity'] ?? 0),
            'type'       => $r['type'] ?? '',
            'reason'     => $r['reason'] ?? null,
            'id'         => Db::i($r['id']),
            'created_at' => Tz::iso($r['created_at'] ?? null),
            'created_by' => isset($r['created_by']) ? Db::i($r['created_by']) : null,
            'product'    => self::product($product),
        ];
    }

    public static function supply(array $r): array
    {
        return [
            'product_id' => Db::i($r['product_id']),
            'quantity'   => Db::f($r['quantity'] ?? 0),
            'buy_price'  => Db::f($r['buy_price'] ?? 0),
            'id'         => Db::i($r['id']),
            'created_at' => Tz::iso($r['created_at'] ?? null),
        ];
    }

    public static function task(array $r): array
    {
        return [
            'title'       => $r['title'],
            'description' => $r['description'] ?? null,
            'status'      => $r['status'] ?? 'pending',
            'assigned_to' => Db::i($r['assigned_to'] ?? 0),
            'due_date'    => Tz::iso($r['due_date'] ?? null),
            'id'          => Db::i($r['id']),
            'created_at'  => Tz::iso($r['created_at'] ?? null),
            'created_by'  => Db::i($r['created_by'] ?? 0),
        ];
    }

    public static function setting(array $r): array
    {
        return [
            'name'                => $r['name'] ?? "Mening Do'konim",
            'address'             => $r['address'] ?? null,
            'phone'               => $r['phone'] ?? null,
            'header_text'         => $r['header_text'] ?? null,
            'footer_text'         => $r['footer_text'] ?? null,
            'logo_url'            => $r['logo_url'] ?? null,
            'low_stock_threshold' => Db::i($r['low_stock_threshold'] ?? 5),
            'bonus_percentage'    => Db::f($r['bonus_percentage'] ?? 1),
            'debt_reminder_days'  => Db::i($r['debt_reminder_days'] ?? 3),
            'id'                  => Db::i($r['id']),
        ];
    }

    public static function payment(array $r): array
    {
        return [
            'id'             => Db::i($r['id']),
            'client_id'      => Db::i($r['client_id'] ?? 0),
            'amount'         => Db::f($r['amount'] ?? 0),
            'payment_method' => $r['payment_method'] ?? 'cash',
            'note'           => $r['note'] ?? null,
            'created_at'     => Tz::iso($r['created_at'] ?? null),
            'created_by'     => isset($r['created_by']) ? Db::i($r['created_by']) : null,
            'shift_id'       => isset($r['shift_id']) ? Db::i($r['shift_id']) : null,
        ];
    }

    public static function supplier(array $r): array
    {
        return [
            'id'         => Db::i($r['id']),
            'name'       => $r['name'],
            'phone'      => $r['phone'] ?? null,
            'address'    => $r['address'] ?? null,
            'balance'    => Db::f($r['balance'] ?? 0),
            'created_at' => Tz::iso($r['created_at'] ?? null),
        ];
    }

    public static function auditLog(array $r, ?string $username = null): array
    {
        return [
            'id'         => Db::i($r['id']),
            'user_id'    => isset($r['user_id']) ? Db::i($r['user_id']) : null,
            'username'   => $username,
            'action'     => $r['action'] ?? '',
            'details'    => $r['details'] ?? null,
            'created_at' => Tz::iso($r['created_at'] ?? null),
        ];
    }

    public static function attendance(array $r, ?array $employee = null): array
    {
        return [
            'id'          => Db::i($r['id']),
            'employee_id' => Db::i($r['employee_id'] ?? 0),
            'employee'    => self::employee($employee),
            'status'      => $r['status'] ?? '',
            'note'        => $r['note'] ?? null,
            'created_at'  => Tz::iso($r['created_at'] ?? null),
        ];
    }

    // --- Ko'p qatorli yordamchilar --------------------------------------

    /**
     * Cheklar ro'yxatini bitta-bittadan emas, PARTIYA bilan yig'adi.
     *
     * Ilgari ORM har chek uchun alohida so'rov yuborardi (N+1). 100 ta chek
     * ro'yxati 300+ so'rovga aylanardi. Bu yerda: cheklar, ularning
     * mahsulotlari, kassirlar va mijozlar — jami 4 ta so'rov, chek soni
     * qancha bo'lishidan qat'i nazar.
     */
    public static function sales(array $rows): array
    {
        if ($rows === []) {
            return [];
        }

        $saleIds = array_map(fn($r) => (int)$r['id'], $rows);
        $marks = Db::marks($saleIds);

        $itemRows = Db::all(
            "SELECT si.*, p.id AS p_id, p.name AS p_name, p.barcode AS p_barcode,
                    p.buy_price AS p_buy_price, p.sell_price AS p_sell_price,
                    p.stock AS p_stock, p.is_infinite AS p_is_infinite,
                    p.unit AS p_unit, p.category_id AS p_category_id,
                    p.is_favorite AS p_is_favorite
             FROM sale_items si
             LEFT JOIN products p ON p.id = si.product_id
             WHERE si.sale_id IN ($marks)
             ORDER BY si.id",
            $saleIds
        );

        $itemsBySale = [];
        foreach ($itemRows as $ir) {
            $product = $ir['p_id'] === null ? null : [
                'id'          => $ir['p_id'],
                'name'        => $ir['p_name'],
                'barcode'     => $ir['p_barcode'],
                'buy_price'   => $ir['p_buy_price'],
                'sell_price'  => $ir['p_sell_price'],
                'stock'       => $ir['p_stock'],
                'is_infinite' => $ir['p_is_infinite'],
                'unit'        => $ir['p_unit'],
                'category_id' => $ir['p_category_id'],
                'is_favorite' => $ir['p_is_favorite'],
            ];
            $itemsBySale[(int)$ir['sale_id']][] = self::saleItem($ir, $product);
        }

        $cashiers = self::lookup('employees', array_filter(array_map(fn($r) => $r['cashier_id'] ?? null, $rows)));
        $clients = self::lookup('clients', array_filter(array_map(fn($r) => $r['client_id'] ?? null, $rows)));

        $out = [];
        foreach ($rows as $r) {
            $out[] = self::sale(
                $r,
                $itemsBySale[(int)$r['id']] ?? [],
                $cashiers[(int)($r['cashier_id'] ?? 0)] ?? null,
                $clients[(int)($r['client_id'] ?? 0)] ?? null
            );
        }
        return $out;
    }

    /** id -> qator ko'rinishidagi lug'at. Bitta so'rov bilan. */
    public static function lookup(string $table, array $ids): array
    {
        $ids = array_values(array_unique(array_map('intval', array_filter($ids, fn($v) => $v !== null && $v !== ''))));
        if ($ids === []) {
            return [];
        }
        $rows = Db::all(
            'SELECT * FROM ' . Db::quoteId($table) . ' WHERE id IN (' . Db::marks($ids) . ')',
            $ids
        );
        $map = [];
        foreach ($rows as $r) {
            $map[(int)$r['id']] = $r;
        }
        return $map;
    }
}
