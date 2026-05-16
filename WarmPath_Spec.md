# WarmPath — Architecture Brief & Build Spec
**Version 1.0 — for Claude Code**
**Author: Jagan Mohan KB**
**Date: April 2026**

---

## 0. How to use this document

Hand this entire file to Claude Code with the prompt:

> "Read WarmPath_Spec.md in full and build the application exactly as specified. Start with the file structure, then Setup, then Tab 1 (Contacts), then Tab 2 (Applications). Ask me before making any architectural decisions not covered here."

Do not start coding until you have read every section. The intelligence layer (Section 5) must be built before the UI, because the UI depends on the scoring output.

---

## 1. Product overview

### What WarmPath is

A single-file HTML job search tool that inverts the standard job search workflow.

**Standard workflow (LinkedIn):** Browse jobs → find connections as afterthought
**WarmPath workflow:** Surface warm contacts → find open roles at their companies → generate tailored outreach

The core insight: a warm contact at a target company is worth more than any job posting. WarmPath makes contacts the centrepiece and jobs the output.

### Who it is for

Any professional conducting a senior job search. Not Jagan-specific. All personal data is supplied by the user at runtime via LinkedIn archive upload. Zero hardcoded personal information anywhere in the codebase.

### Technical constraints

- Single HTML file. No build step. No server required for core functionality.
- All data stored in browser localStorage. No backend, no accounts, no database.
- Works by double-clicking the file (limited mode) or via the included launcher script (full mode with AI features).
- AI message generation uses the Anthropic API (`claude-sonnet-4-20250514`) called directly from the browser. This requires the local server launcher to avoid CORS errors.
- Must work for any user, any LinkedIn archive, any market.

---

## 2. File structure

Deliver exactly these files:

```
warmpath/
├── warmpath.html          # The entire application — single file
├── launch.command         # Mac launcher script (double-click to start)
├── launch.bat             # Windows launcher script
└── WarmPath_Spec.md       # This document (included for reference)
```

### warmpath.html internal structure

```
<head>
  CSS (all styles inline in <style> tag)
  JSZip CDN (https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js)
</head>
<body>
  <!-- Onboarding overlay (shown on first visit) -->
  <!-- Top navigation bar -->
  <!-- Tab panels: Contacts | Applications | Setup -->
  <script>
    // Section order in script:
    // 1. Constants and config
    // 2. Archive data (starts empty, populated at runtime)
    // 3. Scoring engine
    // 4. Data management (load/save/merge)
    // 5. Archive file processors
    // 6. UI renderers
    // 7. Outreach and AI generation
    // 8. Applications tracker
    // 9. Onboarding flow
    // 10. Init
  </script>
</body>
```

---

## 3. Data model

All data lives in localStorage. Keys:

| Key | Type | Contents |
|-----|------|----------|
| `wp_contacts` | Contact[] | All contacts with grades and status |
| `wp_applications` | Application[] | Job applications |
| `wp_profile` | UserProfile | Name, headline, background, target role |
| `wp_msg` | Record<slug, {c,l}> | Message count and last date by LinkedIn URL slug |
| `wp_rec` | string[] | Recommender full names |
| `wp_pos` | Position[] | Career positions with dates |
| `wp_cofo` | Record<name, date> | Company follows |
| `wp_end` | string[] | Endorser names (lowercase) |
| `wp_skills` | Skill[] | Skills with endorsement counts |
| `wp_onboarded` | "1" | Whether setup has been completed |

### Contact object

```typescript
interface Contact {
  name: string;
  company: string;
  position: string;
  role: string;              // display string: "position, company"
  relationship: string;      // "LinkedIn connection" | "Ex-colleague" | "PM community" | etc
  grade: "A" | "B" | "C";
  score: number;             // 0-200 composite
  gradeReasons: string[];    // human-readable signal list
  warmthTier: WarmthTier;    // drives message tone
  msgCount: number;          // from Messages.csv
  status: ContactStatus;
  notes: string;
  url: string;               // LinkedIn profile URL
  connectedOn: string;       // ISO date string
  source: "linkedin_import" | "manual";
  lastContacted?: string;    // ISO date string
  savedRole?: string;        // role title user pinged them about
}

type ContactStatus = "Not contacted" | "Message sent" | "Replied" | "Call done" | "Referral given" | "Intro made" | "No response";
type WarmthTier = "recommender" | "close-colleague" | "colleague" | "active-contact" | "known" | "warm-unknown" | "cold";
```

### Application object

