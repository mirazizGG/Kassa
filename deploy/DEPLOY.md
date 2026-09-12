# Развёртывание на VPS с PostgreSQL

Инструкция на день переезда. Рассчитана на чистый Ubuntu 22.04/24.04.
Выполнять по порядку — шаги 6 и 7 переносят данные, всё до них подготовительное.

Ключевое правило: **магазин должен быть закрыт**, пока идёт перенос. Продажи,
проведённые в SQLite после снятия копии, на сервер не попадут.

---

## 0. Что должно быть под рукой

- Доступ по SSH с sudo.
- Домен, A-запись которого указывает на IP сервера (нужен для TLS).
- Файл `backend/market.db` с боевого компьютера магазина.
- Папка `backend/uploads/` оттуда же — там фотографии накладных. В дамп базы они
  не входят (архивируются отдельно), поэтому при переезде копируются вручную.

---

## 1. Пользователь и пакеты

```bash
sudo adduser --system --group --home /opt/kassa kassa
sudo apt update
sudo apt install -y python3.12 python3.12-venv git postgresql postgresql-client \
                    nodejs npm caddy
```

Проверьте версию Python — нужна **3.12**: именно её проверяет CI, и именно на
ней собран `requirements.txt`. Пины `numpy<2.1` и `pandas<2.3` стоят ради старого
Windows-сервера; на более новых Python они могут не иметь готовых колёс и уйти в
долгую сборку из исходников. Не рискуйте — ставьте 3.12.

```bash
python3.12 --version
```

## 2. База данных

```bash
sudo -u postgres psql <<'SQL'
CREATE USER kassa WITH PASSWORD 'ЗАМЕНИТЕ_НА_СИЛЬНЫЙ_ПАРОЛЬ';
CREATE DATABASE kassa OWNER kassa ENCODING 'UTF8';
SQL
```

Проверка подключения:

```bash
psql "postgresql://kassa:ПАРОЛЬ@localhost:5432/kassa" -c "SELECT version();"
```

## 3. Код и окружение

```bash
sudo -u kassa git clone <URL-репозитория> /opt/kassa
cd /opt/kassa
sudo -u kassa python3.12 -m venv venv
sudo -u kassa venv/bin/pip install -U pip
sudo -u kassa venv/bin/pip install -r backend/requirements.txt
```

Если репозитория нет — скопируйте папку проекта в `/opt/kassa` и выполните
`git init`, иначе `deploy/scripts/update.sh` работать не будет.

## 4. Настройки

```bash
sudo -u kassa cp deploy/env/production.env.example deploy/env/production.env
sudo -u kassa chmod 600 deploy/env/production.env
sudo -u kassa nano deploy/env/production.env
```

Обязательно заполнить:

| Переменная | Чем |
|---|---|
| `SECRET_KEY` | `python -c "import secrets; print(secrets.token_hex(32))"` |
| `DATABASE_URL` | `postgresql://kassa:ПАРОЛЬ@localhost:5432/kassa` |
| `ALLOWED_ORIGINS` | `https://ваш-домен` — **не** `*` |
| `PRIMARY_ADMIN_PASSWORD` | сильный пароль (после переноса не используется) |

Приложение **не запустится**, если `SECRET_KEY` пустой, короче 32 символов или
равен одной из заглушек из примера. Это намеренно.

## 5. Сборка фронтенда

```bash
cd /opt/kassa/frontend
sudo -u kassa npm ci --no-audit --no-fund
sudo -u kassa npm run build
```

`frontend/dist` отдаёт сам бэкенд — отдельный веб-сервер для статики не нужен.
Если `dist/index.html` отсутствует, по `/` вернётся JSON вместо интерфейса.

---

## 6. Перенос данных — самый ответственный шаг

### 6.1 Подготовка на компьютере магазина

**Закройте магазин.** Убедитесь, что все смены закрыты.

