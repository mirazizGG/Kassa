#!/bin/bash
# --- Самолечение от виндовых переносов строк ---------------------------
# Если файл попал на сервер через Windows, каждая строка заканчивается
# лишним символом возврата каретки. Оболочка считает его частью команды
# и падает с ошибкой вида: command not found.
#
# Ничего не проверяем — просто убираем такие символы и перезапускаемся
# один раз. Если их не было, файл не изменится.
if [ -z "${KASSA_CRLF_FIXED:-}" ]; then
    KASSA_CRLF_FIXED=1; export KASSA_CRLF_FIXED
    # Якорь X нужен, потому что подстановка $() отрезает хвостовые символы.
    _CR=$(printf '\rX'); _CR=${_CR%X}
    _LF="$0.lf"
    if tr -d "$_CR" < "$0" > "$_LF" 2>/dev/null && [ -s "$_LF" ]; then
        cat "$_LF" > "$0"
    fi
    rm -f "$_LF"
    exec bash "$0" "$@"
fi
# =====================================================================
# ШАГ 2. ПЕРЕКЛЮЧЕНИЕ с Python на PHP.
#
# ЧТО ДЕЛАЕТ:
#   1. снимает резервную копию базы, накладных и старого сайта;
#   2. распаковывает PHP-версию в ~/kassa;
#   3. берёт DATABASE_URL из старого .env — база ОСТАЁТСЯ ТА ЖЕ;
#   4. обновляет схему (добавляет недостающие столбцы и индексы);
#   5. кладёт интерфейс в корень сайта (вместо Python-версии);
#   6. переносит фотографии накладных туда, откуда их отдаёт веб-сервер;
#   7. снимает Python-приложение с регистрации в панели;
#   8. убирает старое приложение в архивную папку.
#
# ЧЕГО НЕ ДЕЛАЕТ:
#   * НЕ удаляет и НЕ очищает базу данных;
#   * НЕ удаляет старые файлы — переносит их в ~/arxiv-python-<дата>;
#   * НЕ трогает домен и DNS.
#
# Запуск:
#   bash ~/02-switch.sh
# =====================================================================

set -euo pipefail

STAMP=$(date +%Y%m%d-%H%M%S)
NEW_APP="$HOME/kassa"
ARCHIVE_DIR="$HOME/arxiv-python-$STAMP"
BACKUP_DIR="$HOME/kassa-backup-$STAMP"

