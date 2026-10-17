"""MySQL HeatWave store: reads story tables, writes play tables.

Same method names as MemoryStore. Every query uses %s parameters (never
string formatting), so a nickname or a chapter cannot inject SQL.

atomic(): everything the engine does for ONE player action runs inside one
transaction. If any step fails (network blip, database restart), all of it
is rolled back, so the game is never left half-saved and the child can
simply retry (review fix: a failed save used to leave players stuck).
"""

from __future__ import annotations

import json
import threading
from contextlib import contextmanager
from typing import Any, Iterator

import mysql.connector
from mysql.connector import errorcode, pooling


class MySQLStore:
    kind = "mysql"

    def __init__(self, host: str, port: int, user: str, password: str, database: str,
                 pool_size: int = 5):
        self._pool = pooling.MySQLConnectionPool(
            pool_name="monkey_king",
            pool_size=pool_size,
            pool_reset_session=True,
            host=host, port=port, user=user, password=password, database=database,
            autocommit=True,
            charset="utf8mb4",
            connection_timeout=5,
        )
        self._local = threading.local()   # the transaction this thread is inside, if any

    # ---------------------------------------------------------- plumbing
    @contextmanager
    def atomic(self) -> Iterator[None]:
        """All store calls inside this block share one transaction: all saved, or none.

        Re-entrant: an inner atomic() joins the outer one. Commit happens once,
        at the end of the outermost block; any exception rolls everything back.
        """
        if getattr(self._local, "conn", None) is not None:
            yield
            return
        conn = self._pool.get_connection()
        try:
            # An explicit START TRANSACTION. (Setting .autocommit = False on a POOLED
            # connection is silently ignored by mysql-connector - a test caught that.)
            conn.start_transaction()
            self._local.conn = conn
            try:
                yield
                conn.commit()
            except BaseException:
                conn.rollback()
                raise
        finally:
            self._local.conn = None
            conn.close()   # back to the pool

    @contextmanager
    def _cursor(self, dictionary: bool = True) -> Iterator[Any]:
        tx = getattr(self._local, "conn", None)
        conn = tx or self._pool.get_connection()
        try:
            cur = conn.cursor(dictionary=dictionary)
            try:
                yield cur
            finally:
                cur.close()
        finally:
            if tx is None:
                conn.close()  # returns the connection to the pool

    def _all(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        with self._cursor() as cur:
            cur.execute(sql, params)
            return list(cur.fetchall())

    def _one(self, sql: str, params: tuple = ()) -> dict[str, Any] | None:
        rows = self._all(sql, params)
        return rows[0] if rows else None

    def _run(self, sql: str, params: tuple = ()) -> None:
        with self._cursor() as cur:
            cur.execute(sql, params)

    def _insert_with_try_no(self, table: str, where_sql: str, where_params: tuple,
                            insert_sql: str, insert_params_after_try: tuple) -> int:
        """Pick try_no = MAX(try_no)+1 and insert it, inside a transaction.

        SELECT ... FOR UPDATE locks the session's rows, so two clicks
        arriving together cannot both get the same try number. If the engine
        already opened a transaction (atomic), this joins it.
        """
        with self.atomic(), self._cursor(dictionary=False) as cur:
            cur.execute(f"SELECT COALESCE(MAX(try_no), 0) + 1 FROM {table} WHERE {where_sql} FOR UPDATE",
                        where_params)
            (try_no,) = cur.fetchone()
            cur.execute(insert_sql, (*where_params, try_no, *insert_params_after_try))
            return int(try_no)

    def ping(self) -> bool:
        return self._one("SELECT 1 AS ok") is not None

    def lock_session(self, session_id: str) -> None:
        """Inside atomic(): hold this game's row until commit, so two clicks are saved one after the other."""
        self._all("SELECT session_id FROM sessions WHERE session_id = %s FOR UPDATE", (session_id,))

    def schema_version(self) -> int:
        """Which upgrade the database is on (see app/migrations.py)."""
        from app.migrations import current_version
        with self._cursor(dictionary=False) as cur:
            return current_version(cur)

    # ------------------------------------------------------------ content
    def variant_ids(self) -> list[str]:
        return [r["variant_id"] for r in self._all("SELECT variant_id FROM variants ORDER BY variant_id")]

    def variant(self, variant_id: str) -> dict[str, Any] | None:
        row = self._one("SELECT variant_id, culprit, culprit_words, ending_text FROM variants "
                        "WHERE variant_id = %s", (variant_id,))
        if row:
            row["culprit_words"] = [w for w in (row["culprit_words"] or "").split(",") if w]
        return row

    def realms(self) -> list[dict[str, Any]]:
        return self._all("SELECT realm_id, name, display_order, image_url, look_text, listen_text "
                         "FROM realms ORDER BY display_order, realm_id")

    def pearls(self) -> list[dict[str, Any]]:
        rows = self._all("SELECT pearl_id, realm_id, true_order, time_label, title, visual, shared_text, "
                         "predict_q, predict_ok, predict_no1, predict_no2 FROM pearls ORDER BY true_order")
        for r in rows:
            r["visual"] = json.loads(r["visual"]) if r["visual"] else None
        return rows

    def sign(self, pearl_id: str, variant_id: str) -> str | None:
        row = self._one("SELECT sign_text FROM pearl_signs WHERE pearl_id = %s AND variant_id = %s",
                        (pearl_id, variant_id))
        return row["sign_text"] if row else None

    def duel_round(self, round_no: int, variant_id: str) -> dict[str, Any] | None:
        # The doc's rule: the variant's own row wins, otherwise the shared 'ALL' row.
        return self._one(
            "SELECT round_no, variant_id, form_name, claim_text, is_lie, proof_pearls, proof_mode, "
            "reason_ok, reason_no1, reason_no2 FROM duel_rounds "
            "WHERE round_no = %s AND variant_id IN (%s, 'ALL') "
            "ORDER BY variant_id = 'ALL' LIMIT 1",
            (round_no, variant_id),
        )

    def hint(self, puzzle_key: str, level_no: int) -> str | None:
        row = self._one("SELECT hint_text FROM hints WHERE puzzle_key = %s AND level_no = %s",
                        (puzzle_key, level_no))
        return row["hint_text"] if row else None

    def assessment_items(self, phase: str) -> list[dict[str, Any]]:
        return self._all("SELECT item_id, phase, skill, question, choice_ok, choice_no1, choice_no2 "
                         "FROM assessment_items WHERE phase = %s ORDER BY item_id", (phase,))

    # ----------------------------------------------------------- sessions
    def create_session(self, session_id: str, nickname: str, variant_id: str, pearl_salt: str,
                       stage: str = "pretest") -> None:
        self._run("INSERT INTO sessions (session_id, nickname, variant_id, pearl_salt, stage) "
                  "VALUES (%s, %s, %s, %s, %s)", (session_id, nickname, variant_id, pearl_salt, stage))

    def session(self, session_id: str) -> dict[str, Any] | None:
        return self._one("SELECT session_id, nickname, variant_id, hairs_left, stage, legend_step, pearl_salt "
                         "FROM sessions WHERE session_id = %s", (session_id,))

    def update_session(self, session_id: str, **fields: Any) -> None:
        allowed = {"hairs_left", "stage", "legend_step"}
        bad = set(fields) - allowed
        if bad:
            raise ValueError(f"cannot update {bad}")
        # Column names come only from the fixed `allowed` set above, never from user input.
        sets = ", ".join(f"{k} = %s" for k in fields)
        self._run(f"UPDATE sessions SET {sets} WHERE session_id = %s", (*fields.values(), session_id))

    # --------------------------------------------------------------- play
    def log_action(self, session_id: str, realm_id: str, action: str) -> None:
        self._run("INSERT INTO actions_log (session_id, realm_id, action) VALUES (%s, %s, %s)",
                  (session_id, realm_id, action))

    def actions(self, session_id: str) -> list[dict[str, Any]]:
        return self._all("SELECT session_id, realm_id, action FROM actions_log WHERE session_id = %s "
                         "ORDER BY id", (session_id,))

    def add_unlock(self, session_id: str, pearl_id: str, predicted_ok: bool, actions_before: int) -> None:
        try:
            self._run("INSERT INTO unlocks (session_id, pearl_id, predicted_ok, actions_before) "
                      "VALUES (%s, %s, %s, %s)", (session_id, pearl_id, int(predicted_ok), actions_before))
        except mysql.connector.IntegrityError as e:
            if e.errno == errorcode.ER_DUP_ENTRY:
                raise KeyError("pearl already opened") from e
            raise

    def unlocks(self, session_id: str) -> list[dict[str, Any]]:
        return self._all("SELECT session_id, pearl_id, predicted_ok, actions_before FROM unlocks "
                         "WHERE session_id = %s ORDER BY opened_at, pearl_id", (session_id,))

    def add_timeline_try(self, session_id: str, order_given: str, is_correct: bool) -> int:
        return self._insert_with_try_no(
            "timeline_tries", "session_id = %s", (session_id,),
            "INSERT INTO timeline_tries (session_id, try_no, order_given, is_correct) VALUES (%s, %s, %s, %s)",
            (order_given, int(is_correct)),
        )

    def timeline_tries(self, session_id: str) -> list[dict[str, Any]]:
        return self._all("SELECT session_id, try_no, order_given, is_correct FROM timeline_tries "
                         "WHERE session_id = %s ORDER BY try_no", (session_id,))

    def add_duel_answer(self, session_id: str, round_no: int, said_lie: bool, proof: str, reason: str,
                        is_correct: bool) -> int:
        return self._insert_with_try_no(
            "duel_answers", "session_id = %s AND round_no = %s", (session_id, round_no),
            "INSERT INTO duel_answers (session_id, round_no, try_no, said_lie, proof, reason, is_correct) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (int(said_lie), proof, reason, int(is_correct)),
        )

    def duel_answers(self, session_id: str) -> list[dict[str, Any]]:
        return self._all("SELECT session_id, round_no, try_no, said_lie, proof, reason, is_correct "
                         "FROM duel_answers WHERE session_id = %s ORDER BY round_no, try_no", (session_id,))

    def add_hint_use(self, session_id: str, puzzle_key: str, level_no: int) -> None:
        self._run("INSERT INTO hint_uses (session_id, puzzle_key, level_no) VALUES (%s, %s, %s)",
                  (session_id, puzzle_key, level_no))

    def hint_uses(self, session_id: str) -> list[dict[str, Any]]:
        return self._all("SELECT session_id, puzzle_key, level_no FROM hint_uses WHERE session_id = %s "
                         "ORDER BY id", (session_id,))

    def add_verdict(self, session_id: str, named: str, proof: str, is_correct: bool) -> int:
        return self._insert_with_try_no(
            "verdicts", "session_id = %s", (session_id,),
            "INSERT INTO verdicts (session_id, try_no, named, proof, is_correct) VALUES (%s, %s, %s, %s, %s)",
            (named, proof, int(is_correct)),
        )

    def set_legend(self, session_id: str, legend_text: str) -> None:
        self._run("UPDATE verdicts SET legend_text = %s WHERE session_id = %s AND is_correct = 1 "
                  "ORDER BY try_no DESC LIMIT 1", (legend_text, session_id))

    def verdicts(self, session_id: str) -> list[dict[str, Any]]:
        return self._all("SELECT session_id, try_no, named, proof, is_correct, legend_text FROM verdicts "
                         "WHERE session_id = %s ORDER BY try_no", (session_id,))

    def add_assessment_answer(self, session_id: str, item_id: str, choice: str, is_correct: bool) -> None:
        try:
            self._run("INSERT INTO assessment_answers (session_id, item_id, choice, is_correct) "
                      "VALUES (%s, %s, %s, %s)", (session_id, item_id, choice, int(is_correct)))
        except mysql.connector.IntegrityError as e:
            if e.errno == errorcode.ER_DUP_ENTRY:
                raise KeyError("already answered") from e
            raise

    def assessment_answers(self, session_id: str) -> list[dict[str, Any]]:
        return self._all("SELECT session_id, item_id, choice, is_correct FROM assessment_answers "
                         "WHERE session_id = %s ORDER BY item_id", (session_id,))

    # ------------------------------------------------------------ teacher
    def all_play_data(self) -> dict[str, list[dict[str, Any]]]:
        return {
            "sessions": self._all("SELECT session_id, nickname, variant_id, hairs_left, stage, legend_step "
                                  "FROM sessions"),
            "actions": self._all("SELECT session_id, realm_id, action FROM actions_log"),
            "unlocks": self._all("SELECT session_id, pearl_id, predicted_ok, actions_before FROM unlocks"),
            "timeline_tries": self._all("SELECT session_id, try_no, order_given, is_correct FROM timeline_tries"),
            "duel_answers": self._all("SELECT session_id, round_no, try_no, said_lie, proof, reason, is_correct "
                                      "FROM duel_answers"),
            "hint_uses": self._all("SELECT session_id, puzzle_key, level_no FROM hint_uses"),
            "verdicts": self._all("SELECT session_id, try_no, named, proof, is_correct, legend_text FROM verdicts"),
            "assessment_answers": self._all("SELECT session_id, item_id, choice, is_correct FROM assessment_answers"),
        }
