<?php
/**
 * Zahira nusxa — sof PHP da, tashqi dasturlarsiz.
 *
 * NIMA UCHUN mysqldump / pg_dump EMAS
 * -----------------------------------
 * Shared hosting'da shell_exec ko'pincha o'chirilgan va mysqldump yo'lini
 * hech kim kafolatlamaydi. Bu yerda nusxa PDO orqali olinadi: baza qanday
 * bo'lsa, shunday o'qiladi va SQL fayl bo'lib yoziladi. Ya'ni nusxa har
 * qanday hostingda ishlaydi.
 *
 * MUHIM: nusxani BOSHQA joyga ham ko'chiring. Bazasi bilan bitta serverda
 * yotgan yagona nusxa — bu nusxa emas.
 */

declare(strict_types=1);

final class Backup
{
    public static function dir(): string
    {
        $dir = env('BACKUP_DIR') ?: ROOT_DIR . '/backups';
        if (!is_dir($dir)) {
            @mkdir($dir, 0700, true);
        }
        return $dir;
    }

    /**
     * Bazaning to'liq nusxasini oladi.
     *
     * @return array{file: string, tables: int, rows: int, bytes: int}
     */
    public static function run(): array
    {
        $dir = self::dir();
        if (!is_dir($dir) || !is_writable($dir)) {
            throw new RuntimeException("Zahira papkasi yozib bo'lmaydi: $dir");
        }

        $stamp = (new DateTimeImmutable('now', Tz::shopTz()))->format('Ymd-His');
        $gzip = function_exists('gzopen');
        $path = $dir . "/backup_$stamp.sql" . ($gzip ? '.gz' : '');

        $fh = $gzip ? gzopen($path, 'wb9') : fopen($path, 'wb');
        if ($fh === false) {
            throw new RuntimeException("Zahira faylini yaratib bo'lmadi: $path");
        }

        $write = $gzip
            ? fn(string $s) => gzwrite($fh, $s)
            : fn(string $s) => fwrite($fh, $s);

        $driver = Db::driver();
        $pdo = Db::pdo();
        $tables = 0;
        $rows = 0;

        try {
            $write("-- Kassa zahira nusxasi\n");
            $write('-- Sana: ' . (new DateTimeImmutable('now', Tz::shopTz()))->format('d.m.Y H:i:s')
                . ' (' . SHOP_TIMEZONE . ")\n");
            $write("-- Drayver: $driver\n");
            $write("-- Tiklash: ushbu faylni bazaga import qiling (phpMyAdmin yoki mysql < fayl)\n\n");

            if ($driver === 'mysql') {
                $write("SET NAMES utf8mb4;\nSET FOREIGN_KEY_CHECKS=0;\n\n");
            } elseif ($driver === 'sqlite') {
                $write("PRAGMA foreign_keys=OFF;\nBEGIN TRANSACTION;\n\n");
            }

            foreach (array_keys(Schema::tables()) as $table) {
                $quoted = Db::quoteId($table);

                // Jadval mavjudmi? (eski bazada yangi jadval bo'lmasligi mumkin)
                try {
                    $count = (int)Db::val("SELECT COUNT(*) FROM $quoted", [], 0);
                } catch (Throwable) {
                    continue;
                }
                $tables++;

                $write("-- ---------- $table ($count qator) ----------\n");
                if ($count === 0) {
                    $write("\n");
                    continue;
                }

                // Katta jadvalni bo'lib-bo'lib o'qiymiz: butun savdo tarixini
                // bir vaqtda xotiraga solsak, shared hosting chegarasidan oshadi.
                // НЕ У КАЖДОЙ таблицы есть столбец id.
                //
                // В базе, созданной Python-версией, schema_migrations
                // ключуется по name. Безусловный "ORDER BY id" ронял
                // резервное копирование ЦЕЛИКОМ из-за одной этой таблицы —
                // то есть копий не было вовсе, а операция выглядела как
                // разовый сбой.
                $hasId = in_array('id', Schema::columnsOf($table), true);
                $stmt = $pdo->prepare("SELECT * FROM $quoted" . ($hasId ? ' ORDER BY id' : ''));
                $stmt->execute();

                $batch = [];
                $columns = null;

                while (($row = $stmt->fetch(PDO::FETCH_ASSOC)) !== false) {
                    if ($columns === null) {
                        $columns = array_map(fn($c) => Db::quoteId($c), array_keys($row));
                    }
                    $values = [];
                    foreach ($row as $v) {
                        $values[] = $v === null ? 'NULL' : $pdo->quote((string)$v);
                    }
                    $batch[] = '(' . implode(',', $values) . ')';
                    $rows++;

                    if (count($batch) >= 200) {
                        $write("INSERT INTO $quoted (" . implode(',', $columns) . ") VALUES\n"
                            . implode(",\n", $batch) . ";\n");
                        $batch = [];
                    }
                }
                if ($batch !== []) {
                    $write("INSERT INTO $quoted (" . implode(',', $columns) . ") VALUES\n"
                        . implode(",\n", $batch) . ";\n");
                }
                $write("\n");
            }

            if ($driver === 'mysql') {
                $write("SET FOREIGN_KEY_CHECKS=1;\n");
            } elseif ($driver === 'sqlite') {
                $write("COMMIT;\n");
            }
        } finally {
            $gzip ? gzclose($fh) : fclose($fh);
        }

        @chmod($path, 0600);
        self::cleanOld();

        return [
            'file'   => basename($path),
            'tables' => $tables,
            'rows'   => $rows,
            'bytes'  => (int)@filesize($path),
        ];
    }

