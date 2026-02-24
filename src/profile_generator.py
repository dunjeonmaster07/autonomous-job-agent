"""Generate config/profile.yaml from parsed resume data."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from src.config import CONFIG_DIR, PROFILE_PATH
from src.log import get_logger

log = get_logger(__name__)


def generate_profile(parsed: dict[str, Any], overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build a complete profile dict from parsed resume data + optional overrides."""
    ov = overrides or {}

    name = ov.get("name") or parsed.get("name", "")
    title = ov.get("title") or parsed.get("title", "")
    years = ov.get("years_experience") or parsed.get("years_experience", 0)
    level = ov.get("level") or parsed.get("level", "intermediate")
    skills = ov.get("skills") or parsed.get("skills", [])
    summary = ov.get("summary") or parsed.get("summary", "")
    roles = ov.get("preferred_roles") or parsed.get("preferred_roles", [])
    locations = ov.get("locations") or parsed.get("locations", ["Remote"])

    if not summary and title and skills:
        skill_str = ", ".join(skills[:6])
        summary = (
            f"{title} with {years} years of experience. "
            f"Skilled in {skill_str}."
        )

    if not roles and title:
        roles = [title]

    salary_min = ov.get("salary_min", 0)
    salary_max = ov.get("salary_max", 0)

    profile: dict[str, Any] = {
        "profile": {
            "name": name,
            "title": title,
            "years_experience": int(years) if years else 0,
            "level": level,
            "skills": skills[:15],
            "summary": summary,
        },
        "preferred_roles": roles[:8],
        "preferred_companies": {
            "type": "any",
            "names": [],
        },
        "locations": locations[:8],
        "salary_lpa": {
            "min": salary_min,
            "max": salary_max,
            "compare_only_when_listed": True,
        },
        "min_score_auto_apply": 0.65,
    }
    return profile


def write_profile(profile: dict[str, Any], path: Path | None = None) -> Path:
    """Write profile dict to YAML file."""
    path = path or PROFILE_PATH
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    header = (
        "# ============================================================\n"
        "# Candidate Profile — auto-generated from resume\n"
        "# Edit freely to fine-tune job matching\n"
        "# ============================================================\n\n"
    )

    yaml_str = yaml.dump(profile, default_flow_style=False, sort_keys=False, allow_unicode=True)
    path.write_text(header + yaml_str, encoding="utf-8")
    log.info("Profile written → %s", path)
    return path