```typescript
interface Application {
  company: string;
  role: string;
  via: "Referral" | "Direct apply" | "Recruiter inbound" | "LinkedIn Easy Apply" | "Agency";
  referredBy: string;
  dateApplied: string;       // ISO date
  status: ApplicationStatus;
  nextDate: string;          // ISO datetime for next interview
  interviewer: string;       // "Round 2 — VP Product"
  notes: string;
  feedback: FeedbackEntry[];
  companyIntel?: CompanyIntel; // cached Glassdoor/salary data
}

type ApplicationStatus = "Applied" | "Screening" | "Round 1" | "Round 2" | "Round 3" | "Final round" | "Offer received" | "Offer accepted" | "Rejected" | "Withdrawn" | "On hold";

interface FeedbackEntry {
  round: string;
  date: string;
  outcome: string;
  notes: string;
}

interface CompanyIntel {
  glassdoorRating?: number;
  salaryRange?: string;
  reviewSentiment?: string;
  fetchedAt: string;
}
```

### UserProfile object

```typescript
interface UserProfile {
  name: string;
  headline: string;
  bg: string;                // 2-3 sentence background for outreach
  target: string;            // target role description
  currentLevel: string;      // "Staff PM" | "Head of Product" | etc
  topSkills: string[];       // from Skills.csv, top 10 by endorsement count
}
```

---

## 4. Scoring engine

This is the most important part of the application. Build it first. The UI depends on it.

### Principle

Every contact gets a composite score (0–200) computed from up to 9 signals. The score determines grade (A/B/C), warmth tier (drives message tone), and ranking in the contact list.

### Signal definitions

```javascript
function smartScore(contact, archiveData) {
  const { MSG_LOOKUP, RECOMMENDERS, POSITIONS_DATA, COMPANY_FOLLOWS, TARGET_COS } = archiveData;

  const co      = (contact.company || '').toLowerCase();
  const pos     = (contact.position || contact.role || '').toLowerCase();
  const name    = (contact.name || '').toLowerCase();
  const connDate = contact.connectedOn ? new Date(contact.connectedOn) : null;
  const urlSlug  = ((contact.url || '').split('/in/')[1] || '').replace(/\/$/, '').split('/')[0].toLowerCase();

  let score = 0;
  const reasons = [];

  // ── Signal 1: Message history (strongest warmth signal) ──────
  // Source: Messages.csv
  const msgData  = urlSlug ? MSG_LOOKUP[urlSlug] : null;
  const msgCount = msgData ? msgData.c : 0;
  if      (msgCount >= 20) { score += 55; reasons.push(`${msgCount} messages exchanged`); }
  else if (msgCount >= 10) { score += 40; reasons.push(`${msgCount} messages`); }
  else if (msgCount >= 5)  { score += 28; reasons.push(`${msgCount} messages`); }
  else if (msgCount >= 2)  { score += 15; reasons.push('messaged before'); }

  // ── Signal 2: Wrote a recommendation ─────────────────────────
  // Source: Recommendations_Received.csv
  const isRec = RECOMMENDERS.some(r => {
    const parts = r.toLowerCase().split(' ');
    return parts[0] && name.includes(parts[0]) && (parts[1] ? name.includes(parts[1]) : true);
  });
  if (isRec) { score += 50; reasons.push('wrote you a recommendation'); }

  // ── Signal 3: At a target company ────────────────────────────
  // Source: hardcoded TARGET_COS list + user's custom targets
  if (TARGET_COS.some(t => co.includes(t))) { score += 40; reasons.push('at target company'); }

  // ── Signal 4: PM or product title ────────────────────────────
  const pmTitles = ['product manager','head of product','vp product','director of product',
    'chief product','group pm','principal pm','staff pm','cpo',' pm ','pm,'];
  if (pmTitles.some(t => pos.includes(t))) { score += 35; reasons.push('product role'); }

  // ── Signal 5: Exact tenure overlap ───────────────────────────
  // Source: Positions.csv — dynamically computed, no hardcoding
  const careerPeriods = POSITIONS_DATA.map(p => ({
    co: p.co.toLowerCase(),
    display: p.co_display,
    from: new Date(p.from),
    to: new Date(p.to)
  }));

  if (connDate && careerPeriods.length > 0) {
    for (const p of careerPeriods) {
      if (connDate >= p.from && connDate <= p.to && co.includes(p.co)) {
        score += 35; reasons.push(`colleague at ${p.display}`); break;
      }
    }
    if (!reasons.some(r => r.includes('colleague'))) {
      for (const p of careerPeriods) {
        if (connDate >= p.from && connDate <= p.to) {
          score += 15; reasons.push(`connected during ${p.display} era`); break;
        }
      }
    }
  }

  // ── Signal 6: Company follow (active research signal) ────────
  // Source: Company_Follows.csv — only recent follows score highly
  const fk = Object.keys(COMPANY_FOLLOWS).find(k =>
    co.includes(k) || (k.length > 4 && co.includes(k.split(' ')[0])));
  if (fk) {
    const daysSince = (Date.now() - new Date(COMPANY_FOLLOWS[fk])) / 86400000;
    if (daysSince < 60)  { score += 20; reasons.push('following their company'); }
    else if (daysSince < 180) { score += 10; }
  }

  // ── Signal 7: Connection recency ─────────────────────────────
  if (connDate) {
    const daysAgo = (Date.now() - connDate) / 86400000;
    if      (daysAgo < 90)  { score += 20; reasons.push('connected recently'); }
    else if (daysAgo < 365) { score += 12; reasons.push('connected this year'); }
    else if (daysAgo < 730) { score +=  5; }
  }

  // ── Signal 8: Adjacent roles (engineering, design, recruiting) ──
  const adjTitles = ['engineer','developer','designer','founder','cto','ceo',
    'recruiter','talent','engineering manager','tech lead','architect'];
  if (adjTitles.some(t => pos.includes(t)) && score < 50) {
    score += 15; reasons.push('eng / adjacent role');
  }

  // ── Signal 9: Has email address ──────────────────────────────
  if ((contact.notes || '').includes('Email:')) { score += 5; reasons.push('has email'); }

  // ── Derive grade and warmth tier ─────────────────────────────
  const isExColleague = reasons.some(r => r.includes('colleague'));
  const isHighMsg     = msgCount >= 10;

  const warmthTier =
    isRec                        ? 'recommender'     :
    isExColleague && isHighMsg   ? 'close-colleague' :
    isExColleague                ? 'colleague'       :
    isHighMsg                    ? 'active-contact'  :
    msgCount >= 2                ? 'known'           :
    score >= 55                  ? 'warm-unknown'    :
                                   'cold';

  const grade = score >= 55 ? 'A' : score >= 25 ? 'B' : 'C';

  return { grade, score, reasons, warmthTier, msgCount };
}
```

