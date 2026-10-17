#!/usr/bin/env bash
# Run EVERY test on the OCI server, against the real MySQL HeatWave.
#   bash scripts/test_on_server.sh          (from the project folder, after deploy/deploy.sh)
#
# The database settings come from .env. The tests use their OWN databases
# (monkey_king_test, monkey_king_migrate_test, monkey_king_fresh_test) and
# never touch the game's database. Without MySQL settings, the MySQL half of
# the tests is skipped - this script makes sure it is not.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python
[ -x "$PY" ] || PY=python3
"$PY" -m pip install -q -r requirements-dev.txt
exec "$PY" - "$@" <<'PYCODE'
import os, subprocess, sys
sys.path.insert(0, ".")
from app.config import load_settings
s = load_settings()
if not s.db_host:
    sys.exit("DB_HOST is empty in .env, so the MySQL tests would be skipped. Fill in .env first.")
env = dict(os.environ, MK_TEST_DB_HOST=s.db_host, MK_TEST_DB_PORT=str(s.db_port),
           MK_TEST_DB_USER=s.db_user, MK_TEST_DB_PASSWORD=s.db_password)
code = subprocess.call([sys.executable, "-m", "pytest", "-q", "-rs", *sys.argv[1:]], env=env)
print("\nAll tests passed on this server's MySQL." if code == 0 else "\nSome tests FAILED (see above).")
sys.exit(code)
PYCODE
