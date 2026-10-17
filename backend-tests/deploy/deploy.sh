#!/usr/bin/env bash
# Setup AND update on the OCI compute instance (Oracle Linux 9), run as opc:
#   bash deploy/deploy.sh
# Run it from inside the cloned project folder (/home/opc/monkey-king).
# To update later: git pull, then run it again. It upgrades the database
# (keeping player data), restarts the game, and plays one test game to prove it works.
set -euo pipefail

cd "$(dirname "$0")/.."
echo "== 1. Python 3.12 and a virtual environment"
sudo dnf install -y python3.12 python3.12-pip
python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt

echo "== 2. Settings"
if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env - edit it now (DB_PASSWORD, OCI_COMPARTMENT_ID), then run this script again."
  exit 1
fi

echo "== 3. Database tables and story (creates, or upgrades an older version)"
.venv/bin/python scripts/setup_db.py

echo "== 4. Open port 80 in the server firewall"
sudo firewall-cmd --permanent --add-service=http || true
sudo firewall-cmd --reload || true

echo "== 5. Run the game as a service"
# use this folder's real path, in case the repo was cloned under another name
sed "s#/home/opc/monkey-king#$(pwd)#g" deploy/monkey-king.service | sudo tee /etc/systemd/system/monkey-king.service >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable --now monkey-king
sudo systemctl restart monkey-king
sleep 3

echo "== 6. Prove it works: health, database, AI, pages, and one whole test game (then deleted)"
.venv/bin/python scripts/check_deployment.py http://127.0.0.1 --play --cleanup
echo "Done. Open http://<your public IP>/ in a browser, and run the same check from a laptop:"
echo "  python scripts/check_deployment.py http://<your public IP>"
