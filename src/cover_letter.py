"""Generate tailored cover letters using Groq (or fallback template)."""
from __future__ import annotations

import os
from pathlib import Path

from src.config import DATA_DIR
from src.log import get_logger
from src.models import ScoredJob
from src.retry import retry

log = get_logger(__name__)


def _candidate_name(profile: dict) -> str:
    return (
        os.environ.get("CANDIDATE_NAME", "").strip()
        or profile.get("profile", {}).get("name", "")
        or "Candidate"
    )


@retry(max_attempts=2, base_delay=2.0, retryable=(Exception,))
def _call_groq(api_key: str, model: str, prompt: str) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
    r = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=400,
    )
    return (r.choices[0].message.content or "").strip()


def generate_cover_letter(scored: ScoredJob, profile: dict) -> str:
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        log.debug("No GROQ_API_KEY — using template cover letter")
        return _fallback_letter(scored, profile)

    model = os.environ.get("GROQ_LLM_MODEL", "llama-3.3-70b-versatile").strip()
    candidate_name = _candidate_name(profile)

    try:
        job = scored.job
        summary = profile.get("profile", {}).get("summary", "")
        skills = profile.get("profile", {}).get("skills", [])
        prompt = f"""Write a short, professional cover letter (under 200 words) for this role.
Candidate name: {candidate_name}
Candidate summary: {summary}
Key skills: {', '.join(skills[:8])}
Job title: {job.title}
Company: {job.company}
Job description (excerpt): {job.description[:1500]}

Match the tone to the company and role. Mention 2–3 relevant skills. End with a clear one-line CTA.
Use "I" and "my" for the candidate. End the letter with "Best regards," followed by the candidate name: {candidate_name}. Do not use placeholders like [Your Name]."""

        result = _call_groq(api_key, model, prompt)
        log.info("Cover letter generated for %s @ %s", job.title, job.company)
        return result
    except Exception as exc:
        log.warning("Cover letter generation failed (%s), using template", exc)
        return _fallback_letter(scored, profile)


def _fallback_letter(scored: ScoredJob, profile: dict) -> str:
    job = scored.job
    summary = profile.get("profile", {}).get("summary", "")
    skills = ", ".join(profile.get("profile", {}).get("skills", [])[:5])
    name = _candidate_name(profile)
    return f"""Dear Hiring Team,

I am writing to apply for the {job.title} position at {job.company}.

{summary}

My experience aligns with your requirements, including: {skills}. I am particularly interested in contributing to your team's success.

I would welcome the opportunity to discuss how my background can contribute to your team.

Best regards,
{name}"""


def save_cover_letter(scored: ScoredJob, content: str) -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if c.isalnum() or c in " -_" else "_" for c in scored.job.company)[:40]
    path = DATA_DIR / f"cover_{scored.job.id}_{safe}.txt"
    path.write_text(content, encoding="utf-8")
    return path
