"""Extract structured profile data from a resume file.

Supports PDF (via pypdf or pdftotext), DOCX (via stdlib zipfile), and TXT.
If a Groq API key is available the raw text is sent to the LLM for
structured extraction; otherwise a heuristic regex parser is used.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from src.log import get_logger
from src.retry import retry

log = get_logger(__name__)

# ── Text extraction ──────────────────────────────────────────────────────


def extract_text(path: Path) -> str:
    """Return plain text from a PDF, DOCX, or TXT file."""
    suffix = path.suffix.lower()
    if suffix == ".txt":
        return path.read_text(encoding="utf-8", errors="ignore")
    if suffix == ".docx":
        return _extract_docx(path)
    if suffix == ".pdf":
        return _extract_pdf(path)
    raise ValueError(f"Unsupported resume format: {suffix}")


def _fix_spacing(text: str) -> str:
    """Re-insert spaces when PDF extraction merges words together.

    Detects the problem by checking if the space-to-character ratio is
    abnormally low, then applies heuristic space insertion.
    """
    if not text or len(text) < 50:
        return text
    space_ratio = text.count(" ") / len(text)
    if space_ratio > 0.08:
        return text

    log.debug("Low space ratio (%.2f%%) — applying spacing fix", space_ratio * 100)
    fixed = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    fixed = re.sub(r"([a-zA-Z])(\d)", r"\1 \2", fixed)
    fixed = re.sub(r"(\d)([a-zA-Z])", r"\1 \2", fixed)
    fixed = re.sub(r"([.!?,;:])([A-Za-z])", r"\1 \2", fixed)
    fixed = re.sub(r"([a-z])(—|–|-\s)([A-Za-z])", r"\1 \2 \3", fixed)
    return fixed


def _extract_pdf(path: Path) -> str:
    # Prefer pdftotext (better spacing) over pypdf
    if shutil.which("pdftotext"):
        result = subprocess.run(
            ["pdftotext", "-layout", str(path), "-"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout

    try:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        pages: list[str] = []
        for page in reader.pages:
            raw = page.extract_text() or ""
            pages.append(_fix_spacing(raw))
        return "\n".join(pages)
    except ImportError:
        pass

    raise RuntimeError(
        "Cannot read PDF — install pypdf (`pip install pypdf`) "
        "or pdftotext (poppler-utils)."
    )


def _extract_docx(path: Path) -> str:
    """Parse DOCX using only stdlib (zipfile + xml)."""
    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    texts: list[str] = []
    with zipfile.ZipFile(path) as zf:
        with zf.open("word/document.xml") as f:
            tree = ElementTree.parse(f)
            for para in tree.iter(f"{ns}p"):
                parts = [node.text for node in para.iter(f"{ns}t") if node.text]
                if parts:
                    texts.append("".join(parts))
    return "\n".join(texts)


# ── LLM-based extraction ────────────────────────────────────────────────

_PARSE_PROMPT = """\
You are a resume parser. Extract structured data from the resume text below.
Return ONLY valid JSON with these exact keys (use empty string or empty list if unknown):

{{
  "name": "Full Name",
  "email": "email@example.com",
  "phone": "phone number",
  "title": "Current or most recent job title",
  "years_experience": 0,
  "level": "junior | intermediate | senior",
  "skills": ["skill1", "skill2"],
  "summary": "2-3 sentence professional summary",
  "preferred_roles": ["Role 1", "Role 2", "Role 3"],
  "role_reasons": {{"Role 1": "one-line reason why this role fits", "Role 2": "reason"}},
  "locations": ["City 1", "City 2"],
  "education": "Highest degree and institution"
}}

Rules:
- "preferred_roles" should be 5-10 realistic job titles this person should apply to,
  inferred from their experience and skills. Include a mix of exact-match and
  adjacent roles they could transition into.
- "role_reasons" must have one entry per role in "preferred_roles", with a short
  (under 15 words) justification based on the candidate's actual experience.
- "level": junior (<3 yrs), intermediate (3-7 yrs), senior (>7 yrs).
- "skills" should include technologies, tools, and soft skills mentioned.
- "locations" should list cities mentioned or inferred from work history.