### Target company list

The default list. Users can extend it in Setup. Store as `const DEFAULT_TARGET_COS`:

```javascript
const DEFAULT_TARGET_COS = [
  // India SaaS / platform
  'freshworks','chargebee','razorpay','postman','setu','hasura','darwinbox',
  'sprinklr','clevertap','yellow.ai','exotel','juspay','sarvam','keka',
  'leadsquared','zoho','gojek',
  // Global platform / developer tools
  'atlassian','salesforce','mulesoft','workato','zapier','twilio','stripe',
  'hubspot','shopify','replit','cohere','cursor','vercel','docusign',
  'microsoft','google','amazon','adobe','servicenow','zendesk','monday',
  'linear','retool','supabase'
];
```

### Grade definitions (display)

| Grade | Score | Meaning |
|-------|-------|---------|
| A | ≥55 | Warm — prioritise this week |
| B | 25–54 | Lukewarm — worth a personalised message |
| C | <25 | Cold — batch or skip |

---

## 5. Archive file processors

Each processor takes raw CSV text, parses it, updates the in-memory archive data, persists to localStorage, and re-scores affected contacts.

### Dedup and merge rule

**Never silently overwrite.** When a contact already exists (matched by full name, case-insensitive):
1. Enrich missing fields (URL, connectedOn, company, position) if the existing contact lacks them
2. Update score and gradeReasons if the new score is higher
3. Never downgrade a manually-set grade (source === 'manual')
4. Never overwrite status, notes, or savedRole set by the user
5. Return 'merged' so the caller can count it separately from 'added'

```javascript
function mergeOrAddContact(newC, contacts) {
  const idx = contacts.findIndex(c =>
    c.name.toLowerCase().trim() === (newC.name || '').toLowerCase().trim()
  );
  if (idx === -1) {
    contacts.push(newC);
    return 'added';
  }
  const c = contacts[idx];
  if (!c.url && newC.url)               c.url         = newC.url;
  if (!c.connectedOn && newC.connectedOn) c.connectedOn = newC.connectedOn;
  if (!c.company && newC.company)       c.company     = newC.company;
  if (!c.position && newC.position)     c.position    = newC.position;
  if (!c.notes && newC.notes)           c.notes       = newC.notes;
  if (newC.score > (c.score || 0)) {
    c.score        = newC.score;
    c.gradeReasons = newC.gradeReasons;
    c.warmthTier   = newC.warmthTier;
    if (c.source !== 'manual' && newC.grade === 'A' && c.grade !== 'A') {
      c.grade = 'A';
    }
  }
  return 'merged';
}
```

### File type detection

Detect by filename (case-insensitive substring match):

