<?php
/**
 * Ilovaning yagona kirish tayyorgarligi.
 *
 * NIMA UCHUN FRAMEWORK YO'Q
 * -------------------------
 * Laravel/Symfony har so'rovda ~15 MB xotira va ~30 ms yuklanish vaqtini
 * oladi. Shared hosting'da aynan shu narsa "yuklama" bo'lib ko'rinadi.
 * Bu yerda esa butun karkas ~1 ms da yuklanadi: avtoyuklovchi jadval
 * skanerlamaydi, faqat kerak bo'lgan fayl require qilinadi.
 *
 * Python versiyasidan farqi shundaki, jarayon so'rovdan keyin O'LADI:
 * bo'sh turganda xotira nolga teng. Python/Passenger bir jarayonda
 * 218 MB ushlab turardi va parallel so'rovlarda shuncha marta ko'payardi.
 */

declare(strict_types=1);

define('APP_DIR', __DIR__);
define('ROOT_DIR', dirname(__DIR__));
define('APP_START', microtime(true));

// --- .env ---------------------------------------------------------------
// Ataylab oddiy: parse_ini_file tirnoq va maxsus belgilarda kutilmagan
// natija beradi (masalan parolda '#' bo'lsa). Qo'lda o'qiymiz.
function env_load(string $path): void
{
    if (!is_readable($path)) {
        return;
    }
    foreach (file($path, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) as $line) {
        $line = ltrim($line);
        if ($line === '' || $line[0] === '#') {
            continue;
        }
        $pos = strpos($line, '=');
        if ($pos === false) {
            continue;
        }
        $key = trim(substr($line, 0, $pos));
        $val = trim(substr($line, $pos + 1));
        // Tirnoqlarni olib tashlaymiz, lekin faqat juft bo'lsa.
        $len = strlen($val);
        if ($len >= 2 && (($val[0] === '"' && $val[$len - 1] === '"')
            || ($val[0] === "'" && $val[$len - 1] === "'"))) {
            $val = substr($val, 1, -1);
        }
        if ($key !== '' && getenv($key) === false) {
            putenv("$key=$val");
            $_ENV[$key] = $val;
        }
    }
}

function env(string $key, ?string $default = null): ?string
{
    $v = $_ENV[$key] ?? getenv($key);
    if ($v === false || $v === null || $v === '') {
        return $default;
    }
    return is_string($v) ? trim($v) : $default;
}

function env_bool(string $key, bool $default = false): bool
{
    $v = env($key);
    if ($v === null) {
        return $default;
    }
    return in_array(strtolower($v), ['1', 'true', 'yes', 'on'], true);
}

env_load(ROOT_DIR . '/.env');

// --- Muhit --------------------------------------------------------------
define('APP_ENV', strtolower(env('APP_ENV', 'development')));
define('IS_PROD', APP_ENV === 'production');

// Production'da xatolar EKRANGA chiqmasligi kerak: stack trace ichida
// baza paroli va fayl yo'llari bo'ladi. Jurnalga esa yoziladi.
ini_set('display_errors', IS_PROD ? '0' : '1');
ini_set('log_errors', '1');
error_reporting(E_ALL);
ini_set('error_log', ROOT_DIR . '/logs/php-error.log');

// Vaqt bilan ishlashda ikkilanish bo'lmasin: butun PHP UTC da yashaydi,
// do'kon vaqt mintaqasi faqat Tz.php ichida qo'llanadi.
date_default_timezone_set('UTC');

// Kirish/chiqishda har doim UTF-8.
mb_internal_encoding('UTF-8');

// --- SECRET_KEY ---------------------------------------------------------
// Python versiyasidagi bilan bir xil qoida: production'da namunaviy yoki
// qisqa kalit bilan ishga tushmaydi. Kalit JWT imzosi — ochiq qolsa,
// istalgan odam o'ziga admin token yasay oladi.
const DEV_SECRET_KEY = 'dev_secret_key_change_in_production_12345';
const PLACEHOLDER_SECRET_KEYS = [
    DEV_SECRET_KEY,
    'change_me_generate_with_secrets_token_hex_32',
];
const MIN_SECRET_KEY_LEN = 32;

