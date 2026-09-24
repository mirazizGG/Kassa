<?php
/**
 * Bosh administrator parolini tiklash.
 *
 * NIMA UCHUN ALOHIDA SKRIPT
 * -------------------------
 * Bosh admin hisobini API orqali o'zgartirib bo'lmaydi — bu ATAYIN qilingan:
 * saytga kirgan hech kim, hatto boshqa admin ham, uning parolini almashtira
 * olmaydi. Demak parolni tiklashning yagona yo'li — serverga kirish huquqi.
 *
 * Ishlatish (kassa papkasidan):
 *
 *     php bin/reset_admin.php "yangi-parol"
 *     php bin/reset_admin.php "yangi-parol" xodim_nomi
 *
 * Ikkinchi parametr berilmasa — bosh admin (miraziz).
 *
 * MUHIM: parol almashtirilganda joriy sessiya BEKOR qilinadi. Ya'ni eski
 * token darhol ishlamay qoladi va qurilmalardan qayta kirish kerak bo'ladi.
 * Aks holda parolni bilgan odam eski token bilan yana 10 soat ishlayverardi.
 */

declare(strict_types=1);

if (PHP_SAPI !== 'cli') {
    http_response_code(403);
    exit("Bu skript faqat buyruq satridan ishlaydi.\n");
}

require dirname(__DIR__) . '/app/bootstrap.php';

$password = $argv[1] ?? '';
$username = $argv[2] ?? PRIMARY_ADMIN_USERNAME;

if ($password === '') {
    echo "Ishlatish: php bin/reset_admin.php \"yangi-parol\" [xodim_nomi]\n";
    echo "Sukut bo'yicha xodim: " . PRIMARY_ADMIN_USERNAME . "\n";
    exit(1);
}

// Juda qisqa parol — kassa uchun haqiqiy xavf: /auth/token daqiqasiga 20 ta
// urinishga ruxsat beradi, ya'ni to'rt raqamli parol bir kunda topiladi.
if (mb_strlen($password) < 8) {
    echo "XATO: parol kamida 8 belgidan iborat bo'lsin.\n";
    exit(1);
}

$user = Db::one('SELECT id, username, role FROM employees WHERE username = ?', [$username]);
if ($user === null) {
    echo "XATO: '$username' nomli xodim topilmadi.\n";
    echo "Bazada bor xodimlar:\n";
    foreach (Db::all('SELECT username, role FROM employees ORDER BY id') as $e) {
        echo "  {$e['username']} ({$e['role']})\n";
    }
    exit(1);
}

$changed = Db::run(
    'UPDATE employees
        SET hashed_password = ?, session_token = NULL, session_expires_at = NULL
      WHERE id = ?',
    [Auth::hashPassword($password), (int)$user['id']]
);

if ($changed === 0) {
    echo "XATO: parol yangilanmadi.\n";
    exit(1);
}

// Jurnalga yozamiz: parolni kim va qachon almashtirgani izsiz qolmasin.
Audit::log((int)$user['id'], 'PAROL_TIKLANDI',
    "Parol serverdan tiklandi: @{$user['username']} ({$user['role']})");

echo "Parol yangilandi: {$user['username']}\n";
echo "Joriy sessiya bekor qilindi — barcha qurilmalardan qaytadan kiring.\n";
exit(0);
