#!/usr/bin/env python3
"""
Interactive onboarding wizard — guided setup for non-technical users.

    python onboard.py

Walks through: resume → profile → API keys → credential protection → ready.
"""
from __future__ import annotations

import getpass
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.log import get_logger
from src.config import RESUME_DIR, ensure_dirs

log = get_logger(__name__)

# ── Helpers ──────────────────────────────────────────────────────────────


def _ask(prompt: str, default: str = "") -> str:
    hint = f" [{default}]" if default else ""
    val = input(f"  {prompt}{hint}: ").strip()
    return val or default


def _ask_yn(prompt: str, default: bool = True) -> bool:
    hint = "Y/n" if default else "y/N"
    val = input(f"  {prompt} ({hint}): ").strip().lower()
    if not val:
        return default
    return val in ("y", "yes")


def _ask_password(prompt: str) -> str:
    return getpass.getpass(f"  {prompt}: ")


def _banner() -> None:
    print()
    print("╔════════════════════════════════════════════╗")
    print("║   Autonomous Job Search Agent — Setup      ║")
    print("╚════════════════════════════════════════════╝")
    print()


def _step(num: int, total: int, title: str) -> None:
    print(f"\n{'─'*50}")
    print(f"  Step {num}/{total}: {title}")
    print(f"{'─'*50}")


# ── Steps ────────────────────────────────────────────────────────────────


def step_resume() -> Path | None:
    """Copy resume into the project."""
    _step(1, 5, "Resume")
    print("  Provide the path to your resume (PDF, DOCX, or TXT).")
    print("  Drag-and-drop the file into this terminal, or type the path.\n")

    path_str = _ask("Resume file path").strip("'\"")
    if not path_str:
        print("  ⚠  No resume provided — you can add one later to resume/")
        return None

    src = Path(path_str).expanduser().resolve()
    if not src.exists():
        print(f"  ✗ File not found: {src}")
        return None

    ensure_dirs()
    dest = RESUME_DIR / src.name
    shutil.copy2(src, dest)
    print(f"  ✓ Resume copied → resume/{src.name}")
    return dest


def step_profile(resume_path: Path | None) -> dict | None:
    """Parse resume and generate profile."""
    _step(2, 5, "Profile")

    if resume_path is None:
        print("  No resume to parse. Generating a blank profile.")
        print("  You can edit config/profile.yaml manually.\n")
        _write_blank_profile()
        return None

    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        print("  For smarter resume parsing, a Groq API key helps (free).")
        print("  Get one at: https://console.groq.com/keys")
        api_key = _ask("Groq API key (or Enter to skip)")
        if api_key:
            os.environ["GROQ_API_KEY"] = api_key

    print("\n  Analyzing your resume...")
    try:
        from src.resume_parser import parse_resume

        parsed = parse_resume(resume_path, api_key=api_key or None)
    except Exception as exc:
        print(f"  ✗ Resume parsing failed: {exc}")
        print("  Generating a blank profile — edit config/profile.yaml manually.")
        _write_blank_profile()
        return None

    all_roles = parsed.get("preferred_roles", [])
    print(f"\n  Extracted profile:")
    print(f"    Name:       {parsed.get('name', '?')}")
    print(f"    Title:      {parsed.get('title', '?')}")
    print(f"    Experience: {parsed.get('years_experience', '?')} years ({parsed.get('level', '?')})")
    print(f"    Skills:     {', '.join(parsed.get('skills', [])[:8])}")
    print(f"    Roles:      {', '.join(all_roles[:5])}")
    print(f"    Locations:  {', '.join(parsed.get('locations', []))}")

    if not _ask_yn("\n  Does this look correct?", default=True):
        name = _ask("Name", parsed.get("name", ""))
        title = _ask("Current title", parsed.get("title", ""))
        parsed["name"] = name
        parsed["title"] = title
        all_roles_str = _ask("All roles to search (comma-separated)", ", ".join(all_roles))
        all_roles = [r.strip() for r in all_roles_str.split(",") if r.strip()]
        locs_str = _ask("Target locations (comma-separated)", ", ".join(parsed.get("locations", [])))
        parsed["locations"] = [l.strip() for l in locs_str.split(",") if l.strip()]

    print("\n  Classify your roles into two tiers:")
    print("    Core roles   — match your actual background (searched first, scored highest)")
    print("    Stretch roles — adjacent/growth roles (searched with lower priority)\n")
    core_str = _ask("Core roles (comma-separated)", ", ".join(all_roles[:4]))
    parsed["core_roles"] = [r.strip() for r in core_str.split(",") if r.strip()]
    stretch_str = _ask("Stretch roles (comma-separated)", ", ".join(all_roles[4:]))
    parsed["stretch_roles"] = [r.strip() for r in stretch_str.split(",") if r.strip()]

    print("\n  Salary expectations (in LPA — lakhs per annum):")
    min_sal = _ask("Minimum salary LPA (0 to skip)", "0")
    max_sal = _ask("Maximum salary LPA (0 to skip)", "0")
    parsed["salary_min"] = int(min_sal) if min_sal.isdigit() else 0
    parsed["salary_max"] = int(max_sal) if max_sal.isdigit() else 0

    from src.profile_generator import generate_profile, write_profile

    profile = generate_profile(parsed, overrides=parsed)
    write_profile(profile)
    print("  ✓ Profile saved → config/profile.yaml")
    return profile


