<?php
/**
 * Yagona kirish nuqtasi (front controller).
 *
 * Statik fayllar bu yergacha YETIB KELMAYDI: .htaccess ularni to'g'ridan-
 * to'g'ri Apache/LiteSpeed orqali beradi. Ya'ni JS, CSS, rasm va nakladnoy
 * fotosi uchun PHP umuman ishga tushmaydi — bu eng katta tejamkorlik.
 *
 * PHP faqat API so'roviga va SPA sahifasiga javob beradi.
 */

declare(strict_types=1);

// --- app/ papkasini TOPAMIZ ------------------------------------------
//
// Hostingda joylashuv har xil bo'ladi:
//   * document root = <ilova>/public       -> app/ bir pog'ona yuqorida
//   * fayllar public_html ga ko'chirilgan   -> app/ yonidagi kassa/ ichida
//
// Ikkinchi holatda oddiy dirname(__DIR__) noto'g'ri joyga qaraydi va sayt
// "bootstrap topilmadi" bilan yiqilardi. Shuning uchun bir nechta odatiy
// joyni ketma-ket tekshiramiz — deploy paytida fayl tahrirlash kerak emas.
$__candidates = [
    dirname(__DIR__) . '/app/bootstrap.php',        // <ilova>/public -> <ilova>/app
    dirname(__DIR__) . '/kassa/app/bootstrap.php',  // public_html yonida kassa/
    dirname(__DIR__, 2) . '/kassa/app/bootstrap.php',
    __DIR__ . '/app/bootstrap.php',                 // hammasi bitta papkada
    dirname(__DIR__) . '/../kassa/app/bootstrap.php',
];
// Путь может быть записан в файле рядом с index.php.
//
// Раньше здесь использовалась переменная окружения из .htaccess (SetEnv).
// Но mod_env загружен не на каждом сервере, и тогда Apache отвечает 500 на
// ВЕСЬ сайт — причём до PHP дело не доходит, и в журнале приложения пусто.
// Обычный файл не зависит от настроек веб-сервера и работает везде.
$__pathFile = __DIR__ . '/.kassa-app-path';
if (is_file($__pathFile)) {
    $__p = trim((string)file_get_contents($__pathFile));
    if ($__p !== '') {
        array_unshift($__candidates, rtrim($__p, "/\\") . '/bootstrap.php');
    }
}
if (getenv('KASSA_APP_DIR')) {
    array_unshift($__candidates, rtrim((string)getenv('KASSA_APP_DIR'), "/\\") . '/bootstrap.php');
}

$__bootstrap = null;
foreach ($__candidates as $__c) {
    if (is_file($__c)) {
        $__bootstrap = $__c;
        break;
    }
}
if ($__bootstrap === null) {
    http_response_code(500);
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode([
        'detail' => "Ilova yadrosi (app/bootstrap.php) topilmadi. "
            . "app/ papkasini public/ yonida qoldiring, yoki index.php yonida "
            . "'.kassa-app-path' faylini yarating va ichiga app/ papkasining "
            . "to'liq yo'lini yozing.",
    ], JSON_UNESCAPED_UNICODE);
    exit;
}

require $__bootstrap;

// --- So'rov yo'li -------------------------------------------------------
$uri = $_SERVER['REQUEST_URI'] ?? '/';
$path = parse_url($uri, PHP_URL_PATH);
$path = is_string($path) ? rawurldecode($path) : '/';

// Ilova ildizi domen ostidagi papkada bo'lsa (masalan /kassa), uni kesamiz.
$base = env('APP_BASE_PATH', '');
if ($base !== null && $base !== '' && str_starts_with($path, $base)) {
    $path = substr($path, strlen($base));
}
$path = '/' . ltrim($path, '/');

$method = strtoupper($_SERVER['REQUEST_METHOD'] ?? 'GET');

// PHP ning o'rnatilgan serveri (php -S) uchun: mavjud statik faylni o'zi
// bersin. Ishlab chiqarishda buni .htaccess qiladi va bu shart bajarilmaydi.
if (PHP_SAPI === 'cli-server') {
    $candidate = __DIR__ . $path;
    if ($path !== '/' && is_file($candidate)) {
        return false;
    }
}