    /**
     * Nakladnoy fotolarini alohida arxivlaydi.
     *
     * Ular BAZADA YO'Q. Shusiz tiklashdan keyin firma qarzi qoladi, uni
     * tasdiqlaydigan hujjat esa yo'qoladi: SupplyReceipt satri mavjud
     * bo'lmagan faylga ishora qilib turadi.
     */
    public static function archiveUploads(): ?string
    {
        if (!is_dir(UPLOAD_DIR) || !class_exists('ZipArchive')) {
            return null;
        }

        $files = [];
        $it = new RecursiveIteratorIterator(
            new RecursiveDirectoryIterator(UPLOAD_DIR, FilesystemIterator::SKIP_DOTS)
        );
        foreach ($it as $f) {
            if ($f->isFile()) {
                $files[] = $f->getPathname();
            }
        }
        if ($files === []) {
            return null;
        }

        $stamp = (new DateTimeImmutable('now', Tz::shopTz()))->format('Ymd-His');
        $path = self::dir() . "/uploads_$stamp.zip";

        $zip = new ZipArchive();
        if ($zip->open($path, ZipArchive::CREATE | ZipArchive::OVERWRITE) !== true) {
            return null;
        }
        $base = rtrim(UPLOAD_DIR, '/\\');
        foreach ($files as $f) {
            $zip->addFile($f, ltrim(str_replace($base, '', $f), '/\\'));
        }
        $zip->close();
        @chmod($path, 0600);

        return basename($path);
    }

    /**
     * Baza statistikasini yangilaydi.
     *
     * Baza qaysi indeksni ishlatishni STATISTIKAGA qarab tanlaydi. Savdo
     * jadvali o'sib borgani sari eski statistika haqiqatdan uzoqlashadi va
     * rejalashtiruvchi noto'g'ri indeksni tanlab qo'yishi mumkin — o'shanda
     * hisobot sekinlashadi, garchi indekslar joyida bo'lsa ham.
     *
     * Kuniga ikki marta yangilash yetarli va arzon (VACUUM emas — u butun
     * faylni qayta yozadi va uzoq davom etadi).
     */
    public static function analyze(): int
    {
        $tables = array_keys(Schema::tables());
        try {
            if (Db::isMysql()) {
                $list = implode(', ', array_map(fn($t) => Db::quoteId($t), $tables));
                Db::pdo()->exec("ANALYZE TABLE $list");
            } else {
                // SQLite va PostgreSQL da bitta buyruq butun bazani qamraydi.
                Db::pdo()->exec('ANALYZE');
            }
            return count($tables);
        } catch (Throwable $e) {
            error_log('[kassa] ANALYZE bajarilmadi: ' . $e->getMessage());
            return 0;
        }
    }

    /**
     * Eski nusxalarni tozalaydi.
     *
     * Ikki tur fayl uchun RETENSHN ALOHIDA: baza nusxalari va nakladnoy
     * arxivlari bir-birining fayllarini o'chirmasligi kerak. To'liq tiklash
     * uchun bir SANAdagi IKKALA fayl ham kerak.
     */
    public static function cleanOld(): int
    {
        $keep = max(1, (int)(env('BACKUP_RETENTION') ?? 30));
        $removed = 0;

        foreach ([['backup_*.sql', 'backup_*.sql.gz'], ['uploads_*.zip']] as $patterns) {
            $files = [];
            foreach ($patterns as $pattern) {
                foreach (glob(self::dir() . '/' . $pattern) ?: [] as $f) {
                    $files[$f] = (int)@filemtime($f);
                }
            }
            arsort($files);
            $i = 0;
            foreach (array_keys($files) as $f) {
                if (++$i > $keep) {
                    @unlink($f);
                    $removed++;
                }
            }
        }

        return $removed;
    }
}
