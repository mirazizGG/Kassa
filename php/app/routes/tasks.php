<?php
/**
 * /tasks — xodim vazifalari (faqat admin yaratadi/o'chiradi).
 *
 * Interfeysda bu "Xodimlar" sahifasi ichida ko'rinadi.
 * Xodimning o'zi faqat O'Z vazifasining holatini o'zgartira oladi.
 */

declare(strict_types=1);

// =======================================================================
// POST /tasks/
// =======================================================================
Router::post('/', function (): never {
    $user = Auth::require(['admin'], 'Faqat admin vazifa yarata oladi');
    $b = Http::body();

    $title = Http::reqStr($b, 'title', 300, 'Nomi');
    $assignedTo = Http::reqInt($b, 'assigned_to', "Mas'ul xodim");

    if (Db::one('SELECT id FROM employees WHERE id = ?', [$assignedTo]) === null) {
        fail(404, 'Xodim topilmadi');
    }

    $data = [
        'title'       => $title,
        'description' => Http::str($b, 'description', null, 2000, 'Izoh'),
        'status'      => Http::enum($b, 'status', ['pending', 'in_progress', 'completed'], 'pending', 'Holat'),
        'assigned_to' => $assignedTo,
        'created_by'  => (int)$user['id'],
        'created_at'  => Tz::now(),
        'due_date'    => Tz::parseFilterDate(Http::str($b, 'due_date', null, 40)),
    ];

    $id = Db::tx(function () use ($data, $user, $title, $assignedTo): int {
        $id = Db::insert('tasks', $data);
        Audit::log((int)$user['id'], 'YANGI_VAZIFA', "Vazifa: $title. Assigned to ID: $assignedTo");
        return $id;
    });

    // Eslatma: Python versiyasi bu yerda Telegram orqali xabar yuborardi.
    // Shared hosting'da bot ishlamaydi (uzluksiz jarayon yo'q), shuning
    // uchun xabar yuborilmaydi. Vazifaning o'zi normal yaratiladi.

    Http::json(Shape::task(Db::one('SELECT * FROM tasks WHERE id = ?', [$id])));
});

// =======================================================================
// GET /tasks/
// =======================================================================
Router::get('/', function (): never {
    $user = Auth::user();

    // Admin hammasini ko'radi, qolganlar faqat o'zinikini.
    $rows = $user['role'] === 'admin'
        ? Db::all('SELECT * FROM tasks ORDER BY id DESC LIMIT 1000')
        : Db::all('SELECT * FROM tasks WHERE assigned_to = ? ORDER BY id DESC LIMIT 1000', [(int)$user['id']]);

    Http::json(array_map(fn($r) => Shape::task($r), $rows));
});

// =======================================================================
// PUT /tasks/{task_id}
// =======================================================================
Router::put('/{task_id}', function (array $p): never {
    $user = Auth::user();
    $taskId = Router::id($p, 'task_id');
    $b = Http::body();

    $task = Db::one('SELECT * FROM tasks WHERE id = ?', [$taskId]);
    if ($task === null) {
        fail(404, 'Task not found');
    }

    $isAdmin = $user['role'] === 'admin';

    if (!$isAdmin) {
        if ((int)$task['assigned_to'] !== (int)$user['id']) {
            fail(403, "Faqat o'zingizga biriktirilgan vazifa statusini o'zgartira olasiz");
        }
        // Xodim faqat HOLATNI o'zgartira oladi.
        if (!empty($b['title']) || !empty($b['description']) || !empty($b['assigned_to'])) {
            fail(403, 'Workers can only update status');
        }
    }

    $data = [];
    if (array_key_exists('status', $b)) {
        $data['status'] = Http::enum($b, 'status', ['pending', 'in_progress', 'completed'], null, 'Holat');
    }
    if ($isAdmin) {
        if (array_key_exists('title', $b)) {
            $data['title'] = Http::reqStr($b, 'title', 300, 'Nomi');
        }
        if (array_key_exists('description', $b)) {
            $data['description'] = Http::str($b, 'description', null, 2000, 'Izoh');
        }
        if (array_key_exists('assigned_to', $b)) {
            $data['assigned_to'] = Http::reqInt($b, 'assigned_to', "Mas'ul xodim");
        }
        if (array_key_exists('due_date', $b)) {
            $data['due_date'] = Tz::parseFilterDate(Http::str($b, 'due_date', null, 40));
        }
    }

    Db::tx(function () use ($data, $taskId, $user): void {
        if ($data !== []) {
            Db::update('tasks', $taskId, $data);
        }
        $now = Db::one('SELECT status FROM tasks WHERE id = ?', [$taskId]);
        Audit::log((int)$user['id'], 'VAZIFA_YANGILANDI',
            "Vazifa ID: $taskId. Status: " . ($now['status'] ?? '-'));
    });

    Http::json(Shape::task(Db::one('SELECT * FROM tasks WHERE id = ?', [$taskId])));
});

// =======================================================================
// DELETE /tasks/{task_id}
// =======================================================================
Router::delete('/{task_id}', function (array $p): never {
    $user = Auth::require(['admin'], "Faqat admin vazifani o'chira oladi");
    $taskId = Router::id($p, 'task_id');

    $task = Db::one('SELECT * FROM tasks WHERE id = ?', [$taskId]);
    if ($task === null) {
        fail(404, 'Task not found');
    }

    Db::tx(function () use ($taskId, $user, $task): void {
        Db::delete('tasks', $taskId);
        Audit::log((int)$user['id'], 'VAZIFA_OCHIRILDI',
            "Vazifa ID: $taskId. Title: {$task['title']}");
    });

    Http::json(['message' => 'Task deleted']);
});
