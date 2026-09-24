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
# ШАГ 1. РАЗВЕДКА. Этот скрипт НИЧЕГО НЕ МЕНЯЕТ.
#
# Он только смотрит, что сейчас на сервере, и печатает отчёт.
# Прочитайте отчёт целиком, прежде чем запускать 02-switch.sh.
#
# Запуск:
#   bash ~/01-check.sh
# =====================================================================

set -u

say()  { printf '%s\n' "$*"; }
head2() { printf '\n\033[1m=== %s ===\033[0m\n' "$*"; }
ok()   { printf '  \033[32m✓\033[0m %s\n' "$*"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$*"; }
bad()  { printf '  \033[31m✗\033[0m %s\n' "$*"; }

PROBLEMS=0

head2 "Кто и где"
say "  Пользователь : $(whoami)"
say "  Домашний кат.: $HOME"
say "  Сервер       : $(hostname 2>/dev/null || echo '?')"

# --- Старое приложение -------------------------------------------------
head2 "Старое приложение (Python)"
OLD=""
for d in "$HOME/smart-kassa" "$HOME/kassa-python" "$HOME/app" "$HOME/smartkassa"; do
    if [ -d "$d/backend" ] || [ -f "$d/passenger_wsgi.py" ]; then OLD="$d"; break; fi
done
if [ -n "$OLD" ]; then
    ok "найдено: $OLD"
    say "     размер: $(du -sh "$OLD" 2>/dev/null | cut -f1)"
    [ -f "$OLD/passenger_wsgi.py" ] && say "     passenger_wsgi.py на месте"
else
    warn "папка Python-приложения не найдена в обычных местах"
    say "     посмотрите сами:  ls -la \$HOME"
fi

# --- Фотографии накладных ---------------------------------------------
head2 "Фотографии накладных (их НЕТ в базе!)"
UP=""
for d in "$OLD/backend/uploads" "$OLD/uploads" "$HOME/uploads"; do
    [ -n "$d" ] && [ -d "$d" ] && { UP="$d"; break; }
done
if [ -n "$UP" ]; then
    N=$(find "$UP" -type f 2>/dev/null | wc -l | tr -d ' ')
    ok "найдено: $UP  ($N файлов, $(du -sh "$UP" 2>/dev/null | cut -f1))"
    [ "$N" -gt 0 ] && warn "ЭТИ ФАЙЛЫ НУЖНО ПЕРЕНЕСТИ — в дампе базы их нет"
else
    warn "папка uploads не найдена (возможно, накладные не загружали)"
fi

# --- Настройки старого приложения --------------------------------------
head2 "Подключение к базе (из старого .env)"
ENVFILE=""
for f in "$OLD/backend/.env" "$OLD/.env"; do
    [ -n "$f" ] && [ -f "$f" ] && { ENVFILE="$f"; break; }
done
DBURL=""
if [ -n "$ENVFILE" ]; then
    ok "файл настроек: $ENVFILE"
    DBURL=$(grep -E '^DATABASE_URL=' "$ENVFILE" 2>/dev/null | head -1 | cut -d= -f2-)
    if [ -n "$DBURL" ]; then
        MASKED=$(printf '%s' "$DBURL" | sed -E 's#(//[^:]+:)[^@]+(@)#\1********\2#')
        ok "DATABASE_URL = $MASKED"
        case "$DBURL" in
            postgres*) say "     тип: PostgreSQL — PHP-версия работает с ним напрямую" ;;
            mysql*)    say "     тип: MySQL — PHP-версия работает с ним напрямую" ;;
            *)         warn "тип не распознан" ;;
        esac
    else
        bad "DATABASE_URL в файле не найден"; PROBLEMS=$((PROBLEMS+1))
    fi
    SK=$(grep -cE '^SECRET_KEY=.+' "$ENVFILE" 2>/dev/null || true)
    [ "${SK:-0}" -gt 0 ] && say "     SECRET_KEY есть (перенесём — старые токены не понадобятся)"
else
    bad "старый .env не найден — DATABASE_URL придётся ввести вручную"
    PROBLEMS=$((PROBLEMS+1))
fi

