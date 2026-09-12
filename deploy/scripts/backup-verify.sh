#!/usr/bin/env bash
# Zahira nusxani HAQIQATDAN tiklanadimi - tekshiradi.
#
# Nusxa olinishi va nusxadan TIKLANISHI - ikki xil narsa. Bu skript oxirgi
# nusxani vaqtinchalik bazaga tiklab, jadvallar sonini sanaydi va o'chiradi.
# Oyda bir marta ishlating.
set -euo pipefail

BACKUP_DIR="${1:-/opt/kassa/backend/backups}"
LATEST="$(ls -t "$BACKUP_DIR"/backup_* 2>/dev/null | head -1)"
[[ -n "$LATEST" ]] || { echo "Zahira nusxa topilmadi: $BACKUP_DIR"; exit 1; }

echo "Tekshirilmoqda: $LATEST"
TMPDB="kassa_restore_test_$$"

if [[ "$LATEST" == *.dump ]]; then
    createdb "$TMPDB"
    trap 'dropdb --if-exists "$TMPDB"' EXIT
    pg_restore --no-owner --no-privileges -d "$TMPDB" "$LATEST"
    psql -d "$TMPDB" -tAc \
        "SELECT 'sales=' || (SELECT count(*) FROM sales) ||
                ' products=' || (SELECT count(*) FROM products) ||
                ' clients=' || (SELECT count(*) FROM clients)"
else
    sqlite3 "$LATEST" \
        "SELECT 'sales=' || (SELECT count(*) FROM sales) ||
                ' products=' || (SELECT count(*) FROM products) ||
                ' clients=' || (SELECT count(*) FROM clients);"
fi

echo "Nusxa o'qildi va tiklandi - yaroqli."