| Filename contains | Processor |
|------------------|-----------|
| `connection` | processConnections |
| `message` | processMessages |
| `position` | processPositions |
| `recommend` | processRecommendations |
| `endorsement` | processEndorsements |
| `company` | processCompanyFollows |
| `skill` | processSkills |
| `profile` | processProfile |

### LinkedIn CSV preamble handling

LinkedIn exports always have a preamble row (e.g. "Connections" or "Notes:") before the real headers. Always scan the first 5 rows to find the real header row before parsing data.

```javascript
function findHeaderRow(rows) {
  for (let i = 0; i < Math.min(rows.length, 5); i++) {
    const h = rows[i].map(x => (x || '').toLowerCase());
    if (h.some(x => x.includes('first name') || x.includes('name') || x.includes('from'))) {
      return i;
    }
  }
  return 0;
}
```

### processConnections(text, state)

Parses Connections.csv. For each row:
1. Build a Contact object with smartScore applied
2. Call mergeOrAddContact
3. Return `{ added, merged, total }` stats

Expected columns: First Name, Last Name, URL, Email Address, Company, Position, Connected On

### processMessages(text, state)

Parses messages.csv. For each row, identify the non-user participant by:
- If FROM contains the user's name → partner is TO, URL is RECIPIENT PROFILE URLS (first)
- Otherwise → partner is FROM, URL is SENDER PROFILE URL

Extract slug from URL: `url.split('/in/')[1]?.split('/')[0]?.toLowerCase()`

Build MSG_LOOKUP as `{ [slug]: { c: messageCount, l: lastDateString } }`

Only store entries with 2+ messages (c >= 2).

After processing: re-score all contacts and save.

Expected columns: CONVERSATION ID, CONVERSATION TITLE, FROM, SENDER PROFILE URL, TO, RECIPIENT PROFILE URLS, DATE, SUBJECT, CONTENT, FOLDER, ATTACHMENTS

### processPositions(text, state)

Parses Positions.csv. Build POSITIONS_DATA array:

```javascript
{
  co: companyName.toLowerCase(),
  co_display: companyName,
  title: title,
  from: parsedISODate,  // "Oct 2024" → "2024-10-01"
  to: parsedISODate     // empty → "2027-01-01" (future sentinel)
}
```

Date parsing: handle "Oct 2024", "2024", and empty strings gracefully.

After processing: re-score all contacts and save.

### processRecommendations(text, state)

Parses Recommendations_Received.csv. Build RECOMMENDERS as array of full name strings.

Expected columns: First Name, Last Name, Company, Job Title, Text, Creation Date, Status

After processing: re-score contacts and save.

### processSkills(text, state)

Parses Skills.csv if present. Build skills array sorted by endorsement count descending. Store top 20. Used in UserProfile.topSkills and for role matching context.

### processProfile(text, state)

Parses Profile.csv. Extract: First Name, Last Name, Headline, Summary. Pre-populate UserProfile fields if user hasn't manually set them yet.

### processEndorsements(text, state)

Build ENDORSERS as array of `"firstname lastname"` strings (lowercase).

### processCompanyFollows(text, state)

Build COMPANY_FOLLOWS as `{ [companyNameLower]: dateString }`.

---

## 6. UI — three tabs

### Design system

```css
:root {
  --bg: #f2f0eb;
  --surface: #ffffff;
  --surface2: #f8f7f3;
  --border: #e3e0d8;
  --border2: #ccc9c0;
  --text: #1a1917;
  --muted: #6b6860;
  --faint: #999590;

  /* Brand colours */
  --purple: #4a42a8;
  --purple-bg: #eeedf8;
  --teal: #0d6b52;
  --teal-bg: #e0f5ee;
  --amber: #b87115;
  --amber-bg: #faecd8;
  --coral: #963a1a;
  --coral-bg: #faece7;
  --blue: #1759a0;
  --blue-bg: #e5f0fb;
  --green: #2e6e1a;
  --green-bg: #e8f3e0;
  --red: #9e2b2b;
  --red-bg: #fbeaea;

  --radius: 10px;
  --radius-lg: 12px;
}
```

Font: system stack `-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif`

### Top navigation bar

```
[WarmPath] [Contacts (count)] [Applications (count)] [Setup]    [Setup/Re-import button]
```

- Sticky, white background, subtle border-bottom
- Active tab has purple underline
- Contact count = Grade A contacts only (e.g. "Contacts (47 A)")
- Application count = active applications only (not rejected/withdrawn)
- "Setup / Re-import" button always visible top-right, opens onboarding

---

### Tab 1: Contacts

The main working surface.

#### Layout

```
[Search bar] [Filter: Grade] [Filter: Status] [Filter: Relationship] [count shown]

[Smart grade review button — amber, only shown if archive data loaded]
[Import banner — shown after import with stats]
[Data panel — contact/archive/clear counts + buttons]

[Contact cards — sorted by score desc]
```