# --- Проверка живости базы --------------------------------------------
head2 "База данных отвечает?"
if [ -n "$DBURL" ]; then
    DBHOST=$(printf '%s' "$DBURL" | sed -E 's#^[a-z+]+://[^@]*@([^:/]+).*#\1#')
    DBNAME=$(printf '%s' "$DBURL" | sed -E 's#.*/([^/?]+)(\?.*)?$#\1#')
    DBUSER=$(printf '%s' "$DBURL" | sed -E 's#^[a-z+]+://([^:]+):.*#\1#')
    DBPASS=$(printf '%s' "$DBURL" | sed -E 's#^[a-z+]+://[^:]+:([^@]+)@.*#\1#')
    say "  хост: $DBHOST | база: $DBNAME | пользователь: $DBUSER"
    case "$DBURL" in
      postgres*)
        if command -v psql >/dev/null 2>&1; then
            CNT=$(PGPASSWORD="$DBPASS" psql -h "$DBHOST" -U "$DBUSER" -d "$DBNAME" -tAc \
                 "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'" 2>/dev/null || echo "")
            if [ -n "$CNT" ]; then
                ok "подключение есть, таблиц: $CNT"
                for t in employees products clients sales sale_items shifts audit_logs; do
                    R=$(PGPASSWORD="$DBPASS" psql -h "$DBHOST" -U "$DBUSER" -d "$DBNAME" -tAc "SELECT count(*) FROM $t" 2>/dev/null || echo "-")
                    printf '     %-12s %s\n' "$t" "$R"
                done
            else
                bad "подключиться не удалось"; PROBLEMS=$((PROBLEMS+1))
            fi
        else
            warn "psql не установлен — проверю позже через PHP"
        fi ;;
      mysql*)
        if command -v mysql >/dev/null 2>&1; then
            CNT=$(mysql -h "$DBHOST" -u "$DBUSER" -p"$DBPASS" -D "$DBNAME" -sN -e \
                 "SELECT count(*) FROM information_schema.tables WHERE table_schema='$DBNAME'" 2>/dev/null || echo "")
            [ -n "$CNT" ] && ok "подключение есть, таблиц: $CNT" || { bad "подключиться не удалось"; PROBLEMS=$((PROBLEMS+1)); }
        else
            warn "mysql-клиент не установлен — проверю позже через PHP"
        fi ;;
    esac
fi

# --- Куда смотрит домен ------------------------------------------------
head2 "Корень сайта (document root)"
DOCROOT=""
for d in "$HOME/public_html" "$HOME/domains/smart-kassa.uz/public_html" \
         "$HOME/public_html/smart-kassa.uz" "$HOME/www"; do
    [ -d "$d" ] && { DOCROOT="$d"; break; }
done
if [ -n "$DOCROOT" ]; then
    ok "найден: $DOCROOT"
    say "     содержимое:"
    ls -A "$DOCROOT" 2>/dev/null | head -12 | sed 's/^/       /'
    if [ -f "$DOCROOT/.htaccess" ] && grep -qi "passenger" "$DOCROOT/.htaccess" 2>/dev/null; then
        warn "в .htaccess есть настройки Passenger (Python) — их заменим"
    fi
else
    bad "корень сайта не найден"; PROBLEMS=$((PROBLEMS+1))
fi

if command -v uapi >/dev/null 2>&1; then
    say ""
    say "  Домены в панели:"
    uapi --output=json DomainInfo list_domains 2>/dev/null \
      | tr ',' '\n' | grep -oE '"[a-z0-9.-]+\.[a-z]{2,}"' | tr -d '"' | sort -u | sed 's/^/       /' | head -10 \
      || say "       (uapi не ответил — смотрите в панели cPanel → Domains)"
fi

# --- Приложение Python в панели ----------------------------------------
head2 "Python-приложение в панели (Passenger)"
if command -v uapi >/dev/null 2>&1; then
    APPS=$(uapi --output=json PassengerApps list_applications 2>/dev/null || true)
    if printf '%s' "$APPS" | grep -q '"name"'; then
        printf '%s' "$APPS" | tr ',' '