Запустите приложение на SQLite **один раз** с новой версией кода. Это обновит
схему и переведёт время смен в UTC. Без этого шага скрипт переноса откажется
работать — и правильно сделает: иначе время смен уехало бы на 5 часов.

```bash
cd backend && python main.py     # дождитесь "Startup: Complete", затем Ctrl+C
```

Снимите копию:

```bash
cp backend/market.db market.db.perenos
```

### 6.2 Копирование на сервер

```bash
scp market.db.perenos user@сервер:/tmp/
scp -r backend/uploads user@сервер:/tmp/uploads

sudo mv /tmp/market.db.perenos /opt/kassa/backend/
sudo cp -r /tmp/uploads/* /opt/kassa/backend/uploads/
sudo chown -R kassa:kassa /opt/kassa/backend/market.db.perenos /opt/kassa/backend/uploads
```

### 6.3 Сухой прогон

Ничего не пишет. Показывает, сколько строк по каждой таблице переедет.

```bash
cd /opt/kassa/backend
sudo -u kassa env $(grep -v '^#' ../deploy/env/production.env | xargs) \
    ../venv/bin/python migrate_to_postgres.py --source market.db.perenos --dry-run
```

Сверьте числа с тем, что видите в интерфейсе магазина: товары, клиенты, продажи.
Если что-то не сходится — **остановитесь** и разберитесь.

### 6.4 Перенос

```bash
sudo -u kassa env $(grep -v '^#' ../deploy/env/production.env | xargs) \
    ../venv/bin/python migrate_to_postgres.py --source market.db.perenos
```

Скрипт:

1. проверит, что миграция времени смен на источнике выполнена;
2. создаст схему в PostgreSQL;
3. откажется работать, если целевая база не пуста;
4. скопирует таблицы в порядке зависимостей внешних ключей;
5. **сдвинет последовательности `id`** — без этого первая же новая продажа
   упадёт с `duplicate key`;
6. сверит количество строк по каждой таблице.

Последняя строка должна быть `Ko'chirish muvaffaqiyatli tugadi.` Если вместо неё
`KO'CHIRISHDA FARQ BOR` — базу не использовать, выяснять причину.

---

## 7. Запуск

```bash
sudo cp /opt/kassa/deploy/systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now kassa-web kassa-worker
```

Два юнита не случайно:

- **kassa-web** — четыре воркера, `RUN_BACKGROUND_JOBS=false`;
- **kassa-worker** — один процесс, `RUN_BACKGROUND_JOBS=true`, здесь живут
  планировщик, Telegram-бот и бэкапы.

Если запустить фоновые задачи в четырёх воркерах, Telegram начнёт отвечать
`409 Conflict` в цикле, каждый должник получит по четыре напоминания, а четыре
бэкап-задачи будут писать в одну папку одновременно.

Проверка:

```bash
curl -s localhost:8000/health   # {"status":"ok","background_jobs":false,...}
curl -s localhost:8001/health   # {"status":"ok","background_jobs":true,...}
sudo systemctl status kassa-web kassa-worker
```

## 8. TLS

```bash
sudo cp /opt/kassa/deploy/Caddyfile /etc/caddy/Caddyfile
sudo nano /etc/caddy/Caddyfile      # замените домен
sudo systemctl reload caddy
```

Caddy получит сертификат Let's Encrypt автоматически. Нужны открытые порты 80 и
443 и корректная A-запись.

## 9. Проверка боем

Пройдите этот список до того, как пустить кассиров:

- [ ] `https://домен` открывается, замок в адресной строке зелёный
- [ ] вход под `miraziz` работает **старым** паролем (перенесённым, не из `.env`)
- [ ] в справочнике товаров те же позиции и остатки, что были в магазине
- [ ] у клиентов сохранились долги и бонусы
- [ ] история продаж на месте, даты и время показываются **правильно** (не сдвинуты на 5 часов)
- [ ] открывается смена, проводится пробная продажа, закрывается смена
- [ ] пробная продажа возвращается
- [ ] `curl -s localhost:8000/health` отвечает
- [ ] Telegram-бот отвечает на `/start`
- [ ] `sudo -u kassa /opt/kassa/deploy/scripts/backup-verify.sh` проходит

