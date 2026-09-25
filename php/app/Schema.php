<?php
/**
 * Baza sxemasi: jadvallar, indekslar va bir martalik migratsiyalar.
 *
 * Python versiyasidagi `init_db()` + `ensure_*` funksiyalarining o'rnida.
 * Ikki xil o'zgarish bor va farqi muhim:
 *
 *   * TUZILISH o'zgarishi (jadval/ustun/indeks qo'shish) idempotent —
 *     har safar ishlatish xavfsiz, "IF NOT EXISTS" bilan;
 *   * MA'LUMOT migratsiyasi qatorlarni qayta yozadi va ikki marta ishlasa
 *     ma'lumotni buzadi. Shuning uchun `schema_migrations` jadvalida
 *     belgilanadi va bir marta bajariladi.
 *
 * Ustun nomlari Python modellari bilan BIR XIL — ya'ni eski baza to'g'ridan-
 * to'g'ri ko'chiriladi va API javoblari ham o'zgarmaydi.
 */

declare(strict_types=1);

final class Schema
{
    /** Jadvallar TASHQI KALIT tartibida: avval murojaat qilinadigani. */
    public static function tables(): array
    {
        return [
            'employees' => [
                'id'                 => 'pk',
                'username'           => 'str',
                'hashed_password'    => 'str',
                'role'               => 'str',
                'permissions'        => 'str',
                'is_active'          => 'bool default 1',
                'full_name'          => 'str',
                'phone'              => 'str',
                'address'            => 'str',
                'passport'           => 'str',
                'notes'              => 'text',
                'telegram_id'        => 'bigint',
                'session_token'      => 'str',
                'session_expires_at' => 'dt',
            ],
            'categories' => [
                'id'   => 'pk',
                'name' => 'str',
            ],
            'expense_categories' => [
                'id'   => 'pk',
                'name' => 'str',
            ],
            'products' => [
                'id'          => 'pk',
                'name'        => 'str',
                'barcode'     => 'str',
                'buy_price'   => 'money default 0',
                'sell_price'  => 'money default 0',
                'stock'       => 'money default 0',
                'is_infinite' => 'bool default 0',
                'unit'        => "str default 'dona'",
                'category_id' => 'fk:categories',
                'is_favorite' => 'bool default 0',
            ],
            // Bitta mahsulotning QO'SHIMCHA shtrix-kodlari. Masalan "Agusha"
            // ning har xil ta'mlari har xil kod bilan keladi, lekin do'kon
            // ularni bitta mahsulot, bitta narx va bitta qoldiq sifatida
            // yuritadi. Asosiy kod products.barcode da qoladi.
            'product_barcodes' => [
                'id'         => 'pk',
                'product_id' => 'fk:products',
                'barcode'    => 'str',
            ],
            'users' => [
                'id'            => 'pk',
                'telegram_id'   => 'bigint',
                'full_name'     => 'str',
                'phone'         => 'str',
                'bonus_balance' => 'money default 0',
            ],
            'clients' => [
                'id'            => 'pk',
                'name'          => 'str',
                'phone'         => 'str',
                'telegram_id'   => 'bigint',
                'balance'       => 'money default 0',
                'bonus_balance' => 'money default 0',
                'debt_due_date' => 'dt',
                'created_at'    => 'dt',
            ],
            'suppliers' => [
                'id'         => 'pk',
                'name'       => 'str',
                'phone'      => 'str',
                'address'    => 'str',
                'balance'    => 'money default 0',
                'created_at' => 'dt',
            ],
            'shifts' => [
                'id'              => 'pk',
                'cashier_id'      => 'fk:employees',
                'opening_balance' => 'money default 0',
                'closing_balance' => 'money',
                'opened_at'       => 'dt',
                'closed_at'       => 'dt',
                'status'          => "str default 'open'",
                'note'            => 'text',
                // Yopilishda MUZLATILGAN hisob-kitob. Ilgari smena hisobi
                // har so'rovda jonli sotuvlardan qayta hisoblanardi: yopilgandan
                // keyingi vozvrat o'tgan smenaning kamomadini o'zgartirib
                // yuborardi va kassir imzolagan raqam hisobotdagidan farq qilardi.
                'total_cash'      => 'money',
                'total_card'      => 'money',
                'total_transfer'  => 'money',
                'total_debt'      => 'money',
                'total_expenses'  => 'money',
                'total_refunds'   => 'money',
                'expected_cash'   => 'money',
                'cash_difference' => 'money',
                'closed_by'       => 'fk:employees',
            ],
            'sales' => [
                'id'              => 'pk',
                'created_at'      => 'dt',
                'total_amount'    => 'money default 0',
                'payment_method'  => 'str',
                'cashier_id'      => 'fk:employees',
                'client_id'       => 'fk:clients',
                'status'          => "str default 'completed'",
                'cash_amount'     => 'money default 0',
                'card_amount'     => 'money default 0',
                'transfer_amount' => 'money default 0',
                'debt_amount'     => 'money default 0',
                'bonus_earned'    => 'money default 0',
                'bonus_spent'     => 'money default 0',
                // Takroriy chekni oldini olish. Kassir "To'lash" ni ikki marta
                // bossa yoki so'rov timeout bo'lib qayta yuborilsa, ilgari
                // IKKITA chek yozilardi: ombordan tovar ikki marta yechilardi.
                'idempotency_key' => 'str',
                // Vozvrat QAYSI smenada qilingani — pul jismonan o'sha
                // smenaning kassasidan chiqadi.
                'refunded_at'     => 'dt',
                'refund_shift_id' => 'fk:shifts',
            ],
            'sale_items' => [
                'id'         => 'pk',
                'sale_id'    => 'fk:sales',
                'product_id' => 'fk:products',
                'quantity'   => 'money default 0',
                'price'      => 'money default 0',
                // Sotuv paytidagi tannarx. Keyin kirim narxi o'zgarsa,
                // o'tmishdagi foyda surilib ketmasligi uchun.
                'buy_price'  => 'money',
            ],
            'expenses' => [
                'id'             => 'pk',
                'reason'         => 'str',
                'category'       => "str default 'Boshqa'",
                'amount'         => 'money default 0',
                'created_at'     => 'dt',
                'created_by'     => 'fk:employees',
                // Faqat NAQD xarajat smena kassasidan ayiriladi.
                'payment_method' => "str default 'cash'",
                'shift_id'       => 'fk:shifts',
            ],
            'audit_logs' => [
                'id'         => 'pk',
                'user_id'    => 'fk:employees',
                'action'     => 'str',
                'details'    => 'text',
                'created_at' => 'dt',
            ],
            'supplies' => [
                'id'         => 'pk',
                'product_id' => 'fk:products',
                'quantity'   => 'money default 0',
                'buy_price'  => 'money default 0',
                'created_at' => 'dt',
            ],
            'stock_moves' => [
                'id'         => 'pk',
                'product_id' => 'fk:products',
                'quantity'   => 'money default 0',
                'type'       => 'str',
                'reason'     => 'text',
                'created_by' => 'fk:employees',
                'created_at' => 'dt',
            ],
            'payments' => [
                'id'             => 'pk',
                'client_id'      => 'fk:clients',
                'amount'         => 'money default 0',
                'payment_method' => "str default 'cash'",
                'note'           => 'text',
                'created_at'     => 'dt',
                'created_by'     => 'fk:employees',
                'shift_id'       => 'fk:shifts',
            ],
            'attendance' => [
                'id'          => 'pk',
                'employee_id' => 'fk:employees',
                'status'      => 'str',
                'created_at'  => 'dt',
                'note'        => 'text',
            ],
            'tasks' => [
                'id'          => 'pk',
                'title'       => 'str',
                'description' => 'text',
                'status'      => "str default 'pending'",
                'assigned_to' => 'fk:employees',
                'created_by'  => 'fk:employees',
                'created_at'  => 'dt',
                'due_date'    => 'dt',
            ],
            'supply_receipts' => [
                'id'            => 'pk',
                'supplier_id'   => 'fk:suppliers',
                'total_amount'  => 'money default 0',
                'invoice_image' => 'str',
                'date'          => 'dt',
                'note'          => 'text',
            ],
            'supplier_payments' => [
                'id'             => 'pk',
                'supplier_id'    => 'fk:suppliers',
                'amount'         => 'money default 0',
                'payment_method' => "str default 'cash'",
                'date'           => 'dt',
                'note'           => 'text',
            ],
            'store_settings' => [
                'id'                  => 'pk',
                'name'                => "str default 'Mening Do''konim'",
                'address'             => 'str',
                'phone'               => 'str',
                'header_text'         => 'text',
                'footer_text'         => 'text',
                'logo_url'            => 'str',
                'low_stock_threshold' => 'int default 5',
                'bonus_percentage'    => 'money default 1',
                'debt_reminder_days'  => 'int default 3',
            ],
            'schema_migrations' => [
                'id'         => 'pk',
                'name'       => 'str',
                'applied_at' => 'dt',
            ],
        ];
    }