' | grep -E '"(name|path|domain|base_uri)"' | sed 's/^/     /' | head -12
        warn "приложение зарегистрировано — его нужно СНЯТЬ, иначе Passenger"
        say  "     продолжит перехватывать запросы и PHP не увидит их вовсе."
        say  "     Это сделает 02-switch.sh, либо вручную:"
        say  "     cPanel -> Setup Python App -> корзина напротив приложения"
    else
        say "     (uapi не вернул список — проверьте в cPanel -> Setup Python App)"
    fi
else
    warn "uapi недоступен — проверьте в cPanel -> Setup Python App"
fi

# --- PHP ---------------------------------------------------------------
head2 "PHP"
if command -v php >/dev/null 2>&1; then
    V=$(php -r 'echo PHP_VERSION;' 2>/dev/null)
    MAJOR=$(php -r 'echo PHP_MAJOR_VERSION*100+PHP_MINOR_VERSION;' 2>/dev/null)
    if [ "${MAJOR:-0}" -ge 801 ]; then ok "php $V"; else bad "php $V — нужна 8.1 или новее"; PROBLEMS=$((PROBLEMS+1)); fi
    say "  путь: $(command -v php)"
    for e in pdo_pgsql pdo_mysql mbstring openssl zip fileinfo curl opcache; do
        if php -m 2>/dev/null | grep -qix "$e"; then ok "расширение $e"; else
            case "$e" in
              pdo_pgsql|pdo_mysql) warn "нет $e (нужно только для своего типа базы)" ;;
              opcache) warn "нет opcache — будет медленнее, включите в cPanel" ;;
              zip) warn "нет zip — архив накладных не соберётся, остальное работает" ;;
              *) bad "НЕТ $e — обязательно"; PROBLEMS=$((PROBLEMS+1)) ;;
            esac
        fi
    done
else
    bad "php не найден в PATH"; PROBLEMS=$((PROBLEMS+1))
fi

# --- Архив -------------------------------------------------------------
head2 "Архив новой версии"
ARC=""
for f in "$HOME"/kassa-php*.tar.gz "$HOME"/*/kassa-php*.tar.gz; do
    [ -f "$f" ] && { ARC="$f"; break; }
done
if [ -n "$ARC" ]; then
    ok "найден: $ARC  ($(du -h "$ARC" 2>/dev/null | cut -f1))"
    tar -tzf "$ARC" >/dev/null 2>&1 && ok "архив читается" || { bad "архив повреждён"; PROBLEMS=$((PROBLEMS+1)); }
else
    bad "архив kassa-php-*.tar.gz не найден в \$HOME"
    say "     загрузите его через cPanel → File Manager в /home/$(whoami)/"
    PROBLEMS=$((PROBLEMS+1))
fi

# --- Домен -------------------------------------------------------------
head2 "DNS домена"
if command -v dig >/dev/null 2>&1; then
    NS=$(dig +short NS smart-kassa.uz 2>/dev/null | head -3)
    A=$(dig +short A smart-kassa.uz 2>/dev/null | head -2)
    if [ -n "$NS" ]; then ok "NS-записи: $(echo $NS | tr '\n' ' ')"; else
        bad "NS-записей НЕТ — домен не делегирован у регистратора"
        say "     сайт не откроется по адресу smart-kassa.uz, пока это не исправят"
        say "     это НЕ проблема сервера — решается в кабинете регистратора"
    fi
    [ -n "$A" ] && ok "A-запись: $A" || warn "A-записи нет"
else
    warn "dig не установлен, проверьте DNS снаружи"
fi

# --- Итог --------------------------------------------------------------
head2 "Итог"
say "  Старое приложение : ${OLD:-НЕ НАЙДЕНО}"
say "  Накладные         : ${UP:-нет}"
say "  Корень сайта      : ${DOCROOT:-НЕ НАЙДЕН}"
say "  Архив             : ${ARC:-НЕ НАЙДЕН}"
say ""
if [ "$PROBLEMS" -eq 0 ]; then
    printf '  \033[32mВсё на месте. Можно запускать 02-switch.sh\033[0m\n'
else
    printf '  \033[31mПроблем: %s. Сначала устраните их.\033[0m\n' "$PROBLEMS"
fi
say ""
say "  База данных при переключении НЕ ТРОГАЕТСЯ — она в отдельном сервере СУБД,"
say "  а не в файлах. Удаление папки приложения на неё не влияет."
say ""
