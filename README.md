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

### Tab 1 — Network · *Find & Reach*
- Imports your full LinkedIn connection archive (4,000+ contacts handled smoothly)
- Scores every contact across 12 signals: message history, career overlap, recommendations, company follows, role seniority, recruiter status, connection recency, and more
- Grades contacts A / B / C (A = prioritise this week)
- **Contact statuses** track relationship health: Not contacted → Messaged → Replied → Met → Referred me → No response
- **⚡ Boost** any contact +50 pts for off-LinkedIn warmth (phone call, coffee chat, etc.) — shows 🔥 badge
- **Connection decay indicator** — 🟡 if a Grade A contact hasn't been messaged in 90+ days, 🔴 if 180+ days

#### Two views — By company (default) and By contact

**By company view** (default):
- Groups contacts by company, deduplicated across spelling variants ("ThoughtWorks", "Thoughtworks Technologies" → one group)
- **Target companies always sort to the top**, then by warmth (A-contact count) within each tier
- Each company shows a grade summary (e.g. 2A · 1B), contact count, Glassdoor rating chip, and outreach badge
- **Company status** — mark each company as Watching / No opening / On hold
- All companies start collapsed — click to expand and see contacts
- 🎯 target badge on companies matching your target list

**By contact view**:
- Classic paginated contact card list
- Side drawer per contact for outreach and resume tailoring
- 🎯 Target cos filter pill to focus only on your target companies

**Both views share:**
- **Side drawer** per contact — click any card to open a 560px panel beside the list
- **Template selector** — pick from 5 built-in templates (job referral, advisory, speaking, networking, general) or your own custom templates; subject line auto-previews with placeholders filled
- **AI outreach messages** tuned to relationship warmth (7 tiers); tone override: Casual / Professional / Formal
- **JD-aware generation** — paste a job URL (auto-fetched) or paste the full JD text; message references specific requirements
- **Link to tracked job** — associate a message draft with a job from your Jobs tab; paste a JD URL and it auto-detects the matching job and selects it, or offers to create a new one; ↻ refresh button updates the list without reopening the drawer
- **Copy resume prompt** — one click generates a tailored Claude.ai prompt for resume rewriting; paste it into claude.ai
- **Resume fact-checker** — compares dates and contact info across LinkedIn data, pasted resume, and your profile; flags mismatches
- **Interaction audit log** — every message sent is logged with date, role, and response (Replied / No response / Not interested); full timeline per contact
- **Job outreach history** in drawer — see all jobs you've approached this contact about, with live status dropdowns
- **Glassdoor rating** — on-demand, per company header; fetched once and cached permanently
- Works without an AI key using built-in warmth-tier templates
- One-click LinkedIn Jobs, Indeed, Naukri, Glassdoor search per company
- Filter by grade (A/B/C), status, relationship type, search

### Tab 2 — Jobs · *Track & Apply*
- **Job registry** — add any role you're pursuing with title, company, URL, status, and notes
- **Job URL auto-fill** — paste a Greenhouse, Lever, Workday, Ashby, LinkedIn, Indeed, or Naukri URL and company, title, and reference ID are detected instantly via regex; **Read ↗ button** fetches the live page via AI to extract title, company, and ref ID for URLs that can't be parsed from structure alone
- **Duplicate detection** — Read ↗ checks existing jobs by reference ID and title+company before adding; warns if a match is found
- **Job pipeline**: Pursuing → Applied → Interviewing → Offer → Closed
- **Link contacts to jobs** as outreach records — track each contact-job pair through an 8-status outreach pipeline: Planned → Messaged → Replied → Had a call → Referral asked → Referred ✓ → Not referring → No response
- **Company-first contact selector** — the "Link a contact" dropdown shows people at that company first, sorted by warmth score, with a search box for everyone else
- **→ Move to Applications** — one-click handoff when a job reaches Applied or Interviewing; pre-fills the referred-by name from outreach records automatically
- Active job count (Pursuing + Applied + Interviewing) shown in the nav tab badge
- Filter jobs by status
- **Sample data banner** — new users see an amber dismissible banner indicating the pre-loaded jobs are examples; auto-hides when the first real job is added or all sample jobs are deleted

### Tab 3 — Applications · *Interview & Close*
- Pipeline board: Applied → Screening → Interviewing → Final → Offer → Closed
- **Closed column** includes Rejected, Withdrawn, and On hold — full pipeline visibility
- Full application tracking: referred by, next interview date, round notes
- Feedback log per round
- HR email templates: rejection feedback request, follow-up after silence, post-interview thank you, offer negotiation
- Referral linking: contacts who referred you are badged and clickable

### Tab 4 — Setup

