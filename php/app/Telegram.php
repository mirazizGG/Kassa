<?php
/**
 * Telegram Bot API — curl ustidagi yupqa qobiq (bin/bot.php va zahira uchun).
 *
 * Kutubxona yo'q: bizga kerak bo'lgani bir nechta metod, ularning hammasi
 * bitta POST so'rov.
 */

declare(strict_types=1);

final class Telegram
{
    public static function token(): string
    {
        return trim((string)env('TELEGRAM_BOT_TOKEN'));
    }

    public static function enabled(): bool
    {
        return self::token() !== '';
    }

    /**
     * API chaqiruvi. Muvaffaqiyatda `result`, aks holda RuntimeException.
     *
     * @param array<string, mixed> $params
     */
    public static function call(string $method, array $params = [], int $timeout = 30): mixed
    {
        $ch = curl_init('https://api.telegram.org/bot' . self::token() . '/' . $method);
        $hasFile = false;
        foreach ($params as $k => $v) {
            if ($v instanceof CURLFile) {
                $hasFile = true;
            } elseif (is_array($v)) {
                $params[$k] = json_encode($v, JSON_UNESCAPED_UNICODE);
            }
        }
        curl_setopt_array($ch, [
            CURLOPT_POST           => true,
            CURLOPT_POSTFIELDS     => $hasFile ? $params : http_build_query($params),
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_CONNECTTIMEOUT => 15,
            CURLOPT_TIMEOUT        => $timeout,
        ]);
        // Windows'da antivirus HTTPS ni o'z sertifikati bilan tekshiradi —
        // u faqat Windows sertifikat omborida bor. Tekshiruv O'CHIRILMAYDI.
        if (PHP_OS_FAMILY === 'Windows' && defined('CURLSSLOPT_NATIVE_CA')) {
            curl_setopt($ch, CURLOPT_SSL_OPTIONS, CURLSSLOPT_NATIVE_CA);
        }
        $body = curl_exec($ch);
        $err = curl_error($ch);
        curl_close($ch);

        if ($body === false) {
            throw new RuntimeException("tarmoq xatosi: $err");
        }
        $data = json_decode((string)$body, true);
        if (!is_array($data) || empty($data['ok'])) {
            $code = (int)($data['error_code'] ?? 0);
            throw new RuntimeException(
                'Telegram: ' . ($data['description'] ?? substr((string)$body, 0, 200)),
                $code
            );
        }
        return $data['result'] ?? null;
    }

    /** HTML formatdagi xabar. Xato bo'lsa false (masalan foydalanuvchi botni bloklagan). */
    public static function send(int|string $chatId, string $html, ?array $keyboard = null): bool
    {
        if (env_bool('BOT_DRY_RUN', false)) {
            bot_log("[DRY] -> $chatId:\n$html");
            return true;
        }
        $params = [
            'chat_id'                  => $chatId,
            'text'                     => mb_substr($html, 0, 4000),
            'parse_mode'               => 'HTML',
            'disable_web_page_preview' => 'true',
        ];
        if ($keyboard !== null) {
            $params['reply_markup'] = $keyboard;
        }
        try {
            self::call('sendMessage', $params);
            return true;
        } catch (Throwable $e) {
            bot_log("xabar yuborilmadi ($chatId): " . $e->getMessage());
            return false;
        }
    }

    /** Fayl yuborish: diskdagi yo'l yoki xotiradagi baytlar. */
    public static function sendDocument(int|string $chatId, string $pathOrBytes, string $filename, string $caption = '', bool $isBytes = false): bool
    {
        if (env_bool('BOT_DRY_RUN', false)) {
            bot_log("[DRY] fayl -> $chatId: $filename (" . strlen($isBytes ? $pathOrBytes : (string)@file_get_contents($pathOrBytes)) . " bayt) $caption");
            return true;
        }
        $tmp = null;
        if ($isBytes) {
            $tmp = tempnam(sys_get_temp_dir(), 'kassa');
            file_put_contents($tmp, $pathOrBytes);
            $path = $tmp;
        } else {
            $path = $pathOrBytes;
        }
        try {
            self::call('sendDocument', [
                'chat_id'    => $chatId,
                'caption'    => mb_substr($caption, 0, 1000),
                'parse_mode' => 'HTML',
                'document'   => new CURLFile($path, 'application/octet-stream', $filename),
            ], 180);
            return true;
        } catch (Throwable $e) {
            bot_log("fayl yuborilmadi ($chatId, $filename): " . $e->getMessage());
            return false;
        } finally {
            if ($tmp !== null) {
                @unlink($tmp);
            }
        }
    }

    /** Oddiy tugmali klaviatura. $rows — tugma matnlari qatorlari. */
    public static function keyboard(array $rows): array
    {
        return [
            'keyboard'        => array_map(
                fn($row) => array_map(fn($t) => is_array($t) ? $t : ['text' => $t], $row),
                $rows
            ),
            'resize_keyboard' => true,
        ];
    }

    public static function removeKeyboard(): array
    {
        return ['remove_keyboard' => true];
    }
}

/** Bot jurnali: ekranga va logs/bot.log ga. */
function bot_log(string $message): void
{
    $line = '[' . (new DateTimeImmutable('now', Tz::shopTz()))->format('Y-m-d H:i:s') . "] $message\n";
    echo $line;
    $dir = ROOT_DIR . '/logs';
    if (is_dir($dir)) {
        @file_put_contents($dir . '/bot.log', $line, FILE_APPEND);
    }
}
