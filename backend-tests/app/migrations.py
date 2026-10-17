"""Database upgrades (review 2, problem 2).

`CREATE TABLE IF NOT EXISTS` never changes a table that already exists, so a
database set up with version 1 of the game kept its old columns and the new
code failed on it. This module fixes that:

* `schema_version` records which version a database is on.
* `migrate()` finds the version (also for old databases that have no
  `schema_version` table yet, by looking at their columns), runs each missing
  upgrade step in order, then runs schema.sql (creates any new tables) and
  seed.sql (refreshes the story text), and records the new version.
* Every step checks before it changes anything, so running it twice, or again
  after it stopped half-way, is safe. (MySQL cannot undo ALTER TABLE inside a
  transaction, so "check first" is what makes a half-finished upgrade safe.)

Player data is kept. Used by scripts/setup_db.py; the server only CHECKS the
version at startup (it never changes tables by itself).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"

# Version 1: the first release.  Version 2: the review fixes (pictures, reasons,
# two-pearl proofs, per-game pearl codes, before/after questions).
SCHEMA_VERSION = 2


def statements(sql_text: str) -> list[str]:
    """Split a .sql file into statements. Statements end with ';' at a line end."""
    no_comments = "\n".join(line for line in sql_text.splitlines() if not line.strip().startswith("--"))
    return [s.strip() for s in re.split(r";\s*\n", no_comments + "\n") if s.strip()]


# ------------------------------------------------------------ looking

def _db(cur) -> str:
    cur.execute("SELECT DATABASE()")
    return cur.fetchone()[0]


def table_exists(cur, table: str) -> bool:
    cur.execute("SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s",
                (_db(cur), table))
    return cur.fetchone()[0] > 0


def column_exists(cur, table: str, column: str) -> bool:
    cur.execute("SELECT COUNT(*) FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND COLUMN_NAME = %s", (_db(cur), table, column))
    return cur.fetchone()[0] > 0


def current_version(cur) -> int:
    """0 = empty database. Old databases without schema_version are recognised by their columns."""
    if table_exists(cur, "schema_version"):
        cur.execute("SELECT COALESCE(MAX(version), 0) FROM schema_version")
        version = int(cur.fetchone()[0])
        if version:
            return version
    if not table_exists(cur, "sessions"):
        return 0
    return 2 if column_exists(cur, "sessions", "pearl_salt") else 1


# ------------------------------------------------------------ steps

def _add_column(cur, table: str, column: str, definition: str) -> None:
    if not column_exists(cur, table, column):
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _upgrade_1_to_2(cur) -> None:
    _add_column(cur, "pearls", "visual", "VARCHAR(200) AFTER title")
    _add_column(cur, "duel_rounds", "proof_mode", "VARCHAR(4) NOT NULL DEFAULT 'any' AFTER proof_pearls")
    # Existing rows get '' for the reasons; seed.sql fills in the real text right after.
    _add_column(cur, "duel_rounds", "reason_ok", "VARCHAR(120) NOT NULL AFTER proof_mode")
    _add_column(cur, "duel_rounds", "reason_no1", "VARCHAR(120) NOT NULL AFTER reason_ok")
    _add_column(cur, "duel_rounds", "reason_no2", "VARCHAR(120) NOT NULL AFTER reason_no1")
    _add_column(cur, "sessions", "pearl_salt", "VARCHAR(32) NOT NULL AFTER legend_step")
    # Games started under version 1 get their own secret too, so they can carry on.
    cur.execute("UPDATE sessions SET pearl_salt = LEFT(SHA2(CONCAT(session_id, RAND()), 256), 32) "
                "WHERE pearl_salt = ''")
    if column_exists(cur, "duel_answers", "proof_pearl"):   # one pearl -> up to two, e.g. 'P2,P3'
        cur.execute("ALTER TABLE duel_answers CHANGE COLUMN proof_pearl proof VARCHAR(20) NOT NULL")
    _add_column(cur, "duel_answers", "reason", "VARCHAR(120) NOT NULL AFTER proof")
    # The new tables (assessment_items, assessment_answers) come from schema.sql, run next.


UPGRADES: dict[int, Callable[[Any], None]] = {1: _upgrade_1_to_2}   # from-version -> step


# ------------------------------------------------------------ running

def migrate(cur, log: Callable[[str], None] = print) -> tuple[int, int]:
    """Bring the database `cur` is using up to SCHEMA_VERSION. Returns (before, after)."""
    before = current_version(cur)
    if before > SCHEMA_VERSION:
        raise RuntimeError(f"Database is version {before}, newer than this code ({SCHEMA_VERSION}). "
                           "Update the code instead.")
    for version in range(max(before, 1), SCHEMA_VERSION):
        if before == 0:
            break                                   # empty database: schema.sql builds the latest tables
        log(f"upgrading database from version {version} to {version + 1}")
        UPGRADES[version](cur)
    for name in ("schema.sql", "seed.sql"):
        for stmt in statements((SQL_DIR / name).read_text(encoding="utf-8")):
            cur.execute(stmt)
        log(f"ran sql/{name}")
    cur.execute("INSERT IGNORE INTO schema_version (version) VALUES (%s)", (SCHEMA_VERSION,))
    return before, SCHEMA_VERSION
