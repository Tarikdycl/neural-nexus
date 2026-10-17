"""Story content: loading, checking, and turning it into seed.sql.

content/story.json is the single source of story text. Two things read it:
  * build_seed_sql() writes sql/seed.sql, which loads the text into MySQL.
  * MemoryStore reads it directly (the doc's "load it into a Python
    dictionary" fallback for when the database is down).
A test checks that the committed seed.sql still matches story.json, so the
two copies can never drift apart.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
STORY_PATH = ROOT / "content" / "story.json"
SEED_PATH = ROOT / "sql" / "seed.sql"

PEARL_IDS = ["P1", "P2", "P3", "P4", "P5", "P6"]
VARIANT_IDS = ["V1", "V2", "V3"]
NARRATION_KEYS = ["predict_match", "predict_differ", "all_found", "timeline_solved", "duel_intro",
                  "verdict_intro", "timeline_pair"]
SIGN_PEARLS = {"P2", "P5"}  # the two pearls that hold a variant sign
SIGN_PLACEHOLDER = "[variant sign]"
VISUAL_KINDS = {"sun", "tide", "moon"}


def load_story(path: Path = STORY_PATH) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        story = json.load(f)
    validate_story(story)
    return story


def validate_story(story: dict[str, Any]) -> None:
    """Fail loudly at startup if the content sheet is incomplete.

    These are the facts the engine relies on. Catching a missing hint or a
    typo in a pearl id here is far better than a child hitting it mid-game.
    """
    problems: list[str] = []

    variants = {v["variant_id"]: v for v in story["variants"]}
    if sorted(variants) != VARIANT_IDS:
        problems.append(f"variants must be {VARIANT_IDS}, got {sorted(variants)}")
    for v in story["variants"]:
        if v["culprit"] not in story["suspects"]:
            problems.append(f"{v['variant_id']} culprit {v['culprit']!r} is not in suspects")
        if not v.get("culprit_words"):
            problems.append(f"{v['variant_id']} needs culprit_words for the output check")

    pearls = story["pearls"]
    if [p["pearl_id"] for p in sorted(pearls, key=lambda p: p["true_order"])] != PEARL_IDS:
        problems.append("pearls must be P1..P6 with true_order 1..6")
    realm_ids = {r["realm_id"] for r in story["realms"]}
    for p in pearls:
        if p["realm_id"] not in realm_ids:
            problems.append(f"{p['pearl_id']} has unknown realm {p['realm_id']}")
        has_slot = SIGN_PLACEHOLDER in p["shared_text"]
        if has_slot != (p["pearl_id"] in SIGN_PEARLS):
            problems.append(f"{p['pearl_id']}: '{SIGN_PLACEHOLDER}' must appear only in P2 and P5")
        choices = {p["predict_ok"], p["predict_no1"], p["predict_no2"]}
        if len(choices) != 3:
            problems.append(f"{p['pearl_id']}: the 3 predict choices must be different")
        if not isinstance(p.get("visual"), dict) or p["visual"].get("kind") not in VISUAL_KINDS:
            problems.append(f"{p['pearl_id']}: needs a visual with kind sun, tide or moon")

    signs = {(s["pearl_id"], s["variant_id"]) for s in story["pearl_signs"]}
    for pid in SIGN_PEARLS:
        for vid in VARIANT_IDS:
            if (pid, vid) not in signs:
                problems.append(f"missing sign for {pid}/{vid}")

    rounds = {(r["round_no"], r["variant_id"]) for r in story["duel_rounds"]}
    for rnd in (1, 2, 3):
        for vid in VARIANT_IDS:
            if (rnd, vid) not in rounds and (rnd, "ALL") not in rounds:
                problems.append(f"no duel round {rnd} for {vid}")
    for r in story["duel_rounds"]:
        for pid in r["proof_pearls"].split(","):
            if pid not in PEARL_IDS:
                problems.append(f"round {r['round_no']} proof {pid} is not a pearl")
        if r.get("proof_mode") not in ("any", "all"):
            problems.append(f"round {r['round_no']} {r['variant_id']}: proof_mode must be 'any' or 'all'")
        if len({r.get("reason_ok"), r.get("reason_no1"), r.get("reason_no2")} - {None, ""}) != 3:
            problems.append(f"round {r['round_no']} {r['variant_id']}: needs 3 different reasons")

    hint_keys = {(h["puzzle_key"], h["level_no"]) for h in story["hints"]}
    for key in PEARL_IDS + ["TIMELINE", "R1", "R2", "R3", "VERDICT"]:
        for level in (1, 2, 3):
            if (key, level) not in hint_keys:
                problems.append(f"missing hint {key} level {level}")

    narration = story.get("narration", {})
    for key in NARRATION_KEYS:
        if not narration.get(key):
            problems.append(f"narration needs '{key}'")
    for rid in realm_ids:
        if not narration.get("realm_enter", {}).get(rid):
            problems.append(f"narration needs realm_enter for {rid}")
    if "{a}" not in narration.get("timeline_pair", "") or "{b}" not in narration.get("timeline_pair", ""):
        problems.append("narration timeline_pair needs {a} and {b}")

    if len(story["legend"]["questions"]) != 3:
        problems.append("legend needs exactly 3 helper questions")

    items = story.get("assessment", {}).get("items", [])
    for phase in ("pre", "post"):
        if not [i for i in items if i["phase"] == phase]:
            problems.append(f"assessment needs at least one '{phase}' question")
    for i in items:
        if len({i["choice_ok"], i["choice_no1"], i["choice_no2"]}) != 3:
            problems.append(f"assessment {i['item_id']}: the 3 choices must be different")
    skills = lambda ph: sorted(i["skill"] for i in items if i["phase"] == ph)  # noqa: E731
    if skills("pre") != skills("post"):
        problems.append("before and after questions must test the same skills")

    if problems:
        raise ValueError("story.json has problems:\n  - " + "\n  - ".join(problems))


# ---------------------------------------------------------------- seed.sql

def _sql(value: Any) -> str:
    """Render one Python value as a MySQL literal."""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value).replace("\\", "\\\\").replace("'", "''").replace("\n", "\\n")  # \n: ending turns
    return f"'{text}'"


def _upsert(table: str, columns: list[str], key_columns: list[str], rows: list[list[Any]]) -> str:
    """INSERT ... ON DUPLICATE KEY UPDATE, so seeding twice is harmless.

    Uses the MySQL 8.0.19+ row-alias form (AS new) because VALUES() inside
    ON DUPLICATE KEY UPDATE is deprecated in MySQL 8.0.20 and later.
    """
    col_list = ", ".join(columns)
    values = ",\n  ".join("(" + ", ".join(_sql(v) for v in row) + ")" for row in rows)
    updates = ", ".join(f"{c} = new.{c}" for c in columns if c not in key_columns)
    return (
        f"INSERT INTO {table} ({col_list}) VALUES\n  {values}\n"
        f"AS new ON DUPLICATE KEY UPDATE {updates};\n"
    )


def build_seed_sql(story: dict[str, Any]) -> str:
    parts = [
        "-- GENERATED FILE - do not edit by hand.\n"
        "-- Edit content/story.json, then run: python scripts/build_seed.py\n"
        "-- Load order (design doc section 8): variants -> realms -> pearls ->\n"
        "-- pearl_signs -> duel_rounds -> assessment_items -> hints. Safe to run more than once.\n"
    ]
    parts.append(_upsert(
        "variants", ["variant_id", "culprit", "culprit_words", "ending_text"], ["variant_id"],
        [[v["variant_id"], v["culprit"], ",".join(v["culprit_words"]), v["ending_text"]]
         for v in story["variants"]],
    ))
    parts.append(_upsert(
        "realms", ["realm_id", "name", "display_order", "image_url", "look_text", "listen_text"],
        ["realm_id"],
        [[r["realm_id"], r["name"], r["display_order"], r["image_url"], r["look_text"], r["listen_text"]]
         for r in story["realms"]],
    ))
    pearl_cols = ["pearl_id", "realm_id", "true_order", "time_label", "title", "visual", "shared_text",
                  "predict_q", "predict_ok", "predict_no1", "predict_no2"]
    parts.append(_upsert(
        "pearls", pearl_cols, ["pearl_id"],
        [[json.dumps(p[c], sort_keys=True) if c == "visual" else p[c] for c in pearl_cols] for p in story["pearls"]],
    ))
    parts.append(_upsert(
        "pearl_signs", ["pearl_id", "variant_id", "sign_text"], ["pearl_id", "variant_id"],
        [[s["pearl_id"], s["variant_id"], s["sign_text"]] for s in story["pearl_signs"]],
    ))
    duel_cols = ["round_no", "variant_id", "form_name", "claim_text", "is_lie", "proof_pearls", "proof_mode",
                 "reason_ok", "reason_no1", "reason_no2"]
    parts.append(_upsert(
        "duel_rounds", duel_cols, ["round_no", "variant_id"],
        [[r[c] for c in duel_cols] for r in story["duel_rounds"]],
    ))
    item_cols = ["item_id", "phase", "skill", "question", "choice_ok", "choice_no1", "choice_no2"]
    parts.append(_upsert(
        "assessment_items", item_cols, ["item_id"],
        [[i[c] for c in item_cols] for i in story["assessment"]["items"]],
    ))
    parts.append(_upsert(
        "hints", ["puzzle_key", "level_no", "hint_text"], ["puzzle_key", "level_no"],
        [[h["puzzle_key"], h["level_no"], h["hint_text"]] for h in story["hints"]],
    ))
    return "\n".join(parts)
