"""Streamlit UI for the Autonomous Job Search Agent."""
from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.config import (
    CONFIG_DIR,
    DATA_DIR,
    PROFILE_PATH,
    REPORTS_DIR,
    RESUME_DIR,
    ensure_dirs,
    get_resume_path,
)
from src.log import get_logger

log = get_logger(__name__)

# ── Constants ────────────────────────────────────────────────────────────

COMMON_SKILLS: list[str] = [
    "Python", "Java", "JavaScript", "TypeScript", "React", "Node.js",
    "Angular", "Vue.js", "SQL", "NoSQL", "MongoDB", "PostgreSQL", "MySQL",
    "Redis", "Docker", "Kubernetes", "AWS", "GCP", "Azure", "Terraform",
    "Ansible", "Jenkins", "Git", "Linux", "CI/CD", "REST APIs", "GraphQL",
    "Microservices", "Agile", "Scrum", "JIRA", "Excel", "Power BI",
    "Tableau", "SAP", "Salesforce", "HRIS", "Recruitment",
    "Talent Acquisition", "Employee Relations", "Onboarding", "Payroll",
    "Machine Learning", "Deep Learning", "NLP", "Data Science", "Pandas",
    "TensorFlow", "PyTorch", "Spark", "Kafka", "Elasticsearch", "Figma",
    "UI/UX", "Communication", "Leadership", "Project Management",
    "Stakeholder Management", "RPA", "AI Automation",
    "Incident Response", "Root Cause Analysis", "SRE",
]

CITIES: list[str] = [
    "Bangalore", "Mumbai", "Delhi", "Hyderabad", "Pune", "Chennai",
    "Kolkata", "Gurgaon", "Noida", "Ahmedabad", "Jaipur", "Lucknow",
    "Chandigarh", "Kochi", "Indore", "Remote",
]

_GLASS_CSS = """
<style>
/* gradient background */
[data-testid="stAppViewContainer"] {
    background: linear-gradient(135deg, #e8eaf6 0%, #f3e5f5 40%, #e0f2f1 100%);
}
[data-testid="stSidebar"] {
    background: rgba(255,255,255,0.55);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    border-right: 1px solid rgba(255,255,255,0.3);
}
/* glass cards for main content */
.block-container {
    padding-top: 2rem;
}
[data-testid="stMetric"] {
    background: rgba(255,255,255,0.6);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    padding: 0.75rem 1rem;
    border-radius: 12px;
    border: 1px solid rgba(255,255,255,0.4);
    box-shadow: 0 4px 16px rgba(0,0,0,0.06);
}
/* glass effect on forms and expanders */
[data-testid="stForm"],
[data-testid="stExpander"] {
    background: rgba(255,255,255,0.5);
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    border-radius: 12px;
    border: 1px solid rgba(255,255,255,0.35);
    box-shadow: 0 4px 20px rgba(0,0,0,0.04);
}
/* buttons */
.stButton > button[kind="primary"] {
    border-radius: 8px;
    font-weight: 600;
}
/* headings */
h1, h2, h3 {
    color: #1a1a2e;
}
/* role card */
.role-card {
    padding: 1rem 1.25rem;
    background: rgba(255,255,255,0.65);
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    border: 1px solid rgba(74,144,217,0.25);
    border-radius: 12px;
    box-shadow: 0 4px 16px rgba(0,0,0,0.05);
}
/* review blocks */
.review-original {
    padding: 0.5rem 0.75rem; background: rgba(231,76,60,0.08);
    border-left: 3px solid #e74c3c; border-radius: 6px;
    font-size: 0.9rem; color: #333;
}
.review-replacement {
    padding: 0.5rem 0.75rem; background: rgba(39,174,96,0.08);
    border-left: 3px solid #27ae60; border-radius: 6px;
    font-size: 0.9rem; color: #333;
}
</style>
"""

# ── Helpers ──────────────────────────────────────────────────────────────


def _load_env() -> dict[str, str]:
    env_path = ROOT / ".env"
    values: dict[str, str] = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                values[k.strip()] = v.strip()
    return values