def _write_blank_profile() -> None:
    from src.profile_generator import generate_profile, write_profile

    profile = generate_profile({
        "name": "Your Name",
        "title": "Your Title",
        "years_experience": 0,
        "level": "intermediate",
        "skills": [],
        "summary": "",
        "core_roles": ["Software Engineer"],
        "stretch_roles": [],
        "locations": ["Remote"],
    })
    write_profile(profile)
    print("  ✓ Blank profile saved → config/profile.yaml (edit it!)")


def step_api_keys() -> dict[str, str]:
    """Collect API keys for job search and cover letters."""
    _step(3, 5, "API Keys")
    keys: dict[str, str] = {}

    groq = os.environ.get("GROQ_API_KEY", "").strip()
    if not groq:
        print("  Groq API key — needed for AI cover letters and resume parsing (free).")
        print("  Get one at: https://console.groq.com/keys")
        groq = _ask("Groq API key (or Enter to skip)")
    if groq:
        keys["GROQ_API_KEY"] = groq
        print("  ✓ Groq API key set")

    print()
    print("  ┌─ Job Search Sources ──────────────────────────────────┐")
    print("  │ Add at least one for real job results.                │")
    print("  │ More sources = broader coverage. All are free-tier.   │")
    print("  │                                                       │")
    print("  │ • SerpAPI — Google Jobs (LinkedIn, Indeed, Glassdoor) │")
    print("  │ • Adzuna — India job aggregator                      │")
    print("  │ • RapidAPI — LinkedIn Jobs + JSearch                  │")
    print("  │ • Remotive — remote jobs (free, no key needed)       │")
    print("  └───────────────────────────────────────────────────────┘")

    print()
    print("  SerpAPI — aggregates LinkedIn, Indeed, Glassdoor, Naukri (100 free/month).")
    print("  Get one at: https://serpapi.com")
    serp = _ask("SerpAPI key (or Enter to skip)")
    if serp:
        keys["SERPAPI_KEY"] = serp
        print("  ✓ SerpAPI key set")

    print()
    print("  Adzuna — India-focused job aggregator (250 free requests/day).")
    print("  Get keys at: https://developer.adzuna.com/")
    adzuna_id = _ask("Adzuna App ID (or Enter to skip)")
    if adzuna_id:
        keys["ADZUNA_APP_ID"] = adzuna_id
        adzuna_key = _ask("Adzuna App Key")
        if adzuna_key:
            keys["ADZUNA_APP_KEY"] = adzuna_key
        print("  ✓ Adzuna keys set")

    print()
    print("  RapidAPI — powers LinkedIn Jobs and JSearch sources.")
    print("  Get a key at: https://rapidapi.com/jaypat87/api/linkedin-jobs-search")
    rapidapi = _ask("RapidAPI key (or Enter to skip)")
    if rapidapi:
        keys["RAPIDAPI_KEY"] = rapidapi
        print("  ✓ RapidAPI key set")

    if not any(k in keys for k in ("SERPAPI_KEY", "ADZUNA_APP_ID", "RAPIDAPI_KEY")):
        print()
        print("  ⚠  No search API keys set — will use mock data + Remotive (remote jobs).")
        print("     Add keys later via the web UI (Settings page) or edit .env")
    else:
        print()
        print("  ℹ  Remotive (remote tech jobs) is also active — no key needed.")

    return keys


