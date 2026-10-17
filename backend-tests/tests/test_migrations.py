"""Review 2, problem 2: a database set up with version 1 must upgrade cleanly.

tests/fixtures/v1_schema.sql and v1_seed.sql are the EXACT files from the first
release (git commit 50fd602). Each test builds a real version-1 database with a
game in progress, upgrades it, and checks that it now matches a fresh install,
keeps the player data, and plays a whole game. MySQL only.
"""

import random
from pathlib import Path

import mysql.connector
import pytest

from app.migrations import SCHEMA_VERSION, current_version, migrate, statements
from conftest import STORY, FixedVariant, mysql_settings  # noqa: F401
from app.engine import Engine
from app.narrator import Narrator

FIX = Path(__file__).resolve().parent / "fixtures"
OLD_DB, FRESH_DB = "monkey_king_migrate_test", "monkey_king_fresh_test"
OLD_SID = "11111111-1111-1111-1111-111111111111"


@pytest.fixture(scope="module")
def cfg():
    c = mysql_settings()
    if not c:
        pytest.skip("MySQL not configured (set MK_TEST_DB_HOST to include MySQL tests)")
    return c


def _connect(cfg, db=None):
    conn = mysql.connector.connect(autocommit=True, **cfg)
    cur = conn.cursor()
    if db:
        cur.execute(f"DROP DATABASE IF EXISTS {db}")
        cur.execute(f"CREATE DATABASE {db} CHARACTER SET utf8mb4")
        cur.execute(f"USE {db}")
    return conn, cur


def _run_file(cur, path):
    for stmt in statements(path.read_text(encoding="utf-8")):
        cur.execute(stmt)


@pytest.fixture
def v1_db(cfg):
    """A version-1 database with one game in progress (half-way through the duel)."""
    conn, cur = _connect(cfg, OLD_DB)
    _run_file(cur, FIX / "v1_schema.sql")
    _run_file(cur, FIX / "v1_seed.sql")
    cur.execute("INSERT INTO sessions (session_id, nickname, variant_id, hairs_left, stage) "
                "VALUES (%s, 'OldPlayer', 'V2', 2, 'duel')", (OLD_SID,))
    cur.execute("INSERT INTO unlocks (session_id, pearl_id, predicted_ok, actions_before) VALUES (%s, 'P1', 1, 2)",
                (OLD_SID,))
    cur.execute("INSERT INTO duel_answers (session_id, round_no, try_no, said_lie, proof_pearl, is_correct) "
                "VALUES (%s, 1, 1, 1, 'P2', 1)", (OLD_SID,))
    yield cur
    cur.execute(f"DROP DATABASE IF EXISTS {OLD_DB}")
    cur.close()
    conn.close()


def _columns(cur):
    cur.execute("SELECT TABLE_NAME, COLUMN_NAME, ORDINAL_POSITION, COLUMN_TYPE, IS_NULLABLE, COLUMN_DEFAULT "
                "FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() "
                "ORDER BY TABLE_NAME, ORDINAL_POSITION")
    return cur.fetchall()


def _engine_on(cfg, db, variant="V1"):
    from app.store_mysql import MySQLStore
    store = MySQLStore(cfg["host"], cfg["port"], cfg["user"], cfg["password"], db)
    return Engine(store, Narrator(None, STORY["fallbacks"]), STORY, rng=FixedVariant(variant))


def test_old_database_is_recognised_as_version_1(v1_db):
    assert current_version(v1_db) == 1


def test_the_review_problem_is_real_without_the_upgrade(cfg, v1_db):
    """Before upgrading, the new code cannot start a game on the old tables."""
    with pytest.raises(mysql.connector.Error):
        _engine_on(cfg, OLD_DB).start("NewPlayer")


