# Autonomous Job Search Agent

An autonomous agent that searches for jobs, scores them against your profile, generates personalized cover letters, and auto-applies via browser — all from your resume.

---

## Getting Started

### Prerequisites

- Python 3.10+ installed on your machine
- A resume file (PDF, DOCX, or TXT)

### Option A: Web UI (recommended for everyone)

**1. Clone and launch**

```bash
git clone https://github.com/dunjeonmaster07/autonomous-job-agent.git
cd autonomous-job-agent
./start.sh
```

This single command creates a virtual environment, installs all dependencies, and opens the web UI in your browser at `http://localhost:8501/setup`. No email prompt, no CLI questions.

**2. Setup page — add your API keys**

The first thing you see is the API key form. Groq is mandatory — it powers resume parsing, role suggestions, cover letters, and resume review.

- **Groq API Key** *(required)* — get one in 30 seconds at [console.groq.com/keys](https://console.groq.com/keys).
- **Job Search Sources** *(at least one recommended)* — add as many as you like for broader coverage:
  - **SerpAPI** — Google Jobs aggregator (LinkedIn, Indeed, Glassdoor, Naukri, TimesJobs). [100 free/month](https://serpapi.com).
  - **Adzuna** — India-focused job aggregator. [250 free requests/day](https://developer.adzuna.com/).
  - **RapidAPI** — powers LinkedIn Jobs and JSearch. [Free tier](https://rapidapi.com/jaypat87/api/linkedin-jobs-search).
  - **Remotive** — remote tech jobs. Always active, no key needed.

Until the Groq key is saved, the rest of the setup page is locked.

**3. Setup page — upload your resume**

Drag and drop your resume (PDF, DOCX, or TXT). The AI parses it instantly and shows:

- **Extracted Profile** — name, title, years of experience, skills displayed as metric cards
- **Role-Based Targets** — 5-10 job titles you should apply for, each with a one-line reason based on your actual experience (e.g., "Cloud Support Engineer — 10 yrs cloud + incident response")

**4. Setup page — review your resume (optional)**

Click **Review My Resume** to get AI-powered improvement suggestions. Each suggestion shows:

- **Current text** (red) — the exact phrase from your resume that needs work
- **Replace with** (green) — the improved version, ready to paste back
- **Reason** — why this change makes your resume more competitive

Covers wording, metrics, keywords, skills gaps, structure, and formatting across the entire resume.

**5. Setup page — save your profile**

Everything extracted from your resume appears in an editable form:

- **Name, title, experience** — text fields
- **Experience level** — dropdown (junior / intermediate / senior)
- **Skills** — multiselect with 60+ common skills pre-loaded, plus anything found in your resume
- **Core roles** — roles that directly match your background (searched first, scored highest)
- **Stretch roles** — adjacent/growth roles (searched with lower priority, scored lower)
- **Target locations** — multiselect with major Indian cities + Remote
- **Salary range** — min/max LPA (required)

Review, tweak if needed, click **Save Profile**.

**6. Dashboard — run the agent**

Navigate to `http://localhost:8501/dashboard`. Configure:

- Max jobs to search (default: 30)
- Minimum score threshold (default: 20%)
- Generate cover letters (on/off)
- Auto-apply via browser (on/off)

Click **Run Agent Now**. A live status indicator shows progress. After 15-30 seconds, results appear:

- **Jobs Found** — total from all sources
- **Scored** — jobs above your score threshold
- **Cover Letters** — generated for top matches
- **Applied** — auto-submitted via browser (if enabled)

Below the metrics, the full daily report is rendered with scored jobs, match reasons, and clickable apply links.

**7. Reports — browse anytime**

Navigate to `http://localhost:8501/reports`:

- **Daily Reports** tab — select any date to see that day's report
- **Application History** tab — sortable table of all tracked applications with scores, statuses, and apply links

**8. Settings — update later**

Navigate to `http://localhost:8501/settings` to update API keys, platform credentials (LinkedIn, Naukri, etc.), email report settings, encrypt credentials, or clear data.

### Option B: CLI (for servers, cron, or terminal users)

**1. Install**

```bash
git clone https://github.com/dunjeonmaster07/autonomous-job-agent.git
cd autonomous-job-agent
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

**2. Run the setup wizard**

```bash
python onboard.py
```

The wizard walks through five steps in your terminal:

- **Step 1** — Paste or drag your resume file path
- **Step 2** — Review extracted profile (name, title, skills, roles, locations, salary)
- **Step 3** — Paste Groq key + job search API keys (SerpAPI, Adzuna, RapidAPI)
- **Step 4** — Optionally set LinkedIn, Naukri, and generic apply credentials
- **Step 5** — Optionally encrypt all credentials with a master password

**3. Run the agent**

```bash
python run_agent.py
```

**4. Set up daily auto-run (optional)**

```bash
python setup_cron.py         # Installs a daily cron job
python src/run_daily.py      # Or run as a background scheduler
```

---

## For Non-Technical Users

If you've never used a terminal before, here's the absolute minimum:

1. **Open Terminal** (on Mac: search for "Terminal" in Spotlight)
2. **Paste this** and press Enter:

```bash
cd ~/Downloads && git clone https://github.com/dunjeonmaster07/autonomous-job-agent.git && cd autonomous-job-agent && ./start.sh
```

3. **A browser window opens** at `http://localhost:8501/setup` — no email prompt, no CLI questions.
4. **Paste your Groq API key** (free — link provided on the page).
5. **Upload your resume** (drag and drop) — the AI extracts your profile and suggests roles.
6. **Click "Review My Resume"** to get specific before/after improvement suggestions.
7. **Save your profile**, go to **Dashboard**, **click Run**. Your job matches appear with scores, reasons, and apply links.

If `./start.sh` doesn't work, try:

```bash
chmod +x start.sh && ./start.sh
```

---

## What It Does

```
Resume  →  Profile  →  Search  →  Score  →  Cover Letters  →  Auto-Apply  →  Report  →  Email
```

| Step | What happens |
|------|-------------|
| **Upload resume** | Extracts text from PDF/DOCX/TXT, parses with AI or heuristic |
| **Generate profile** | Builds skills, roles, locations, salary from your resume |
| **Search jobs** | Queries up to 5 sources in parallel (SerpAPI, JSearch, Adzuna, LinkedIn, Remotive), deduplicates |
| **Score & rank** | Role-aware matching: core role title 40%, stretch 20%, skills 25%, seniority 10%, location 15%, salary 10%. Filters Director/VP-level jobs. |
| **Cover letters** | AI-generated via Groq LLM, falls back to template |
| **Auto-apply** | Playwright browser automation for LinkedIn, Naukri, Workday, Greenhouse, Lever, Indeed |
| **Track** | CSV log of every application with score, status, timestamp |
| **Report & email** | Daily markdown report + optional HTML email |

---

## Web UI Pages

### Setup (`/setup`)
Groq API key (mandatory gate) → job search API keys (SerpAPI, Adzuna, RapidAPI — all optional, Remotive auto-enabled) → resume upload → AI-extracted profile summary → role-based targets (5-10 roles with reasons) → resume review (before/after suggestions) → editable profile form with core/stretch role tiers and salary validation. Glassmorphism UI with frosted-glass cards.

### Dashboard (`/dashboard`)
Status metric cards, configurable run parameters (max jobs, min score, cover letters, auto-apply), one-click "Run Agent" button with live status, results metrics, and report preview.

### Reports (`/reports`)
Browse daily reports by date, rendered as formatted markdown. Application history table with sortable columns, score progress bars, and clickable apply links.

### Settings (`/settings`)
Update all credentials — AI key, job search sources (SerpAPI, Adzuna, RapidAPI, JSearch), auto-apply logins (LinkedIn, Naukri), and email settings — in one form. Encrypt credentials with a master password. Clear data and reports.

---

## Architecture

### Scoring System

Roles are split into **core** (direct background match) and **stretch** (adjacent/growth). Title matches score higher than description-only mentions.

| Weight | Criterion |
|-------:|-----------|
| 40% | Core role exact match in job **title** |
| 35% | Core role word-overlap match in title (≥60% words) |
| 20% | Stretch role match in job title |
| 8–15% | Role mentioned in description only (stretch/core) |
| 25% | Skills overlap (5% per skill, up to 5) |
| 10% | Seniority level fit |
| 15% | Location match (handles aliases: Bangalore/Bengaluru, Gurgaon/Gurugram) |
| 10% | Salary in range (only when job listing shows salary) |
| +5% | Bonus for 3+ skills with a core role match |
| 0% | **Filtered out**: Director/VP/C-suite titles, fresher-only jobs |

### Browser Auto-Apply

| Platform | Strategy |
|----------|----------|
| LinkedIn | Easy Apply flow |
| Naukri | Login → Apply → Upload resume |
| Workday | Click Apply → Fill email → Upload |
| Greenhouse | Fill name/email → Upload resume → Submit |
| Lever | Apply → Fill form → Upload → Submit |
| Indeed | Click Apply → Handle redirects |
| Aggregators | Click through to company site |
| Generic | Fallback login + apply detection |

---

## Engineering Details

### No external infrastructure
No database, no Docker, no CI/CD, no cloud deployment. Everything is flat files — CSV, YAML, Markdown, log files.

### Retry mechanism
All external API calls (Groq, SerpAPI, JSearch, SMTP) use exponential backoff with jitter. Configurable attempts, delay, and retryable exception types. Stdlib only.

### Parallel job search
Up to 5 job sources (SerpAPI, JSearch, Adzuna, LinkedIn, Remotive) run concurrently via `ThreadPoolExecutor`. Core roles are searched first; stretch roles fill remaining API budget. Results are merged and deduplicated by job ID.

### Credential encryption
API keys and passwords can be encrypted with a master password using PBKDF2-HMAC-SHA256 (200K iterations). No third-party crypto libraries — stdlib `hashlib` + `os.urandom` only.

### Structured logging
All output uses Python's `logging` module. Console + daily log files in `logs/`. Configurable via `LOG_LEVEL` env var (DEBUG, INFO, WARNING, ERROR).

### File-safe tracking
CSV application tracker uses advisory file locking (`fcntl`) to prevent corruption from concurrent writes.

### Resume parsing
PDF via `pypdf` (or `pdftotext` fallback), DOCX via stdlib `zipfile` + `xml.etree`, TXT direct read. Structured extraction via Groq LLM with heuristic fallback when no API key is available.

---

## Project Structure

```
autonomous-job-agent/
├── start.sh                   # One-touch launcher (run this)
├── app.py                     # Streamlit web UI
├── onboard.py                 # CLI setup wizard (alternative)
├── run_agent.py               # CLI agent runner
├── setup_cron.py              # Install daily cron job
├── requirements.txt           # Python dependencies
│
├── config/
│   └── profile.yaml           # Your profile (auto-generated or manual)
│
├── src/
│   ├── agent.py               # Pipeline orchestrator (parallel search)
│   ├── config.py              # Configuration loader
│   ├── models.py              # Job & ScoredJob dataclasses
│   ├── scorer.py              # Weighted job scoring
│   ├── cover_letter.py        # Cover letter generation (with retry)
│   ├── browser_apply.py       # Browser automation (7+ platforms)
│   ├── tracker.py             # CSV tracker (with file locking)
│   ├── report.py              # Markdown report generator
│   ├── email_report.py        # HTML email sender (with retry)
│   ├── run_daily.py           # Daily scheduler / cron entry
│   ├── log.py                 # Logging configuration
│   ├── retry.py               # Retry decorator (exponential backoff)
│   ├── resume_parser.py       # Resume text extraction + parsing
│   ├── profile_generator.py   # Generate profile.yaml from resume
│   ├── secrets_manager.py     # Encrypt/decrypt credentials
│   │
│   └── sources/               # Pluggable job search providers
│       ├── base.py            # Abstract interface
│       ├── serpapi.py          # SerpAPI Google Jobs (with retry)
│       ├── jsearch.py          # JSearch RapidAPI (with retry)
│       ├── adzuna.py          # Adzuna India aggregator (with retry)
│       ├── linkedin_rapid.py  # LinkedIn Jobs via RapidAPI (with retry)
│       ├── remotive.py        # Remotive remote jobs (free, no key)
│       └── mock.py            # Mock data for testing/fallback
│
├── resume/                    # Your resume (PDF/DOCX)
├── data/                      # Application tracker CSV
├── reports/                   # Daily markdown reports
└── logs/                      # Application log files
```

---

## Configuration

### Environment Variables (`.env`)

| Variable | Required | Description |
|----------|----------|-------------|
| `GROQ_API_KEY` | For AI features | Cover letters & smart resume parsing |
| `SERPAPI_KEY` | Recommended | Google Jobs — aggregates LinkedIn, Indeed, Glassdoor, Naukri (100 free/month) |
| `ADZUNA_APP_ID` | Optional | Adzuna India job aggregator (250 free/day) |
| `ADZUNA_APP_KEY` | Optional | Adzuna app key (pair with APP_ID) |
| `RAPIDAPI_KEY` | Optional | Powers LinkedIn Jobs + JSearch sources |
| `JSEARCH_API_KEY` | Optional | JSearch on RapidAPI (alternative aggregator) |
| `LINKEDIN_EMAIL/PASSWORD` | Optional | LinkedIn Easy Apply |
| `NAUKRI_EMAIL/PASSWORD` | Optional | Naukri auto-apply |
| `APPLY_EMAIL/PASSWORD` | Optional | Generic career sites |
| `SMTP_*` / `TO_EMAIL` | Optional | Email reports |
| `LOG_LEVEL` | Optional | DEBUG, INFO (default), WARNING, ERROR |
| `MASTER_PASSWORD` | Optional | Auto-decrypt `.env.enc` for cron |

Remotive (remote tech jobs) requires no API key — it's auto-enabled when "Remote" is in your locations.

All of these can be set through the **Settings** page in the web UI — no need to edit files.

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `streamlit` | Web UI |
| `pyyaml` | Profile config |
| `python-dotenv` | Environment variables |
| `requests` | HTTP API calls |
| `openai` | Groq LLM client |
| `playwright` | Browser automation |
| `pypdf` | PDF resume parsing |

Everything else (logging, retry, encryption, parallel execution, DOCX parsing) uses **Python stdlib only**.

---

## FAQ

**Q: I'm not technical at all. Can I use this?**
Run `./start.sh` — a browser window opens. Upload your resume, click buttons. Done.

**Q: Do I need a database?**
No. Everything uses flat files.

**Q: Are my passwords safe?**
Go to Settings → Data Management → Encrypt. Your credentials are protected with a master password using PBKDF2.

**Q: What if the agent fails to apply?**
Failures are logged with reasons. Reports include troubleshooting tips and direct apply links. API retries happen automatically.

**Q: Can I run this daily hands-free?**
Yes. `python setup_cron.py` installs a cron job. Set `MASTER_PASSWORD` for unattended decryption.

**Q: What if I don't add any job search API keys?**
Remotive (remote tech jobs) is always active with no key. Beyond that, the agent falls back to mock data. Add SerpAPI, Adzuna, or RapidAPI keys through the Settings page anytime to unlock real job search across LinkedIn, Indeed, Glassdoor, Naukri, and more.

**Q: Web UI or CLI — which should I use?**
Web UI (`./start.sh`) for interactive use. CLI (`python run_agent.py`) for cron jobs, headless servers, or if you prefer the terminal.
