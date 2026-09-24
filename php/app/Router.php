<?php
/**
 * Marshrutlash.
 *
 * TEZLIK SIRI: butun marshrut jadvali yuklanmaydi. So'rov yo'lining BIRINCHI
 * bo'lagi qaysi fayl ekanini aytadi va faqat O'SHA fayl require qilinadi.
 * Ya'ni /sales/ so'rovi uchun sales.php o'qiladi, qolgan o'nta fayl esa
 * umuman diskdan olinmaydi. Python versiyasida har bir jarayon ishga
 * tushganda BARCHA routerlar, SQLAlchemy modellari va Pydantic sxemalari
 * yuklanardi — 218 MB ning katta qismi shundan edi.
 */

declare(strict_types=1);

final class Router
{
    /** @var array<int, array{0:string,1:string,2:callable}> */
    private static array $routes = [];
    private static string $prefix = '';

    /** Marshrut qo'shish. Yo'l prefiksga NISBATAN yoziladi. */
    public static function add(string $method, string $path, callable $handler): void
    {
        self::$routes[] = [strtoupper($method), self::normalize($path), $handler];
    }

    public static function get(string $p, callable $h): void
    {
        self::add('GET', $p, $h);
    }

    public static function post(string $p, callable $h): void
    {
        self::add('POST', $p, $h);
    }

    public static function put(string $p, callable $h): void
    {
        self::add('PUT', $p, $h);
    }

    public static function patch(string $p, callable $h): void
    {
        self::add('PATCH', $p, $h);
    }

    public static function delete(string $p, callable $h): void
    {
        self::add('DELETE', $p, $h);
    }

    /**
     * Yo'lni bir ko'rinishga keltiradi.
     *
     * FastAPI da "/sales/" va "/settings" ikkalasi ham uchraydi (birinchisi
     * prefiks + "/", ikkinchisi prefiks + ""). Ikkalasini ham bo'sh satrga
     * keltiramiz, shunda mijoz oxiridagi "/" ni qo'ysa ham, qo'ymasa ham
     * bir xil ishlaydi — Python versiyasi bu holda 307 bilan qayta
     * yo'naltirardi, bu esa ortiqcha so'rov.
     */
    private static function normalize(string $path): string
    {
        $p = '/' . trim($path, '/');
        return $p === '/' ? '' : $p;
    }

    /**
     * So'rovni bajaradi.
     *
     * @param string $method HTTP usuli
     * @param string $rest   prefiksdan keyingi yo'l
     */
    public static function dispatch(string $method, string $rest): bool
    {
        $method = strtoupper($method);
        $rest = self::normalize($rest);
        $methodMismatch = false;

        foreach (self::$routes as [$m, $pattern, $handler]) {
            $params = self::match($pattern, $rest);
            if ($params === null) {
                continue;
            }
            if ($m !== $method) {
                $methodMismatch = true;
                continue;
            }
            $result = $handler($params);
            // Ishlovchi o'zi javob bergan bo'lsa (Http::json exit qiladi),
            // bu yergacha yetib kelmaydi. Massiv qaytarsa — JSON qilamiz.
            Http::json($result);
        }

        if ($methodMismatch) {
            Http::fail(405, 'Method Not Allowed');
        }

        // Hech narsa mos kelmadi. To'xtatmaymiz — chaqiruvchi hal qiladi:
        // brauzer navigatsiyasi bo'lsa SPA sahifasi berilishi kerak.
        // FastAPI ham shunday ishlardi: mos kelmagan yo'l "/" ga
        // o'rnatilgan statik ilovaga tushardi.
        return false;
    }

    /**
     * Naqsh mos keladimi? Mos kelsa parametrlarni qaytaradi.
     * "{id}" bo'lagi bitta bo'lakni ushlaydi.
     */
    private static function match(string $pattern, string $path): ?array
    {
        if (!str_contains($pattern, '{')) {
            return $pattern === $path ? [] : null;
        }

        $pSeg = explode('/', ltrim($pattern, '/'));
        $aSeg = explode('/', ltrim($path, '/'));
        if (count($pSeg) !== count($aSeg)) {
            return null;
        }

        $params = [];
        foreach ($pSeg as $i => $seg) {
            if (strlen($seg) > 2 && $seg[0] === '{' && $seg[-1] === '}') {
                $name = substr($seg, 1, -1);
                if ($aSeg[$i] === '') {
                    return null;
                }
                $params[$name] = rawurldecode($aSeg[$i]);
                continue;
            }
            if ($seg !== $aSeg[$i]) {
                return null;
            }
        }
        return $params;
    }

    /** Yo'l parametrini butun son sifatida oladi. */
    public static function id(array $params, string $name = 'id'): int
    {
        $raw = $params[$name] ?? '';
        if (!is_numeric($raw) || (int)$raw != (float)$raw || (int)$raw < 1) {
            fail(422, "Manzildagi «{$name}» noto'g'ri.");
        }
        return (int)$raw;
    }
}