def test_upgrade_matches_a_fresh_install_exactly(cfg, v1_db):
    assert migrate(v1_db, log=lambda _: None) == (1, SCHEMA_VERSION)
    upgraded = _columns(v1_db)
    conn, fresh = _connect(cfg, FRESH_DB)
    try:
        assert migrate(fresh, log=lambda _: None) == (0, SCHEMA_VERSION)
        assert upgraded == _columns(fresh)      # same tables, columns, order, types, defaults
        for table in ("pearls", "duel_rounds", "hints", "assessment_items"):
            v1_db.execute(f"SELECT COUNT(*) FROM {table}")
            fresh.execute(f"SELECT COUNT(*) FROM {table}")
            assert v1_db.fetchone() == fresh.fetchone(), table
        v1_db.execute("SELECT reason_ok FROM duel_rounds WHERE reason_ok = ''")
        assert v1_db.fetchall() == []           # the story text was filled in by the seed
    finally:
        fresh.execute(f"DROP DATABASE IF EXISTS {FRESH_DB}")
        fresh.close()
        conn.close()


def test_upgrade_keeps_player_data(v1_db):
    migrate(v1_db, log=lambda _: None)
    v1_db.execute("SELECT nickname, stage, hairs_left, LENGTH(pearl_salt) FROM sessions WHERE session_id = %s",
                  (OLD_SID,))
    assert v1_db.fetchone() == ("OldPlayer", "duel", 2, 32)   # the old game got its own secret
    v1_db.execute("SELECT proof, reason, is_correct FROM duel_answers WHERE session_id = %s", (OLD_SID,))
    assert v1_db.fetchall() == [("P2", "", 1)]
    v1_db.execute("SELECT pearl_id FROM unlocks WHERE session_id = %s", (OLD_SID,))
    assert v1_db.fetchall() == [("P1",)]


def test_upgrade_is_safe_to_run_again(v1_db):
    migrate(v1_db, log=lambda _: None)
    before = _columns(v1_db)
    assert migrate(v1_db, log=lambda _: None) == (SCHEMA_VERSION, SCHEMA_VERSION)
    assert _columns(v1_db) == before


def test_upgrade_finishes_after_stopping_half_way(v1_db):
    """MySQL cannot undo ALTER TABLE, so an upgrade cut off in the middle must be finishable."""
    v1_db.execute("ALTER TABLE pearls ADD COLUMN visual VARCHAR(200) AFTER title")
    v1_db.execute("ALTER TABLE duel_answers CHANGE COLUMN proof_pearl proof VARCHAR(20) NOT NULL")
    assert current_version(v1_db) == 1
    assert migrate(v1_db, log=lambda _: None) == (1, SCHEMA_VERSION)
    assert current_version(v1_db) == SCHEMA_VERSION


def test_a_whole_game_plays_on_the_upgraded_database(cfg, v1_db):
    from conftest import play_to
    migrate(v1_db, log=lambda _: None)
    engine = _engine_on(cfg, OLD_DB, variant="V3")
    sid = play_to(engine, STORY, "done", nickname="AfterUpgrade")
    assert engine.state(sid)["stage"] == "done"
    assert engine.teacher()["players"] >= 1


def test_server_refuses_an_old_database_with_clear_advice(cfg, v1_db, monkeypatch):
    from app.config import load_settings
    from app.main import build_store
    monkeypatch.setenv("STORE", "mysql")
    monkeypatch.setenv("DB_HOST", cfg["host"])
    monkeypatch.setenv("DB_PORT", str(cfg["port"]))
    monkeypatch.setenv("DB_USER", cfg["user"])
    monkeypatch.setenv("DB_PASSWORD", cfg["password"])
    monkeypatch.setenv("DB_NAME", OLD_DB)
    monkeypatch.setenv("FALLBACK_TO_MEMORY", "0")
    with pytest.raises(RuntimeError, match="version 1.*setup_db.py"):
        build_store(load_settings(), STORY)
    migrate(v1_db, log=lambda _: None)
    assert build_store(load_settings(), STORY).kind == "mysql"