#### Stats row (4 cards)

Total contacts | Grade A | Active conversations (Replied + Call done) | Referrals received

#### Add contact form

Collapsible. Fields: Name, Role/Company, Relationship type, Grade, Status, Notes.

#### Contact card

Each card has two states: collapsed (summary row) and expanded (outreach drawer).

**Collapsed state:**
```
[Avatar initials] [Name]                    [Grade badge] [Status badge]
                  [Role · Company · Signals] [Grade select] [Outreach ↓ button]
                  [LinkedIn ↗] [Message on LinkedIn] [Email via Gmail]
                  [Signals: "1138 messages · colleague at Freshworks · score 95"]
```

Avatar colour: teal background for Grade A, amber for B, gray for C.

**Expanded outreach drawer (click "Outreach ↓"):**

```
─────────────────────────────────────────────────────
FIND OPEN ROLES AT [COMPANY]
[LinkedIn Jobs ↗] [Company Careers ↗] [Indeed ↗] [Naukri ↗]

ROLE YOU WANT TO REFERENCE
[                                        ] [Generate message]
paste job title or URL from the links above

COMPANY INTELLIGENCE  (loaded on demand)
[Glassdoor: 4.1 ★] [Salary: ₹40–55L Staff PM] [→ Load intel]

GENERATED OUTREACH — EDIT BEFORE SENDING
[textarea — editable, monospace, 8 rows]

[Copy] [Log as sent] [Regenerate] [status text]
─────────────────────────────────────────────────────
```

**Company intelligence** loads on demand (user clicks "Load intel"). Calls AI with web search to fetch Glassdoor rating and salary range. Caches result in contact object to avoid repeated calls.

#### Batch grade reviewer

Triggered by "Smart grade review" button. Shows top 80 contacts above score threshold, sorted by score descending, with suggested grade and override dropdown. Two action buttons: "Accept all" and "Save changes".

#### Job search link construction

For each contact, pre-build search URLs using LinkedIn company IDs where known:

```javascript
const LINKEDIN_COMPANY_IDS = {
  'freshworks': '1626966', 'atlassian': '4809', 'chargebee': '2543029',
  'razorpay': '10268668', 'postman': '10528', 'setu': '29414442',
  'hasura': '18031165', 'darwinbox': '11388522', 'sprinklr': '2611821',
  'clevertap': '5269444', 'exotel': '2590029', 'juspay': '5257875',
  'keka': '10524497', 'zoho': '1062776', 'salesforce': '1271',
  'docusign': '2818', 'microsoft': '1035', 'google': '1441',
  'twilio': '166119', 'stripe': '2614441', 'hubspot': '1166390',
  'atlassian': '4809', 'leadsquared': '3448515'
};

function getJobLinks(company, userKeywords) {
  const co = (company || '').toLowerCase();
  const liId = Object.entries(LINKEDIN_COMPANY_IDS).find(([k]) => co.includes(k))?.[1];
  const kw = encodeURIComponent(userKeywords || 'product manager');
  const links = [];
  if (liId) {
    links.push({ label: `LinkedIn Jobs — ${company}`,
      url: `https://www.linkedin.com/jobs/search/?f_C=${liId}&keywords=${kw}&f_TPR=r2592000` });
  } else {
    links.push({ label: `LinkedIn Jobs — search`,
      url: `https://www.linkedin.com/jobs/search/?keywords=${kw}+${encodeURIComponent(company)}&f_TPR=r2592000` });
  }
  links.push({ label: `Indeed — ${company}`,
    url: `https://in.indeed.com/jobs?q=${kw}&l=Bengaluru` });
  links.push({ label: `Naukri — ${company}`,
    url: `https://www.naukri.com/jobs-in-bangalore?keyword=${kw}` });
  return links;
}
```

---

### Tab 2: Applications

#### Layout

```
[+ Add application button]

[Pipeline board: Applied | Screening | In interview | Final | Offer]

[Application cards — sorted: active first, then by date desc]

[HR email templates — collapsible section at bottom]
```

#### Pipeline board

5 columns showing live count of applications in each stage. Clicking a stage filters the list below.

#### Application card

```
[Company name] [Role title] [Status badge] [via Referral badge]
[Referred by: name]                         [Next: Tomorrow · Round 2]
[Notes / prep]                              [Applied: 14 Apr]

[+ Feedback] [Edit] [Remove]

[Feedback log — shown if feedback exists]
  Round 1 · 10 Apr · Passed ✓
    "Asked about marketplace economics. Answered well..."