Пробную продажу и возврат потом удалять не нужно — они останутся в истории как
след проверки, это нормально.

---

## Эксплуатация

### Бэкапы

Снимаются по расписанию `BACKUP_HOURS` (по умолчанию 12:00 и 22:00) и при старте.
В `/opt/kassa/backend/backups/` появляются два вида файлов:

- `backup_*.dump` — база (`pg_dump --format=custom`);
- `uploads_*.tar.gz` — фотографии накладных, которых в дампе нет.

У каждого вида свой ретеншн, они не удаляют файлы друг друга. Для полного
восстановления нужны **оба** файла за одну дату.

**Раз в месяц проверяйте, что копия действительно восстанавливается:**

```bash
sudo -u kassa /opt/kassa/deploy/scripts/backup-verify.sh
```

Снять копию и восстановить из копии — разные вещи. Проверять надо вторую.

### Восстановление

```bash
sudo systemctl stop kassa-web kassa-worker
sudo -u postgres dropdb kassa
sudo -u postgres createdb kassa -O kassa
sudo -u kassa pg_restore --no-owner --no-privileges \
    -d "postgresql://kassa:ПАРОЛЬ@localhost:5432/kassa" \
    /opt/kassa/backend/backups/backup_ГГГГММДД_ЧЧММСС.dump
sudo systemctl start kassa-web kassa-worker
```

Фотографии накладных в дамп базы не входят — они архивируются отдельно, рядом с
дампом: `backups/uploads_ГГГГММДД_ЧЧММСС.tar.gz`. Восстанавливаются так:

```bash
sudo -u kassa tar -xzf /opt/kassa/backend/backups/uploads_ГГГГММДД_ЧЧММСС.tar.gz     -C /opt/kassa/backend --strip-components=0
```

Архив содержит папку `uploads/`, поэтому распаковывать надо в `backend/`.
Ретеншн у архивов свой и не пересекается с ретеншном дампов.

### Обновление

```bash
sudo -u kassa /opt/kassa/deploy/scripts/update.sh
```

Только после закрытия магазина. Скрипт снимет бэкап, обновит код, пересоберёт
фронтенд, прогонит тесты и перезапустит сервисы.

Кнопка обновления внутри приложения на сервере отключена
(`ALLOW_SELF_UPDATE=false`) намеренно: пересборка фронтенда занимает минуты, и
все кассы на это время встанут.

### Логи

```bash
sudo journalctl -u kassa-web -f
sudo journalctl -u kassa-worker -f
sudo tail -f /var/log/caddy/kassa.log
```

---

## Если что-то пошло не так

**Магазин открылся пустым.** Перенос не выполнялся, либо `DATABASE_URL` указывает
не на ту базу. Остановите сервисы, проверьте `psql ... -c "SELECT count(*) FROM products;"`.

**`duplicate key value violates unique constraint`** при первой продаже.
Последовательности не сдвинуты — шаг 6.4 прервался. Выполните вручную:

```sql
SELECT setval(pg_get_serial_sequence('sales','id'), (SELECT MAX(id) FROM sales));
```
и так по каждой таблице.

**Время сдвинуто на 5 часов.** Перед переносом не запустили приложение на SQLite,
и миграция времени смен не отработала. Скрипт это проверяет и должен был
отказаться — если вы обошли проверку, восстанавливайтесь из `market.db.perenos`.

**Бот молчит, в логах `409 Conflict`.** Где-то запущен второй поллер: либо старый
компьютер магазина ещё работает, либо `RUN_BACKGROUND_JOBS=true` попал в
`kassa-web`.

**Поиск ничего не находит.** Проверьте, что развёрнута версия с `icontains` —
обычный `LIKE` в PostgreSQL регистрозависим.