**Import & Data sub-tab**
- LinkedIn archive import (zip or individual CSVs)
- Collapsible export instructions (auto-expands for new users)
- Last imported date with 60-day re-import nudge

**Profile sub-tab**
- About you: name, headline, domain/industry, primary goal, seniority level, location, email, phone, LinkedIn URL
- Background summary and target role
- Resume paste (used for tailoring)
- Target companies with AI-powered suggestions

**Settings sub-tab**
- Multi-provider AI config (Anthropic, OpenAI, Ollama, custom); API key help; job location preference (up to 3 ranked locations)
- **Scoring weights** — adjust the 0–10 weight of each of the 12 signals; Recalculate and Reset to defaults buttons
- **Template library** — 5 built-in presets (view only) + add/delete your own custom templates with subject line and message body; supports `[name]`, `[company]`, `[role]`, `[your_name]`, `[goal]` placeholders
- **Backup & Restore** — download all WarmPath data as a timestamped JSON; restore from backup with confirmation dialog. A reminder banner appears if no backup in 7 days.

### Activity strip
- Weekly stats above the contact list: outreaches sent, replies received, reply rate, resumes tailored
- Week-over-week trend (↑ / ↓ / →)
- All-time reply rate

---

## Why it's different

| Standard tools | WarmPath |
|----------------|----------|
| Start with job listings | Start with warm contacts |
| Data lives on someone's server | Data lives only in your browser |
| Requires signup / account | Double-click to open |
| Generic outreach suggestions | Tone + template matched to relationship warmth |
| No connection between contacts and applications | Jobs tab links contacts ↔ roles ↔ applications |
| Cloud-dependent | Works fully offline (except AI generation) |

**Zero data leaves your machine.** Everything is stored in your browser's `localStorage`. No backend, no accounts, no database. Your LinkedIn connections, messages, and job search activity are yours alone.

---

## Getting started

### Requirements
- A modern browser (Chrome, Safari, Firefox) — desktop or mobile
- Your LinkedIn data archive (instructions below)
- Optional: an AI provider API key for message generation and job match

### Step 1 — Download your LinkedIn archive

1. LinkedIn → **Me** → **Settings & Privacy**
2. **Data Privacy** → **Get a copy of your data**
3. Select **"Download larger data archive"** → Request archive
4. Wait for the email (10–30 minutes) → Download the `.zip` file

### Step 2 — Open WarmPath

**Mac (with AI features):**
```
Double-click launch.command
Then open http://localhost:8080/index.html
```
> First time: macOS may block it. Open Terminal, type `chmod +x ` (with a space), drag `launch.command` into Terminal, press Enter. Then double-click.

**Windows (with AI features):**
```
Double-click launch.bat
Then open http://localhost:8080/index.html
```

**Without AI features (templates still work):**
```
Double-click index.html directly
```

### Step 3 — Import your archive

1. Go to **Setup → Import & Data**
2. Drag your LinkedIn `.zip` into the dropzone
3. Wait a few seconds — even 4,000+ contacts import quickly
4. Switch to **Network** tab — your scored, graded contacts are ready in company view

> **Before you import:** WarmPath pre-loads sample contacts, jobs, and applications so you can explore all three tabs immediately. All sample data is cleared automatically the moment your real archive is imported.

### Step 4 — Set your target companies

Go to **Setup → Profile → Target companies**. Add the companies you most want to work at. These will sort to the top of the company view and boost contact scores.

### Step 5 — Optional: Add an AI provider

Go to **Setup → Settings** to add your API key.

| Provider | Cost | Privacy | Best for |
|----------|------|---------|---------|
| Anthropic (Claude) | ~$0.003/message | API call | Best message quality |
| OpenAI (GPT-4o) | ~$0.005/message | API call | Good alternative |
| Ollama | Free | Fully local | Maximum privacy |

Without an AI key, WarmPath uses built-in warmth-tier templates — still fully functional.

---

## The guided pipeline — Network → Jobs → Applications

WarmPath's three tabs are a pipeline, not independent tools. Status advances flow automatically so you never re-enter data.

| Action | Network tab | Jobs tab (outreach) | Jobs tab (job) | Applications |
|--------|-------------|---------------------|----------------|--------------|
| Identify a role | Not contacted | Planned | Pursuing | — |
| Send a message | **Messaged** ← auto | **Messaged** ← synced | Pursuing | — |
| They reply | **Replied** ← auto | **Replied** ← synced | Pursuing | — |
| Had a call | Met | Had a call | Pursuing | — |
| Ask for referral | — | Referral asked | Pursuing | — |
| Referred ✓ | Referred me | **Referred ✓** | **Applied** ← auto-nudged | — |
| Formally apply | — | — | Applied | **Applied** ← via Move button |
| In interviews | — | — | Interviewing | Screening → Round 1/2/3 → Final |
| Outcome | — | — | Offer / Closed | Offer / Rejected / Withdrawn |