    /** Noyob (unique) indekslar. */
    public static function uniques(): array
    {
        return [
            'uq_employees_username'   => ['employees', ['username']],
            'uq_employees_telegram'   => ['employees', ['telegram_id']],
            'uq_categories_name'      => ['categories', ['name']],
            'uq_expcat_name'          => ['expense_categories', ['name']],
            'uq_products_barcode'     => ['products', ['barcode']],
            'uq_product_barcodes'     => ['product_barcodes', ['barcode']],
            'uq_users_telegram'       => ['users', ['telegram_id']],
            'uq_clients_telegram'     => ['clients', ['telegram_id']],
            // Takroriy chekni bazaning O'ZI to'xtatadi: ikki parallel so'rov
            // bir xil kalit bilan kelsa, ikkinchisi IntegrityError oladi va
            // kod uni birinchi chekni qaytarish bilan hal qiladi.
            'uq_sales_idem'           => ['sales', ['idempotency_key']],
            'uq_migrations_name'      => ['schema_migrations', ['name']],
        ];
    }

    /**
     * Oddiy indekslar — haqiqatda filtrlanadigan ustunlarga.
     *
     * Eslatma: modelga index=True qo'shish mavjud jadvalda indeks
     * YARATMAYDI. Yangi indeks kerak bo'lsa aynan shu ro'yxatga qo'shiladi.
     */
    /**
     * Indekslar — HAQIQATDA filtrlanadigan ustunlar bo'yicha.
     *
     * Ro'yxat qasddan qisqa. Har bir indeks o'qishni tezlashtiradi, lekin
     * YOZISHNI sekinlashtiradi: bitta INSERT barcha indekslarni yangilaydi.
     * Kassada yozish ham tez-tez bo'ladi, shuning uchun bu yerda faqat
     * o'zini oqlaydiganlari.
     *
     * Ko'p ustunli indeksda TARTIB muhim: (cashier_id, status, created_at)
     * "cashier_id bo'yicha", "cashier_id + status bo'yicha" va uchalasi
     * bo'yicha so'rovlarga xizmat qiladi — ya'ni alohida (cashier_id)
     * indeksi ortiqcha bo'lib qoladi.
     *
     * Eslatma: modelga index=True qo'shish mavjud jadvalda indeks
     * YARATMAYDI. Yangi indeks kerak bo'lsa aynan shu ro'yxatga qo'shiladi.
     */
    public static function indexes(): array
    {
        return [
            // --- savdo: eng tez-tez yoziladigan va o'qiladigan jadval ---
            // Sana bo'yicha ro'yxat (holatdan qat'i nazar).
            'ix_sales_created'       => ['sales', ['created_at']],
            // Smena hisobi va kassir ro'yxati: uch shart ham bitta indeksda.
            'ix_sales_cashier_win'   => ['sales', ['cashier_id', 'status', 'created_at']],
            // Moliya va grafiklar: tugallangan savdolar sana oralig'ida.
            'ix_sales_status_date'   => ['sales', ['status', 'created_at']],
            'ix_sales_client'        => ['sales', ['client_id']],
            // Smenada berilgan vozvratlar.
            'ix_sales_refund_shift'  => ['sales', ['refund_shift_id']],

            'ix_sale_items_sale'     => ['sale_items', ['sale_id']],
            'ix_sale_items_product'  => ['sale_items', ['product_id']],

            'ix_products_name'       => ['products', ['name']],
            'ix_products_category'   => ['products', ['category_id']],
            'ix_product_barcodes_p'  => ['product_barcodes', ['product_id']],

            'ix_clients_name'        => ['clients', ['name']],
            // Qarzdorlar ro'yxati: WHERE balance < 0.
            'ix_clients_balance'     => ['clients', ['balance']],

            // Ochiq smenani topish — har bir savdoda bajariladi.
            'ix_shifts_cashier_st'   => ['shifts', ['cashier_id', 'status']],
            'ix_shifts_opened'       => ['shifts', ['opened_at']],

            // Smena kassasi: faqat NAQD xarajat va to'lovlar.
            'ix_expenses_shift_pm'   => ['expenses', ['shift_id', 'payment_method']],
            'ix_expenses_created'    => ['expenses', ['created_at']],
            'ix_expenses_by'         => ['expenses', ['created_by']],

            'ix_payments_shift_pm'   => ['payments', ['shift_id', 'payment_method']],
            'ix_payments_client'     => ['payments', ['client_id']],
            'ix_payments_created'    => ['payments', ['created_at']],

            'ix_audit_created'       => ['audit_logs', ['created_at']],
            'ix_audit_user'          => ['audit_logs', ['user_id']],
            'ix_audit_action_date'   => ['audit_logs', ['action', 'created_at']],

            'ix_stock_moves_prod'    => ['stock_moves', ['product_id', 'created_at']],
            'ix_stock_moves_created' => ['stock_moves', ['created_at']],

            // Kirimni bekor qilishda "oldingi kirim" izlanadi.
            'ix_supplies_product'    => ['supplies', ['product_id', 'created_at']],
            'ix_supplies_created'    => ['supplies', ['created_at']],

            'ix_attendance_emp'      => ['attendance', ['employee_id', 'created_at']],
            'ix_receipts_supplier'   => ['supply_receipts', ['supplier_id']],
            'ix_suppay_supplier'     => ['supplier_payments', ['supplier_id']],
            'ix_tasks_assigned'      => ['tasks', ['assigned_to']],
        ];
    }