say()  { printf '%s\n' "$*"; }
step() { printf '\n\033[1m[%s] %s\033[0m\n' "$1" "$2"; }
ok()   { printf '  \033[32m✓\033[0m %s\n' "$*"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$*"; }
die()  { printf '  \033[31m✗ %s\033[0m\n' "$*"; exit 1; }

# --- Выбираем PHP 8.1+ -------------------------------------------------
# В PATH на cPanel обычно лежит старая версия (7.4). Рабочие бинарники
# стоят рядом, по одному на версию — берём самый подходящий.
pick_php() {
    local c v
    for c in /opt/cpanel/ea-php85/root/usr/bin/php              /opt/cpanel/ea-php84/root/usr/bin/php              /opt/cpanel/ea-php83/root/usr/bin/php              /opt/cpanel/ea-php82/root/usr/bin/php              /opt/cpanel/ea-php81/root/usr/bin/php              /opt/alt/php83/usr/bin/php /opt/alt/php82/usr/bin/php              /opt/alt/php81/usr/bin/php "$(command -v php 2>/dev/null)"; do
        [ -x "$c" ] || continue
        v=$("$c" -r 'echo PHP_MAJOR_VERSION*100+PHP_MINOR_VERSION;' 2>/dev/null)
        if [ -n "$v" ] && [ "$v" -ge 801 ] 2>/dev/null; then
            printf '%s' "$c"
            return 0
        fi
    done
    return 1
}
PHP_BIN=$(pick_php) || die "не найден PHP 8.1 или новее"

# --- Корень сайта БЕРЁМ ИЗ ПАНЕЛИ, а не угадываем ----------------------
# На этом аккаунте больше десяти доменов. Ошибиться корнем — значит
# выложить кассу поверх чужого сайта.
KASSA_DOMAIN="${KASSA_DOMAIN:-smart-kassa.uz}"
DOCROOT=""
if command -v uapi >/dev/null 2>&1; then
    DOCROOT=$(uapi --output=json DomainInfo single_domain_data domain="$KASSA_DOMAIN" 2>/dev/null         | tr ',' '
' | grep -m1 '"documentroot"' | cut -d'"' -f4)
fi

# --- Находим всё нужное -----------------------------------------------
OLD=""
for d in "$HOME/smart-kassa" "$HOME/kassa-python" "$HOME/smartkassa"; do
    [ -d "$d/backend" ] && { OLD="$d"; break; }
done

ENVFILE=""
for f in "$OLD/backend/.env" "$OLD/.env"; do
    [ -n "$OLD" ] && [ -f "$f" ] && { ENVFILE="$f"; break; }
done

if [ -z "$DOCROOT" ] || [ ! -d "$DOCROOT" ]; then
    say ""
    say "Не удалось определить корень сайта для домена $KASSA_DOMAIN."
    say "Посмотрите в cPanel -> Domains -> Document Root и введите путь."
    printf "Корень сайта: "
    read -r DOCROOT
fi
[ -n "$DOCROOT" ] && [ -d "$DOCROOT" ] || die "корень сайта не найден"

# --- Что уже лежит в корне ---------------------------------------------
# Мы НИЧЕГО не удаляем. Но оператор должен видеть, с чем касса будет
# соседствовать: этот корень может быть общим с другими проектами.
FOREIGN=""
for e in "$DOCROOT"/*; do
    [ -e "$e" ] || continue
    B=$(basename "$e")
    case "$B" in
        index.php|index.html|assets|favicon*|uploads|cgi-bin) ;;
        *) FOREIGN="$FOREIGN $B" ;;
    esac
done

ARC=""
for f in "$HOME"/kassa-php*.tar.gz; do
    [ -f "$f" ] && { ARC="$f"; break; }
done
[ -n "$ARC" ] || die "архив kassa-php-*.tar.gz не найден в $HOME"

DBURL=""
[ -n "$ENVFILE" ] && DBURL=$(grep -E '^DATABASE_URL=' "$ENVFILE" 2>/dev/null | head -1 | cut -d= -f2- || true)
if [ -z "$DBURL" ]; then
    say ""
    say "DATABASE_URL в старом .env не найден. Введите вручную, например:"
    say "  postgresql://erkatoyu_kuser:ПАРОЛЬ@localhost:5432/erkatoyu_kassa"
    printf "DATABASE_URL: "
    read -r DBURL
fi
[ -n "$DBURL" ] || die "без DATABASE_URL продолжать нельзя"

SECRET=""
[ -n "$ENVFILE" ] && SECRET=$(grep -E '^SECRET_KEY=' "$ENVFILE" 2>/dev/null | head -1 | cut -d= -f2- || true)
if [ ${#SECRET} -lt 32 ]; then
    SECRET=$("$PHP_BIN" -r 'echo bin2hex(random_bytes(32));')
    NEWKEY=1
else
    NEWKEY=0
fi

UP=""
for d in "$OLD/backend/uploads" "$OLD/uploads"; do
    [ -n "$OLD" ] && [ -d "$d" ] && { UP="$d"; break; }
done

# --- Показываем план и просим подтверждения ---------------------------
MASKED=$(printf '%s' "$DBURL" | sed -E 's#(//[^:]+:)[^@]+(@)#\1********\2#')
say ""
say "============================================================"
say "  ПЛАН"
say "============================================================"
say "  Старое приложение  : ${OLD:-нет}  ->  переедет в $ARCHIVE_DIR"
say "  Корень сайта       : $DOCROOT     ->  копия в $BACKUP_DIR"
say "  Новое приложение   : $NEW_APP"
say "  Архив              : $ARC"
say "  База данных        : $MASKED"
say "                       (ОСТАЁТСЯ КАК ЕСТЬ — только читаем и дополняем схему)"
say "  Накладные          : ${UP:-нет}"
say "  PHP                : $PHP_BIN"
if [ -n "$FOREIGN" ]; then
    say ""
    say "  ВНИМАНИЕ: в корне сайта есть ЧУЖИЕ файлы и папки:"
    say "     $FOREIGN"
    say "  Они НЕ БУДУТ удалены — касса ляжет рядом."
fi
[ "$NEWKEY" = "1" ] && say "  SECRET_KEY         : создан новый (все текущие сеансы закроются)" \
                    || say "  SECRET_KEY         : взят из старого .env"
say "============================================================"
say ""
printf "Продолжить? Напишите ровно DA и нажмите Enter: "
read -r ANSWER
[ "$ANSWER" = "DA" ] || die "отменено пользователем"

# --- 1. Резервные копии -----------------------------------------------
step 1 "Резервные копии (до любых изменений)"
mkdir -p "$BACKUP_DIR"

case "$DBURL" in
  postgres*)
    if command -v pg_dump >/dev/null 2>&1; then
        H=$(printf '%s' "$DBURL" | sed -E 's#^[a-z+]+://[^@]*@([^:/]+).*#\1#')
        U=$(printf '%s' "$DBURL" | sed -E 's#^[a-z+]+://([^:]+):.*#\1#')
        P=$(printf '%s' "$DBURL" | sed -E 's#^[a-z+]+://[^:]+:([^@]+)@.*#\1#')
        D=$(printf '%s' "$DBURL" | sed -E 's#.*/([^/?]+)(\?.*)?$#\1#')
        if PGPASSWORD="$P" pg_dump -h "$H" -U "$U" -d "$D" -f "$BACKUP_DIR/db.sql" 2>/dev/null; then
            ok "дамп базы: $BACKUP_DIR/db.sql ($(du -h "$BACKUP_DIR/db.sql" | cut -f1))"
        else
            warn "pg_dump не отработал — копию снимет сам PHP на шаге 5"
        fi
    else
        warn "pg_dump не установлен — копию снимет сам PHP на шаге 5"
    fi ;;
  mysql*)
    if command -v mysqldump >/dev/null 2>&1; then
        H=$(printf '%s' "$DBURL" | sed -E 's#^[a-z+]+://[^@]*@([^:/]+).*#\1#')
        U=$(printf '%s' "$DBURL" | sed -E 's#^[a-z+]+://([^:]+):.*#\1#')
        P=$(printf '%s' "$DBURL" | sed -E 's#^[a-z+]+://[^:]+:([^@]+)@.*#\1#')
        D=$(printf '%s' "$DBURL" | sed -E 's#.*/([^/?]+)(\?.*)?$#\1#')
        mysqldump -h "$H" -u "$U" -p"$P" "$D" > "$BACKUP_DIR/db.sql" 2>/dev/null \
          && ok "дамп базы: $BACKUP_DIR/db.sql" || warn "mysqldump не отработал"
    fi ;;
esac

if [ -n "$UP" ]; then
    cp -r "$UP" "$BACKUP_DIR/uploads" && ok "накладные скопированы в резерв"
fi
[ -n "$ENVFILE" ] && cp "$ENVFILE" "$BACKUP_DIR/old.env" && ok "старый .env сохранён"
cp -r "$DOCROOT" "$BACKUP_DIR/public_html_old" 2>/dev/null && ok "копия корня сайта сохранена"
ok "всё лежит в: $BACKUP_DIR"

# --- 2. Распаковка ----------------------------------------------------
step 2 "Распаковка PHP-версии"
if [ -d "$NEW_APP" ]; then
    mv "$NEW_APP" "$NEW_APP.old-$STAMP"
    warn "прежняя папка $NEW_APP отодвинута в $NEW_APP.old-$STAMP"
fi
mkdir -p "$NEW_APP"
tar -xzf "$ARC" -C "$NEW_APP"
[ -f "$NEW_APP/app/bootstrap.php" ] || die "архив распакован неправильно: нет app/bootstrap.php"
ok "распаковано в $NEW_APP"

# --- 3. Настройки -----------------------------------------------------
step 3 "Настройки (.env)"
# UPLOAD_DIR указываем ЯВНО.
#
# Корень сайта ($DOCROOT) и приложение ($NEW_APP) — разные папки. Без этой
# строки приложение писало бы новые фотографии накладных в
# $NEW_APP/public/uploads, а веб-сервер отдавал бы $DOCROOT/uploads:
# файл сохранялся бы, но не открывался.
cat > "$NEW_APP/.env" <<ENVEOF
APP_ENV=production
SECRET_KEY=$SECRET
DATABASE_URL=$DBURL
SHOP_TIMEZONE=Asia/Tashkent
UPLOAD_DIR=$DOCROOT/uploads
ALLOWED_ORIGINS=
TRUST_PROXY_HEADERS=false
BACKUP_ENABLED=true
BACKUP_RETENTION=30
ALLOW_SELF_UPDATE=false
ENVEOF
chmod 600 "$NEW_APP/.env"
ok "записан $NEW_APP/.env (права 600)"

mkdir -p "$NEW_APP/logs" "$NEW_APP/backups" "$NEW_APP/public/uploads/invoices"
chmod 700 "$NEW_APP/logs" "$NEW_APP/backups"
chmod 755 "$NEW_APP/public/uploads" "$NEW_APP/public/uploads/invoices"
ok "папки созданы"

# --- 4. Схема ---------------------------------------------------------
step 4 "Обновление схемы (данные НЕ трогаются)"
cd "$NEW_APP"
"$PHP_BIN" bin/setup.php || die "setup.php завершился с ошибкой — смотрите вывод выше"
ok "схема обновлена, существующие строки на месте"

say ""
say "  Контрольная копия средствами самого приложения:"
"$PHP_BIN" bin/backup.php || warn "резервная копия не снялась — проверьте позже"

# --- 5. Корень сайта --------------------------------------------------
step 5 "Интерфейс в корень сайта"
# НИЧЕГО НЕ УДАЛЯЕМ.
#
# Этот корень может быть ОБЩИМ с другими проектами: домен
# smart-kassa.uz припаркован на папку главного домена. Очистка
# снесла бы чужие сайты, лежащие рядом.
#
# Старый .htaccess сохраняем отдельно — в нём настройки Passenger,
# и откат сводится к возврату одного этого файла.
cp "$DOCROOT/.htaccess" "$BACKUP_DIR/htaccess-old" 2>/dev/null \
    && ok "старый .htaccess сохранён в резерв"

# Блок выбора версии PHP, сгенерированный cPanel, НУЖНО СОХРАНИТЬ.
# Он задаёт домену PHP 8.3. Без него сайт откатится на версию по
# умолчанию для аккаунта (там 7.4), и приложение просто не запустится.
PHPBLOCK=""
if [ -f "$BACKUP_DIR/htaccess-old" ]; then
    PHPBLOCK=$(sed -n '/# php -- BEGIN cPanel-generated handler/,/# php -- END cPanel-generated handler/p' "$BACKUP_DIR/htaccess-old")
fi

cp -r "$NEW_APP/public/." "$DOCROOT/"
ok "файлы кассы добавлены в $DOCROOT (существующее не тронуто)"
[ -n "$FOREIGN" ] && ok "соседние папки на месте:$FOREIGN"

# index.php должен найти app/ — указываем путь ОБЫЧНЫМ ФАЙЛОМ.
#
# Раньше здесь была строка SetEnv в .htaccess. На боевом хостинге
# модуль mod_env оказался не загружен, и Apache отвечал 500 на ВЕСЬ
# сайт — при этом журнал приложения оставался пустым, потому что до
# PHP выполнение не доходило. Искать такую причину тяжело.
#
# Обычный файл не зависит от того, какие модули собраны в сервере.
printf '%s/app\n' "$NEW_APP" > "$DOCROOT/.kassa-app-path"
chmod 644 "$DOCROOT/.kassa-app-path"
ok "путь к ядру записан в .kassa-app-path"

if [ -n "$PHPBLOCK" ]; then
    if ! grep -q "cPanel-generated handler" "$DOCROOT/.htaccess" 2>/dev/null; then
        printf '\n%s\n' "$PHPBLOCK" >> "$DOCROOT/.htaccess"
        ok "версия PHP из панели сохранена в .htaccess"
    fi
else
    warn "блок версии PHP не найден в старом .htaccess"
    say  "     проверьте: cPanel -> Select PHP Version -> должна быть 8.1+"
fi

# Passenger (Python) больше не нужен
if grep -qi "passenger" "$DOCROOT/.htaccess" 2>/dev/null; then
    sed -i '/[Pp]assenger/d' "$DOCROOT/.htaccess"
    warn "строки Passenger удалены из .htaccess"
fi

chmod 644 "$DOCROOT/.htaccess" "$DOCROOT/index.php" 2>/dev/null || true

# Сбрасываем кэш скомпилированного кода (opcache).
#
# PHP держит разобранные файлы в памяти и перечитывает их с диска не чаще
# чем раз в минуту. Сразу после выкладки это значит, что часть файлов может
# браться новая, а часть — старая. Один раз такое смешение уже давало
# необъяснимую ошибку 500. Сброс делается изнутри веб-сервера: из консоли
# у него отдельная память, оттуда не достать.
RESET="__opcache_reset_$(date +%s)_$$.php"
printf '%s' '<?php if (function_exists("opcache_reset")) { opcache_reset(); } echo "reset-ok";'     > "$DOCROOT/$RESET" 2>/dev/null || true
if [ -f "$DOCROOT/$RESET" ]; then
    R=$(curl -sk --max-time 10 "https://smart-kassa.uz/$RESET" 2>/dev/null         || curl -s --max-time 10 "http://127.0.0.1/$RESET" 2>/dev/null || echo "")
    rm -f "$DOCROOT/$RESET"
    case "$R" in
        *reset-ok*) ok "кэш скомпилированного кода сброшен" ;;
        *) warn "сбросить кэш не вышло — новый код может подхватиться в течение минуты"
           say  "     если что-то ведёт себя странно: cPanel -> Select PHP Version -> Restart PHP" ;;
    esac