def _save_env(values: dict[str, str]) -> None:
    env_path = ROOT / ".env"
    template_path = ROOT / ".env.example"

    lines: list[str] = []
    written: set[str] = set()

    if template_path.exists():
        for line in template_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                k, _, _ = stripped.partition("=")
                k = k.strip()
                lines.append(f"{k}={values.get(k, '')}")
                written.add(k)
            else:
                lines.append(line)

    for k, v in values.items():
        if k not in written:
            lines.append(f"{k}={v}")

    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _load_profile() -> dict | None:
    if not PROFILE_PATH.exists():
        return None
    import yaml

    with open(PROFILE_PATH) as f:
        return yaml.safe_load(f)


def _groq_key() -> str:
    return (
        _load_env().get("GROQ_API_KEY", "")
        or st.session_state.get("_groq_key", "")
    )


def _status() -> dict[str, bool]:
    env = _load_env()
    has_search_key = bool(
        env.get("SERPAPI_KEY")
        or env.get("JSEARCH_API_KEY")
        or env.get("ADZUNA_APP_ID")
        or env.get("RAPIDAPI_KEY")
    )
    return {
        "profile": PROFILE_PATH.exists(),
        "resume": get_resume_path() is not None,
        "groq_key": bool(env.get("GROQ_API_KEY")),
        "api_keys": has_search_key,
    }


def _check(label: str, ok: bool) -> str:
    icon = "✅" if ok else "⬜"
    return f"{icon}  {label}"


def _setup_done() -> bool:
    return PROFILE_PATH.exists()


# ── Page: Setup ──────────────────────────────────────────────────────────


