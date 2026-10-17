"""Create or UPGRADE the database, then load the story (seed.sql).

Run on the server, from the project folder, with .env filled in:
    python scripts/setup_db.py

* Empty database: creates every table and loads the story.
* Database from an older version of the game: upgrades its tables first
  (app/migrations.py), keeping player data.
* Safe to run again at any time: it only does what is missing, and the seed
  upserts rows, so story text is refreshed.

    python scripts/setup_db.py --fresh   DELETES the database and starts empty
                                         (asks you to type the name first).
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import mysql.connector  # noqa: E402

from app.config import load_settings  # noqa: E402
from app.migrations import migrate, statements  # noqa: E402,F401  (statements: used by the tests)


def main() -> None:
    s = load_settings()
    if not s.db_host:
        sys.exit("DB_HOST is empty. Fill in .env first (copy .env.example to .env).")
    if not re.fullmatch(r"[A-Za-z0-9_]+", s.db_name):
        sys.exit("DB_NAME may only use letters, numbers and _")
    conn = mysql.connector.connect(host=s.db_host, port=s.db_port, user=s.db_user,
                                   password=s.db_password, autocommit=True, charset="utf8mb4")
    cur = conn.cursor()
    if "--fresh" in sys.argv:
        typed = input(f"This DELETES database '{s.db_name}' and all player data. Type its name to go on: ")
        if typed.strip() != s.db_name:
            sys.exit("Stopped. Nothing was deleted.")
        cur.execute(f"DROP DATABASE IF EXISTS {s.db_name}")
        print(f"deleted database '{s.db_name}'")
    cur.execute(f"CREATE DATABASE IF NOT EXISTS {s.db_name} CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")
    cur.execute(f"USE {s.db_name}")
    before, after = migrate(cur)
    print("  database version: " + (f"{before} -> {after}" if before != after else str(after))
          + ("  (new database)" if before == 0 else ""))
    for table in ("variants", "realms", "pearls", "pearl_signs", "duel_rounds", "assessment_items", "hints"):
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        print(f"  {table:12s} {cur.fetchone()[0]} rows")
    cur.close()
    conn.close()
    print(f"Database '{s.db_name}' is ready.")


if __name__ == "__main__":
    main()
