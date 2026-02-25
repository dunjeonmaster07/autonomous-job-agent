"""Load profile and env configuration."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

from src.log import get_logger

log = get_logger(__name__)

load_dotenv()

CONFIG_DIR: Path = Path(__file__).resolve().parent.parent / "config"
PROFILE_PATH: Path = CONFIG_DIR / "profile.yaml"
REPORTS_DIR: Path = Path(__file__).resolve().parent.parent / "reports"
DATA_DIR: Path = Path(__file__).resolve().parent.parent / "data"
RESUME_DIR: Path = Path(__file__).resolve().parent.parent / "resume"


def load_profile() -> dict[str, Any]:
    with open(PROFILE_PATH, "r") as f:
        data = yaml.safe_load(f)

    # Backward compat: migrate flat preferred_roles → core_roles + stretch_roles
    if "preferred_roles" in data and "core_roles" not in data:
        data["core_roles"] = data.pop("preferred_roles")
        data.setdefault("stretch_roles", [])

    # Provide a combined view for code that still reads preferred_roles
    if "preferred_roles" not in data:
        data["preferred_roles"] = (
            list(data.get("core_roles", []))
            + list(data.get("stretch_roles", []))
        )

    return data


def get_env(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


def ensure_dirs() -> None:
    for d in (REPORTS_DIR, DATA_DIR, RESUME_DIR):
        d.mkdir(parents=True, exist_ok=True)


def get_resume_path() -> Path | None:
    """First PDF or DOCX in resume folder."""
    if not RESUME_DIR.exists():
        return None
    for ext in (".pdf", ".docx", ".doc"):
        for p in RESUME_DIR.iterdir():
            if p.suffix.lower() == ext and p.is_file():
                return p
    return None


def try_load_encrypted_env() -> None:
    """If .env.enc exists, attempt to load it (prompts for password)."""
    enc_path = Path(__file__).resolve().parent.parent / ".env.enc"
    if not enc_path.exists():
        return
    try:
        from src.secrets_manager import load_encrypted_env

        master_pw = os.environ.get("MASTER_PASSWORD")
        if load_encrypted_env(password=master_pw):
            log.info("Loaded encrypted credentials from .env.enc")
    except Exception as exc:
        log.warning("Failed to load encrypted env: %s", exc)