def page_setup() -> None:
    st.header("Autonomous Job Search Agent")
    st.write("Get started — add your API key, upload your resume, review your profile.")

    # ── Step 1: API Keys (mandatory Groq) ────────────────────────────────
    st.subheader("1 — API Keys")

    env = _load_env()
    has_groq = bool(env.get("GROQ_API_KEY"))

    with st.form("api_keys"):
        st.markdown(
            "**Groq API Key** *(required)* — powers AI resume parsing, role suggestions, "
            "and cover letters. "
            "([Get a free key here](https://console.groq.com/keys))"
        )
        groq = st.text_input(
            "Groq API key *",
            value=env.get("GROQ_API_KEY", ""),
            type="password",
            placeholder="gsk_...",
        )

        st.markdown("---")
        st.markdown(
            "**Job Search Sources** — add at least one for real job results. "
            "More sources = broader coverage. All are free-tier friendly."
        )

        jc1, jc2 = st.columns(2)
        with jc1:
            serp = st.text_input(
                "SerpAPI key (Google Jobs)",
                value=env.get("SERPAPI_KEY", ""),
                type="password",
                placeholder="Optional",
                help="Aggregates LinkedIn, Indeed, Glassdoor, Naukri, TimesJobs results. "
                     "[Get 100 free searches/month](https://serpapi.com)",
            )
            adzuna_id = st.text_input(
                "Adzuna App ID",
                value=env.get("ADZUNA_APP_ID", ""),
                placeholder="Optional",
                help="India job aggregator. [Get 250 free requests/day](https://developer.adzuna.com/)",
            )
        with jc2:
            rapidapi_key = st.text_input(
                "RapidAPI key (LinkedIn + JSearch)",
                value=env.get("RAPIDAPI_KEY", ""),
                type="password",
                placeholder="Optional",
                help="Powers LinkedIn Jobs and JSearch sources. "
                     "[Sign up free](https://rapidapi.com/jaypat87/api/linkedin-jobs-search)",
            )
            adzuna_key = st.text_input(
                "Adzuna App Key",
                value=env.get("ADZUNA_APP_KEY", ""),
                type="password",
                placeholder="Optional",
            )

        st.caption(
            "**Remotive** (remote tech jobs) is always active — no key needed. "
            "You can add more keys later in **Settings**."
        )

        save_keys = st.form_submit_button("Save API Keys", type="primary", use_container_width=True)

    if save_keys:
        if not groq:
            st.error("Groq API key is required to continue.")
        else:
            env["GROQ_API_KEY"] = groq
            env["SERPAPI_KEY"] = serp
            env["ADZUNA_APP_ID"] = adzuna_id
            env["ADZUNA_APP_KEY"] = adzuna_key
            env["RAPIDAPI_KEY"] = rapidapi_key
            _save_env(env)
            os.environ["GROQ_API_KEY"] = groq
            st.session_state["_groq_key"] = groq
            if serp:
                os.environ["SERPAPI_KEY"] = serp
            st.success("API keys saved!")
            st.rerun()

    if not has_groq and not st.session_state.get("_groq_key"):
        st.warning("Enter your Groq API key above to unlock resume parsing, role suggestions, and AI review.")
        return

    # ── Step 2: Resume ───────────────────────────────────────────────────
    st.divider()
    st.subheader("2 — Upload Resume")

    uploaded = st.file_uploader(
        "Drop your resume here (PDF, DOCX, or TXT)",
        type=["pdf", "docx", "txt"],
    )

    if uploaded:
        ensure_dirs()
        dest = RESUME_DIR / uploaded.name
        dest.write_bytes(uploaded.getvalue())
        st.success(f"Saved to `resume/{uploaded.name}`")

        with st.spinner("Analyzing your resume…"):
            try:
                from src.resume_parser import parse_resume

                parsed = parse_resume(dest, api_key=_groq_key() or None)
                st.session_state["parsed"] = parsed
                st.success("Resume parsed successfully!")
            except Exception as exc:
                st.error(f"Parsing failed: {exc}")
                st.session_state["parsed"] = {}

    existing_resume = get_resume_path()
    if existing_resume and not uploaded:
        st.info(f"Current resume: **{existing_resume.name}**")

    # ── Parsed Profile Summary ───────────────────────────────────────────
    parsed_data = st.session_state.get("parsed", {})

    if parsed_data and parsed_data.get("name"):
        st.divider()
        st.subheader("Extracted Profile")
        c1, c2, c3 = st.columns(3)
        c1.metric("Name", parsed_data.get("name", "—"))
        c2.metric("Title", parsed_data.get("title", "—"))
        c3.metric("Experience", f"{parsed_data.get('years_experience', 0)} yrs")

        skills_list = parsed_data.get("skills", [])
        if skills_list:
            st.markdown("**Skills:** " + ", ".join(skills_list[:12]))

    # ── Role-Based Targets ───────────────────────────────────────────────
    suggested_roles = parsed_data.get("preferred_roles", [])
    role_reasons = parsed_data.get("role_reasons", {})

    if suggested_roles:
        st.divider()
        st.subheader("Role-Based Targets — Focus On")

        roles_html = ""
        for i, role in enumerate(suggested_roles, 1):
            reason = role_reasons.get(role, "")
            reason_html = f'<br><span style="color:#666;font-size:0.85rem">{reason}</span>' if reason else ""
            roles_html += (
                f'<div style="margin-bottom:0.6rem">'
                f'<strong>{i}. {role}</strong>'
                f'{reason_html}'
                f'</div>'
            )

        st.markdown(f'<div class="role-card">{roles_html}</div>', unsafe_allow_html=True)

    # ── Resume Review ────────────────────────────────────────────────────
    resume_for_review = existing_resume or (RESUME_DIR / uploaded.name if uploaded else None)

    if resume_for_review and resume_for_review.exists():
        st.divider()
        st.subheader("Resume Review")
        st.caption(
            "Get specific improvement suggestions with exact before/after text "
            "you can paste back into your resume."
        )

        if st.button("Review My Resume", use_container_width=True):
            with st.spinner("Analyzing your resume for improvements…"):
                try:
                    from src.resume_parser import review_resume

                    feedback = review_resume(resume_for_review, api_key=_groq_key())
                    st.session_state["resume_feedback"] = feedback
                except Exception as exc:
                    st.error(f"Review failed: {exc}")

        feedback = st.session_state.get("resume_feedback", [])
        if feedback:
            _CAT_ICONS = {
                "Structure": "🏗️", "Metrics": "📊", "Keywords": "🔑",
                "Skills Gap": "🧩", "Wording": "✏️", "Formatting": "📐",
            }
            for item in feedback:
                cat = item.get("category", "Tip")
                icon = _CAT_ICONS.get(cat, "💡")
                original = item.get("original", "")
                replacement = item.get("replacement", "")
                reason = item.get("reason", "")

                with st.expander(f"{icon}  **{cat}**", expanded=True):
                    if original and original != "[missing]":
                        st.markdown("**Current text:**")
                        st.markdown(f'<div class="review-original">{original}</div>', unsafe_allow_html=True)
                    elif original == "[missing]":
                        st.markdown("**Missing from your resume**")

                    if replacement:
                        st.markdown("**Replace with:**")
                        st.markdown(f'<div class="review-replacement">{replacement}</div>', unsafe_allow_html=True)

                    if reason:
                        st.caption(reason)

    # ── Step 3: Profile ──────────────────────────────────────────────────
    st.divider()
    st.subheader("3 — Review & Save Profile")

    parsed = st.session_state.get("parsed", {})
    existing = _load_profile() or {}
    ep = existing.get("profile", {})

    def _d(key: str, fallback=""):
        return parsed.get(key) or ep.get(key) or fallback

    with st.form("profile_form"):
        c1, c2 = st.columns(2)
        with c1:
            name = st.text_input("Full name", value=_d("name"))
            title = st.text_input("Current / target title", value=_d("title"))
            years = st.number_input(
                "Years of experience", 0, 50,
                value=int(_d("years_experience", 0)),
            )
        with c2:
            level_opts = ["junior", "intermediate", "senior"]
            lv = _d("level", "intermediate")
            level = st.selectbox(
                "Experience level",
                level_opts,
                index=level_opts.index(lv) if lv in level_opts else 1,
            )
            existing_sal = existing.get("salary_lpa", {})
            s1, s2 = st.columns(2)
            with s1:
                min_sal = st.number_input(
                    "Min salary (LPA) *", 0, 300,
                    value=int(existing_sal.get("min", 0)) or None,
                    placeholder="e.g. 20",
                )
            with s2:
                max_sal = st.number_input(
                    "Max salary (LPA) *", 0, 300,
                    value=int(existing_sal.get("max", 0)) or None,
                    placeholder="e.g. 40",
                )

        default_skills = parsed.get("skills") or ep.get("skills") or []
        all_skill_opts = list(dict.fromkeys([s for s in default_skills] + COMMON_SKILLS))
        skills = st.multiselect(
            "Skills",
            options=all_skill_opts,
            default=[s for s in default_skills if s in all_skill_opts][:15],
            help="Select from the list or type to filter",
        )

        st.markdown("**Roles**")
        rc1, rc2 = st.columns(2)

        default_core = (
            parsed.get("core_roles")
            or existing.get("core_roles")
            or parsed.get("preferred_roles")
            or existing.get("preferred_roles")
            or []
        )
        default_stretch = (
            parsed.get("stretch_roles")
            or existing.get("stretch_roles")
            or []
        )

        with rc1:
            core_roles_text = st.text_area(
                "Core roles (one per line)",
                value="\n".join(default_core),
                height=130,
                help="Roles that directly match your background — highest search priority and scoring weight",
            )
        with rc2:
            stretch_roles_text = st.text_area(
                "Stretch roles (one per line)",
                value="\n".join(default_stretch),
                height=130,
                help="Adjacent/growth roles — searched with lower priority and scored lower than core roles",
            )

        default_locs = parsed.get("locations") or existing.get("locations") or []
        all_loc_opts = list(dict.fromkeys([l for l in default_locs] + CITIES))
        locations = st.multiselect(
            "Target locations",
            options=all_loc_opts,
            default=[l for l in default_locs if l in all_loc_opts],
        )

        summary = st.text_area(
            "Professional summary (optional — auto-generated if blank)",
            value=_d("summary", ep.get("summary", "")),
            height=100,
        )

        save = st.form_submit_button("Save Profile", type="primary", use_container_width=True)

    if save:
        errors: list[str] = []
        if not min_sal:
            errors.append("Min salary is required.")
        if not max_sal:
            errors.append("Max salary is required.")
        if min_sal and max_sal and min_sal > max_sal:
            errors.append("Min salary cannot be greater than max salary.")

        if errors:
            for e in errors:
                st.error(e)
        else:
            core_roles = [r.strip() for r in core_roles_text.splitlines() if r.strip()]
            stretch_roles = [r.strip() for r in stretch_roles_text.splitlines() if r.strip()]
            from src.profile_generator import generate_profile, write_profile

            overrides = {
                "name": name, "title": title,
                "years_experience": years, "level": level,
                "skills": skills,
                "core_roles": core_roles, "stretch_roles": stretch_roles,
                "locations": locations, "summary": summary,
                "salary_min": min_sal, "salary_max": max_sal,
            }
            write_profile(generate_profile(parsed or {}, overrides=overrides))
            st.session_state.pop("last_result", None)
            st.session_state.pop("resume_feedback", None)
            st.success("Profile saved!")
            st.info("Head to **Dashboard** and click **Run Agent Now** to search jobs with your new profile.")


