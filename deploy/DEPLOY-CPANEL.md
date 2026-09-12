# Развёртывание на cPanel (shared hosting)

Для `smart-kassa.uz` на сервере `37.153.159.11`, пользователь `erkatoyu`.

Эта инструкция — для **шаред-хостинга без root**. Если получите VPS, используйте
[DEPLOY.md](DEPLOY.md): там всё работает как задумано, без компромиссов ниже.

## Что будет работать, а что нет

| | |
|---|---|
| Касса, склад, клиенты, финансы, смены, аудит | **полностью** |
| Бэкапы | через cron, два раза в день |
| Telegram-бот | **выключен** |
| Обновление из приложения | **выключено** |

Бот отключён намеренно: он работает на постоянном long polling, а Passenger
гасит простаивающие процессы. Напоминания о долге и отметки прихода/ухода на
шареде были бы ненадёжными — лучше честно выключить, чем получить «иногда
работает». Отметки посещаемости придётся вести иначе, пока не переедете на VPS.

---

## 1. Домен

В cPanel → **Domains** → Create A Domain добавьте `smart-kassa.uz`.
Document Root оставьте предложенный, например `/home/erkatoyu/domains/smart-kassa.uz/public_html`.

DNS у регистратора домена:

| Тип | Имя | Значение |
|---|---|---|
| A | `@` | `37.153.159.11` |
| A | `www` | `37.153.159.11` |

Проверка: `dig +short smart-kassa.uz` должен вернуть `37.153.159.11`.
Пока не вернёт — SSL не выдастся.

## 2. База данных

cPanel → **PostgreSQL Databases**:

1. Create Database: `kassa` → полное имя будет вида `erkatoyu_kassa`
2. Create User: `kassa` → полное имя `erkatoyu_kassa`, придумайте сильный пароль
3. Add User To Database → все привилегии

Запишите полные имена — они понадобятся в `DATABASE_URL`.

Проверка из SSH:

```bash
psql "postgresql://erkatoyu_kassa:ПАРОЛЬ@localhost:5432/erkatoyu_kassa" -c "SELECT version();"
```

## 3. Распаковка

```bash
mkdir -p ~/smart-kassa
tar -xzf "/home/erkatoyu/Miraziz project/kassa-deploy-2026-09-11.tar.gz" -C ~/smart-kassa
ls ~/smart-kassa          # backend, frontend, deploy, passenger_wsgi.py
```

## 4. Python-приложение в cPanel

cPanel → **Setup Python App** → Create Application:

| Поле | Значение |
|---|---|
| Python version | **3.12** |
| Application root | `smart-kassa` |
| Application URL | `smart-kassa.uz` (корень домена) |
| Application startup file | `passenger_wsgi.py` |
| Application Entry point | `application` |

Нажмите Create. cPanel создаст виртуальное окружение и покажет команду вида
`source /home/erkatoyu/virtualenv/smart-kassa/3.12/bin/activate`. **Скопируйте её** —
она нужна дальше.

Затем установите зависимости:

```bash
source /home/erkatoyu/virtualenv/smart-kassa/3.12/bin/activate
cd ~/smart-kassa
pip install -U pip
pip install -r backend/requirements.txt
```

## 5. Настройки

```bash
cd ~/smart-kassa
cp deploy/env/production.env.example backend/.env
chmod 600 backend/.env
python -c "import secrets; print(secrets.token_hex(32))"   # ключ, скопируйте
nano backend/.env
```

Заполните:

```
APP_ENV=production
SECRET_KEY=<ключ из команды выше>
PRIMARY_ADMIN_PASSWORD=<сильный пароль>
DATABASE_URL=postgresql://erkatoyu_kassa:ПАРОЛЬ@localhost:5432/erkatoyu_kassa
ALLOWED_ORIGINS=https://smart-kassa.uz,https://www.smart-kassa.uz
SHOP_TIMEZONE=Asia/Tashkent
TRUST_PROXY_HEADERS=true
RUN_BACKGROUND_JOBS=false
ALLOW_SELF_UPDATE=false
BACKUP_ENABLED=true
TELEGRAM_BOT_TOKEN=
```

Оставьте `TELEGRAM_BOT_TOKEN` пустым — бот на шареде не запускается.

`ALLOWED_ORIGINS` должен быть заполнен: в режиме `production` приложение
**не стартует** с `*`. Так же с пустым или коротким `SECRET_KEY` — это намеренно.

## 6. Перенос данных магазина

**Порядок важен:** сначала перенос, потом первый запуск. Иначе приложение
создаст своего `miraziz`, база перестанет быть пустой, и скрипт переноса
откажется работать.

На компьютере магазина закройте смены, запустите программу один раз новой
версией (она переведёт время смен в UTC), затем:

```bash
cp backend/market.db market.db.perenos
# загрузите market.db.perenos на сервер в ~/smart-kassa/backend/
```

На сервере:

```bash
source /home/erkatoyu/virtualenv/smart-kassa/3.12/bin/activate
cd ~/smart-kassa/backend
set -a; . ./.env; set +a

python migrate_to_postgres.py --source market.db.perenos --dry-run
```

Сверьте числа с тем, что видите в магазине. Совпало — повторите без `--dry-run`.

**Если магазин новый и переносить нечего** — вместо этого выполните:

```bash
python setup_db.py
```

Скрипт создаст таблицы и первого админа. Он нужен всегда: под Passenger
события старта приложения не выполняются, поэтому база сама не создастся.

После любого обновления схемы повторяйте `python setup_db.py`.

## 7. Запуск

cPanel → Setup Python App → ваше приложение → **Restart**.

Проверка:

```bash
curl -s https://smart-kassa.uz/health
```

Ожидается `{"status":"ok","background_jobs":false,"bot":false}`.
`background_jobs: false` — так и должно быть на шареде.

Откройте `https://smart-kassa.uz`, войдите под `miraziz`.

## 8. SSL

cPanel → **SSL/TLS Status** → отметьте `smart-kassa.uz` и `www` → Run AutoSSL.
Сертификат Let's Encrypt выдаётся автоматически, если DNS уже указывает на сервер.

## 9. Бэкапы через cron

cPanel → **Cron Jobs** → Add New Cron Job, дважды в день:

Common Settings: Twice a day (или вручную `0 12,22 * * *`)

Command:

```
cd /home/erkatoyu/smart-kassa/backend && /home/erkatoyu/virtualenv/smart-kassa/3.12/bin/python run_backup.py >> /home/erkatoyu/kassa-backup.log 2>&1
```

Проверить вручную:

```bash
cd ~/smart-kassa/backend
/home/erkatoyu/virtualenv/smart-kassa/3.12/bin/python run_backup.py
ls -la backups/
```

Копии складываются в `~/smart-kassa/backend/backups/`: база (`backup_*.dump`) и
фотографии накладных (`uploads_*.tar.gz`) — **два файла за одну дату**, для
полного восстановления нужны оба.

**Раз в месяц проверяйте, что копия восстанавливается** — снять копию и
восстановить из копии разные вещи:

```bash
~/smart-kassa/deploy/scripts/backup-verify.sh ~/smart-kassa/backend/backups
```

Скачивайте копии к себе: cPanel → File Manager → `smart-kassa/backend/backups`.
Держать единственную копию на том же сервере, что и базу, — не бэкап.

## 10. Проверка перед тем, как пускать кассиров

- [ ] `https://smart-kassa.uz` открывается, замок зелёный
- [ ] вход под `miraziz` работает **старым** паролем (перенесённым)
- [ ] товары и остатки те же, что были в магазине
- [ ] у клиентов сохранились долги и бонусы
- [ ] даты и время показываются правильно, не сдвинуты на 5 часов
- [ ] открывается смена, проходит пробная продажа, закрывается смена
- [ ] пробная продажа возвращается
- [ ] `curl -s https://smart-kassa.uz/health` отвечает
- [ ] cron-бэкап отработал вручную и создал два файла

---

## Обновление версии

```bash
source /home/erkatoyu/virtualenv/smart-kassa/3.12/bin/activate
cd ~/smart-kassa

# 1. бэкап ДО обновления
cd backend && python run_backup.py && cd ..

# 2. распаковать новый архив поверх
tar -xzf ~/новый-архив.tar.gz -C ~/smart-kassa

# 3. зависимости и схема
pip install -r backend/requirements.txt
cd backend && python setup_db.py && cd ..
```

Затем cPanel → Setup Python App → **Restart**.

Делайте это после закрытия магазина.

## Если что-то пошло не так

**502 или белый экран.** Смотрите `~/smart-kassa/stderr.log` (Passenger пишет туда).
Чаще всего: не заполнен `SECRET_KEY`, `ALLOWED_ORIGINS` остался `*`, или не
установлены зависимости.

**«Internal Server Error» сразу после Create Application.** Нормально, пока не
выполнены шаги 5 и 6 — приложению нечем подключиться к базе.

**Сайт открылся, но пустой магазин.** Перенос данных не выполнялся. Проверьте:
`psql "$DATABASE_URL" -c "SELECT count(*) FROM products;"`

**Время на 5 часов не то.** Перед переносом не запустили программу на SQLite
новой версией. Восстанавливайтесь из `market.db.perenos` и повторите шаг 6.

**Изменения в коде не видны.** Passenger кэширует процесс — нужен Restart из
cPanel либо `touch ~/smart-kassa/tmp/restart.txt`.