Resume text:
{resume_text}
"""


@retry(max_attempts=2, base_delay=2.0, retryable=(Exception,))
def _llm_parse(resume_text: str, api_key: str, model: str) -> dict[str, Any]:
    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
    prompt = _PARSE_PROMPT.format(resume_text=resume_text[:6000])
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=800,
        temperature=0.1,
    )
    raw = (resp.choices[0].message.content or "").strip()
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError("LLM did not return valid JSON")
    return json.loads(raw[start:end])


# ── Heuristic fallback ──────────────────────────────────────────────────

_SECTION_RE = re.compile(
    r"^(?:skills|technical skills|core competencies|expertise|experience"
    r"|education|summary|objective|profile|about|certifications?)\s*[:|\-]?\s*$",
    re.IGNORECASE | re.MULTILINE,
)

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_RE = re.compile(r"[\+]?\d[\d\s\-().]{7,15}\d")
_YEARS_RE = re.compile(r"(\d{1,2})\+?\s*(?:years?|yrs?)", re.IGNORECASE)

_COMMON_SKILLS = [
    "python", "java", "javascript", "typescript", "react", "node", "angular",
    "vue", "sql", "nosql", "mongodb", "postgresql", "mysql", "redis",
    "docker", "kubernetes", "aws", "gcp", "azure", "terraform", "ansible",
    "jenkins", "git", "linux", "ci/cd", "rest", "graphql", "microservices",
    "agile", "scrum", "jira", "excel", "power bi", "tableau", "sap",
    "salesforce", "hris", "recruitment", "talent acquisition", "employee relations",
    "onboarding", "payroll", "compliance", "performance management",
    "machine learning", "deep learning", "nlp", "data science", "pandas",
    "tensorflow", "pytorch", "spark", "hadoop", "kafka", "elasticsearch",
    "figma", "sketch", "photoshop", "illustrator", "ui/ux",
    "communication", "leadership", "project management", "stakeholder management",
]

_INDIAN_CITIES = [
    "bangalore", "bengaluru", "mumbai", "delhi", "hyderabad", "pune",
    "chennai", "kolkata", "gurgaon", "gurugram", "noida", "ahmedabad",
    "jaipur", "lucknow", "chandigarh", "kochi", "indore", "remote",
]


def _heuristic_parse(text: str) -> dict[str, Any]:
    """Best-effort extraction without an LLM."""
    lines = text.strip().splitlines()
    name = lines[0].strip() if lines else ""
    if len(name) > 60 or not name:
        name = ""

    email_match = _EMAIL_RE.search(text)
    phone_match = _PHONE_RE.search(text)

    years = 0
    for m in _YEARS_RE.finditer(text):
        y = int(m.group(1))
        if y > years:
            years = y

    low = text.lower()
    skills = [s for s in _COMMON_SKILLS if s in low]

    locations: list[str] = []
    for city in _INDIAN_CITIES:
        if city in low:
            locations.append(city.capitalize())
    locations = list(dict.fromkeys(locations))

    level = "junior"
    if years >= 7:
        level = "senior"
    elif years >= 3:
        level = "intermediate"

    title = ""
    for line in lines[1:20]:
        stripped = line.strip()
        if 3 < len(stripped) < 80 and not _EMAIL_RE.search(stripped) and not _PHONE_RE.search(stripped):
            if any(kw in stripped.lower() for kw in ["engineer", "manager", "developer", "analyst",
                                                      "designer", "consultant", "lead", "director",
                                                      "specialist", "coordinator", "executive",
                                                      "architect", "scientist", "officer"]):
                title = stripped
                break

    return {
        "name": name,
        "email": email_match.group(0) if email_match else "",
        "phone": phone_match.group(0) if phone_match else "",
        "title": title,
        "years_experience": years,
        "level": level,
        "skills": skills[:20],
        "summary": "",
        "preferred_roles": [],
        "locations": locations[:6] or ["Remote"],
        "education": "",
    }


# ── Public API ───────────────────────────────────────────────────────────


def parse_resume(path: Path, api_key: str | None = None) -> dict[str, Any]:
    """Extract structured profile data from a resume file.

    Uses Groq LLM if *api_key* is provided, otherwise heuristic fallback.
    """
    log.info("Extracting text from %s", path.name)
    text = extract_text(path)
    if not text.strip():
        raise ValueError(f"Could not extract any text from {path.name}")

    api_key = api_key or os.environ.get("GROQ_API_KEY", "").strip()
    model = os.environ.get("GROQ_LLM_MODEL", "llama-3.3-70b-versatile").strip()

    if api_key:
        log.info("Parsing resume with LLM (%s)", model)
        try:
            data = _llm_parse(text, api_key, model)
            data.setdefault("role_reasons", {})
            log.info("LLM extraction complete — name=%s, skills=%d", data.get("name"), len(data.get("skills", [])))
            return data
        except Exception as exc:
            log.warning("LLM parsing failed (%s), falling back to heuristic", exc)

    log.info("Parsing resume with heuristic extractor")
    data = _heuristic_parse(text)
    log.info("Heuristic extraction complete — name=%s, skills=%d", data.get("name"), len(data.get("skills", [])))
    return data


# ── Resume review / improvement suggestions ─────────────────────────────

_REVIEW_PROMPT = """\
You are a senior career coach and resume writer. Perform a thorough,
section-by-section review of the resume below. Cover EVERY major bullet
point and section. Provide as many improvements as possible.