    // --- DDL yasash -----------------------------------------------------

    /** Mantiqiy turni haqiqiy SQL turiga o'giradi. */
    private static function sqlType(string $spec, string $driver): string
    {
        $default = '';
        $defaultRaw = null;
        if (preg_match('/\s+default\s+(.+)$/i', $spec, $m)) {
            $defaultRaw = trim($m[1]);
            $default = ' DEFAULT ' . $defaultRaw;
            $spec = trim(preg_replace('/\s+default\s+.+$/i', '', $spec) ?? $spec);
        }

        // PostgreSQL da mantiqiy ustun HAQIQIY boolean bo'ladi (Python
        // versiyasi ham shunday yaratgan). Unga sukut qiymat sifatida 1/0
        // yozib bo'lmaydi — TRUE/FALSE kerak.
        if ($spec === 'bool' && $driver === 'pgsql' && $defaultRaw !== null) {
            $default = ' DEFAULT ' . ($defaultRaw === '1' ? 'TRUE' : 'FALSE');
        }

        if (str_starts_with($spec, 'fk:')) {
            $spec = 'int';
        }

        $type = match ($spec) {
            'pk' => match ($driver) {
                'mysql'  => 'INT AUTO_INCREMENT PRIMARY KEY',
                'pgsql'  => 'SERIAL PRIMARY KEY',
                default  => 'INTEGER PRIMARY KEY AUTOINCREMENT',
            },
            'int'    => 'INTEGER',
            'bigint' => 'BIGINT',
            // Pul DOUBLE da: UZS amalda butun son, DOUBLE esa 15-16 raqamni
            // aniq saqlaydi — triliongacha xato yo'q. Python tomonida ham
            // Float (REAL/double precision) edi, ya'ni ma'lumot bir xil o'qiladi.
            'money'  => $driver === 'pgsql' ? 'DOUBLE PRECISION' : 'DOUBLE',
            // PostgreSQL: haqiqiy BOOLEAN. SMALLINT bo'lsa PHP dan
            // kelgan bool qiymat ('t'/'f') ustunga tushmay, xato berardi —
            // va eski (Python yaratgan) baza bilan ham mos kelmasdi.
            'bool'   => match ($driver) {
                'mysql' => 'TINYINT(1)',
                'pgsql' => 'BOOLEAN',
                default => 'INTEGER',
            },
            'str'    => $driver === 'pgsql' ? 'VARCHAR(255)' : 'VARCHAR(255)',
            'text'   => 'TEXT',
            // Mikrosekundlar SAQLANADI: bir soniya ichidagi ikki savdoning
            // tartibi yo'qolmasin.
            'dt'     => match ($driver) {
                'mysql' => 'DATETIME(6)',
                'pgsql' => 'TIMESTAMP',
                default => 'TEXT',
            },
            default  => 'VARCHAR(255)',
        };

        return $type . ($spec === 'pk' ? '' : $default);
    }

