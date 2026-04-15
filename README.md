# WarmPath 🌱

**A warm-contact-first job search tool. Built for senior professionals who know the real value of their network.**

---

## The problem with standard job search

Most job search tools start with listings.

You browse LinkedIn Jobs → find a role → apply → maybe then look for a connection at that company.

By that point, you're one of 400 applicants. The referral is an afterthought.

**WarmPath inverts this.**

> Surface your warmest contacts first → find open roles at their companies → generate a tailored outreach message → track the application.

A warm contact at a target company is worth more than any job posting. WarmPath makes contacts the centrepiece and jobs the output.

---

## What it does

### Tab 1 — Contacts
- Imports your full LinkedIn connection archive (4,000+ contacts handled smoothly)
- Scores every contact across 12 signals: message history, career overlap, recommendations, company follows, role seniority, recruiter status, connection recency, and more
- Grades contacts A / B / C (A = prioritise this week)
- Generates personalised outreach messages tuned to the relationship warmth (7 tiers from recommender to cold)
- Works without an AI key using built-in templates; generates AI-powered messages with Anthropic, OpenAI, Ollama, or any custom endpoint
- One-click LinkedIn Jobs, Indeed, Naukri search pre-filtered to their company
- 📝 Note field per contact — log feedback, fit signals, or anything they shared

### Tab 2 — Applications
- Pipeline board: Applied → Screening → Interviewing → Final → Offer
- Full application tracking: referred by, next interview date, round notes
- Feedback log per round
- HR email templates: rejection feedback request, follow-up after silence, post-interview thank you, offer negotiation
- Referral linking: contacts who referred you are badged and clickable

### Tab 3 — Setup
- Import LinkedIn archive (zip or individual CSVs)
- Last imported date shown — nudges you to re-import after 60 days
- Profile auto-populated from archive
- Multi-provider AI settings with instructions for each
- Data management: clear contacts, archive, or everything

---

## Why it's different

| Standard tools | WarmPath |
|----------------|----------|
| Start with job listings | Start with warm contacts |
| Data lives on someone's server | Data lives only in your browser |
| Requires signup / account | Double-click to open |
| Generic outreach suggestions | Tone matched to relationship warmth |
| No connection between contacts and applications | Referral links contacts ↔ applications |
| Cloud-dependent | Works fully offline (except AI generation) |

**Zero data leaves your machine.** Everything is stored in your browser's localStorage. No backend, no accounts, no database. Your LinkedIn connections, messages, and job search activity are yours alone.

---

## Getting started

### Requirements
- A modern browser (Chrome, Safari, Firefox)
- Your LinkedIn data archive (instructions below)
- Optional: an AI provider API key for message generation

### Step 1 — Download your LinkedIn archive

1. LinkedIn → **Me** → **Settings & Privacy**
2. **Data Privacy** → **Get a copy of your data**
3. Select **"Download larger data archive"** → Request archive
4. Wait for the email (10–30 minutes) → Download the `.zip` file

### Step 2 — Open WarmPath

**Mac (with AI features):**
```
Double-click launch.command
```
> First time: macOS may block it. Open Terminal, type `chmod +x ` (with a space), drag `launch.command` into Terminal, press Enter. Then double-click.

**Windows (with AI features):**
```
Double-click launch.bat
```

**Without AI features (limited mode):**
```
Double-click index.html directly
```

### Step 3 — Import your archive

1. Go to **Setup** tab
2. Drag your LinkedIn `.zip` into the dropzone
3. Wait for import to complete (a few seconds even for 4,000+ contacts)
4. Switch to **Contacts** tab — your scored, graded contacts are ready

### Step 4 — Optional: Add an AI provider

Go to **Setup → AI Settings** to add your API key.

| Provider | Cost | Privacy | Best for |
|----------|------|---------|---------|
| Anthropic (Claude) | ~$0.003/message | API call | Best message quality |
| OpenAI (GPT-4o) | ~$0.005/message | API call | Good alternative |
| Ollama | Free | Fully local | Maximum privacy |

Without an AI key, WarmPath uses built-in warmth-tier templates — still fully functional.

---

## Scoring logic

Every contact gets a composite score (0–200+) from 12 signals:

| Signal | Max points | Source |
|--------|-----------|--------|
| Message history (count) | 55 | messages.csv |
| Message recency | 10 | messages.csv |
| Wrote you a recommendation | 50 | Recommendations_Received.csv |
| At a target company | 40 | Connections.csv |
| PM / product title | 35 | Connections.csv |
| Career tenure overlap | 35 | Positions.csv |
| Their title matches your target role | 25 | Connections.csv |
| Recruiter at target company | 30 | Connections.csv |
| Connection recency | 20 | Connections.csv |
| Following their company | 20 | Company_Follows.csv |
| Adjacent role (eng/design/recruiting) | 15 | Connections.csv |
| Has email address | 5 | Connections.csv |

**Grade A** = score ≥ 55 (warm — prioritise this week)
**Grade B** = score 25–54 (lukewarm — worth a personalised message)
**Grade C** = score < 25 (cold — batch or skip)

---

## File structure

```
warmpath/
├── index.html          # The entire application
├── launch.command      # Mac launcher (double-click to start)
├── launch.bat          # Windows launcher
└── README.md           # This file
```

---

## Privacy

- **No data leaves your device.** Ever.
- All contact data, applications, and settings are stored in your browser's `localStorage`
- The only external calls are: AI API requests (if you configure a provider) and the job search links you click
- No analytics, no tracking, no accounts
- Deleting the HTML file does not delete your data — use **Setup → Clear everything** to wipe localStorage

---

## Limitations (v1)

- Desktop-first (works on mobile but not optimised)
- No sync across devices (by design — data stays local)
- LinkedIn archive export is full-archive only (no incremental updates) — re-import every 2–3 months
- AI message generation requires the local server launcher (CORS restriction on direct file access)
- No dark mode in v1

---

## Roadmap ideas

- [ ] Delta import (only process new connections since last import)
- [ ] Mobile layout improvements

---

## Built with

- Vanilla HTML, CSS, JavaScript — no framework, no build step
- [JSZip](https://stuk.github.io/jszip/) for LinkedIn archive zip extraction
- Anthropic / OpenAI / Ollama APIs for message generation (optional)

---

## Feedback

This is an early version. If you use it and have thoughts — what's working, what's confusing, what's missing — feedback is genuinely welcome.

---

*WarmPath works for any professional conducting a senior job search. No personal data is hardcoded. All data is supplied by the user at runtime via their own LinkedIn archive.*