# ── Page: Dashboard ──────────────────────────────────────────────────────


def page_dashboard() -> None:
    st.header("Dashboard")

    if not _setup_done():
        st.warning("Profile not found — complete **Setup** first.")
        return

    status = _status()
    c1, c2, c3 = st.columns(3)
    c1.metric("Profile", "Ready" if status["profile"] else "Missing")
    c2.metric("Resume", "Ready" if status["resume"] else "Missing")
    c3.metric("API Keys", "Set" if status["api_keys"] else "Not set")

    st.divider()
    st.subheader("Run Agent")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        max_jobs = st.number_input("Max jobs", 10, 100, 30)
    with c2:
        min_score = st.slider("Min score %", 0, 100, 20) / 100
    with c3:
        gen_letters = st.checkbox("Cover letters", value=True)
    with c4:
        auto_apply = st.checkbox("Auto-apply", value=False)

    profile_data = _load_profile() or {}
    has_roles = profile_data.get("core_roles") or profile_data.get("stretch_roles") or profile_data.get("preferred_roles")
    if not has_roles:
        st.warning("Your profile has no preferred roles. Go to **Setup**, upload a resume, and **Save Profile** first.")

    if st.button("Run Agent Now", type="primary", use_container_width=True):
        with st.status("Running agent…", expanded=True) as sw:
            try:
                sw.write("Searching job sources in parallel…")
                from src.agent import run

                result = run(
                    max_jobs=max_jobs,
                    min_score=min_score,
                    generate_letters=gen_letters,
                    auto_apply=auto_apply,
                )
                st.session_state["last_result"] = result
                sw.update(label="Agent run complete!", state="complete")
            except Exception as exc:
                sw.update(label="Agent failed", state="error")
                st.error(str(exc))

    result = st.session_state.get("last_result")
    if result:
        st.divider()
        st.subheader("Latest Results")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Jobs Found", result.get("jobs_found", 0))
        c2.metric("Scored", result.get("scored_count", 0))
        c3.metric("Cover Letters", result.get("cover_letters_generated", 0))
        c4.metric("Applied", result.get("browser_applied", 0))

        if result.get("report_path"):
            st.info(f"Report saved → `{result['report_path']}`")

        preview = result.get("report_preview", "")
        if preview:
            with st.expander("Report Preview", expanded=True):
                st.markdown(preview)
    else:
        st.divider()
        st.info("No results yet. Click **Run Agent Now** above to start your first search.")