Auto-syncs that happen without any manual work:
- **✓ Log as sent** in the contact drawer → contact status becomes Messaged, all linked outreach records advance to Messaged
- **Log response (replied)** → contact becomes Replied, outreach records advance to Replied
- **Outreach hits Referred ✓** → job status auto-nudges to Applied with a banner notification
- **→ Move to Applications** → reads the referred-by contact name from outreach records, pre-fills it in the application, job closes in Jobs tab

---

## The company view workflow

1. **Open Network tab** — companies are listed, sorted by target → warmth
2. **Click a company header** to expand — see grade summary and contacts
3. **Expand contacts** — see individuals at the company
4. **Generate message** — contact drawer generates an outreach message referencing the role
5. **Add to Jobs tab** — track the role in your job pipeline

---

## The contact outreach workflow

1. **Click a contact card** → side drawer opens with their drafted message
2. **Pick a template** (optional) — choose from presets or custom templates; subject line previews instantly
3. **Link to a job** (optional) — associate with a tracked job from your Jobs tab
4. **Customise** (optional) — enter a job title or URL, or paste the full JD; choose tone
5. **Generate / Regenerate** — AI rewrites the message using JD requirements, template style, and relationship context
6. **Edit** the message directly in the textarea
7. **✓ Log as sent** — records the interaction; contact status advances to Messaged; all linked job outreach records sync automatically
8. **Log response** — mark Replied / No response; outreach records sync; if a job is linked, status advances automatically
9. **"Add to Jobs tracker?" prompt** — if a role was set, a one-click banner offers to create the Jobs entry without leaving the drawer
10. The full **Interaction history** and **Job outreach history** timelines build automatically per contact

---

## Scoring logic

Every contact gets a composite score (0–200+) from 12 signals. All signal weights are configurable (0–10) in **Setup → Settings → Scoring**.

| Signal | Default weight | Source |
|--------|---------------|--------|
| Gave me a recommendation | 10 | Recommendations_Received.csv |
| Worked together (same company) | 9 | Positions.csv |
| High message volume (10+ messages) | 8 | messages.csv |
| Messaged within last 90 days | 8 | messages.csv |
| At a target company | 8 | Connections.csv |
| Recruiter at a target company | 7 | Connections.csv |
| PM / product title | 7 | Connections.csv |
| Senior title matching your target | 5 | Connections.csv |
| Connected recently (< 90 days) | 5 | Connections.csv |
| Following their company | 4 | Company_Follows.csv |
| Adjacent role (eng / design / HR) | 3 | Connections.csv |
| Has email address | 2 | Connections.csv |

**Grade A** = score ≥ 55 (warm — prioritise this week)  
**Grade B** = score 25–54 (lukewarm — worth a personalised message)  
**Grade C** = score < 25 (cold — batch or skip)

**Company view sort order**: Target companies first → then by A-contact count → then by total score.

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
- All contact data, jobs, applications, settings, and activity logs are stored in your browser's `localStorage`
- The only external calls are: AI API requests (if you configure a provider) and job search links you click
- No analytics, no tracking, no accounts
- Deleting the HTML file does not delete your data — use **Setup → Clear everything** to wipe localStorage
- Use **Setup → Settings → Backup** to export and safeguard your data

---

## Limitations

- No sync across devices (by design — data stays local)
- LinkedIn archive export is full-archive only (no incremental updates) — re-import every 2–3 months
- AI message generation requires the local server launcher (CORS restriction when opening index.html directly)
- AI features require an internet connection and a configured API key (or local Ollama)
- Job match searches work best for companies with statically rendered careers pages; JS-rendered pages fall back to AI knowledge — always verify manually

---

## Roadmap

- [ ] Delta import (only process new connections since last import)
- [ ] Export interaction log as CSV
- [ ] Contact location matching for post-job-search prioritisation
- [ ] Multi-device sync via encrypted export/import

---

## Built with

- Vanilla HTML, CSS, JavaScript — no framework, no build step
- [JSZip](https://stuk.github.io/jszip/) for LinkedIn archive zip extraction
- Anthropic / OpenAI / Ollama APIs for message generation and job matching (optional)

---

## Feedback

This is an actively developed tool. If you use it and have thoughts — what's working, what's confusing, what's missing — feedback is genuinely welcome.

---

*WarmPath works for any professional conducting a senior job search. No personal data is hardcoded. All data is supplied by the user at runtime via their own LinkedIn archive.*
