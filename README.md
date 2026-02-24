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
git clone <repo-url> && cd autonomous-job-agent
./start.sh
```

This single command creates a virtual environment, installs all dependencies, and opens the web UI in your browser at `http://localhost:8501`.

**2. Setup page — upload your resume**

Drag and drop your resume file into the upload area. The agent extracts your name, title, skills, experience, and suggests job roles to search for.

**3. Setup page — review your profile**

Everything extracted from your resume appears in an editable form:

- **Name, title, experience** — text fields
- **Experience level** — dropdown (junior / intermediate / senior)
- **Skills** — multiselect with 60+ common skills pre-loaded, plus anything found in your resume
- **Preferred roles** — text area, one role per line (these are what the agent searches for)
- **Target locations** — multiselect with major Indian cities + Remote
- **Salary range** — min/max LPA inputs

Review, tweak if needed, click **Save Profile**.

**4. Setup page — add API keys**

Two fields, both optional but recommended:

- **Groq API Key** (free) — powers AI cover letters and smart resume parsing. Get one at [console.groq.com/keys](https://console.groq.com/keys).
- **SerpAPI Key** (free tier: 100 searches/month) — enables real job search. Get one at [serpapi.com](https://serpapi.com).

Paste your keys, click **Save API Keys**. Without these, the agent uses mock job data and template cover letters.

**5. Dashboard — run the agent**

Click **Dashboard** in the sidebar. Configure:

- Max jobs to search (default: 30)
- Minimum score threshold (default: 20%)
- Generate cover letters (on/off)
- Auto-apply via browser (on/off)

Click **Run Agent Now**. A live status indicator shows progress. After 15–30 seconds, results appear:

- **Jobs Found** — total from all sources
- **Scored** — jobs above your score threshold
- **Cover Letters** — generated for top matches
- **Applied** — auto-submitted via browser (if enabled)

Below the metrics, the full daily report is rendered with scored jobs, match reasons, and clickable apply links.

**6. Reports — browse anytime**

Click **Reports** in the sidebar:

- **Daily Reports** tab — select any date to see that day's report
- **Application History** tab — sortable table of all tracked applications with scores, statuses, and apply links

**7. Settings — update later**

Click **Settings** to update API keys, platform credentials (LinkedIn, Naukri, etc.), email report settings, encrypt credentials, or clear data.

### Option B: CLI (for servers, cron, or terminal users)

**1. Install**

```bash
git clone <repo-url> && cd autonomous-job-agent
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
- **Step 3** — Paste Groq and SerpAPI keys
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
cd ~/Downloads && git clone <repo-url> && cd autonomous-job-agent && ./start.sh
```

3. **A browser window opens.** From here it's all buttons and forms — no typing commands.
4. **Upload your resume** (drag and drop), **review the form**, **paste API keys** (links are provided), **click Run**.
5. **That's it.** Your job matches appear with scores, reasons, and one-click apply links.

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
| **Search jobs** | Queries SerpAPI / JSearch in parallel, deduplicates |
| **Score & rank** | Weighted matching: role 40%, skills 25%, seniority 15%, location 15%, salary 10% |
| **Cover letters** | AI-generated via Groq LLM, falls back to template |
| **Auto-apply** | Playwright browser automation for LinkedIn, Naukri, Workday, Greenhouse, Lever, Indeed |
| **Track** | CSV log of every application with score, status, timestamp |
| **Report & email** | Daily markdown report + optional HTML email |

---

## Web UI Pages

### Setup
Upload resume, review/edit extracted profile, configure API keys — all in a form with dropdowns and multiselects. No YAML, no terminal.

### Dashboard
Metric cards (jobs found, scored, applied), configurable run parameters, one-click "Run Agent" button with live status, report preview.

### Reports
Browse daily reports by date, rendered as formatted markdown. Application history table with sortable columns, score progress bars, and clickable apply links.

### Settings
Update all credentials (LinkedIn, Naukri, SMTP, etc.) in one form. Encrypt credentials with a master password. Clear data and reports.

---

## Architecture

### Scoring System

| Weight | Criterion |
|-------:|-----------|
| 40% | Role title match |
| 25% | Skills overlap (5% per skill, up to 5) |
| 15% | Seniority level fit |
| 15% | Location match (handles aliases: Bangalore/Bengaluru, Gurgaon/Gurugram) |
| 10% | Salary in range (only when job listing shows salary) |
| +5% | Bonus for 3+ skill matches |

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
Job sources run concurrently via `ThreadPoolExecutor`. Results are merged and deduplicated by job ID.

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
│       └── mock.py            # Mock data for testing
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
| `SERPAPI_KEY` | Recommended | Real job search (100 free/month) |
| `LINKEDIN_EMAIL/PASSWORD` | Optional | LinkedIn Easy Apply |
| `NAUKRI_EMAIL/PASSWORD` | Optional | Naukri auto-apply |
| `APPLY_EMAIL/PASSWORD` | Optional | Generic career sites |
| `SMTP_*` / `TO_EMAIL` | Optional | Email reports |
| `LOG_LEVEL` | Optional | DEBUG, INFO (default), WARNING, ERROR |
| `MASTER_PASSWORD` | Optional | Auto-decrypt `.env.enc` for cron |

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

**Q: What if I don't add any API keys?**
The agent works with mock job data and template cover letters. You can add keys later through the Settings page to enable real job search and AI cover letters.

**Q: Web UI or CLI — which should I use?**
Web UI (`./start.sh`) for interactive use. CLI (`python run_agent.py`) for cron jobs, headless servers, or if you prefer the terminal.