fi

# --- 6. Накладные — В КОРЕНЬ САЙТА -------------------------------------
step 6 "Фотографии накладных"
mkdir -p "$DOCROOT/uploads/invoices"
if [ -n "$UP" ] && [ -d "$UP/invoices" ]; then
    cp -r "$UP/invoices/." "$DOCROOT/uploads/invoices/" 2>/dev/null || true
elif [ -n "$UP" ]; then
    cp -r "$UP/." "$DOCROOT/uploads/invoices/" 2>/dev/null || true
fi
N=$(find "$DOCROOT/uploads/invoices" -type f 2>/dev/null | wc -l | tr -d ' ')
ok "фотографий в $DOCROOT/uploads/invoices: $N"
chmod -R 755 "$DOCROOT/uploads" 2>/dev/null || true
# В папке загрузок код выполняться не должен — файл защиты обязателен.
[ -f "$DOCROOT/uploads/.htaccess" ] && ok "защита папки загрузок на месте"     || warn "нет uploads/.htaccess — скопируйте из $NEW_APP/public/uploads/"

# --- 7. Снять Python-приложение с регистрации --------------------------
step 7 "Отключение Passenger (Python)"
# Пока приложение зарегистрировано, веб-сервер отдаёт запросы Python-процессу
# и до PHP они не доходят вовсе. Одних правок .htaccess недостаточно.
UNREGISTERED=0
if command -v uapi >/dev/null 2>&1; then
    APPS=$(uapi --output=json PassengerApps list_applications 2>/dev/null || true)
    for NAME in $(printf '%s' "$APPS" | grep -oE '"name":"[^"]+"' | cut -d'"' -f4 | sort -u); do
        if uapi PassengerApps unregister_application name="$NAME" >/dev/null 2>&1; then
            ok "снято с регистрации: $NAME"
            UNREGISTERED=1
        else
            warn "не удалось снять: $NAME"
        fi
    done