Return ONLY valid JSON — an array of objects (aim for 10-15), each with:
  "category"    — one of: "Wording", "Metrics", "Keywords", "Skills Gap",
                  "Structure", "Formatting"
  "original"    — the EXACT phrase or sentence from the resume that needs
                  improvement. Copy it verbatim, preserving spaces and
                  punctuation. If suggesting a new addition, use "[missing]".
  "replacement" — the improved version, ready to paste in. Be specific:
                  add numbers, percentages, timeframes, tools, and outcomes.
  "reason"      — one sentence explaining why.

Go through EACH section of the resume systematically:

1. SUMMARY / OBJECTIVE — rewrite vague statements with impact verbs and
   measurable outcomes.
2. EVERY WORK EXPERIENCE bullet — add quantification where missing
   (team size, percentage improvements, dollar amounts, SLA numbers, etc.).
   Rewrite weak verbs ("handled", "responsible for", "worked on") into
   strong action verbs ("spearheaded", "reduced", "automated", "delivered").
3. SKILLS section — identify missing ATS keywords for the candidate's
   target industry. Suggest where to add them.
4. CERTIFICATIONS / EDUCATION — suggest relevant certifications that are
   missing but would strengthen the profile.
5. STRUCTURE — missing sections (e.g. certifications, projects, summary),
   section ordering, formatting issues.

Rules:
- Quote the EXACT original text. Do not paraphrase or shorten it.
- In "replacement", write the complete improved sentence — not a diff.
- Cover as many bullet points as the token limit allows.
- If the resume is strong in an area, skip it — only include improvements.

Resume text:
{resume_text}
"""


@retry(max_attempts=2, base_delay=2.0, retryable=(Exception,))
def _llm_review(resume_text: str, api_key: str, model: str) -> list[dict[str, str]]:
    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
    prompt = _REVIEW_PROMPT.format(resume_text=resume_text[:8000])
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=4000,
        temperature=0.3,
    )
    raw = (resp.choices[0].message.content or "").strip()
    start = raw.find("[")
    end = raw.rfind("]") + 1
    if start == -1 or end == 0:
        raise ValueError("LLM did not return a valid JSON array")
    return json.loads(raw[start:end])


def review_resume(path: Path, api_key: str | None = None) -> list[dict[str, str]]:
    """Return 10-15 improvement suggestions covering the entire resume.

    Each item has keys: category, original, replacement, reason.
    Requires a Groq API key.
    """
    text = extract_text(path)
    if not text.strip():
        raise ValueError(f"Could not extract text from {path.name}")

    api_key = api_key or os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        raise ValueError("Groq API key required for resume review")

    model = os.environ.get("GROQ_LLM_MODEL", "llama-3.3-70b-versatile").strip()
    log.info("Reviewing resume with LLM (%s)", model)
    suggestions = _llm_review(text, api_key, model)
    log.info("Resume review complete — %d suggestions", len(suggestions))
    return suggestions