    public static function createAll(bool $verbose = true): void
    {
        $driver = Db::driver();
        $pdo = Db::pdo();

        foreach (self::tables() as $table => $columns) {
            $parts = [];
            $fks = [];
            foreach ($columns as $col => $spec) {
                $parts[] = Db::quoteId($col) . ' ' . self::sqlType($spec, $driver);
                if (str_starts_with($spec, 'fk:')) {
                    $target = substr($spec, 3);
                    // ON DELETE SET NULL: xodim o'chirilsa savdo tarixi
                    // qolsin. To'g'ridan-to'g'ri o'chirish baribir kod
                    // darajasida taqiqlangan (409 bilan).
                    $fks[] = 'FOREIGN KEY (' . Db::quoteId($col) . ') REFERENCES '
                        . Db::quoteId($target) . '(id) ON DELETE SET NULL';
                }
            }
            $body = implode(",\n  ", array_merge($parts, $fks));
            $suffix = $driver === 'mysql' ? ' ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci' : '';
            $sql = 'CREATE TABLE IF NOT EXISTS ' . Db::quoteId($table) . " (\n  $body\n)$suffix";

            $pdo->exec($sql);
            if ($verbose) {
                echo "  jadval: $table\n";
            }
        }

        self::ensureColumns($verbose);
        self::ensureIndexes($verbose);
    }

