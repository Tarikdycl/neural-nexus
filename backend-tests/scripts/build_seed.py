"""Rebuild sql/seed.sql from content/story.json.

Run from the project folder:  python scripts/build_seed.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.content import SEED_PATH, build_seed_sql, load_story  # noqa: E402

if __name__ == "__main__":
    SEED_PATH.write_text(build_seed_sql(load_story()), encoding="utf-8")
    print(f"wrote {SEED_PATH}")