def step_credentials() -> dict[str, str]:
    """Collect optional platform credentials."""
    _step(4, 5, "Platform Credentials (optional)")
    creds: dict[str, str] = {}

    print("  These are used for auto-applying on job platforms.")
    print("  Skip any you don't want to set up now.\n")

    if _ask_yn("Set up LinkedIn Easy Apply?", default=False):
        creds["LINKEDIN_EMAIL"] = _ask("LinkedIn email")
        creds["LINKEDIN_PASSWORD"] = _ask_password("LinkedIn password")
        print("  ✓ LinkedIn credentials set")

    if _ask_yn("Set up Naukri auto-apply?", default=False):
        creds["NAUKRI_EMAIL"] = _ask("Naukri email")
        creds["NAUKRI_PASSWORD"] = _ask_password("Naukri password")
        print("  ✓ Naukri credentials set")

    email = _ask("Email for generic career sites (or Enter to skip)")
    if email:
        creds["APPLY_EMAIL"] = email
        pwd = _ask_password("Password for career sites")
        if pwd:
            creds["APPLY_PASSWORD"] = pwd
        print("  ✓ Generic apply credentials set")

    return creds


def step_protect_and_save(api_keys: dict[str, str], creds: dict[str, str]) -> None:
    """Write .env and optionally encrypt it."""
    _step(5, 5, "Save & Protect")

    env_path = ROOT / ".env"
    env_example = ROOT / ".env.example"

    existing: dict[str, str] = {}
    template_lines: list[str] = []
    if env_example.exists():
        for line in env_example.read_text(encoding="utf-8").splitlines():
            template_lines.append(line)
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                k, _, v = stripped.partition("=")
                existing[k.strip()] = v.strip()

    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                k, _, v = stripped.partition("=")
                existing[k.strip()] = v.strip()

    all_values = {**existing, **api_keys, **creds}

    env_lines: list[str] = []
    written_keys: set[str] = set()
    for line in template_lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            k, _, _ = stripped.partition("=")
            k = k.strip()
            env_lines.append(f"{k}={all_values.get(k, '')}")
            written_keys.add(k)
        else:
            env_lines.append(line)

    for k, v in all_values.items():
        if k not in written_keys:
            env_lines.append(f"{k}={v}")

    env_path.write_text("\n".join(env_lines) + "\n", encoding="utf-8")
    print(f"  ✓ Configuration saved → .env")

    has_secrets = any(v for k, v in all_values.items() if k in {
        "GROQ_API_KEY", "SERPAPI_KEY", "ADZUNA_APP_KEY", "RAPIDAPI_KEY",
        "LINKEDIN_PASSWORD", "NAUKRI_PASSWORD", "APPLY_PASSWORD", "SMTP_PASSWORD",
    })

    if has_secrets and _ask_yn("Encrypt credentials with a master password?", default=True):
        try:
            from src.secrets_manager import encrypt_env

            master = _ask_password("Set master password")
            confirm = _ask_password("Confirm master password")
            if master != confirm:
                print("  ✗ Passwords don't match — skipping encryption")
            else:
                encrypt_env(env_path, password=master)
                print("  ✓ Credentials encrypted → .env.enc")
                print("    You can delete .env for extra security.")
                print("    The agent will prompt for your master password at startup.")
        except Exception as exc:
            print(f"  ✗ Encryption failed: {exc}")
    else:
        print("  ⚠  Credentials stored in plain text in .env")
        print("    Run 'python -m src.secrets_manager' later to encrypt.")


# ── Main ─────────────────────────────────────────────────────────────────


def main() -> None:
    _banner()
    print("  This wizard will set up everything you need.")
    print("  You can press Enter to skip any step.\n")

    ensure_dirs()

    resume_path = step_resume()
    step_profile(resume_path)
    api_keys = step_api_keys()
    creds = step_credentials()
    step_protect_and_save(api_keys, creds)

    print()
    print("╔════════════════════════════════════════════╗")
    print("║            Setup Complete!                 ║")
    print("╚════════════════════════════════════════════╝")
    print()
    print("  Run the agent:")
    print("    python run_agent.py")
    print()
    print("  Set up daily auto-run:")
    print("    python setup_cron.py")
    print()
    print("  Edit your profile anytime:")
    print("    config/profile.yaml")
    print()


if __name__ == "__main__":
    main()
