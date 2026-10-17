"""Check a running deployment from the outside, the way a player's laptop sees it.

    python scripts/check_deployment.py http://<public-ip>             # quick checks
    python scripts/check_deployment.py http://<public-ip> --play      # + plays one whole game over HTTP
    python scripts/check_deployment.py http://127.0.0.1 --play --cleanup   # on the server: also deletes that test game

Review 2: "verified cloud deployment". This prints one PASS / FAIL / WARN line per
check and exits with 1 if anything FAILed, so "it works" is a fact, not a guess.
Only the Python standard library is needed (no pip install), so it also runs
from a teammate's laptop. --cleanup needs the server's .env (database password).
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STORY = json.loads((ROOT / "content" / "story.json").read_text(encoding="utf-8"))
NICKNAME = "DeployCheck"
failures: list[str] = []


def report(status: str, what: str, detail: str = "") -> None:
    print(f"{status:4s}  {what}" + (f"  ({detail})" if detail else ""))
    if status == "FAIL":
        failures.append(what)


def call(base: str, path: str, body: dict | None = None, timeout: float = 20) -> tuple[int, object]:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(base + path, data=data, method="GET" if body is None else "POST",
                                 headers={"Content-Type": "application/json"} if body is not None else {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            status = r.status
    except urllib.error.HTTPError as e:
        raw, status = e.read(), e.code
    try:
        return status, json.loads(raw)
    except ValueError:
        return status, raw.decode("utf-8", "replace")


def check_basics(base: str) -> None:
    try:
        status, h = call(base, "/api/health")
    except Exception as e:  # noqa: BLE001
        report("FAIL", "server reachable", f"{type(e).__name__}: {e}. Is the service running and port 80 open?")
        return
    report("PASS" if status == 200 and h.get("ok") else "FAIL", "health ok", json.dumps(h))
    if not isinstance(h, dict):
        return
    if h.get("store") == "mysql":
        report("PASS", "game data is saved in MySQL HeatWave")
    else:
        report("FAIL", "game data is saved in MySQL HeatWave",
               f"store is {h.get('store')!r}: games are lost on restart. Check DB_HOST/DB_PASSWORD in .env")
    if h.get("schema_version") == h.get("schema_version_needed"):
        report("PASS", "database version", f"{h.get('schema_version')}")
    elif h.get("store") == "mysql":
        report("FAIL", "database version", f"{h.get('schema_version')}, needs {h.get('schema_version_needed')}: "
                                           "run python scripts/setup_db.py")
    started = time.monotonic()
    _, ai = call(base, "/api/health?check_ai=1", timeout=30)
    check = ai.get("ai_check", {}) if isinstance(ai, dict) else {}
    if not ai.get("ai_configured"):
        report("WARN", "AI narrator", "not configured: the game uses pre-written lines (that is allowed)")
    elif check.get("ok"):
        report("PASS", "AI narrator answers for real", f"{check.get('seconds')} s")
    else:
        report("WARN", "AI narrator answers for real",
               f"error {check.get('error')} after {time.monotonic() - started:.1f} s: pre-written lines are used")
    for path, needle in (("/", "<div id=\"root\""), ("/teacher", "<div id=\"root\""),
                         ("/static/app.js", "Voice"), ("/static/style.css", ".voicebar"),
                         ("/static/vendor/react.production.min.js", None)):
        status, body = call(base, path)
        ok = status == 200 and (needle is None or needle in str(body))
        report("PASS" if ok else "FAIL", f"page {path}", f"HTTP {status}")


def play(base: str) -> str | None:
    """One whole game over HTTP, answering like a careful child. Returns the session id."""
    def post(path, body):
        status, r = call(base, path, body)
        if status != 200:
            raise RuntimeError(f"{path} -> HTTP {status}: {r}")
        return r

    status, start = call(base, "/api/start", {"nickname": NICKNAME})
    if status != 200:
        report("FAIL", "start a game", f"HTTP {status}: {start}")
        return None
    sid = start["session_id"]
    try:
        items = STORY["assessment"]["items"]
        for phase in ("pre",):
            post("/api/assessment", {"session_id": sid, "phase": phase,
                                     "answers": {i["item_id"]: i["choice_ok"] for i in items if i["phase"] == phase}})
        right = {p["predict_q"]: p["predict_ok"] for p in STORY["pearls"]}
        for realm in ("bamboo", "sea", "moon"):
            for action in ("look", "listen"):
                post("/api/action", {"session_id": sid, "realm": realm, "action": action})
            reply = post("/api/ask", {"session_id": sid, "realm": realm, "question": "What do you notice here?"})
            for _ in range(2):
                o = post("/api/open", {"session_id": sid, "realm": realm})
                post("/api/predict", {"session_id": sid, "pearl": o["pearl"], "choice": right[o["question"]]})
        report("PASS", "explore three realms and open six pearls",
               f"last Scroll reply came from: {reply['reply']['source']}")
        _, state = call(base, f"/api/state/{sid}")
        code = {p["title"]: p["pearl"] for p in state["opened"]}
        title = {p["pearl_id"]: p["title"] for p in STORY["pearls"]}
        to_code = lambda pids: [code[title[p]] for p in pids]  # noqa: E731
        if not post("/api/timeline", {"session_id": sid, "order": to_code(["P1", "P2", "P3", "P4", "P5", "P6"])})["correct"]:
            raise RuntimeError("the true timeline was not accepted")
        rounds = {r["round_no"]: r for r in STORY["duel_rounds"]}   # the answer is the same in every variant
        for rnd in (1, 2, 3):
            r = rounds[rnd]
            res = post("/api/duel", {"session_id": sid, "round": rnd, "said_lie": bool(r["is_lie"]),
                                     "proofs": to_code(r["proof_pearls"].split(",")), "reason": r["reason_ok"]})
            if not res["correct"]:
                raise RuntimeError(f"duel round {rnd} was not accepted")
        report("PASS", "timeline and three duel rounds")
        sign = next(p["text"] for p in state["opened"] if p["title"] == title["P2"])
        variant = next(s["variant_id"] for s in STORY["pearl_signs"] if s["pearl_id"] == "P2" and s["sign_text"] in sign)
        culprit = next(v["culprit"] for v in STORY["variants"] if v["variant_id"] == variant)
        if not post("/api/verdict", {"session_id": sid, "named": culprit, "proof": to_code(["P2", "P5"])})["correct"]:
            raise RuntimeError("the verdict was not accepted")
        post("/api/assessment", {"session_id": sid, "phase": "post",
                                 "answers": {i["item_id"]: i["choice_ok"] for i in items if i["phase"] == "post"}})
        post("/api/legend", {"session_id": sid, "text": "Wukong checks the deployment.", "finish": True})
        _, final = call(base, f"/api/state/{sid}")
        report("PASS" if final.get("stage") == "done" else "FAIL", "whole game finished", f"culprit was {culprit}")
    except Exception as e:  # noqa: BLE001
        report("FAIL", "play a whole game", str(e))
    return sid


def cleanup(sid: str) -> None:
    """Delete the test game, so the teacher view only counts real players. Needs the server's .env."""
    sys.path.insert(0, str(ROOT))
    try:
        import mysql.connector
        from app.config import load_settings
        s = load_settings()
        conn = mysql.connector.connect(host=s.db_host, port=s.db_port, user=s.db_user, password=s.db_password,
                                       database=s.db_name, autocommit=False)
        cur = conn.cursor()
        for table in ("assessment_answers", "verdicts", "hint_uses", "duel_answers", "timeline_tries", "unlocks",
                      "actions_log", "sessions"):
            cur.execute(f"DELETE FROM {table} WHERE session_id = %s", (sid,))
        conn.commit()
        conn.close()
        report("PASS", "test game deleted from the database")
    except Exception as e:  # noqa: BLE001
        report("WARN", "test game deleted from the database",
               f"{e}. It shows as nickname {NICKNAME} in the teacher view.")


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        sys.exit(__doc__)
    base = args[0].rstrip("/")
    print(f"Checking {base}\n")
    check_basics(base)
    if "--play" in sys.argv:
        sid = play(base)
        if sid and "--cleanup" in sys.argv:
            cleanup(sid)
    print("\n" + ("ALL CHECKS PASSED" if not failures else f"{len(failures)} FAILED: " + "; ".join(failures)))
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