```

#### Add/edit application form

Fields: Company, Role title, Applied via, Referred by, Date applied, Status, Next interview date+time, Next interviewer/round type, Notes.

#### Feedback log

Per application. Fields: Round name, Date, Outcome (Passed/Waiting/Rejected/More info needed), Notes (questions asked, what went well, what to improve).

#### Company intelligence panel

On each application card, a "Load intel" button fetches and caches Glassdoor rating and salary range for that company.

#### HR email templates (always visible, collapsible)

Four templates with one-click copy:
1. Request feedback after rejection
2. Follow up after silence (10+ days)
3. Thank you after final round
4. Negotiate / ask for timeline

---

### Tab 3: Setup

This tab is also the onboarding flow for new users. On first visit, it shows as a full-screen overlay. On return, it's a normal tab.

#### Sections

**1. About you**

Fields: Name, LinkedIn headline, Background summary (2–3 sentences used in outreach), Target role type, Current level (Staff PM / Head of Product / etc), Location.

Auto-populated from Profile.csv if uploaded. User can edit.

**2. Import your LinkedIn archive**

Two upload options:

Option A — Upload zip (recommended):
```
[Drop zone or click to upload .zip]
Drag your LinkedIn archive zip here
```

Option B — Upload individual files:
```
[Connections.csv]           ○ Not uploaded  — Required. Loads your contacts.
[messages.csv]              ○ Not uploaded  — Adds warmth signals (strongest)
[Positions.csv]             ○ Not uploaded  — Adds career overlap detection
[Recommendations_Received.csv] ○ Not uploaded — Auto-upgrades recommenders to A
[Skills.csv]                ○ Not uploaded  — Enables skill-weighted matching
[Profile.csv]               ○ Not uploaded  — Pre-fills your profile
[Endorsement_Received_Info.csv] ○ Not uploaded — Optional signal
[Company_Follows.csv]       ○ Not uploaded  — Optional signal
```

Status indicators: ○ Not uploaded | ✓ Loaded (green) | ✗ Failed (red)

After each upload: show a status banner with stats (e.g. "4,194 contacts loaded — 686 Grade A · 1,146 Grade B")

**How to download your archive** — always-visible collapsible section:
```
Step 1: LinkedIn → Me → Settings & Privacy
Step 2: Data Privacy → Get a copy of your data
Step 3: Select "Download larger data archive" → Request archive
Step 4: Wait for email (10–30 min) → Download .zip
```

**3. Scoring preview**

After archive is loaded, show a mini breakdown:
- Total contacts: X
- Grade A: X (Y% of total)
- Signals active: Messages ✓ | Positions ✓ | Recommendations ✓
- Top 5 contacts by score (name, company, score, warmth tier)

**4. Data management**

```
Contacts: X | Applications: X | Message history: X slugs | Recommenders: X

