<?php
/**
 * Eng kichik XLSX yozuvchi — tashqi kutubxonasiz.
 *
 * NIMA UCHUN O'ZIMIZNIKI
 * ----------------------
 * Python versiyasida bu pandas + openpyxl edi: ikkalasi birgalikda ~80 MB
 * va import qilinishi bir necha soniya. Shared hosting'da bu qimmat.
 * PhpSpreadsheet ham xuddi shunday og'ir (~10 MB vendor, har so'rovda
 * o'nlab fayl yuklanadi).
 *
 * XLSX aslida — ichida XML bo'lgan ZIP. Bizga kerak bo'lgani oddiy jadval,
 * shuning uchun formatning eng kichik, lekin TO'LIQ HAQIQIY qismini
 * yozamiz: Excel, LibreOffice va Google Sheets uni muammosiz ochadi.
 *
 * Satrlar "inline" yoziladi (sharedStrings jadvalisiz) — bu faylni biroz
 * kattalashtiradi, lekin xotirada butun lug'atni ushlab turishni talab
 * qilmaydi: hisobot qancha uzun bo'lmasin, xotira sarfi deyarli o'zgarmaydi.
 */

declare(strict_types=1);

final class Xlsx
{
    /**
     * Jadvalni XLSX bayt satriga aylantiradi.
     *
     * @param array $headers Ustun sarlavhalari
     * @param array $rows    Qatorlar; har biri $headers bilan bir xil uzunlikda
     */
    public static function build(array $headers, array $rows, string $sheetName = 'Sheet1'): string
    {
        // Varaq nomi cheklovlari: 31 belgigacha, ba'zi belgilar taqiqlangan.
        $sheetName = mb_substr(str_replace(['[', ']', ':', '*', '?', '/', '\\'], '', $sheetName), 0, 31);
        if ($sheetName === '') {
            $sheetName = 'Sheet1';
        }

        $files = [
            '[Content_Types].xml'       => self::contentTypes(),
            '_rels/.rels'               => self::rootRels(),
            'xl/workbook.xml'           => self::workbook($sheetName),
            'xl/_rels/workbook.xml.rels' => self::workbookRels(),
            'xl/worksheets/sheet1.xml'  => self::sheet($headers, $rows),
        ];

        return self::zip($files);
    }