// --- CORS ---------------------------------------------------------------
// Sukut bo'yicha frontend va API bitta manzilda turadi, ya'ni CORS umuman
// kerak emas. Sozlama faqat alohida domendan chaqirish kerak bo'lsa ishlaydi.
$origins = env('ALLOWED_ORIGINS', '');
if ($origins !== null && $origins !== '') {
    $reqOrigin = $_SERVER['HTTP_ORIGIN'] ?? '';
    if ($reqOrigin !== '') {
        $list = array_map('trim', explode(',', $origins));
        if (in_array('*', $list, true) || in_array($reqOrigin, $list, true)) {
            header('Access-Control-Allow-Origin: ' . ($reqOrigin ?: '*'));
            header('Vary: Origin');
            header('Access-Control-Allow-Credentials: true');
            header('Access-Control-Allow-Headers: Authorization, Content-Type');
            header('Access-Control-Allow-Methods: GET, POST, PUT, PATCH, DELETE, OPTIONS');
        }
    }
}

if ($method === 'OPTIONS') {
    http_response_code(204);
    exit;
}

// --- Xavfsizlik sarlavhalari -------------------------------------------
header('X-Content-Type-Options: nosniff');
header('X-Frame-Options: SAMEORIGIN');
header('Referrer-Policy: same-origin');

// --- /health ------------------------------------------------------------
// Bazaga tegmaydi: monitoring har daqiqada chaqirsa ham yuklama bermasin.
if ($path === '/health') {
    Http::json([
        'status'          => 'ok',
        'version'         => APP_VERSION,
        'runtime'         => 'php-' . PHP_VERSION,
        'background_jobs' => false,
        'bot'             => false,
        'env'             => APP_ENV,
    ]);
}

// --- API marshrutlari ---------------------------------------------------
const API_MODULES = [
    'auth', 'pos', 'sales', 'inventory', 'crm',
    'finance', 'suppliers', 'audit', 'settings', 'system', 'tasks',
];

// React Router sahifalari. Ular API prefikslari bilan USTMA-UST tushadi:
// "/settings" ham sahifa, ham endpoint; "/sales" va "/suppliers" ham shunday.
//
// Python versiyasida bu HAQIQIY nosozlik edi: kassir "Sozlamalar" sahifasida
// turib F5 bossa, interfeys o'rniga xom JSON ko'rinardi (yoki "/sales" da
// 307 orqali o'sha JSON ga tushardi). Faqat sahifani qayta ochish yordam
// berardi.
//
// Ajratish belgisi — Accept sarlavhasi: brauzer navigatsiyasi "text/html"
// so'raydi, axios esa "application/json". Eksport fayllari ham axios orqali
// olinadi, ya'ni ular bu yerga tushmaydi.
const SPA_ROUTES = [
    '/', '/login', '/pos', '/sales', '/inventory', '/crm', '/finance',
    '/suppliers', '/settings', '/audit', '/employees', '/attendance', '/shifts',
];

$wantsHtml = str_contains($_SERVER['HTTP_ACCEPT'] ?? '', 'text/html');
$isRead = $method === 'GET' || $method === 'HEAD';
$normalized = $path === '/' ? '/' : '/' . trim($path, '/');

$serveSpa = $isRead && $wantsHtml && in_array($normalized, SPA_ROUTES, true);

if (!$serveSpa) {
    $segments = explode('/', ltrim($path, '/'), 2);
    $module = $segments[0] ?? '';
    $rest = '/' . ($segments[1] ?? '');

    if (in_array($module, API_MODULES, true)) {
        $file = APP_DIR . '/routes/' . $module . '.php';
        if (is_file($file)) {
            require $file;
            // Mos kelsa javob beradi va shu yerda tugaydi.
            Router::dispatch($method, $rest);
        }
        // Mos kelmadi. O'qish so'rovi bo'lsa — pastdagi SPA ga tushadi
        // (masalan "/pos" yoki "/crm" sahifasi). Aks holda 404.
        if (!$isRead) {
            Http::fail(404, 'Not Found');
        }
    }
}

// --- SPA ----------------------------------------------------------------
// Bu yergacha yetib kelgan so'rov — React Router yo'li (/pos, /inventory...).
// Fayl mavjud bo'lganda .htaccess uni allaqachon bergan bo'lardi.
if ($method !== 'GET' && $method !== 'HEAD') {
    Http::fail(404, 'Not Found');
}

$indexHtml = __DIR__ . '/index.html';
if (!is_file($indexHtml)) {
    Http::json([
        'detail' => 'Interfeys yig\'ilmagan. frontend/ ichida "npm run build" '
            . 'bajaring va dist/ ni public/ ga ko\'chiring.',
    ], 503);
}

header('Content-Type: text/html; charset=utf-8');
// SPA qobig'i keshlanmasin: yangi versiya chiqqanda brauzer eskisini
// ushlab qolmasligi kerak. Ichidagi hash'langan JS/CSS esa keshlanadi.
header('Cache-Control: no-cache, must-revalidate');
readfile($indexHtml);