# ── Page: Reports ────────────────────────────────────────────────────────


def page_reports() -> None:
    st.header("Reports & History")

    tab_reports, tab_history = st.tabs(["Daily Reports", "Application History"])

    with tab_reports:
        ensure_dirs()
        reports = sorted(REPORTS_DIR.glob("daily_*.md"), reverse=True)
        if not reports:
            st.info("No reports yet. Run the agent to generate your first report.")
        else:
            selected = st.selectbox(
                "Select report",
                reports,
                format_func=lambda p: p.stem.replace("daily_", ""),
            )
            if selected:
                st.markdown(selected.read_text(encoding="utf-8"))

    with tab_history:
        csv_path = DATA_DIR / "applications.csv"
        if not csv_path.exists():
            st.info("No applications tracked yet.")
            return

        with open(csv_path, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        if not rows:
            st.info("No applications tracked yet.")
            return

        c1, c2, c3 = st.columns(3)
        c1.metric("Total Applications", len(rows))
        c2.metric("Applied", sum(1 for r in rows if r.get("status") == "applied"))
        c3.metric("Suggested", sum(1 for r in rows if r.get("status") == "suggested"))

        import pandas as pd

        df = pd.DataFrame(rows)
        display_cols = ["title", "company", "score", "status", "applied_at", "url"]
        display_cols = [c for c in display_cols if c in df.columns]

        if "score" in df.columns:
            df["score"] = pd.to_numeric(df["score"], errors="coerce")

        st.dataframe(
            df[display_cols],
            use_container_width=True,
            column_config={
                "url": st.column_config.LinkColumn("Apply Link"),
                "score": st.column_config.ProgressColumn("Score", min_value=0, max_value=1, format="%.0f%%"),
            },
            hide_index=True,
        )


# ── Page: Settings ───────────────────────────────────────────────────────


def page_settings() -> None:
    st.header("Settings")

    tab_creds, tab_data = st.tabs(["API Keys & Credentials", "Data Management"])

    with tab_creds:
        env = _load_env()

        with st.form("all_creds"):
            st.subheader("AI & Cover Letters")
            groq = st.text_input("Groq API Key", value=env.get("GROQ_API_KEY", ""), type="password")

            st.subheader("Job Search Sources")
            st.caption(
                "Add API keys for the sources you want. More sources = broader coverage. "
                "Remotive is free and auto-enabled when Remote is in your locations."
            )
            c1, c2 = st.columns(2)
            with c1:
                serp = st.text_input(
                    "SerpAPI Key (Google Jobs)",
                    value=env.get("SERPAPI_KEY", ""), type="password",
                    help="https://serpapi.com — 100 free searches/month",
                )
                adzuna_id = st.text_input(
                    "Adzuna App ID",
                    value=env.get("ADZUNA_APP_ID", ""),
                    help="https://developer.adzuna.com — 250 free requests/day",
                )
                jsearch_key = st.text_input(
                    "JSearch API Key (RapidAPI)",
                    value=env.get("JSEARCH_API_KEY", ""), type="password",
                    help="https://rapidapi.com/letscrape-6bRDu3Sgupt/api/jsearch",
                )
            with c2:
                rapidapi_key = st.text_input(
                    "RapidAPI Key (LinkedIn Jobs)",
                    value=env.get("RAPIDAPI_KEY", ""), type="password",
                    help="https://rapidapi.com/jaypat87/api/linkedin-jobs-search",
                )
                adzuna_key = st.text_input(
                    "Adzuna App Key",
                    value=env.get("ADZUNA_APP_KEY", ""), type="password",
                )
                st.info("Remotive: free, no key needed")

            st.subheader("Auto-Apply Credentials")
            c1, c2 = st.columns(2)
            with c1:
                li_email = st.text_input("LinkedIn Email", value=env.get("LINKEDIN_EMAIL", ""))
                nk_email = st.text_input("Naukri Email", value=env.get("NAUKRI_EMAIL", ""))
                ap_email = st.text_input("Apply Email (generic)", value=env.get("APPLY_EMAIL", ""))
            with c2:
                li_pass = st.text_input("LinkedIn Password", value=env.get("LINKEDIN_PASSWORD", ""), type="password")
                nk_pass = st.text_input("Naukri Password", value=env.get("NAUKRI_PASSWORD", ""), type="password")
                ap_pass = st.text_input("Apply Password", value=env.get("APPLY_PASSWORD", ""), type="password")

            st.subheader("Email Reports")
            c1, c2 = st.columns(2)
            with c1:
                smtp_host = st.text_input("SMTP Host", value=env.get("SMTP_HOST", "smtp.gmail.com"))
                smtp_user = st.text_input("SMTP User", value=env.get("SMTP_USER", ""))
                from_email = st.text_input("From Email", value=env.get("FROM_EMAIL", ""))
            with c2:
                smtp_port = st.text_input("SMTP Port", value=env.get("SMTP_PORT", "587"))
                smtp_pass = st.text_input("SMTP Password", value=env.get("SMTP_PASSWORD", ""), type="password")
                to_email = st.text_input("To Email", value=env.get("TO_EMAIL", ""))

            if st.form_submit_button("Save All", type="primary", use_container_width=True):
                env.update({
                    "GROQ_API_KEY": groq, "SERPAPI_KEY": serp,
                    "JSEARCH_API_KEY": jsearch_key,
                    "ADZUNA_APP_ID": adzuna_id, "ADZUNA_APP_KEY": adzuna_key,
                    "RAPIDAPI_KEY": rapidapi_key,
                    "LINKEDIN_EMAIL": li_email, "LINKEDIN_PASSWORD": li_pass,
                    "NAUKRI_EMAIL": nk_email, "NAUKRI_PASSWORD": nk_pass,
                    "APPLY_EMAIL": ap_email, "APPLY_PASSWORD": ap_pass,
                    "SMTP_HOST": smtp_host, "SMTP_PORT": smtp_port,
                    "SMTP_USER": smtp_user, "SMTP_PASSWORD": smtp_pass,
                    "FROM_EMAIL": from_email, "TO_EMAIL": to_email,
                })
                _save_env(env)
                st.success("All settings saved!")

    with tab_data:
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Encrypt Credentials")
            st.caption("Protect API keys and passwords with a master password.")
            with st.form("encrypt_form"):
                master = st.text_input("Master password", type="password")
                confirm = st.text_input("Confirm password", type="password")
                if st.form_submit_button("Encrypt .env", use_container_width=True):
                    if not master:
                        st.error("Password cannot be empty.")
                    elif master != confirm:
                        st.error("Passwords do not match.")
                    else:
                        try:
                            from src.secrets_manager import encrypt_env

                            encrypt_env(password=master)
                            st.success("Encrypted → `.env.enc`")
                        except Exception as exc:
                            st.error(str(exc))

        with c2:
            st.subheader("Clear Data")
            st.caption("Remove generated files and start fresh.")
            if st.button("Clear application history"):
                csv_path = DATA_DIR / "applications.csv"
                if csv_path.exists():
                    csv_path.unlink()
                    st.success("Application history cleared.")
                else:
                    st.info("Nothing to clear.")
            if st.button("Clear all reports"):
                removed = 0
                for rp in REPORTS_DIR.glob("daily_*.md"):
                    rp.unlink()
                    removed += 1
                st.success(f"Removed {removed} report(s)." if removed else "No reports to clear.")


# ── Main ─────────────────────────────────────────────────────────────────


def _inject_css() -> None:
    st.markdown(_GLASS_CSS, unsafe_allow_html=True)


def _sidebar_status() -> None:
    with st.sidebar:
        st.divider()
        s = _status()
        st.markdown("**Status**")
        st.markdown(_check("Groq API key", s["groq_key"]))
        st.markdown(_check("Profile configured", s["profile"]))
        st.markdown(_check("Resume uploaded", s["resume"]))
        st.markdown(_check("Job search key", s["api_keys"]))

        st.divider()
        if st.button("🗑️ Reset Everything", use_container_width=True):
            for p in RESUME_DIR.glob("*"):
                if p.name != ".gitkeep":
                    p.unlink(missing_ok=True)
            PROFILE_PATH.write_text(
                "profile:\n  name: \"\"\n  title: \"\"\n  years_experience: 0\n"
                "  level: intermediate\n  skills: []\n  summary: \"\"\n"
                "core_roles: []\nstretch_roles: []\n"
                "preferred_companies:\n  type: any\n  names: []\n"
                "locations: []\nsalary_lpa:\n  min: 0\n  max: 0\n"
                "  compare_only_when_listed: true\nmin_score_auto_apply: 0.65\n",
                encoding="utf-8",
            )
            for f in DATA_DIR.glob("*"):
                if f.name not in (".gitkeep", "applications.csv"):
                    f.unlink(missing_ok=True)
            for f in REPORTS_DIR.glob("*"):
                if f.name != ".gitkeep":
                    f.unlink(missing_ok=True)
            log_dir = ROOT / "logs"
            if log_dir.exists():
                for f in log_dir.glob("*"):
                    f.unlink(missing_ok=True)
            kept = st.session_state.get("_groq_key", "")
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            if kept:
                st.session_state["_groq_key"] = kept
            st.success("All data cleared. API keys preserved.")
            st.rerun()


def _wrap_setup():
    _inject_css()
    _sidebar_status()
    page_setup()


def _wrap_dashboard():
    _inject_css()
    _sidebar_status()
    page_dashboard()


def _wrap_reports():
    _inject_css()
    _sidebar_status()
    page_reports()


def _wrap_settings():
    _inject_css()
    _sidebar_status()
    page_settings()


pages = [
    st.Page(_wrap_setup, title="Setup", icon="🏠", url_path="setup", default=True),
    st.Page(_wrap_dashboard, title="Dashboard", icon="🚀", url_path="dashboard"),
    st.Page(_wrap_reports, title="Reports", icon="📋", url_path="reports"),
    st.Page(_wrap_settings, title="Settings", icon="⚙️", url_path="settings"),
]

nav = st.navigation(pages)
nav.run()