    /** To'g'ridan-to'g'ri brauzerga yuboradi. */
    public static function download(array $headers, array $rows, string $filename, string $sheetName = 'Sheet1'): never
    {
        $bytes = self::build($headers, $rows, $sheetName);
        header('Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
        header('Content-Disposition: attachment; filename="' . $filename . '"');
        header('Content-Length: ' . strlen($bytes));
        header('Cache-Control: no-store');
        echo $bytes;
        exit;
    }

    // --- XML qismlari ---------------------------------------------------

    private static function contentTypes(): string
    {
        return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            . '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            . '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            . '<Default Extension="xml" ContentType="application/xml"/>'
            . '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            . '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            . '</Types>';
    }

    private static function rootRels(): string
    {
        return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            . '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            . '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            . '</Relationships>';
    }

    private static function workbook(string $sheetName): string
    {
        return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            . '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
            . ' xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            . '<sheets><sheet name="' . self::esc($sheetName) . '" sheetId="1" r:id="rId1"/></sheets>'
            . '</workbook>';
    }

    private static function workbookRels(): string
    {
        return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            . '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            . '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            . '</Relationships>';
    }

    private static function sheet(array $headers, array $rows): string
    {
        $xml = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            . '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            . '<sheetData>';

        $r = 1;
        $xml .= self::row($headers, $r++);
        foreach ($rows as $row) {
            $xml .= self::row(array_values((array)$row), $r++);
        }

        return $xml . '</sheetData></worksheet>';
    }

    private static function row(array $values, int $rowNum): string
    {
        $out = '<row r="' . $rowNum . '">';
        $col = 0;
        foreach ($values as $v) {
            $ref = self::colName($col++) . $rowNum;
            if (is_int($v) || is_float($v)) {
                // Son bo'lib turishi kerak: aks holda Excel'da yig'indi
                // hisoblab bo'lmaydi.
                if (is_float($v) && !is_finite($v)) {
                    $v = 0;
                }
                $out .= '<c r="' . $ref . '"><v>' . $v . '</v></c>';
            } else {
                $text = (string)$v;
                if ($text === '') {
                    continue;
                }
                $out .= '<c r="' . $ref . '" t="inlineStr"><is><t xml:space="preserve">'
                    . self::esc($text) . '</t></is></c>';
            }
        }
        return $out . '</row>';
    }

    /** 0 -> A, 25 -> Z, 26 -> AA */
    private static function colName(int $index): string
    {
        $name = '';
        $i = $index + 1;
        while ($i > 0) {
            $rem = ($i - 1) % 26;
            $name = chr(65 + $rem) . $name;
            $i = intdiv($i - 1, 26);
        }
        return $name;
    }

    private static function esc(string $text): string
    {
        // XML da ruxsat etilmagan boshqaruv belgilarini olib tashlaymiz —
        // ular bo'lsa Excel faylni "buzilgan" deb e'lon qiladi.
        $text = preg_replace('/[\x00-\x08\x0B\x0C\x0E-\x1F]/u', '', $text) ?? $text;
        return htmlspecialchars($text, ENT_QUOTES | ENT_XML1, 'UTF-8');
    }

    // --- ZIP ------------------------------------------------------------

    /**
     * Fayllarni ZIP ga yig'adi.
     *
     * ZipArchive bo'lsa — o'shani (siqiladi, fayl kichikroq). Bo'lmasa —
     * o'zimizning "siqilmagan" yozuvchi: hostingda kengaytma o'chirilgan
     * bo'lsa ham hisobot yuklanadi.
     */
    private static function zip(array $files): string
    {
        if (class_exists('ZipArchive')) {
            $tmp = tempnam(sys_get_temp_dir(), 'xlsx');
            if ($tmp !== false) {
                $zip = new ZipArchive();
                if ($zip->open($tmp, ZipArchive::OVERWRITE | ZipArchive::CREATE) === true) {
                    foreach ($files as $path => $content) {
                        $zip->addFromString($path, $content);
                    }
                    $zip->close();
                    $bytes = (string)file_get_contents($tmp);
                    @unlink($tmp);
                    return $bytes;
                }
                @unlink($tmp);
            }
        }
        return self::zipStore($files);
    }

    /** Siqmasdan ZIP yozish (store metodi). Har joyda ishlaydi. */
    private static function zipStore(array $files): string
    {
        $local = '';
        $central = '';
        $offset = 0;
        $count = 0;

        // DOS vaqt formati — hozirgi paytni qo'yamiz.
        $now = getdate();
        $dosTime = (($now['hours'] & 0x1F) << 11) | (($now['minutes'] & 0x3F) << 5) | (($now['seconds'] >> 1) & 0x1F);
        $dosDate = ((($now['year'] - 1980) & 0x7F) << 9) | (($now['mon'] & 0x0F) << 5) | ($now['mday'] & 0x1F);

        foreach ($files as $path => $content) {
            $crc = crc32($content);
            $len = strlen($content);

            $header = "\x50\x4b\x03\x04"           // local file header
                . pack('v', 20)                     // version needed
                . pack('v', 0)                      // flags
                . pack('v', 0)                      // method: 0 = store
                . pack('v', $dosTime)
                . pack('v', $dosDate)
                . pack('V', $crc)
                . pack('V', $len)                   // compressed size
                . pack('V', $len)                   // uncompressed size
                . pack('v', strlen($path))
                . pack('v', 0)                      // extra length
                . $path;

            $local .= $header . $content;

            $central .= "\x50\x4b\x01\x02"
                . pack('v', 20) . pack('v', 20)
                . pack('v', 0) . pack('v', 0)
                . pack('v', $dosTime) . pack('v', $dosDate)
                . pack('V', $crc) . pack('V', $len) . pack('V', $len)
                . pack('v', strlen($path))
                . pack('v', 0) . pack('v', 0)
                . pack('v', 0) . pack('v', 0)
                . pack('V', 0)
                . pack('V', $offset)
                . $path;

            $offset += strlen($header) + $len;
            $count++;
        }

        $end = "\x50\x4b\x05\x06"
            . pack('v', 0) . pack('v', 0)
            . pack('v', $count) . pack('v', $count)
            . pack('V', strlen($central))
            . pack('V', $offset)
            . pack('v', 0);

        return $local . $central . $end;
    }

    // --- CSV ------------------------------------------------------------

    /**
     * Jadval faylida FORMULA sifatida bajarilib ketmasligi uchun tayyorlaydi.
     *
     * Excel va LibreOffice `=`, `+`, `-`, `@` bilan boshlanadigan katakni
     * formula deb o'qiydi. Mijoz ismi Telegram orqali, mahsulot nomi esa
     * xodim tomonidan kiritiladi — ya'ni bu matnlar ISHONCHSIZ. Ilgari ular
     * hisobotga o'zgarishsiz tushar va faylni ochgan admin kompyuterida
     * bajarilardi.
     */
    public static function safe(mixed $value): string
    {
        $text = $value === null ? '' : (string)$value;
        if ($text !== '' && in_array($text[0], ['=', '+', '-', '@', "\t", "\r"], true)) {
            return "'" . $text;
        }
        return $text;
    }

    /** CSV ni brauzerga yuboradi (Excel uchun BOM bilan). */
    public static function downloadCsv(array $headers, array $rows, string $filename): never
    {
        header('Content-Type: text/csv; charset=utf-8');
        header('Content-Disposition: attachment; filename="' . $filename . '"');
        header('Cache-Control: no-store');

        $out = fopen('php://output', 'w');
        // BOM — usiz Excel kirill/o'zbek harflarini buzib ko'rsatadi.
        fwrite($out, "\xEF\xBB\xBF");
        fputcsv($out, $headers);
        foreach ($rows as $row) {
            fputcsv($out, array_values((array)$row));
        }
        fclose($out);
        exit;
    }
}
