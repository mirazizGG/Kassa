#!/usr/bin/env bash
# SmartKassa - serverni qo'lda yangilash. Do'kon YOPILGANDAN keyin ishlating.
#
#   sudo -u kassa /opt/kassa/deploy/scripts/update.sh
#
# Ilova ichidagi "Yangilash" tugmasi serverda o'chirilgan (ALLOW_SELF_UPDATE=false):
# savdo paytida avtomatik qayta yig'ish va restart butun do'konni to'xtatadi.
set -euo pipefail

ROOT="${KASSA_ROOT:-/opt/kassa}"
cd "$ROOT"

echo "==> Ochiq smena bor-yo'qligini tekshiring va do'kon yopilganiga ishonch hosil qiling."
read -r -p "Davom etamizmi? [ha/yo'q] " answer
[[ "$answer" == "ha" ]] || { echo "Bekor qilindi."; exit 1; }

echo "==> Yangilashdan oldin zahira nusxa"
sudo systemctl stop kassa-worker
"$ROOT/venv/bin/python" - <<'PY'
import sys
sys.path.insert(0, "/opt/kassa/backend")
from utils.backup import create_backup
path = create_backup()
print("Zahira nusxa:", path or "OLINMADI!")
if not path:
    sys.exit(1)
PY

echo "==> Kod yangilanmoqda"
git pull --ff-only

echo "==> Python paketlari"
"$ROOT/venv/bin/pip" install -q -r backend/requirements.txt

echo "==> Frontend yig'ilmoqda"
cd frontend
npm ci --no-audit --no-fund
npm run build
cd "$ROOT"

echo "==> Testlar"
cd backend
"$ROOT/venv/bin/python" -m pytest -q
cd "$ROOT"

echo "==> Xizmatlar qayta ishga tushirilmoqda"
sudo systemctl restart kassa-web
sudo systemctl start kassa-worker

sleep 3
curl -fsS http://127.0.0.1:8000/health && echo
echo "==> Tayyor."