fi
if [ "$UNREGISTERED" = "0" ]; then
    warn "автоматически снять не вышло"
    say  "     СДЕЛАЙТЕ ВРУЧНУЮ, иначе сайт останется на Python:"
    say  "     cPanel -> Setup Python App -> корзина напротив приложения -> Destroy"
fi

# --- 8. Старое приложение в архив -------------------------------------
step 8 "Старое приложение — в архив"
if [ -n "$OLD" ] && [ -d "$OLD" ]; then
    mv "$OLD" "$ARCHIVE_DIR"
    ok "перенесено: $OLD -> $ARCHIVE_DIR"
    say "     удалить можно потом:  rm -rf $ARCHIVE_DIR"
else
    warn "старого приложения не было"
fi

# --- 9. Проверка ------------------------------------------------------
step 9 "Проверка"
sleep 1
HEALTH=$(curl -sk --max-time 10 "https://smart-kassa.uz/health" 2>/dev/null \
      || curl -s --max-time 10 "http://127.0.0.1/health" 2>/dev/null || echo "")
if printf '%s' "$HEALTH" | grep -q '"runtime":"php'; then
    ok "PHP-версия отвечает: $HEALTH"
elif printf '%s' "$HEALTH" | grep -q '"status":"ok"'; then
    warn "отвечает СТАРАЯ (Python) версия: $HEALTH"
    say  "     Passenger ещё перехватывает запросы. Снимите приложение вручную:"
    say  "     cPanel -> Setup Python App -> Destroy, затем перезагрузите страницу."
else
    warn "через HTTP проверить не вышло (возможно, DNS ещё не настроен)"
    say "     проверьте вручную: curl -sk https://smart-kassa.uz/health"
    say "     журнал ошибок:     tail -30 $NEW_APP/logs/php-error.log"
fi

say ""
say "============================================================"
printf '  \033[32mГОТОВО\033[0m\n'
say "============================================================"
say "  Приложение : $NEW_APP"
say "  Сайт       : $DOCROOT"
say "  Резерв     : $BACKUP_DIR"
say "  Старая вер.: $ARCHIVE_DIR"
say ""
say "  Дальше:"
say "   1. Откройте сайт и войдите — пароли те же, что были."
say "   2. Проверьте товары, долги клиентов, историю продаж."
say "   3. Настройте cron на резервные копии:"
say "      $PHP_BIN $NEW_APP/bin/backup.php"
say ""
say "  Если что-то не так — откат в одну команду:"
say "   mv $ARCHIVE_DIR $OLD"
say "   cp $BACKUP_DIR/htaccess-old $DOCROOT/.htaccess"
say "   (файлы кассы можно оставить — старый .htaccess их не использует)"
say ""
