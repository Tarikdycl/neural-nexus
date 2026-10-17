"""Settings, read from environment variables (or a .env file next to the code).

Secrets (DB password, OCI ids) live only in .env, which .gitignore keeps out
of GitHub. See .env.example for every setting.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Settings:
    store: str                 # "mysql", "memory", or "auto" (mysql if DB_HOST is set)
    fallback_to_memory: bool   # if MySQL is down at startup, keep running from memory
    db_host: str
    db_port: int
    db_user: str
    db_password: str
    db_name: str
    ai_enabled: bool
    ai_timeout_s: float
    oci_config_file: str
    oci_profile: str
    oci_compartment_id: str
    oci_genai_endpoint: str
    oci_genai_model: str
    teacher_code: str          # optional passcode for the teacher view; empty = open


def load_settings() -> Settings:
    return Settings(
        store=os.getenv("STORE", "auto").strip().lower(),
        fallback_to_memory=_bool("FALLBACK_TO_MEMORY", True),
        db_host=os.getenv("DB_HOST", ""),
        db_port=int(os.getenv("DB_PORT", "3306")),
        db_user=os.getenv("DB_USER", "admin"),
        db_password=os.getenv("DB_PASSWORD", ""),
        db_name=os.getenv("DB_NAME", "monkey_king"),
        ai_enabled=_bool("AI_ENABLED", True),
        ai_timeout_s=float(os.getenv("AI_TIMEOUT_S", "6")),
        oci_config_file=os.path.expanduser(os.getenv("OCI_CONFIG_FILE", "~/.oci/config")),
        oci_profile=os.getenv("OCI_PROFILE", "DEFAULT"),
        oci_compartment_id=os.getenv("OCI_COMPARTMENT_ID", ""),
        oci_genai_endpoint=os.getenv(
            "OCI_GENAI_ENDPOINT", "https://inference.generativeai.us-chicago-1.oci.oraclecloud.com"),
        oci_genai_model=os.getenv("OCI_GENAI_MODEL", "cohere.command-a-03-2025"),
        teacher_code=os.getenv("TEACHER_CODE", ""),
    )