[Clear contacts]  [Clear archive data]  [Clear everything & restart]
```

- "Clear contacts" — removes contacts only, keeps archive data
- "Clear archive data" — removes MSG_LOOKUP, POSITIONS_DATA, etc. Contact grades revert to basic scoring.
- "Clear everything & restart" — nukes all localStorage, re-opens setup

**5. About / launcher instructions**

Explain the server requirement for AI generation. Show exact Terminal command. Reference the launch.command file.

---

## 7. AI message generator

### When called

User opens outreach drawer on a contact card, optionally pastes a role title, and clicks "Generate message".

### Tone matrix

The message tone is determined entirely by `warmthTier`. Use this mapping exactly:

| warmthTier | tone | opening style |
|------------|------|---------------|
| `recommender` | Warm, personal, first-name, casual. Reference the recommendation. | Reference something specific from their recommendation text or shared project. |
| `close-colleague` | Casual, warm, first-name. Many messages exchanged. | Specific shared memory, project, or inside reference. Not "hope you're well". |
| `colleague` | Warm, collegial, peer-to-peer. | Reference the specific company or project worked on together. |
| `active-contact` | Friendly, direct. Skip formalities entirely. | Acknowledge prior contact, get to the point fast. |
| `known` | Professional but human. Establish the connection anchor. | One sentence on how you know each other, then the point. |
| `warm-unknown` | Professional, peer-to-peer. Specific hook. | Lead with something specific about their company, role, or recent work. |
| `cold` | Formal but not stiff. Short, respectful of their time. | Reference something very specific about their company or problem space. |

### Prompt template

```javascript
async function generateOutreachMessage(contact, roleHint, userProfile, archiveData) {
  const scored = smartScore(contact, archiveData);
  const toneMap = { /* tone matrix as above */ };
  const tone = toneMap[scored.warmthTier] || toneMap['cold'];

  const prompt = `You are writing a LinkedIn direct message on behalf of ${userProfile.name || 'the user'}.

USER'S BACKGROUND:
${userProfile.bg}
Headline: ${userProfile.headline}
Target roles: ${userProfile.target}
Top skills: ${(userProfile.topSkills || []).slice(0, 5).join(', ')}

CONTACT INTELLIGENCE:
Name: ${contact.name}
Current role: ${contact.role}
Company: ${contact.company}
Relationship: ${contact.relationship}
Messages exchanged historically: ${scored.msgCount}
Warmth tier: ${scored.warmthTier}
Grade: ${scored.grade}
Signals: ${scored.reasons.join(', ')}

TARGET ROLE: ${roleHint || 'a product platform role at ' + contact.company}

TONE: ${tone.tone}
OPENING: ${tone.opening}

RULES:
- Under 130 words total
- 3–4 short paragraphs
- Do NOT use: "hope this message finds you well", "I am passionate about", "synergy", "leverage", "circle back", "reach out", "I came across your profile"
- Do NOT start with "Hi [name], I hope..."
- End with a no-pressure close
- Output ONLY the message text — no subject line, no preamble, no explanation`;

  const response = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      model: 'claude-sonnet-4-20250514',
      max_tokens: 400,
      messages: [{ role: 'user', content: prompt }]
    })
  });

  const data = await response.json();
  return data.content?.map(b => b.text || '').join('') || '';
}
```

### Company intelligence fetch

```javascript
async function fetchCompanyIntel(companyName) {
  const prompt = `Search for current information about "${companyName}" as a place to work.
Return ONLY a JSON object with these exact fields:
{
  "glassdoorRating": number or null,
  "salaryRange": "string like ₹35–55L for Staff PM" or null,
  "reviewSentiment": "1-sentence summary of employee sentiment" or null
}
No other text.`;

  const response = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      model: 'claude-sonnet-4-20250514',
      max_tokens: 200,
      tools: [{ type: 'web_search_20250305', name: 'web_search' }],
      messages: [{ role: 'user', content: prompt }]
    })
  });

  const data = await response.json();
  const text = data.content?.map(b => b.text || '').join('') || '{}';
  try {
    return JSON.parse(text.replace(/```json|```/g, '').trim());
  } catch {
    return null;
  }
}
```

### Log as sent behaviour

When user clicks "Log as sent":
1. Update contact.status to "Message sent"
2. Set contact.lastContacted to today's ISO date
3. Save contact.savedRole to the role input value (if any)
4. Append message preview (first 120 chars) to contact.notes
5. Re-render contacts

---

## 8. Onboarding flow

### First visit

Show full-screen overlay with 4-step wizard. Steps:

**Step 1 — Welcome**
- Explain the person-first concept in 2 sentences
- Show the LinkedIn archive download instructions
- Buttons: "Skip setup" | "I have my archive →"

**Step 2 — Import**
- Upload zip or individual CSVs
- File status list with ○/✓/✗ indicators
- Nudge: "Connections.csv is enough to start. Messages.csv unlocks the strongest warmth signals."
- Status banner showing import results after each upload
- Buttons: "← Back" | "Skip — do manually later" | "Continue →"

**Step 3 — About you**
- Name, headline, background, target role
- Auto-populated from Profile.csv if uploaded
- Buttons: "← Back" | "Continue →"

**Step 4 — Ready**
- Summary: "X contacts loaded, Y Grade A ready for outreach"
- Server note (see Section 9)
- Button: "Start using WarmPath →"

### Returning user

Skip overlay. Just render the app normally. "Setup / Re-import" button always visible in topbar.

---

## 9. Launcher scripts

### launch.command (Mac)

```bash
#!/bin/bash
cd "$(dirname "$0")"
PORT=8080
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then PORT=8181; fi
echo ""
echo "  WarmPath starting on http://localhost:$PORT"
echo "  Keep this window open while using the tool."
echo "  Press Ctrl+C to stop."
echo ""
(sleep 1.2 && open "http://localhost:$PORT/warmpath.html") &
python3 -m http.server $PORT 2>/dev/null || python -m SimpleHTTPServer $PORT
```

Make executable: the file must have execute permission (`chmod +x launch.command`).

**Gatekeeper fix instructions** (shown in Setup tab and Step 4 of onboarding):
> "On first run, macOS may block launch.command. Fix: open Terminal, type `chmod +x ` (with a space), drag the launch.command file into Terminal, press Enter. Then double-click to run."

### launch.bat (Windows)

```batch
@echo off
cd /d "%~dp0"
start "" "http://localhost:8080/warmpath.html"
python -m http.server 8080
pause
```

---

## 10. CSV parser

Use this exact implementation. It handles quoted fields, Windows line endings, and LinkedIn's edge cases:

```javascript
function parseCSV(text) {
  const lines = text.replace(/\r\n/g, '\n').replace(/\r/g, '\n').split('\n');
  const result = [];
  for (const line of lines) {
    if (!line.trim()) continue;
    const row = [];
    let inQ = false, cur = '';
    for (let i = 0; i < line.length; i++) {
      const ch = line[i];
      if (ch === '"') {
        if (inQ && line[i + 1] === '"') { cur += '"'; i++; }
        else inQ = !inQ;
      } else if (ch === ',' && !inQ) {
        row.push(cur.trim());
        cur = '';
      } else {
        cur += ch;
      }
    }
    row.push(cur.trim());
    result.push(row);
  }
  return result;
}
```

---

## 11. Error handling principles

- Every API call wrapped in try/catch. On failure: show inline error in the relevant component, never crash the whole app.
- File import errors: show in the status banner with the specific error message. Never lose already-imported contacts.
- localStorage quota exceeded: warn the user, suggest clearing archive data (which is large) while keeping contacts.
- Missing JSZip: if zip upload is attempted and JSZip isn't loaded, show: "JSZip is loading — try again in a moment."
- CORS error on API call: detect and show: "AI generation requires the local server. Double-click launch.command to enable it."

---

## 12. What NOT to build

Explicitly excluded from v1:

- No Glassdoor/salary data shown in the contacts tab (only in applications tab, on-demand)
- No LinkedIn post scheduler or content drafting
- No resume tailoring in the UI (it's in the outreach message, not a separate feature)
- No multi-user or sync features
- No backend, accounts, or database
- No mobile-specific layout (desktop-first is fine; readable on mobile is sufficient)
- No dark mode (implement CSS variables correctly so it can be added later, but do not implement toggle)
- No analytics or tracking of any kind

---

## 13. Build order

Build in this exact sequence. Each step should be testable before moving to the next.

1. **File scaffolding** — empty HTML with CSS variables, nav, three empty tab panels, and init script
2. **Data layer** — localStorage read/write functions, empty archive data structure
3. **CSV parser** — test with a sample Connections.csv
4. **Scoring engine** — `smartScore()` function, test with mock contacts
5. **Archive processors** — processConnections first, then processMessages (most impactful), then others
6. **Contacts tab** — render list, search/filter, status updates, grade changes
7. **Batch grade reviewer** — the smart grading UI
8. **Outreach drawer** — job links, role input, AI message generator
9. **Applications tab** — pipeline board, cards, feedback log, HR templates
10. **Setup tab** — profile form, file upload UI, data management controls
11. **Onboarding overlay** — 4-step wizard
12. **Launcher scripts** — launch.command and launch.bat
13. **Polish** — responsive layout, error states, empty states, loading indicators

---

## 14. Testing checklist

Before considering the build complete, verify:

- [ ] Import Connections.csv with 4,000+ rows — no crashes, correct grade distribution
- [ ] Re-import same file — no duplicates created, merged count shown correctly
- [ ] Import messages.csv — contact grades update, score reasons change
- [ ] "Generate message" works for each warmth tier — tone is visibly different
- [ ] "Log as sent" updates contact status and notes
- [ ] Add 3 applications, advance through stages, log feedback for each
- [ ] "Load intel" on a company returns plausible data
- [ ] Clear contacts — applications survive, archive data survives
- [ ] Clear archive data — contacts survive, grades revert to basic scoring
- [ ] Clear everything — all localStorage wiped, onboarding re-opens
- [ ] Open file directly (file://) — everything works except AI generation
- [ ] Open via launch.command (http://localhost) — AI generation works
- [ ] Works correctly in Chrome, Safari, Firefox

---

## 15. Key decisions already made (do not revisit)

These were decided after extensive iteration. Do not deviate without explicit confirmation.

| Decision | Rationale |
|----------|-----------|
| Single HTML file | Zero friction distribution. Share file = someone can use it. |
| localStorage only | No backend = no GDPR, no accounts, no cost, no maintenance. |
| Person-first, not job-first | Core product philosophy. Contacts are the centrepiece. |
| Three tabs only | Contacts, Applications, Setup. Everything else is redundant. |
| Progressive archive enrichment | Works with Connections.csv alone. More files = smarter, but never blocks. |
| Merge, don't overwrite | Re-import should never lose user's manual work. |
| Warmth tier drives message tone | Grade is not enough. 1,100 messages ≠ 2 messages even if both Grade A. |
| AI generation via Anthropic API direct | No proxy, no wrapper. Simple and transparent. |
| On-demand company intel | Don't auto-fetch for 4,000 contacts. Fetch when user opens a specific card. |
| No hardcoded personal data | Tool must work for any user out of the box. |

---

*End of spec. Start with Section 13 Build Order, Step 1.*