    /**
     * Yetishmayotgan ustunlarni qo'shadi.
     *
     * Jadval allaqachon mavjud bo'lsa CREATE TABLE IF NOT EXISTS hech narsa
     * qilmaydi — yangi ustun o'z-o'zidan paydo bo'lmaydi. Shuning uchun
     * har bir ustun alohida tekshiriladi.
     */
    public static function ensureColumns(bool $verbose = true): void
    {
        $driver = Db::driver();
        foreach (self::tables() as $table => $columns) {
            $existing = self::columnsOf($table);
            if ($existing === []) {
                continue;
            }
            foreach ($columns as $col => $spec) {
                if (in_array($col, $existing, true) || $spec === 'pk') {
                    continue;
                }
                $sql = 'ALTER TABLE ' . Db::quoteId($table) . ' ADD COLUMN '
                    . Db::quoteId($col) . ' ' . self::sqlType($spec, $driver);
                try {
                    Db::pdo()->exec($sql);
                    if ($verbose) {
                        echo "  ustun qo'shildi: $table.$col\n";
                    }
                } catch (Throwable $e) {
                    echo "  OGOHLANTIRISH: $table.$col qo'shilmadi — " . $e->getMessage() . "\n";
                }
            }
        }
    }

    /** Список столбцов таблицы. Пусто, если таблицы нет. */
    public static function columnsOf(string $table): array
    {
        try {
            return match (Db::driver()) {
                'mysql' => array_column(
                    Db::all('SELECT COLUMN_NAME AS c FROM information_schema.COLUMNS
                             WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = ?', [$table]),
                    'c'
                ),
                'pgsql' => array_column(
                    Db::all('SELECT column_name AS c FROM information_schema.columns
                             WHERE table_name = ?', [$table]),
                    'c'
                ),
                default => array_column(Db::all("PRAGMA table_info(" . Db::quoteId($table) . ")"), 'name'),
            };
        } catch (Throwable) {
            return [];
        }
    }

    public static function ensureIndexes(bool $verbose = true): void
    {
        $driver = Db::driver();

        $make = function (string $name, string $table, array $cols, bool $unique) use ($driver, $verbose): void {
            $u = $unique ? 'UNIQUE ' : '';
            $colSql = implode(', ', array_map(fn($c) => Db::quoteId($c), $cols));
            try {
                if ($driver === 'mysql') {
                    // MySQL "CREATE INDEX IF NOT EXISTS" ni bilmaydi —
                    // avval borligini tekshiramiz.
                    $exists = (int)Db::val(
                        'SELECT COUNT(*) FROM information_schema.STATISTICS
                         WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = ? AND INDEX_NAME = ?',
                        [$table, $name]
                    );
                    if ($exists > 0) {
                        return;
                    }
                    Db::pdo()->exec("CREATE {$u}INDEX " . Db::quoteId($name)
                        . ' ON ' . Db::quoteId($table) . " ($colSql)");
                } else {
                    Db::pdo()->exec("CREATE {$u}INDEX IF NOT EXISTS " . Db::quoteId($name)
                        . ' ON ' . Db::quoteId($table) . " ($colSql)");
                }
                if ($verbose) {
                    echo '  indeks: ' . $name . ($unique ? ' (noyob)' : '') . "\n";
                }
            } catch (Throwable $e) {
                // Noyob indeks mavjud ma'lumotda takror topsa yaratilmaydi —
                // bu ogohlantirish, to'xtatuvchi xato emas.
                echo "  OGOHLANTIRISH: $name yaratilmadi — " . $e->getMessage() . "\n";
            }
        };

        foreach (self::uniques() as $name => [$table, $cols]) {
            $make($name, $table, $cols, true);
        }
        foreach (self::indexes() as $name => [$table, $cols]) {
            $make($name, $table, $cols, false);
        }

        // Eski, endi ortiqcha bo'lib qolgan indekslarni olib tashlaymiz.
        // Ular ko'p ustunli indekslarning PREFIKSI bo'lib qoldi, ya'ni
        // hech narsa tezlashtirmaydi, lekin har INSERT da yangilanadi.
        foreach (self::obsoleteIndexes() as $name) {
            try {
                Db::pdo()->exec($driver === 'mysql'
                    ? 'DROP INDEX ' . Db::quoteId($name) . ' ON ' . Db::quoteId(self::obsoleteTable($name))
                    : 'DROP INDEX IF EXISTS ' . Db::quoteId($name));
                if ($verbose) {
                    echo "  ortiqcha indeks olib tashlandi: $name
";
                }
            } catch (Throwable) {
                // Indeks yo'q bo'lsa — hammasi joyida.
            }
        }
    }

    /** Ko'p ustunli indekslar bilan almashtirilgan eski indekslar. */
    private static function obsoleteIndexes(): array
    {
        return [
            'ix_sales_cashier', 'ix_sales_status', 'ix_sales_refunded_at',
            'ix_shifts_cashier', 'ix_shifts_status',
            'ix_expenses_shift', 'ix_payments_shift',
            'ix_audit_action', 'ix_stock_moves_product',
            'ix_attendance_employee', 'ix_attendance_created',
        ];
    }

    private static function obsoleteTable(string $index): string
    {
        return match (true) {
            str_starts_with($index, 'ix_sales_')       => 'sales',
            str_starts_with($index, 'ix_shifts_')      => 'shifts',
            str_starts_with($index, 'ix_expenses_')    => 'expenses',
            str_starts_with($index, 'ix_payments_')    => 'payments',
            str_starts_with($index, 'ix_audit_')       => 'audit_logs',
            str_starts_with($index, 'ix_stock_moves_') => 'stock_moves',
            str_starts_with($index, 'ix_attendance_')  => 'attendance',
            default                                    => 'sales',
        };
    }

    // --- Bir martalik migratsiyalar -------------------------------------

    public static function migrationApplied(string $name): bool
    {
        try {
            return (int)Db::val('SELECT COUNT(*) FROM schema_migrations WHERE name = ?', [$name]) > 0;
        } catch (Throwable) {
            return false;
        }
    }

    public static function markMigration(string $name): void
    {
        Db::insert('schema_migrations', ['name' => $name, 'applied_at' => Tz::now()]);
    }
}