$secret = env('SECRET_KEY', '');
if ($secret === '' || $secret === null) {
    if (IS_PROD) {
        http_response_code(500);
        header('Content-Type: application/json; charset=utf-8');
        echo json_encode(['detail' => "Server sozlanmagan: SECRET_KEY yo'q."], JSON_UNESCAPED_UNICODE);
        exit;
    }
    $secret = DEV_SECRET_KEY;
}
if (IS_PROD && (in_array($secret, PLACEHOLDER_SECRET_KEYS, true) || strlen($secret) < MIN_SECRET_KEY_LEN)) {
    http_response_code(500);
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode(['detail' => 'Server sozlanmagan: SECRET_KEY zaif.'], JSON_UNESCAPED_UNICODE);
    exit;
}
define('SECRET_KEY', $secret);
unset($secret);

// --- O'zgarmaslar -------------------------------------------------------
// Bosh administrator. Atayin .env dan sozlanmaydi: frontend (Employees.jsx)
// ham aynan shu nomga bog'langan.
const PRIMARY_ADMIN_USERNAME = 'miraziz';
const ACCESS_TOKEN_EXPIRE_MINUTES = 600;
const DEV_ADMIN_PASSWORD = '8038434';

define('SHOP_TIMEZONE', env('SHOP_TIMEZONE', 'Asia/Tashkent'));
// Yuklangan fayllar public/ ICHIDA: veb-server ularni to'g'ridan-to'g'ri
// beradi va PHP umuman ishga tushmaydi. Python versiyasida ham /uploads
// statik sifatida ulangan edi — xulq bir xil.
//
// UPLOAD_DIR ni .env dan berish MUMKIN va ba'zan SHART. Hostingda sayt
// ildizi ilovadan alohida bo'lishi mumkin (fayllar public_html ga
// ko'chirilgan). O'shanda ilova <ilova>/public/uploads ga yozar, veb-server
// esa public_html/uploads dan o'qir edi — yangi nakladnoy fotolari
// yuklanardi, lekin ochilmasdi. Endi yo'lni aniq ko'rsatish mumkin.
define('UPLOAD_DIR', rtrim(env('UPLOAD_DIR') ?? (ROOT_DIR . '/public/uploads'), "/\\"));
define('APP_VERSION', '2.0.0-php');

// --- Karkas -------------------------------------------------------------
require APP_DIR . '/Http.php';
require APP_DIR . '/Tz.php';
require APP_DIR . '/Db.php';
require APP_DIR . '/Auth.php';
require APP_DIR . '/Router.php';
require APP_DIR . '/Audit.php';
require APP_DIR . '/Shape.php';

// Kutilmagan xatoni ham JSON qilib qaytaramiz — frontend har doim
// {"detail": "..."} kutadi, HTML sahifa uni sindiradi.
set_exception_handler(function (Throwable $e): void {
    if ($e instanceof HttpError) {
        Http::fail($e->getCode(), $e->getMessage(), $e->headers);
    }
    $where = $e->getFile() . ':' . $e->getLine();
    error_log('[kassa] ' . get_class($e) . ': ' . $e->getMessage() . ' @ ' . $where);

    // Production'da xato matni EKRANGA chiqmaydi: uning ichida baza paroli
    // va fayl yo'llari bo'lishi mumkin. Ishlab chiqishda esa aynan shu matn
    // kerak — aks holda "kutilmagan xatolik" degan javob bilan qolasiz va
    // sababini topib bo'lmaydi.
    Http::fail(500, IS_PROD
        ? 'Serverda kutilmagan xatolik yuz berdi.'
        : get_class($e) . ': ' . $e->getMessage() . ' @ ' . $where);
});

set_error_handler(function (int $no, string $str, string $file, int $line): bool {
    if (!(error_reporting() & $no)) {
        return false;
    }
    throw new ErrorException($str, 0, $no, $file, $line);
});
