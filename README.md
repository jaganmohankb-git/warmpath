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

### Tab 1 — Network (Contacts)
- Imports your full LinkedIn connection archive (4,000+ contacts handled smoothly)
- Scores every contact across 12 signals: message history, career overlap, recommendations, company follows, role seniority, recruiter status, connection recency, and more
- Grades contacts A / B / C (A = prioritise this week)

#### Two views — By company (default) and By contact

**By company view** (default):
- Groups contacts by company, deduplicated across spelling variants ("ThoughtWorks", "Thoughtworks Technologies" → one group)
- **Target companies always sort to the top**, then by warmth (A-contact count) within each tier
- Each company shows a grade summary (e.g. 2A · 1B), contact count, and Glassdoor rating chip if loaded
- All companies start collapsed — click to expand and see contacts + job match
- **Job match per company** — "Find job match" button fetches and AI-analyses their careers page; result persists across sessions
- **Tailor resume per company** — one click after a job match is found; generates a resume targeted to that specific role
- 🎯 target badge on companies matching your target list

**By contact view**:
- Classic paginated contact card list
- Side drawer per contact for outreach and resume tailoring
- 🎯 Target cos filter pill to focus only on your target companies

**Both views share:**
- **Side drawer** per contact — click any card to open a 560px panel beside the list
- **AI outreach messages** tuned to relationship warmth (7 tiers); tone override: Casual / Professional / Formal
- **JD-aware generation** — paste a job URL (auto-fetched) or paste the full JD text; message references specific requirements; role pre-filled from company job match if already found
- **Tailored resume** — AI rewrites your resume for each role using LinkedIn positions as authoritative dates; never hallucinates employment history
- **Resume fact-checker** — compares dates and contact info across LinkedIn data, pasted resume, and your profile; flags mismatches
- **Interaction audit log** — every message sent is logged with date, role, and response (Replied / No response / Not interested); full timeline per contact
- **Glassdoor rating** — on-demand, per company; fetched once and cached permanently (no auto-refresh)
- Works without an AI key using built-in warmth-tier templates
- One-click LinkedIn Jobs, Indeed, Naukri, Glassdoor search per company
- Filter by grade (A/B/C), status, relationship type, search

### Tab 2 — Applications
- Pipeline board: Applied → Screening → Interviewing → Final → Offer → Closed
- **Closed column** includes Rejected, Withdrawn, and On hold — full pipeline visibility
- Full application tracking: referred by, next interview date, round notes
- Feedback log per round
- HR email templates: rejection feedback request, follow-up after silence, post-interview thank you, offer negotiation
- Referral linking: contacts who referred you are badged and clickable

### Tab 3 — Setup
- **Import & Data sub-tab**: LinkedIn archive import (zip or individual CSVs); collapsible export instructions (auto-expands for new users); last imported date with 60-day re-import nudge
- **Profile sub-tab**: About you (name, headline, level, location, email, phone, LinkedIn URL); background summary and target role; resume paste (used for tailoring); target companies with AI-powered suggestions
- **Settings sub-tab**: Multi-provider AI config (Anthropic, OpenAI, Ollama, custom); API key help; job location preference (up to 3 ranked locations)
- Scoring summary (collapsed by default)

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
| Generic outreach suggestions | Tone matched to relationship warmth |
| No connection between contacts and applications | Referral links contacts ↔ applications |
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

## The company view workflow

1. **Open Network tab** — companies are listed, sorted by target → warmth
2. **Click a company header** to expand — see grade summary and "Find job match" button
3. **Find job match** — AI checks their careers page (or uses knowledge if JS-rendered) and returns the best matching open role
4. **View job ↗** — opens the job posting directly
5. **Tailor resume** — generates a resume targeted to that specific role in one click
6. **Expand contacts** — see individuals at the company; their drawer pre-fills the job title automatically
7. **Generate message** — contact drawer generates an outreach message referencing the role

---

## The contact outreach workflow

1. **Click a contact card** → side drawer opens with their drafted message
2. **Customise** (optional) — enter a job title or URL, or paste the full JD; choose tone
3. **Generate / Regenerate** — AI rewrites the message using JD requirements and relationship context
4. **Edit** the message directly in the textarea
5. **✓ Log as sent** — records the interaction with date and role
6. **Log response** — mark Replied / No response / Not interested + quick note
7. The full **Interaction history** timeline builds automatically per contact

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

**Company view sort order**: Target companies first → then by A-contact count → then by total score.

---

## Company intel (Glassdoor rating)

- Click **Load intel** on any company header (or in the contact drawer) to fetch the Glassdoor overall rating via AI
- Fetched once and cached permanently — never auto-refreshed
- Click **↻ Refresh** in the drawer to update manually
- Displayed as a chip on the company header and in the contact drawer
- Salary data and review sentiment removed to keep token costs low — rating only

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
- All contact data, applications, settings, and activity logs are stored in your browser's `localStorage`
- The only external calls are: AI API requests (if you configure a provider) and job search links you click
- No analytics, no tracking, no accounts
- Deleting the HTML file does not delete your data — use **Setup → Clear everything** to wipe localStorage

---

## Limitations

- No sync across devices (by design — data stays local)
- LinkedIn archive export is full-archive only (no incremental updates) — re-import every 2–3 months
- AI message generation requires the local server launcher (CORS restriction when opening index.html directly)
- AI features require an internet connection and a configured API key (or local Ollama)
- Job match searches work best for companies with statically rendered careers pages; JS-rendered pages (e.g. large enterprise sites) fall back to AI knowledge, which may not reflect live postings — always verify manually

---

## Roadmap

- [ ] Delta import (only process new connections since last import)
- [ ] Mobile bottom-sheet drawer (currently full-width overlay)
- [ ] Export interaction log as CSV
- [ ] Contact location matching for post-job-search prioritisation

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
