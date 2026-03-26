# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

그루북 업무 자동화 웹앱 — an internal tool for Groobook (Korean educational publisher) that automates two workflows:
1. **포장전표 생성**: Parses Excel files, generates print-ready A4 PDF packaging slips
2. **청구서 메일 발송**: Parses billing Excel filenames, looks up campus emails, sends via Gmail SMTP

## Running the App

```bash
python -m venv venv
venv\Scripts\activate       # Windows
# source venv/bin/activate  # macOS/Linux
pip install -r requirements.txt
uvicorn main:app --reload
```

Server runs at `http://127.0.0.1:8000`. There are no build, lint, or test commands.

## Required Configuration

**`.env` file** (git-ignored, required for email feature only):
```env
GMAIL_ADDRESS=your-gmail@gmail.com
GMAIL_APP_PASSWORD=your-16-char-app-password
```

**`campus_emails.json`** (project root): Maps Korean campus names → email addresses. Must be updated manually when adding new campuses.

**WeasyPrint system libraries** (required for PDF generation):
- Windows: GTK3 runtime (tschoonj installer)
- macOS: `brew install pango glib`
- Linux: `libpango-1.0-0 libpangoft2-1.0-0 libgdk-pixbuf2.0-0`

## Architecture

### Request Flow — Packaging Slips

```
Browser upload → POST /api/process/{proc_type}
  → background threading.Thread
  → processors/{naeshin,quarterly,midterm}.py → slip_list[]
  → renderer/pdf_renderer.py (Jinja2 template → WeasyPrint → PDF bytes)
  → stored in tasks[task_id]
Browser polls GET /api/progress/{task_id} → GET /api/download/{task_id}
```

### Request Flow — Email Dispatch (two-step)

```
Browser upload → POST /api/email/scan
  → filename regex parse + campus_emails.json lookup
  → preview table returned (stored in email_scans[scan_id])
User confirms → POST /api/email/send
  → background thread → email_sender.py → Gmail SMTP (port 587, STARTTLS)
```

### State Management

All task state lives in two in-memory dicts in `main.py` (`tasks`, `email_scans`). State is lost on server restart. Do **not** run with `--workers > 1` (multi-process would break shared state).

## Key Files

| File | Role |
|---|---|
| `main.py` | All FastAPI routes + in-memory task store |
| `processors/naeshin.py` | "비법전수 내신노트" Excel parser — fixed banding of 30 |
| `processors/quarterly.py` | Quarterly textbook parser — reads banding from Excel |
| `processors/midterm.py` | Midterm/finals parser — 3 sub-types (본책/미니북/교사용) |
| `processors/email_sender.py` | Filename regex, campus email lookup, SMTP sender |
| `renderer/pdf_renderer.py` | Selects Jinja2 template by `proc_type`, renders PDF bytes |
| `renderer/templates/slip_naeshin.html` | A4 landscape, 2×2 slip grid |
| `renderer/templates/slip_midterm.html` | A4 landscape, 2×3 slip grid (also used for quarterly) |
| `templates/work.html` | Reusable upload page — `{{ show_banding }}` flag controls midterm banding inputs |
| `campus_emails.json` | Campus name → email mapping |

## Excel Parsing Conventions

- **naeshin**: Row 3 = campus names, Row 4 = quantities
- **quarterly**: "밴딩" column in sheet contains banding value; rows = books, cols = campuses
- **midterm**: Books are columns, campuses are rows; even/odd rows alternate teacher vs. total quantities
- **email filenames**: Must match pattern `YYYY년 MM월 캠퍼스명 청구서_내신교재.xlsx`

## Git & Commit Guidelines

- **Atomic Commits:** Follow `.claude/rules/commit-convention.md` strictly.
- **State Management:** Keep track of unpushed local commits.
- **Push Strategy:** Do not push automatically. After completing a logical set of tasks, ask the user if they want to:
  1. **Squash & Push:** Combine multiple local commits into one clean commit and push.
  2. **Straight Push:** Push all local commits as they are.
  3. **Wait:** Keep working without pushing.
