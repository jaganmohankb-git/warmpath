#!/usr/bin/env python3
"""
WarmPath MCP Server
Exposes your LinkedIn network data to Claude Desktop via 16 tools.

Read tools:  score_connection · find_warm_connections_at_company ·
             draft_outreach_message · list_connections · get_todays_plan ·
             get_followup_list · get_weekly_summary · open_linkedin_profile ·
             copy_message_to_clipboard
Write tools: log_message_sent · log_reply
Settings:    set_ex_companies
Job search:  find_open_role · prepare_resume_response
Layer 2:     send_outreach  (draft + open LinkedIn + clipboard + log in one step)
Daily:       morning_briefing  (plan + follow-ups + LinkedIn inbox check)

Data source: warmpath_data.json (or warmpath-backup-*.json) in the parent directory.
Export it from WarmPath → Setup → Settings → Backup → Download, then rename it
to warmpath_data.json and place it in the WarmPath folder.
"""

import json
import os
import platform
import re
import secrets
import subprocess
import webbrowser
from datetime import datetime, timedelta, timezone
from pathlib import Path

from mcp.server.fastmcp import FastMCP
try:
    from mcp.server.fastmcp.server import TransportSecuritySettings
    # Disable DNS rebinding protection so ngrok proxy works
    _TRANSPORT_SECURITY = TransportSecuritySettings(enable_dns_rebinding_protection=False)
except ImportError:
    _TRANSPORT_SECURITY = None

# ─── Data loading ─────────────────────────────────────────────────────────────

def _find_data_file() -> Path:
    """
    Look for the WarmPath data file.
    Cloud (Railway): checks /data/warmpath_data.json first (persistent volume).
    Local: checks parent directory for warmpath_data.json or warmpath-backup-*.json.
    """
    # Cloud deployment: Railway mounts a persistent volume at /data
    cloud_path = Path("/data/warmpath_data.json")
    if cloud_path.exists():
        return cloud_path

    parent = Path(__file__).parent.parent

    preferred = parent / "warmpath_data.json"
    if preferred.exists():
        return preferred

    backups = sorted(parent.glob("warmpath-backup*.json"), reverse=True)
    if backups:
        return backups[0]

    raise FileNotFoundError(
        "\n\n  WarmPath data file not found.\n\n"
        "  To fix this:\n"
        "  1. Open WarmPath in your browser\n"
        "  2. Go to Setup → Settings → Backup → Download backup\n"
        "  3. Rename the downloaded file to: warmpath_data.json\n"
        f"  4. Move it to: {parent}\n"
    )


def _parse_field(raw_value, default):
    """Handle WarmPath's double-encoded JSON fields (values stored as JSON strings)."""
    if raw_value is None:
        return default
    if isinstance(raw_value, str):
        try:
            return json.loads(raw_value)
        except (json.JSONDecodeError, ValueError):
            return default
    return raw_value


def load_data() -> dict:
    """Load and normalise the WarmPath backup JSON."""
    path = _find_data_file()
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    contacts    = _parse_field(raw.get("wp_contacts"),       [])
    profile     = _parse_field(raw.get("wp_profile"),        {})
    recommenders= _parse_field(raw.get("wp_rec"),            [])
    targets     = _parse_field(raw.get("wp_custom_targets"), [])
    applications= _parse_field(raw.get("wp_applications"),   [])

    # Strip out sample/demo contacts that ship with the app
    contacts = [c for c in contacts if not c.get("_sample")]

    return {
        "contacts":      contacts,
        "profile":       profile,
        "recommenders":  [r.lower() for r in recommenders],
        "targets":       [t.lower() for t in targets],
        "applications":  applications,
        "backup_date":   raw.get("_backupDate", "unknown"),
        "source_file":   str(path),
    }


# ─── Data writing ────────────────────────────────────────────────────────────

def save_profile_field(key: str, value) -> None:
    """
    Write a single field into the wp_profile JSON stored in warmpath_data.json.
    """
    path = _find_data_file()
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    profile_raw = raw.get("wp_profile", "{}")
    try:
        profile = json.loads(profile_raw) if isinstance(profile_raw, str) else dict(profile_raw)
    except Exception:
        profile = {}

    profile[key] = value
    raw["wp_profile"] = json.dumps(profile, ensure_ascii=False)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(raw, f, ensure_ascii=False, indent=2)


def save_contacts(contacts: list) -> None:
    """
    Write an updated contacts list back to warmpath_data.json,
    preserving all other fields in the file exactly as they were.
    WarmPath stores wp_contacts as a JSON string inside the outer JSON,
    so we re-serialize it the same way.
    """
    path = _find_data_file()
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    # Re-encode contacts as a JSON string (matching WarmPath's storage format)
    raw["wp_contacts"] = json.dumps(contacts, ensure_ascii=False)
    raw["_backupDate"] = datetime.now(timezone.utc).isoformat()

    with open(path, "w", encoding="utf-8") as f:
        json.dump(raw, f, ensure_ascii=False, indent=2)


def _make_interaction_id() -> str:
    """Generate a short random ID matching WarmPath's format (e.g. 'mohal6uyfn1')."""
    return secrets.token_hex(5) + secrets.token_urlsafe(3)[:3]


def _message_typing_steps(message: str) -> str:
    """
    Convert a message into browser-automation typing instructions.

    LinkedIn's compose box sends on bare Enter ('Press Enter to Send' mode).
    To keep a multi-line message as ONE send, every line break must be
    inserted with Shift+Enter, not Enter.

    Returns a numbered list of steps — type each segment, press Shift+Enter
    between segments — so Claude Desktop knows exactly what keys to press.

    IMPORTANT FOR BROWSER AUTOMATION:
    - NEVER use the `type` action with newline (\\n) characters in LinkedIn.
    - ALWAYS split the message at \\n boundaries and press Shift+Enter between them.
    - Or use Cmd+V (paste) if the message is already on the clipboard — pasting
      respects line breaks without triggering Send.
    """
    segments = message.split("\n")
    steps: list[str] = []
    step_num = 1
    for i, seg in enumerate(segments):
        if seg.strip():
            steps.append(f"  {step_num}. Type: {seg}")
            step_num += 1
        if i < len(segments) - 1:
            steps.append(f"  {step_num}. Press: Shift+Enter  ← NOT plain Enter")
            step_num += 1
    steps.append(
        f"  {step_num}. When the full message looks correct, press Enter (or click Send) ONCE to send."
    )
    return "\n".join(steps)


# ─── Seniority detection ─────────────────────────────────────────────────────

def _get_seniority(position: str) -> int:
    """
    Infer seniority level from a job title string.

    Returns an integer 1–5:
      1 = IC / PM / Associate PM          → warm, conversational
      2 = Senior PM / Senior IC           → professional, peer tone
      3 = Staff / Principal / Lead PM     → focused, peer-to-senior
      4 = Group PM / Director / Head of   → crisp, respectful, specific
      5 = VP / CPO / C-suite              → ultra-concise, no filler, single ask
    """
    if not position:
        return 1
    p = position.lower()

    # Level 5 — VP and above
    if any(k in p for k in ["vp ", "vice president", "chief product", " cpo", "svp", "evp",
                             "c-suite", "president", "chief of product"]):
        return 5

    # Level 4 — Director / Head of / Group PM
    if any(k in p for k in ["director", "head of product", "head of pm", "group product",
                             "group pm", "gpm", "senior director"]):
        return 4

    # Level 3 — Staff / Principal / Lead
    if any(k in p for k in ["staff product", "staff pm", "principal product", "principal pm",
                             "lead product", "lead pm", "product lead"]):
        return 3

    # Level 2 — Senior PM
    if any(k in p for k in ["senior product", "senior pm", "sr. product", "sr product"]):
        return 2

    # Level 1 — PM / Associate / APM / everything else
    return 1


def _seniority_label(level: int) -> str:
    return {1: "PM", 2: "Senior PM", 3: "Staff/Lead PM",
            4: "Director/Head", 5: "VP/C-suite"}.get(level, "PM")


def _seniority_tone_note(level: int) -> str:
    """Return a tone instruction string for inclusion in AI system prompts."""
    notes = {
        1: ("Write in a warm, conversational tone. 4-5 lines is fine. "
            "An informal ask like 'Would you be open to a quick chat?' works well."),
        2: ("Write in a professional, peer-to-peer tone. Keep it to 4 lines. "
            "State your purpose clearly and make a direct but friendly ask."),
        3: ("Write in a focused, peer-to-senior tone. 3-4 lines maximum. "
            "Lead with a specific reason for reaching out. No filler phrases."),
        4: ("Write in a crisp, respectful tone. 3 lines maximum. "
            "One sharp value prop, one direct ask. Remove all filler and pleasantries. "
            "They are busy — get to the point immediately."),
        5: ("Write in an ultra-concise, executive tone. 2-3 sentences maximum — no exceptions. "
            "Single specific ask. Zero filler. Every word must earn its place. "
            "Do not start with 'I hope' or 'I came across your profile'. Start with the point."),
    }
    return notes.get(level, notes[1])


# ─── Careers URL map ─────────────────────────────────────────────────────────

CAREERS_URLS: dict[str, str] = {
    "google":       "https://careers.google.com/jobs/results/",
    "microsoft":    "https://jobs.careers.microsoft.com/global/en/search",
    "amazon":       "https://www.amazon.jobs/en/search",
    "meta":         "https://www.metacareers.com/jobs",
    "apple":        "https://jobs.apple.com/en-us/search",
    "netflix":      "https://jobs.netflix.com/search",
    "stripe":       "https://stripe.com/jobs/search",
    "airbnb":       "https://careers.airbnb.com/",
    "uber":         "https://www.uber.com/us/en/careers/list/",
    "linkedin":     "https://careers.linkedin.com/",
    "salesforce":   "https://salesforce.wd12.myworkdayjobs.com/Salesforce/",
    "adobe":        "https://careers.adobe.com/us/en/search-results",
    "atlassian":    "https://www.atlassian.com/company/careers/all-jobs",
    "spotify":      "https://www.lifeatspotify.com/jobs",
    "razorpay":     "https://razorpay.com/jobs/",
    "zoho":         "https://careers.zoho.com/",
    "freshworks":   "https://careers.freshworks.com/",
    "swiggy":       "https://careers.swiggy.com/",
    "zomato":       "https://www.zomato.com/careers",
    "flipkart":     "https://www.flipkartcareers.com/#!/joblist",
    "paytm":        "https://jobs.paytm.com/",
    "phonepe":      "https://careers.phonepe.com/",
    "meesho":       "https://meesho.io/jobs",
    "cred":         "https://careers.cred.club/",
    "groww":        "https://groww.in/careers",
    "capital one":  "https://www.capitalonecareers.com/",
    "thoughtworks": "https://www.thoughtworks.com/careers/",
    "chargebee":    "https://www.chargebee.com/careers/",
    "notion":       "https://www.notion.so/careers",
    "anthropic":    "https://www.anthropic.com/careers",
}


def _careers_url(company: str) -> tuple[str | None, str | None]:
    """
    Return (matched_key, careers_url) for a company, or (None, None).
    Fuzzy: 'Capital One Financial' matches key 'capital one'.
    """
    co = company.lower()
    for key, url in CAREERS_URLS.items():
        if key in co or co in key:
            return key, url
    return None, None


# ─── Message drafting ─────────────────────────────────────────────────────────

def _draft_message(contact: dict, profile: dict, context: str = "") -> str:
    """
    Generate a warmth-appropriate, seniority-aware draft outreach message.
    Adapts on two axes:
      - Warmth tier (7 levels: recommender → cold)
      - Contact seniority (5 levels: PM → VP/C-suite)
    Higher seniority → more formal, shorter, sharper single ask.
    """
    first    = (contact.get("name") or "there").split()[0]
    company  = contact.get("company") or "your company"
    tier     = contact.get("warmthTier") or "cold"
    position = contact.get("position") or contact.get("role") or ""
    target   = (profile.get("target") or "a senior role").split(",")[0].strip()
    my_name  = profile.get("name") or ""
    my_level = profile.get("currentLevel") or "senior professional"
    goal     = profile.get("primaryGoal") or "Job Search"

    role_ref = context.strip() if context.strip() else target
    seniority = _get_seniority(position)

    # ── Recruiter mode ────────────────────────────────────────────────────────
    if goal == "Recruiting":
        role_part = f" for a {role_ref} role" if role_ref else ""
        if seniority >= 4:
            return (
                f"Hi {first},\n\n"
                f"I'm building out a team{role_part}. Given your vantage point at {company}, "
                f"I'd value your perspective on the right profile.\n\n"
                f"15 minutes at your convenience?"
            )
        return (
            f"Hi {first},\n\n"
            f"I'm building out a team{role_part} and you came to mind — "
            f"your network and perspective would be invaluable.\n\n"
            f"Would you be open to a quick chat? Happy to work around your schedule."
        )

    # ── Advisory / Consulting mode ────────────────────────────────────────────
    if goal == "Advisory/Consulting":
        domain = role_ref or my_level
        if seniority >= 4:
            return (
                f"Hi {first},\n\n"
                f"I've been advising on {domain} and {company}'s direction is relevant to some of that work. "
                f"Worth a brief conversation?\n\n"
                f"{my_name}"
            )
        return (
            f"Hi {first},\n\n"
            f"Good to stay connected. I've been advising companies on {domain} lately "
            f"and {company}'s direction caught my attention — there might be some overlap worth exploring.\n\n"
            f"No pitch — just a conversation if you're open to it.\n\n"
            f"{my_name}"
        )

    # ── Pure networking mode ──────────────────────────────────────────────────
    if goal == "Networking":
        if seniority >= 4:
            return (
                f"Hi {first},\n\n"
                f"I've been following {company}'s work closely. Would love to connect briefly "
                f"and exchange perspectives — no specific agenda.\n\n"
                f"{my_name}"
            )
        return (
            f"Hi {first},\n\n"
            f"Hope things are going well at {company}! "
            f"I've been following what you're building there and wanted to drop a note.\n\n"
            f"No agenda — just staying in touch. Would love to hear what you're working on "
            f"if you ever have a few minutes.\n\n"
            f"{my_name}"
        )

    # ── Job Search — warmth-tier × seniority templates ────────────────────────
    # Seniority 4-5: Director / VP — crisp and concise
    if seniority >= 4:
        templates_senior = {
            "recommender": (
                f"Hi {first},\n\n"
                f"Really appreciate the recommendation — meant a lot.\n\n"
                f"I'm targeting {role_ref} roles and {company} is at the top of my list. "
                f"Would you be open to a brief call?"
            ),
            "close-colleague": (
                f"Hi {first},\n\n"
                f"I'm actively looking at {role_ref} roles — {company} is high on my list. "
                f"Any open positions or the right person to speak with?\n\n"
                f"Appreciate any steer."
            ),
            "colleague": (
                f"Hi {first},\n\n"
                f"I'm exploring {role_ref} opportunities and {company} stands out. "
                f"Would you have 15 minutes to share your perspective on the team?\n\n"
                f"Happy to work around your schedule."
            ),
            "active-contact": (
                f"Hi {first},\n\n"
                f"Following up — I'm actively pursuing {role_ref} roles and {company} is a top choice. "
                f"Any visibility on openings or the right contact?\n\n"
                f"Thank you."
            ),
            "known": (
                f"Hi {first},\n\n"
                f"I'm {my_name}, a {my_level} — we connected previously. "
                f"I'm targeting {role_ref} roles at {company} and would value 15 minutes of your time.\n\n"
                f"Would that be possible?"
            ),
            "warm-unknown": (
                f"Hi {first},\n\n"
                f"I'm a {my_level} targeting {role_ref} roles — {company} is a strong fit. "
                f"Would you be open to a 15-minute conversation?\n\n"
                f"I'll keep it brief and focused."
            ),
            "cold": (
                f"Hi {first},\n\n"
                f"I'm {my_name}, a {my_level}. {company}'s work is directly relevant to my background "
                f"and I'm exploring {role_ref} opportunities.\n\n"
                f"Would 15 minutes be possible?"
            ),
        }
        return templates_senior.get(tier, templates_senior["cold"])

    # Seniority 3: Staff / Principal / Lead — focused, peer-to-senior
    if seniority == 3:
        templates_staff = {
            "recommender": (
                f"Hi {first},\n\n"
                f"Thank you for the recommendation — it genuinely meant a lot.\n\n"
                f"I'm actively targeting {role_ref} roles and {company} is high on my list. "
                f"Would you be open to a quick call to share your perspective?"
            ),
            "close-colleague": (
                f"Hi {first},\n\n"
                f"I'm actively exploring {role_ref} roles and {company} is a natural next step. "
                f"Given our time working together, I'd value your honest take — "
                f"any open roles or people I should connect with?\n\n"
                f"Worth a quick catch-up?"
            ),
            "colleague": (
                f"Hi {first},\n\n"
                f"Great to have stayed in touch. I'm exploring {role_ref} opportunities "
                f"and {company} stood out.\n\n"
                f"Would you be open to sharing your perspective on the team? Even 15 minutes would help."
            ),
            "active-contact": (
                f"Hi {first},\n\n"
                f"Picking up from our last exchange — I'm actively pursuing {role_ref} roles "
                f"and {company} is high on my list.\n\n"
                f"Any open positions or someone I should speak with? Appreciate any steer."
            ),
            "known": (
                f"Hi {first},\n\n"
                f"We connected previously — I'm {my_name}, a {my_level}.\n\n"
                f"I'm exploring {role_ref} opportunities at {company} and would value "
                f"a short conversation. No pressure — appreciate your time."
            ),
            "warm-unknown": (
                f"Hi {first},\n\n"
                f"I've been following {company}'s work and your profile stood out.\n\n"
                f"I'm a {my_level} exploring {role_ref} roles — would you be open to "
                f"a 15-minute conversation? Happy to share more context."
            ),
            "cold": (
                f"Hi {first},\n\n"
                f"I'm {my_name}, a {my_level} exploring {role_ref} opportunities.\n\n"
                f"Your work at {company} caught my attention. Would 15 minutes be possible "
                f"to learn more about the team?"
            ),
        }
        return templates_staff.get(tier, templates_staff["cold"])

    # Seniority 1-2: PM / Senior PM — warm, conversational
    templates = {
        "recommender": (
            f"Hi {first},\n\n"
            f"Thank you again for the recommendation — it genuinely meant a lot.\n\n"
            f"I'm actively exploring {role_ref} opportunities and {company} is high on my list. "
            f"Given your experience there, I'd love your honest perspective on the team and what it takes to succeed.\n\n"
            f"Would you be open to a quick call? Happy to work around your schedule."
        ),
        "close-colleague": (
            f"Hi {first},\n\n"
            f"Hope things are going well at {company}!\n\n"
            f"I'm actively looking at {role_ref} roles and your team came up as a natural fit. "
            f"Given our time together, I'd value your honest take — any open roles or people I should speak with?\n\n"
            f"Worth a quick catch-up?"
        ),
        "colleague": (
            f"Hi {first},\n\n"
            f"Great to have stayed connected since our time together.\n\n"
            f"I'm exploring {role_ref} opportunities and {company} stood out. "
            f"Would you be open to sharing your perspective on the team and culture?\n\n"
            f"Even 15 minutes would be really helpful."
        ),
        "active-contact": (
            f"Hi {first},\n\n"
            f"Picking up from our last exchange — I'm actively looking at {role_ref} roles "
            f"and {company} is high on my list.\n\n"
            f"Any open positions on your radar, or someone I should speak with?\n\n"
            f"Appreciate any steer."
        ),
        "known": (
            f"Hi {first},\n\n"
            f"We connected a while back — I'm {my_name}, a {my_level}.\n\n"
            f"I'm exploring {role_ref} opportunities and {company} stood out as a strong fit. "
            f"Would you be open to a short chat?\n\n"
            f"No pressure either way — appreciate your time."
        ),
        "warm-unknown": (
            f"Hi {first},\n\n"
            f"I've been following {company}'s work and came across your profile.\n\n"
            f"I'm a {my_level} exploring {role_ref} roles — your team looks like a strong fit. "
            f"Would you be open to a 15-minute conversation?\n\n"
            f"Happy to share more context if helpful."
        ),
        "cold": (
            f"Hi {first},\n\n"
            f"I'm {my_name}, a {my_level} exploring {role_ref} opportunities.\n\n"
            f"Your work at {company} caught my attention and I'd be grateful for 15 minutes "
            f"to learn more about the team.\n\n"
            f"Would that be possible?"
        ),
    }
    return templates.get(tier, templates["cold"])


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _grade_label(grade: str) -> str:
    labels = {"A": "🟢 Grade A (warm)", "B": "🟡 Grade B (lukewarm)", "C": "🔴 Grade C (cold)"}
    return labels.get(grade, grade or "unknown")


def _fuzzy_match(query: str, text: str) -> bool:
    """Case-insensitive substring match."""
    return query.lower().strip() in (text or "").lower()


def _find_contact(contacts: list, name: str) -> dict | None:
    """Find a contact by name — exact first, then partial."""
    name_lower = name.lower().strip()
    # Exact match first
    for c in contacts:
        if (c.get("name") or "").lower() == name_lower:
            return c
    # Partial match
    for c in contacts:
        if name_lower in (c.get("name") or "").lower():
            return c
    return None


def _format_interactions(interactions: list) -> str:
    if not interactions:
        return "  No logged interactions."
    lines = []
    for ix in interactions:
        date_str = ix.get("date", "")
        try:
            date_str = datetime.fromisoformat(date_str.replace("Z", "+00:00")).strftime("%Y-%m-%d")
        except Exception:
            pass
        resp = ix.get("response")
        resp_str = f" → Response: {resp}" if resp else ""
        msg_preview = (ix.get("message") or "")[:80]
        if len(ix.get("message") or "") > 80:
            msg_preview += "…"
        lines.append(f"  [{date_str}] {msg_preview}{resp_str}")
    return "\n".join(lines)


# ─── MCP server ───────────────────────────────────────────────────────────────

mcp = FastMCP(
    "WarmPath",
    instructions=(
        "You have access to the user's LinkedIn network data from WarmPath. "
        "Use these tools to look up connections, find warm contacts at companies, "
        "and draft personalised outreach messages. Always prefer warmer contacts "
        "(Grade A > B > C) when suggesting who to reach out to."
    ),
)


@mcp.tool()
def score_connection(name: str) -> str:
    """
    Look up a LinkedIn connection by name and return their warmth score,
    grade, interaction history, and key scoring signals.

    Args:
        name: Full or partial name of the connection to look up.
    """
    data    = load_data()
    contact = _find_contact(data["contacts"], name)

    if not contact:
        close = [
            c["name"] for c in data["contacts"]
            if name.lower().split()[0] in (c.get("name") or "").lower()
        ][:5]
        msg = f'No connection found matching "{name}".'
        if close:
            msg += f'\n\nDid you mean one of these?\n' + "\n".join(f"  • {n}" for n in close)
        return msg

    c = contact
    is_recommender = (c.get("name") or "").lower() in data["recommenders"]
    is_target_co   = any(t in (c.get("company") or "").lower() for t in data["targets"])
    days_since     = ""
    if c.get("lastContacted"):
        try:
            last = datetime.fromisoformat(str(c["lastContacted"]).replace("Z", "+00:00"))
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            delta = (datetime.now(timezone.utc) - last).days
            days_since = f"{delta} days ago"
        except Exception:
            days_since = str(c.get("lastContacted"))

    lines = [
        f"### {c.get('name')}",
        f"**Company:** {c.get('company') or '—'}",
        f"**Role:** {c.get('position') or c.get('role') or '—'}",
        f"",
        f"**Warmth score:** {c.get('score', 0)} / 200+",
        f"**Grade:** {_grade_label(c.get('grade'))}",
        f"**Warmth tier:** {c.get('warmthTier') or '—'}",
        f"**Messages exchanged:** {c.get('msgCount', 0)}",
        f"**Outreach status:** {c.get('status') or 'Not contacted'}",
        f"**Last contacted:** {days_since or 'Never'}",
        f"",
        f"**Scoring signals:**",
    ]

    reasons = c.get("gradeReasons") or []
    if is_recommender:
        reasons = ["wrote you a recommendation"] + [r for r in reasons if "recommend" not in r]
    if is_target_co:
        reasons = [r for r in reasons if "target" not in r] + ["at a target company"]
    if c.get("_boosted"):
        reasons.append("⚡ manually boosted (+50 pts)")

    for r in (reasons or ["no signals detected"]):
        lines.append(f"  • {r}")

    if c.get("notes"):
        lines += ["", f"**Notes:** {c['notes']}"]

    if c.get("url"):
        lines += ["", f"**LinkedIn:** {c['url']}"]

    interactions = c.get("_interactions") or []
    lines += [
        "",
        f"**Interaction history ({len(interactions)} logged):**",
        _format_interactions(interactions),
    ]

    lines += [
        "",
        f"*Data from: {data['source_file'].split('/')[-1]} — backup dated {data['backup_date'][:10] if data['backup_date'] != 'unknown' else 'unknown'}*",
    ]

    return "\n".join(lines)


@mcp.tool()
def find_warm_connections_at_company(company: str) -> str:
    """
    Find all LinkedIn connections at a given company, sorted by warmth score
    (highest first). Shows grade, role, score, and contact status for each.

    Args:
        company: Company name to search for (partial match supported).
    """
    data     = load_data()
    contacts = data["contacts"]

    matches = [
        c for c in contacts
        if _fuzzy_match(company, c.get("company") or "")
    ]

    if not matches:
        # Suggest similar companies
        all_cos = sorted({c.get("company") for c in contacts if c.get("company")})
        suggestions = [co for co in all_cos if company.lower()[:4] in co.lower()][:5]
        msg = f'No connections found at a company matching "{company}".'
        if suggestions:
            msg += "\n\nDid you mean:\n" + "\n".join(f"  • {s}" for s in suggestions)
        return msg

    # Sort: Grade A first, then by score descending
    grade_order = {"A": 0, "B": 1, "C": 2}
    matches.sort(key=lambda c: (grade_order.get(c.get("grade"), 3), -(c.get("score") or 0)))

    # Group by exact company name for header
    company_display = matches[0].get("company") or company
    is_target = any(t in company_display.lower() for t in data["targets"])
    target_marker = " 🎯 target company" if is_target else ""

    lines = [
        f"### {company_display}{target_marker}",
        f"**{len(matches)} connection{'s' if len(matches) != 1 else ''}** found\n",
    ]

    grade_counts = {g: sum(1 for c in matches if c.get("grade") == g) for g in "ABC"}
    summary_parts = [f"{v}{k}" for k, v in grade_counts.items() if v]
    lines.append(f"**Grade summary:** {' · '.join(summary_parts)}\n")

    for c in matches:
        status     = c.get("status") or "Not contacted"
        msg_count  = c.get("msgCount") or 0
        last_date  = c.get("lastContacted") or ""
        try:
            last_date = datetime.fromisoformat(str(last_date).replace("Z", "+00:00")).strftime("%Y-%m-%d")
        except Exception:
            pass

        interaction_note = ""
        if msg_count > 0:
            interaction_note = f" · {msg_count} msgs"
        if last_date:
            interaction_note += f" · last contact {last_date}"

        boosted = " ⚡" if c.get("_boosted") else ""
        lines.append(
            f"**{c.get('name')}**{boosted}  \n"
            f"  {_grade_label(c.get('grade'))} · Score {c.get('score', 0)}  \n"
            f"  {c.get('position') or c.get('role') or 'Role unknown'}  \n"
            f"  Status: {status}{interaction_note}"
        )
        if c.get("notes"):
            lines.append(f"  📝 {c['notes']}")
        lines.append("")

    lines.append(
        f"*Tip: ask me to `draft_outreach_message` for any of these contacts, "
        f"or `score_connection` for a deeper look at a specific person.*"
    )

    return "\n".join(lines)


@mcp.tool()
def draft_outreach_message(name: str, context: str = "") -> str:
    """
    Draft a personalised outreach message for a LinkedIn connection.
    The message tone and framing adapts to relationship warmth and your
    Primary Goal (Job Search / Recruiting / Advisory / Networking).

    Args:
        name:    Full or partial name of the connection to message.
        context: Optional — job title, role URL, or any extra context
                 (e.g. "Senior PM role at their company" or "Series B fintech startup").
                 Leave blank to use your profile's target role.
    """
    data    = load_data()
    contact = _find_contact(data["contacts"], name)

    if not contact:
        return (
            f'No connection found matching "{name}". '
            f'Try list_connections or find_warm_connections_at_company to check the exact name.'
        )

    profile = data["profile"]
    draft   = _draft_message(contact, profile, context)

    c         = contact
    tier      = c.get("warmthTier") or "cold"
    goal      = profile.get("primaryGoal") or "Job Search"
    msg_count = c.get("msgCount") or 0
    status    = c.get("status") or "Not contacted"

    prior_note = ""
    if msg_count > 0:
        prior_note = (
            f"\n\n> ⚠️  **Note:** You've exchanged {msg_count} messages with {c.get('name')} "
            f"and their current status is **{status}**. "
            f"This draft is for a first contact — you may want to adjust the opening "
            f"to reference your previous conversation."
        )

    seniority     = _get_seniority(c.get("position") or c.get("role") or "")
    seniority_lbl = _seniority_label(seniority)

    lines = [
        f"### Draft message for {c.get('name')}",
        f"*{_grade_label(c.get('grade'))} · {tier} · Goal: {goal} · Seniority: {seniority_lbl}*\n",
        "---",
        "",
        draft,
        "",
        "---",
        f"*Copy this, personalise as needed, and send via LinkedIn.*",
        prior_note,
    ]

    if c.get("url"):
        lines.append(f"\n**LinkedIn profile:** {c['url']}")

    return "\n".join(lines)


@mcp.tool()
def list_connections(
    company: str = "",
    warmth_level: str = "",
    keyword: str = "",
    limit: int = 25,
) -> str:
    """
    List LinkedIn connections with optional filters.
    Returns contacts sorted by warmth score (highest first).

    Args:
        company:      Filter by company name (partial match).
        warmth_level: Filter by grade — "A", "B", or "C".
        keyword:      Search in name, role, company, notes, or relationship.
        limit:        Maximum number of results to return (default 25, max 100).
    """
    data     = load_data()
    contacts = data["contacts"]

    filtered = contacts

    if company:
        filtered = [c for c in filtered if _fuzzy_match(company, c.get("company") or "")]

    if warmth_level:
        grade = warmth_level.upper().strip()
        filtered = [c for c in filtered if c.get("grade") == grade]

    if keyword:
        kw = keyword.lower().strip()
        filtered = [
            c for c in filtered
            if any(
                kw in (c.get(field) or "").lower()
                for field in ["name", "position", "role", "company", "notes", "relationship"]
            )
        ]

    # Sort by grade then score
    grade_order = {"A": 0, "B": 1, "C": 2}
    filtered.sort(key=lambda c: (grade_order.get(c.get("grade"), 3), -(c.get("score") or 0)))

    limit = min(max(1, limit), 100)
    total = len(filtered)
    shown = filtered[:limit]

    if not shown:
        return (
            f"No connections found matching your filters.\n"
            f"  company={company!r}  warmth_level={warmth_level!r}  keyword={keyword!r}\n\n"
            f"Try broader terms or remove some filters."
        )

    # Build active filter description
    filter_parts = []
    if company:       filter_parts.append(f"company contains \"{company}\"")
    if warmth_level:  filter_parts.append(f"grade = {warmth_level.upper()}")
    if keyword:       filter_parts.append(f"keyword = \"{keyword}\"")
    filter_desc = " · ".join(filter_parts) if filter_parts else "no filters"

    grade_counts = {g: sum(1 for c in filtered if c.get("grade") == g) for g in "ABC"}
    summary = " · ".join(f"{v}{k}" for k, v in grade_counts.items() if v)

    lines = [
        f"### Connections ({filter_desc})",
        f"**{total} found** ({summary}) — showing {len(shown)}\n",
    ]

    for c in shown:
        status_str = c.get("status") or "Not contacted"
        boosted    = " ⚡" if c.get("_boosted") else ""
        target_co  = " 🎯" if any(t in (c.get("company") or "").lower() for t in data["targets"]) else ""
        lines.append(
            f"**{c.get('name')}**{boosted}  "
            f"{_grade_label(c.get('grade'))} · {c.get('score', 0)} pts  \n"
            f"  {c.get('position') or c.get('role') or '—'} @ {c.get('company') or '—'}{target_co}  \n"
            f"  Status: {status_str} · {c.get('msgCount', 0)} msgs"
        )
        if c.get("notes"):
            lines.append(f"  📝 {c['notes'][:80]}{'…' if len(c.get('notes',''))>80 else ''}")
        lines.append("")

    if total > limit:
        lines.append(
            f"*Showing {limit} of {total}. Add filters or increase limit to see more.*"
        )

    lines.append(
        f"\n*Data from: {data['source_file'].split('/')[-1]}*"
    )

    return "\n".join(lines)


@mcp.tool()
def log_message_sent(name: str, message: str = "", note: str = "") -> str:
    """
    Mark a message as sent to a connection. Updates their status to Messaged,
    records the timestamp, and saves the interaction log to warmpath_data.json
    so it shows up when you next open WarmPath.

    Args:
        name:    Full or partial name of the connection you messaged.
        message: The message text you sent (optional but recommended for history).
        note:    Any private note to attach (optional).
    """
    data    = load_data()
    contact = _find_contact(data["contacts"], name)

    if not contact:
        return f'No connection found matching "{name}". Check the spelling and try again.'

    now      = datetime.now(timezone.utc)
    now_iso  = now.isoformat()
    now_date = now.strftime("%Y-%m-%d")

    # Build interaction record (same structure WarmPath uses)
    interaction = {
        "id":       _make_interaction_id(),
        "date":     now_iso,
        "type":     "linkedin",
        "message":  message,
        "role":     contact.get("savedRole") or "",
        "response": None,
        "note":     note,
    }

    # Update contact fields
    if "_interactions" not in contact or not isinstance(contact["_interactions"], list):
        contact["_interactions"] = []
    contact["_interactions"].append(interaction)

    # Only advance status forward — never overwrite a warmer status
    status_order = ["Not contacted", "Messaged", "Replied", "Met", "Referred me", "No response"]
    current_status = contact.get("status") or "Not contacted"
    if current_status not in status_order or status_order.index(current_status) < status_order.index("Messaged"):
        contact["status"] = "Messaged"

    contact["lastContacted"] = now_date
    if message:
        contact["_lastSentMsg"]  = message
        contact["_lastSentDate"] = now_iso

    # Load ALL contacts (including sample ones) to write back correctly
    path = _find_data_file()
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    all_contacts = _parse_field(raw.get("wp_contacts"), [])

    # Find and replace this contact in the full list (match by name)
    contact_name_lower = (contact.get("name") or "").lower()
    for i, c in enumerate(all_contacts):
        if (c.get("name") or "").lower() == contact_name_lower:
            all_contacts[i] = contact
            break

    save_contacts(all_contacts)

    lines = [
        f"✅ **Logged: message sent to {contact.get('name')}**",
        f"",
        f"**Timestamp:** {now.strftime('%Y-%m-%d %H:%M UTC')}",
        f"**Status updated to:** Messaged",
        f"**Interaction #{len(contact['_interactions'])} recorded**",
    ]
    if message:
        preview = message[:120] + ("…" if len(message) > 120 else "")
        lines += ["", f"**Message preview:** {preview}"]
    if note:
        lines += [f"**Note:** {note}"]
    lines += [
        "",
        f"*warmpath_data.json updated. Next time you export a backup from WarmPath "
        f"and replace this file, these changes will be visible in the app too.*",
    ]
    return "\n".join(lines)


@mcp.tool()
def log_reply(name: str, response: str = "replied", note: str = "") -> str:
    """
    Record that a connection replied to your outreach. Updates their status
    and saves to warmpath_data.json.

    Args:
        name:     Full or partial name of the connection who replied.
        response: One of: "replied", "no_response", "not_interested" (default: "replied").
        note:     Summary of what they said or any follow-up notes (optional).
    """
    data    = load_data()
    contact = _find_contact(data["contacts"], name)

    if not contact:
        return f'No connection found matching "{name}". Check the spelling and try again.'

    # Map response to WarmPath contact status
    response_map = {
        "replied":        "Replied",
        "no_response":    "No response",
        "not_interested": "No response",
    }
    new_status = response_map.get(response.lower().strip(), "Replied")

    now     = datetime.now(timezone.utc)
    now_iso = now.isoformat()

    # Update the last interaction's response field if it exists
    interactions = contact.get("_interactions") or []
    if interactions:
        interactions[-1]["response"] = response
        if note:
            interactions[-1]["note"] = note
        contact["_interactions"] = interactions

    # Advance status (never go backwards)
    status_order   = ["Not contacted", "Messaged", "Replied", "Met", "Referred me", "No response"]
    current_status = contact.get("status") or "Not contacted"
    if new_status == "No response":
        contact["status"] = "No response"
    elif current_status not in status_order or status_order.index(current_status) < status_order.index(new_status):
        contact["status"] = new_status

    contact["lastContacted"] = now.strftime("%Y-%m-%d")

    # Write back
    path = _find_data_file()
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    all_contacts = _parse_field(raw.get("wp_contacts"), [])
    contact_name_lower = (contact.get("name") or "").lower()
    for i, c in enumerate(all_contacts):
        if (c.get("name") or "").lower() == contact_name_lower:
            all_contacts[i] = contact
            break
    save_contacts(all_contacts)

    emoji = {"replied": "💬", "no_response": "🔇", "not_interested": "🚫"}.get(response.lower(), "💬")

    lines = [
        f"{emoji} **Logged: {response} from {contact.get('name')}**",
        f"",
        f"**Timestamp:** {now.strftime('%Y-%m-%d %H:%M UTC')}",
        f"**Status updated to:** {new_status}",
    ]
    if note:
        lines += ["", f"**Note:** {note}"]
    if new_status == "Replied":
        lines += [
            "",
            f"💡 *They replied — good time to ask for a referral or schedule a call. "
            f"Want me to draft a follow-up message?*",
        ]
    lines += [
        "",
        f"*warmpath_data.json updated.*",
    ]
    return "\n".join(lines)


@mcp.tool()
def get_todays_plan(max_contacts: int = 5, exclude_companies: str = "") -> str:
    """
    Generate today's outreach plan — who to message today and why.
    Prioritises Grade A contacts not yet contacted, contacts at target companies,
    and warm contacts who haven't been reached in 90+ days.

    Ex-companies stored in your profile under 'exCompanies' (comma-separated)
    are automatically excluded. You can also pass additional companies to skip
    via exclude_companies.

    Args:
        max_contacts:      How many contacts to suggest today (default 5).
        exclude_companies: Extra comma-separated company names to skip today
                           (e.g. "Stripe, Atlassian"). These are merged with
                           any exCompanies stored in your profile.
    """
    data     = load_data()
    contacts = data["contacts"]
    targets  = data["targets"]
    profile  = data["profile"]
    today    = datetime.now(timezone.utc).date()

    # Build the ex-companies exclusion set from profile + override param
    def _norm(s: str) -> str:
        return s.strip().lower()

    profile_ex  = [_norm(x) for x in (profile.get("exCompanies") or "").split(",") if x.strip()]
    param_ex    = [_norm(x) for x in exclude_companies.split(",") if x.strip()]
    ex_companies = set(profile_ex + param_ex)  # e.g. {"freshworks", "thoughtworks", "athena health"}

    def _is_ex_company(company: str) -> bool:
        """Fuzzy match: 'Freshworks | The Company' matches 'freshworks'."""
        co_lower = (company or "").lower()
        return any(ex and ex in co_lower for ex in ex_companies)

    candidates = []
    skipped_ex: list[str] = []

    for c in contacts:
        grade  = c.get("grade", "C")
        status = c.get("status") or "Not contacted"
        score  = c.get("score") or 0
        company = c.get("company") or ""

        if grade not in ("A", "B"):
            continue
        if status in ("Replied", "Met", "Referred me"):
            continue  # already engaged

        # Skip ex-company contacts silently (track for summary)
        if _is_ex_company(company):
            skipped_ex.append(company)
            continue

        last_raw = c.get("lastContacted") or c.get("_lastSentDate") or ""
        days_since = None
        if last_raw:
            try:
                last_dt = datetime.fromisoformat(str(last_raw).replace("Z", "+00:00"))
                if last_dt.tzinfo is None:
                    last_dt = last_dt.replace(tzinfo=timezone.utc)
                days_since = (datetime.now(timezone.utc) - last_dt).days
            except Exception:
                pass

        is_target = any(t in company.lower() for t in targets)
        is_decay  = days_since is not None and days_since >= 90

        # Skip if recently messaged (within 14 days) unless it's a target company
        if days_since is not None and days_since < 14 and not is_target:
            continue

        priority = 0
        if grade == "A":              priority += 30
        if is_target:                 priority += 25
        if status == "Not contacted": priority += 20
        if is_decay:                  priority += 15
        priority += min(score // 10, 10)

        candidates.append({
            "contact":    c,
            "priority":   priority,
            "days_since": days_since,
            "is_target":  is_target,
            "is_decay":   is_decay,
        })

    candidates.sort(key=lambda x: -x["priority"])
    top = candidates[:max_contacts]

    if not top:
        return (
            "✅ No urgent outreach needed today!\n\n"
            "Everyone in your Grade A/B list has been recently contacted "
            "or is already engaged. Check back in a few days, "
            "or use `get_followup_list` to see who might need a follow-up."
        )

    lines = [
        f"## 📋 Today's outreach plan — {today.strftime('%A, %d %b %Y')}",
        f"**{len(top)} contact{'s' if len(top) != 1 else ''} to reach out to today**\n",
    ]

    for rank, item in enumerate(top, 1):
        c          = item["contact"]
        days_info  = f"{item['days_since']}d since last contact" if item["days_since"] else "never contacted"
        target_tag = " 🎯" if item["is_target"] else ""
        decay_tag  = " 🔴 overdue" if item["is_decay"] else ""
        reasons    = []
        if c.get("grade") == "A":   reasons.append("Grade A")
        if item["is_target"]:       reasons.append("target company")
        if not c.get("lastContacted") and not c.get("_lastSentDate"):
            reasons.append("never messaged")
        if item["is_decay"]:        reasons.append("90+ days silent")

        lines += [
            f"### {rank}. {c.get('name')}{target_tag}{decay_tag}",
            f"**{c.get('position') or c.get('role') or 'Role unknown'}** @ {c.get('company') or '—'}",
            f"Score {c.get('score', 0)} · {_grade_label(c.get('grade'))} · {days_info}",
            f"Why today: {', '.join(reasons)}",
            "",
        ]

    lines += [
        "---",
        "**To action any of these:**",
        "- `draft_outreach_message` — get a personalised draft",
        "- `open_linkedin_profile` — open their LinkedIn in your browser",
        "- `copy_message_to_clipboard` — put the draft on your clipboard ready to paste",
        "- `log_message_sent` — record it once you've sent",
    ]

    if ex_companies:
        skipped_unique = sorted({s for s in skipped_ex if s})
        lines += [
            "",
            f"*🚫 Ex-company contacts excluded: {', '.join(sorted(ex_companies))}*",
            f"*({len(skipped_ex)} contact(s) skipped. To include them, remove from exCompanies in your profile.)*",
        ]
    return "\n".join(lines)


@mcp.tool()
def get_followup_list(days_threshold: int = 7) -> str:
    """
    List contacts you've already messaged but who haven't replied yet,
    and are overdue for a follow-up. Sorted by how long they've been silent.

    Args:
        days_threshold: How many days since last message before a follow-up
                        is suggested (default 7).
    """
    data     = load_data()
    contacts = data["contacts"]
    now      = datetime.now(timezone.utc)

    overdue = []
    for c in contacts:
        status = c.get("status") or "Not contacted"
        if status not in ("Messaged", "Message sent"):
            continue

        last_raw = c.get("_lastSentDate") or c.get("lastContacted") or ""
        if not last_raw:
            continue
        try:
            last_dt = datetime.fromisoformat(str(last_raw).replace("Z", "+00:00"))
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)
            days_since = (now - last_dt).days
        except Exception:
            continue

        if days_since < days_threshold:
            continue

        overdue.append({"contact": c, "days_since": days_since})

    overdue.sort(key=lambda x: -x["days_since"])

    if not overdue:
        return (
            f"✅ No follow-ups needed — no one has been silent for "
            f"more than {days_threshold} days.\n\n"
            f"Check back later or lower the threshold: "
            f"`get_followup_list days_threshold=3`"
        )

    lines = [
        f"## ↩️  Follow-up list — {len(overdue)} contact{'s' if len(overdue) != 1 else ''} awaiting reply\n",
        f"*These people were messaged but haven't replied in {days_threshold}+ days.*\n",
    ]

    for item in overdue:
        c          = item["contact"]
        days       = item["days_since"]
        urgency    = "🔴" if days >= 21 else "🟡" if days >= 14 else "⚪"
        last_msg   = (c.get("_lastSentMsg") or "")[:100]
        msg_preview = f'\n  *Last message: "{last_msg}{"…" if len(c.get("_lastSentMsg",""))>100 else ""}"*' if last_msg else ""

        lines.append(
            f"{urgency} **{c.get('name')}** — {days} days silence\n"
            f"  {c.get('position') or '—'} @ {c.get('company') or '—'} · "
            f"{_grade_label(c.get('grade'))}{msg_preview}\n"
        )

    lines += [
        "---",
        "*Tip: a short follow-up ('just bumping this in case it got buried') "
        "often gets a reply. Want me to draft follow-up messages for any of these?*",
    ]
    return "\n".join(lines)


@mcp.tool()
def get_weekly_summary() -> str:
    """
    Show a summary of your outreach activity this week —
    messages sent, replies received, reply rate, and who to prioritise next.
    """
    data     = load_data()
    contacts = data["contacts"]
    now      = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)

    sent_this_week    = []
    replied_this_week = []
    total_interactions = 0

    for c in contacts:
        for ix in (c.get("_interactions") or []):
            total_interactions += 1
            try:
                ix_dt = datetime.fromisoformat(str(ix.get("date","")).replace("Z","+00:00"))
                if ix_dt.tzinfo is None:
                    ix_dt = ix_dt.replace(tzinfo=timezone.utc)
                if ix_dt >= week_ago:
                    sent_this_week.append({"contact": c, "interaction": ix})
                if ix.get("response") == "replied":
                    replied_this_week.append(c.get("name"))
            except Exception:
                pass

    grade_counts = {g: sum(1 for c in contacts if c.get("grade")==g) for g in "ABC"}
    messaged     = sum(1 for c in contacts if c.get("status") in ("Messaged","Message sent","Replied","Met","Referred me"))
    replied      = sum(1 for c in contacts if c.get("status") == "Replied")
    reply_rate   = round(replied / messaged * 100) if messaged else 0

    # Top untouched Grade A at target companies
    untouched_targets = [
        c for c in contacts
        if c.get("grade") == "A"
        and not c.get("lastContacted") and not c.get("_lastSentDate")
        and any(t in (c.get("company") or "").lower() for t in data["targets"])
    ][:3]

    lines = [
        f"## 📊 Weekly summary — week ending {now.strftime('%d %b %Y')}",
        "",
        f"**Network:** {len(contacts):,} contacts · "
        f"{grade_counts.get('A',0)}A · {grade_counts.get('B',0)}B · {grade_counts.get('C',0)}C",
        "",
        "### This week",
        f"- 📤 Messages sent: **{len(sent_this_week)}**",
        f"- 💬 Replies received: **{len(set(replied_this_week))}**",
        f"- 📈 All-time reply rate: **{reply_rate}%** ({replied} replied / {messaged} messaged)",
        f"- 🗂  Total interactions logged: **{total_interactions}**",
    ]

    if sent_this_week:
        lines += ["", "### Sent this week"]
        for item in sent_this_week[-5:]:
            c  = item["contact"]
            ix = item["interaction"]
            try:
                d = datetime.fromisoformat(str(ix.get("date","")).replace("Z","+00:00")).strftime("%a %d %b")
            except Exception:
                d = ""
            lines.append(f"  - {c.get('name')} @ {c.get('company') or '—'} ({d})")

    if untouched_targets:
        lines += ["", "### 🎯 Untouched Grade A at your target companies"]
        for c in untouched_targets:
            lines.append(f"  - **{c.get('name')}** — {c.get('position') or '—'} @ {c.get('company')}")
        lines.append("\n*These are your highest-value contacts. Want today's outreach plan?*")

    return "\n".join(lines)


@mcp.tool()
def open_linkedin_profile(name: str) -> str:
    """
    Open a contact's LinkedIn profile in your default browser.

    Args:
        name: Full or partial name of the contact.
    """
    data    = load_data()
    contact = _find_contact(data["contacts"], name)

    if not contact:
        return f'No contact found matching "{name}".'

    url = contact.get("url") or ""
    if not url:
        # Fall back to LinkedIn search
        search = contact.get("name", "").replace(" ", "%20")
        url = f"https://www.linkedin.com/search/results/people/?keywords={search}"
        fallback_note = "\n\n⚠️ No saved LinkedIn URL — opened a search instead."
    else:
        fallback_note = ""

    webbrowser.open(url)

    return (
        f"✅ **Opened LinkedIn profile for {contact.get('name')}**\n\n"
        f"**URL:** {url}\n"
        f"**Role:** {contact.get('position') or contact.get('role') or '—'} @ {contact.get('company') or '—'}\n"
        f"**Status:** {contact.get('status') or 'Not contacted'}"
        f"{fallback_note}\n\n"
        f"*Click the Message button on their profile, then use "
        f"`copy_message_to_clipboard` to get your draft ready to paste.*"
    )


@mcp.tool()
def copy_message_to_clipboard(name: str, context: str = "") -> str:
    """
    Draft a personalised outreach message and copy it to your clipboard,
    ready to paste into LinkedIn.

    Args:
        name:    Full or partial name of the contact to message.
        context: Optional job title, role URL, or extra context for the message.
    """
    data    = load_data()
    contact = _find_contact(data["contacts"], name)

    if not contact:
        return f'No contact found matching "{name}".'

    message = _draft_message(contact, data["profile"], context)

    # Copy to clipboard — method varies by OS
    system = platform.system()
    copied = False
    try:
        if system == "Darwin":
            subprocess.run("pbcopy", input=message.encode("utf-8"), check=True)
            copied = True
        elif system == "Windows":
            subprocess.run("clip", input=message.encode("utf-8"), check=True, shell=True)
            copied = True
        elif system == "Linux":
            # Try xclip then xsel
            for cmd in [["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"]]:
                try:
                    subprocess.run(cmd, input=message.encode("utf-8"), check=True)
                    copied = True
                    break
                except FileNotFoundError:
                    continue
    except Exception:
        copied = False

    clip_status = (
        "✅ **Message copied to clipboard.**"
        if copied else
        "⚠️ Clipboard copy failed — copy the message below manually."
    )

    typing_steps = _message_typing_steps(message)

    lines = [
        f"**To:** {contact.get('name')} @ {contact.get('company') or '—'}",
        f"**Warmth:** {_grade_label(contact.get('grade'))} · {contact.get('warmthTier') or '—'}",
        clip_status,
        "",
        "---",
        "",
        message,
        "",
        "---",
        "",
        "**⚠️ Browser automation note — avoid splitting the message:**",
        "LinkedIn sends on bare Enter. Use ONE of these approaches:",
        "",
        "**Paste (recommended):** Cmd+V into the compose box — preserves all line breaks.",
        "",
        "**Type with Shift+Enter (if paste unavailable):**",
        typing_steps,
        "",
        f"*After sending: tell me `log message sent to {contact.get('name')}` and I'll record it.*",
    ]
    return "\n".join(lines)


# ─── Profile settings tools ──────────────────────────────────────────────────

@mcp.tool()
def set_ex_companies(companies: str) -> str:
    """
    Save a list of your ex-employers so they are automatically excluded
    from get_todays_plan and other outreach suggestions.

    You can update this list any time — just call this tool again with the
    full updated list.

    Args:
        companies: Comma-separated company names, e.g.
                   "Freshworks, Thoughtworks, Athena Health, TrustRace"
    """
    names = [c.strip() for c in companies.split(",") if c.strip()]
    if not names:
        return "No company names provided. Pass a comma-separated list, e.g. \"Freshworks, Thoughtworks\"."

    save_profile_field("exCompanies", ", ".join(names))

    return (
        f"✅ **Ex-companies saved:** {', '.join(names)}\n\n"
        f"These will be automatically excluded from `get_todays_plan` and "
        f"outreach suggestions going forward.\n\n"
        f"To update the list, call `set_ex_companies` again with the full new list.\n"
        f"To clear it, call `set_ex_companies` with an empty string."
    )


# ─── Job search tools ────────────────────────────────────────────────────────

@mcp.tool()
def find_open_role(company: str, role_keyword: str = "") -> str:
    """
    Find open roles at a company that match your target role.
    Opens the company's careers page in your browser and returns a
    role-mention line you can weave into your outreach message.

    Args:
        company:      Company name (e.g. "Zoho", "Capital One").
        role_keyword: Optional keyword to narrow the search (e.g. "Staff PM").
                      Defaults to your profile's target role.
    """
    data    = load_data()
    profile = data["profile"]
    target  = role_keyword.strip() or (profile.get("target") or "Product Manager").split(",")[0].strip()

    _, careers_url = _careers_url(company)
    co_enc = company.replace(" ", "%20")
    kw_enc = target.replace(" ", "%20")

    linkedin_jobs_url = (
        f"https://www.linkedin.com/jobs/search/"
        f"?keywords={kw_enc}&f_C=&location=&f_TPR=r2592000"  # last 30 days
        f"&f_WT=2"  # remote-friendly; user can remove
    )
    # More targeted: search LinkedIn Jobs for this company + role
    linkedin_co_url = (
        f"https://www.linkedin.com/jobs/search/"
        f"?keywords={kw_enc}+{co_enc}"
    )

    opened_url = careers_url or linkedin_co_url
    browser_note = ""
    try:
        webbrowser.open(opened_url)
        browser_note = f"🌐 Opened: {opened_url}"
    except Exception:
        browser_note = f"Could not open browser. Visit: {opened_url}"

    lines = [
        f'## Open roles at {company} matching "{target}"',
        "",
        browser_note,
        "",
        "**Links to check:**",
    ]
    if careers_url:
        lines.append(f"- 🏢 **Direct careers page:** {careers_url}")
    lines += [
        f"- 🔗 **LinkedIn Jobs ({company} + {target}):** {linkedin_co_url}",
        "",
        "---",
        "",
        "**Once you find a specific role, use this line in your message:**",
        f'> "I came across the {target} opening at {company} — it lines up closely with what I\'ve been building."',
        "",
        "Or pass the role title + URL to `draft_outreach_message` as the `context` argument:",
        f'> `draft_outreach_message("{company} contact name", "Staff PM role — <job URL>")`',
        "",
        "The message will automatically reference the role and keep the tone appropriate to their seniority.",
    ]
    return "\n".join(lines)


@mcp.tool()
def prepare_resume_response(name: str, role_title: str = "", role_url: str = "") -> str:
    """
    Draft a follow-up message for a contact who has asked for your resume.
    Call this when someone replies asking for your CV / resume.

    Args:
        name:       Full or partial name of the contact who asked.
        role_title: The specific role they mentioned (optional but recommended).
        role_url:   URL to the job posting (optional).
    """
    data    = load_data()
    contact = _find_contact(data["contacts"], name)

    if not contact:
        return f'No contact found matching "{name}".'

    profile   = data["profile"]
    first     = (contact.get("name") or "there").split()[0]
    company   = contact.get("company") or "your company"
    my_name   = profile.get("name") or ""
    my_level  = profile.get("currentLevel") or "senior professional"
    target    = (profile.get("target") or "PM").split(",")[0].strip()
    seniority = _get_seniority(contact.get("position") or contact.get("role") or "")

    role_line = ""
    if role_title and role_url:
        role_line = f" for the {role_title} role ({role_url})"
    elif role_title:
        role_line = f" for the {role_title} role"
    elif role_url:
        role_line = f" for the role ({role_url})"

    # Concise for senior contacts, warmer for peers
    if seniority >= 4:
        draft = (
            f"Hi {first},\n\n"
            f"Thanks for getting back to me. Sharing my resume{role_line} — "
            f"happy to answer any questions.\n\n"
            f"[Attach resume here]\n\n"
            f"{my_name}"
        )
    else:
        draft = (
            f"Hi {first},\n\n"
            f"Really appreciate you getting back to me!\n\n"
            f"Please find my resume attached{role_line}. "
            f"I've been focusing on {target} roles and {company} is genuinely high on my list.\n\n"
            f"Happy to jump on a call if that's easier — whatever works for you.\n\n"
            f"[Attach resume here]\n\n"
            f"{my_name}"
        )

    # Log this as a reply received
    contacts = data["contacts"]
    idx = next(
        (i for i, c in enumerate(contacts)
         if c.get("name", "").lower() == (contact.get("name") or "").lower()),
        None,
    )
    if idx is not None:
        today = datetime.now().strftime("%Y-%m-%d")
        interaction = {
            "id":       _make_interaction_id(),
            "date":     today,
            "type":     "reply-received",
            "source":   "linkedin-inbox",
            "response": "asked for resume",
            "note":     f"Asked for resume{role_line}. Response drafted.",
        }
        if "interactions" not in contacts[idx]:
            contacts[idx]["interactions"] = []
        contacts[idx]["interactions"].append(interaction)
        contacts[idx]["status"] = "Replied"
        save_contacts(contacts)

    typing_steps = _message_typing_steps(draft)

    return "\n".join([
        f"## Resume response for {contact.get('name')} @ {company}",
        f"*Seniority: {_seniority_label(seniority)} · Status updated to: Replied*",
        "",
        "---",
        "",
        draft,
        "",
        "---",
        "",
        "**⚠️ Remember:** Attach your resume PDF before sending.",
        "",
        "**To send without splitting (LinkedIn compose box):**",
        "Paste with Cmd+V, or type using Shift+Enter between lines:",
        "",
        typing_steps,
    ])


@mcp.tool()
def morning_briefing() -> str:
    """
    Start-of-day briefing. Run this once each morning.

    Returns:
      1. Today's outreach plan (who to message)
      2. Follow-up list (who hasn't replied and needs a nudge)
      3. LinkedIn inbox check instructions — Claude will open your LinkedIn
         inbox, read unread messages, and flag anyone who asked for a resume
         so a response can be drafted immediately.

    The inbox check only runs once per day (tracked by date).
    """
    data     = load_data()
    contacts = data["contacts"]
    profile  = data["profile"]
    targets  = data["targets"]
    today    = datetime.now(timezone.utc).date()
    today_str = today.strftime("%Y-%m-%d")

    # Check if inbox was already read today
    last_inbox_check = profile.get("_lastInboxCheck", "")
    inbox_already_done = last_inbox_check == today_str

    # ── Today's plan (top 3 for briefing — use get_todays_plan for full list) ──
    def _norm(s: str) -> str:
        return s.strip().lower()
    ex_set = set(_norm(x) for x in (profile.get("exCompanies") or "").split(",") if x.strip())

    def _is_ex(company: str) -> bool:
        co = (company or "").lower()
        return any(ex and ex in co for ex in ex_set)

    plan_contacts = []
    for c in contacts:
        if c.get("grade") not in ("A", "B"):
            continue
        if (c.get("status") or "") in ("Replied", "Met", "Referred me"):
            continue
        if _is_ex(c.get("company") or ""):
            continue
        last_raw = c.get("lastContacted") or c.get("_lastSentDate") or ""
        days_since = None
        if last_raw:
            try:
                last_dt = datetime.fromisoformat(str(last_raw).replace("Z", "+00:00"))
                if last_dt.tzinfo is None:
                    last_dt = last_dt.replace(tzinfo=timezone.utc)
                days_since = (datetime.now(timezone.utc) - last_dt).days
            except Exception:
                pass
        is_target = any(t in (c.get("company") or "").lower() for t in targets)
        if days_since is not None and days_since < 14 and not is_target:
            continue
        priority = 0
        if c.get("grade") == "A":               priority += 30
        if is_target:                            priority += 25
        if not (c.get("lastContacted") or c.get("_lastSentDate")): priority += 20
        plan_contacts.append((priority, c))

    plan_contacts.sort(key=lambda x: -x[0])
    top3 = plan_contacts[:3]

    # ── Follow-ups overdue ─────────────────────────────────────────────────────
    followups = []
    for c in contacts:
        status = (c.get("status") or "").lower()
        if status not in ("messaged", "message sent"):
            continue
        last_raw = c.get("_lastSentDate") or c.get("lastContacted") or ""
        if not last_raw:
            continue
        try:
            last_dt = datetime.fromisoformat(str(last_raw).replace("Z", "+00:00"))
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)
            days = (datetime.now(timezone.utc) - last_dt).days
            if days >= 5:
                followups.append((days, c))
        except Exception:
            pass
    followups.sort(key=lambda x: -x[0])

    # ── Contacts messaged in last 30 days (for inbox matching) ────────────────
    messaged_recently = []
    for c in contacts:
        last_raw = c.get("_lastSentDate") or c.get("lastContacted") or ""
        if not last_raw:
            continue
        try:
            last_dt = datetime.fromisoformat(str(last_raw).replace("Z", "+00:00"))
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)
            days = (datetime.now(timezone.utc) - last_dt).days
            if days <= 30:
                messaged_recently.append(c.get("name", ""))
        except Exception:
            pass

    # Mark inbox check as done for today
    if not inbox_already_done:
        save_profile_field("_lastInboxCheck", today_str)

    # ── Build output ──────────────────────────────────────────────────────────
    lines = [
        f"# ☀️ Morning briefing — {today.strftime('%A, %d %b %Y')}",
        "",
    ]

    # Today's plan
    lines += ["## 📋 Top contacts to message today"]
    if top3:
        for i, (_, c) in enumerate(top3, 1):
            company = c.get("company") or "—"
            role    = c.get("position") or c.get("role") or "—"
            lines.append(f"{i}. **{c.get('name')}** — {role} @ {company} · {_grade_label(c.get('grade'))}")
    else:
        lines.append("✅ No urgent outreach today — great work keeping up!")
    lines += ["", f"*Full list: ask `get_todays_plan`*", ""]

    # Follow-ups
    lines += ["## 🔔 Overdue follow-ups"]
    if followups:
        for days, c in followups[:3]:
            emoji = "🔴" if days >= 14 else "🟡"
            lines.append(f"{emoji} **{c.get('name')}** @ {c.get('company') or '—'} — {days} days silent")
    else:
        lines.append("✅ No overdue follow-ups.")
    lines += [""]

    # LinkedIn inbox
    lines += ["## 📬 LinkedIn inbox check"]
    if inbox_already_done:
        lines += [
            "✅ Already checked today.",
            "",
            "*To force a re-check, ask: \"check my LinkedIn inbox\".*",
        ]
    else:
        resume_keywords = [
            "resume", "cv", "curriculum vitae", "portfolio",
            "share your profile", "send your details", "apply",
        ]
        lines += [
            "**Not checked yet today.** Here's what to do:",
            "",
            "1. I'll open your LinkedIn inbox now",
            "2. Read the unread messages from these contacts (messaged in last 30 days):",
            "",
        ]
        for n in (messaged_recently[:10] if messaged_recently else ["(none yet)"]):
            lines.append(f"   • {n}")
        lines += [
            "",
            "3. Look for any message containing these keywords:",
            f"   {', '.join(resume_keywords)}",
            "",
            "4. For each resume request found: call `prepare_resume_response(name)` and I'll draft the reply",
            "",
            "**Opening LinkedIn inbox now…**",
            "_(Claude will navigate to https://www.linkedin.com/messaging/ and read unread messages)_",
        ]

        # Open LinkedIn inbox in browser
        try:
            webbrowser.open("https://www.linkedin.com/messaging/")
        except Exception:
            pass

    lines += [
        "",
        "---",
        f"*{len(contacts)} contacts in network · {len(messaged_recently)} messaged in last 30 days*",
    ]

    return "\n".join(lines)


# ─── Layer 2: send_outreach ───────────────────────────────────────────────────

@mcp.tool()
def send_outreach(name: str, context: str = "", confirm: bool = False) -> str:
    """
    All-in-one outreach tool: draft → warn → open LinkedIn → copy to clipboard.

    Call this when the user says "send a message to X" or "reach out to X".

    Workflow:
      1. First call (confirm=False):  draft the message, open LinkedIn, copy to
         clipboard, and return a preview asking the user to confirm.
      2. Second call (confirm=True):  log the message as sent in WarmPath and
         return a confirmation.

    Between the two calls the user pastes the message on LinkedIn and sends it.

    Args:
        name:    Full or partial name of the contact.
        context: Optional job title, role URL, or extra context for the message.
        confirm: Set True after the user has sent the message to log it.
    """
    data    = load_data()
    contact = _find_contact(data["contacts"], name)

    if not contact:
        return f'No contact found matching "{name}".'

    cname   = contact.get("name", name)
    company = contact.get("company") or "—"
    grade   = _grade_label(contact.get("grade"))
    tier    = contact.get("warmthTier") or "—"

    # ── confirm=True: log it and finish ───────────────────────────────────────
    if confirm:
        contacts = data["contacts"]
        idx = next(
            (i for i, c in enumerate(contacts)
             if c.get("name", "").lower() == cname.lower()),
            None,
        )
        if idx is None:
            return f'Could not find "{cname}" to log.'

        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        today   = datetime.now().strftime("%Y-%m-%d")

        interaction = {
            "id":       _make_interaction_id(),
            "date":     today,
            "type":     "message",
            "source":   "claude-desktop",
            "response": "",
            "note":     f"Sent via send_outreach (Layer 2). Context: {context}" if context else "Sent via send_outreach (Layer 2).",
        }

        if "interactions" not in contacts[idx]:
            contacts[idx]["interactions"] = []
        contacts[idx]["interactions"].append(interaction)

        contacts[idx]["lastContacted"]  = today
        contacts[idx]["_lastSentDate"]  = now_iso
        contacts[idx]["status"]         = "Messaged"

        save_contacts(contacts)

        return (
            f"✅ **Logged!** Message to {cname} recorded in WarmPath.\n\n"
            f"**Next step:** If they reply, say *\"log reply from {cname}\"* "
            f"and I'll update their status and warmth score."
        )

    # ── confirm=False: draft, open, copy, preview ─────────────────────────────
    message = _draft_message(contact, data["profile"], context)

    # Warn if already messaged recently
    last_sent = contact.get("_lastSentDate") or contact.get("lastContacted") or ""
    already_warned = ""
    if last_sent:
        try:
            sent_dt = datetime.fromisoformat(last_sent.replace("Z", "+00:00"))
            days_ago = (datetime.now(timezone.utc) - sent_dt).days
            if days_ago < 14:
                already_warned = (
                    f"\n⚠️ **Note:** You messaged {cname} {days_ago} day(s) ago "
                    f"— double-check before sending again.\n"
                )
        except Exception:
            pass

    # Open LinkedIn profile in browser
    url      = contact.get("linkedinUrl") or contact.get("profileUrl") or ""
    opened   = False
    open_note = ""
    if url:
        try:
            webbrowser.open(url)
            opened = True
        except Exception:
            pass
    if not opened:
        search_url = (
            f"https://www.linkedin.com/search/results/people/"
            f"?keywords={contact.get('name', name).replace(' ', '%20')}"
        )
        try:
            webbrowser.open(search_url)
            opened = True
            open_note = "\n*(Opened LinkedIn search — no direct profile URL stored.)*\n"
        except Exception:
            open_note = "\n*(Could not open browser automatically.)*\n"

    # Copy to clipboard
    copied = False
    sys_name = platform.system()
    try:
        if sys_name == "Darwin":
            proc = subprocess.run(["pbcopy"], input=message, text=True, timeout=5)
            copied = proc.returncode == 0
        elif sys_name == "Windows":
            proc = subprocess.run(["clip"], input=message, text=True, timeout=5, shell=True)
            copied = proc.returncode == 0
        else:
            for cmd in [["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"]]:
                try:
                    proc = subprocess.run(cmd, input=message, text=True, timeout=5)
                    if proc.returncode == 0:
                        copied = True
                        break
                except FileNotFoundError:
                    continue
    except Exception:
        pass

    browser_line = (
        f"🌐 **LinkedIn opened** in your browser.{open_note}"
        if opened else
        f"⚠️ Could not open browser — visit LinkedIn manually."
    )
    clip_line = (
        "📋 **Message copied to clipboard.**"
        if copied else
        "⚠️ Clipboard copy failed — copy the message below manually."
    )

    typing_steps = _message_typing_steps(message)

    lines = [
        f"## Outreach to {cname}",
        "",
        f"**Company:** {company}  |  **Warmth:** {grade} · {tier}",
        already_warned,
        browser_line,
        clip_line,
        "",
        "---",
        "",
        message,
        "",
        "---",
        "",
        "**To insert this message in LinkedIn WITHOUT splitting it:**",
        "",
        "**Option A — Paste (recommended):**",
        f"  1. Click the **Message** button on {cname}'s profile",
        "  2. Click the compose box",
        "  3. Press **Cmd+V** (Mac) / **Ctrl+V** (Windows) to paste",
        "  4. Review, then click **Send**",
        "",
        "**Option B — Type with Shift+Enter (for browser automation):**",
        "  ⚠️ Do NOT use bare Enter — LinkedIn will send immediately on each line break.",
        "",
        typing_steps,
        "",
        f"When sent, say *\"sent\"* and I'll log it in WarmPath.",
    ]
    return "\n".join(lines)


# ─── Upload endpoint (for cloud deployments) ──────────────────────────────────

# ─── Section 6: Company Intelligence MCP tools ───────────────────────────────

LS_CO_INTELLIGENCE = "wp_co_intelligence"
LS_CO_INTEL_WEIGHTS = "wp_co_intel_weights"

CI_DEFAULT_WEIGHTS = {
    "ai_investment": 30,
    "hiring_momentum": 25,
    "ecosystem_relevance": 20,
    "india_presence": 15,
    "warmth_score": 10,
}


def _load_company_intelligence(data: dict) -> list[dict]:
    """Load company intelligence from wp_co_intelligence key in warmpath_data."""
    raw = data.get("wp_co_intelligence")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            raw = None
    # Also check the full backup format where each LS key is a string
    if raw is None:
        raw = data.get(LS_CO_INTELLIGENCE)
    if isinstance(raw, list):
        return raw
    return []


def _get_ci_weights(data: dict) -> dict:
    raw = data.get(LS_CO_INTEL_WEIGHTS)
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            raw = {}
    if isinstance(raw, dict):
        w = {**CI_DEFAULT_WEIGHTS}
        w.update({k: v for k, v in raw.items() if k in CI_DEFAULT_WEIGHTS})
        return w
    return {**CI_DEFAULT_WEIGHTS}


def _compute_composite(co: dict, weights: dict, warmth: float = 0.0) -> float:
    w = weights
    score = (
        (co.get("ai_investment_signal", 0)) * w["ai_investment"]
        + (co.get("hiring_momentum", 0)) * w["hiring_momentum"]
        + (co.get("ecosystem_relevance", 0)) * w["ecosystem_relevance"]
        + (co.get("india_presence", 0)) * w["india_presence"]
        + warmth * w["warmth_score"]
    ) / 100
    return round(score, 1)


def _company_warmth_from_contacts(contacts: list, company_name: str) -> float:
    key = company_name.lower()
    matches = [c for c in contacts if key in (c.get("company") or "").lower() or (c.get("company") or "").lower() in key]
    if not matches:
        return 0.0
    avg = sum(c.get("score", 0) for c in matches) / len(matches)
    return round(min(10.0, avg / 10), 1)


@mcp.tool()
def list_target_companies(limit: int = 20) -> str:
    """
    List all companies in the Company Intelligence tracker, sorted by composite score (highest first).
    Shows AI investment, hiring momentum, ecosystem relevance, India presence, warmth, and referral status.

    Args:
        limit: Max companies to return (default 20).
    """
    data = load_data()
    cos = _load_company_intelligence(data)
    if not cos:
        return "No companies tracked yet. Add companies in WarmPath → Companies tab."

    weights = _get_ci_weights(data)
    contacts = data["contacts"]

    rows = []
    for co in cos:
        warmth = _company_warmth_from_contacts(contacts, co.get("name", ""))
        composite = _compute_composite(co, weights, warmth)
        rows.append((composite, co, warmth))

    rows.sort(key=lambda x: -x[0])

    lines = ["# 🏢 Company Intelligence — ranked by composite score\n"]
    for rank, (composite, co, warmth) in enumerate(rows[:limit], 1):
        score_emoji = "🟢" if composite >= 8 else "🟡" if composite >= 6 else "⚪"
        lines.append(
            f"{rank}. {score_emoji} **{co.get('name')}** — composite {composite:.1f}  "
            f"| Referral: {co.get('referral_status','None')}  "
            f"| AI {co.get('ai_investment_signal','?')} · Hiring {co.get('hiring_momentum','?')} "
            f"· Ecosystem {co.get('ecosystem_relevance','?')} · India {co.get('india_presence','?')} "
            f"· Warmth {warmth}"
        )
        if co.get("notes"):
            lines.append(f"   _{co['notes']}_")

    lines.append(f"\n*{len(cos)} companies tracked · weights: AI {weights['ai_investment']}% · Hiring {weights['hiring_momentum']}% · Ecosystem {weights['ecosystem_relevance']}% · India {weights['india_presence']}% · Warmth {weights['warmth_score']}%*")
    return "\n".join(lines)


@mcp.tool()
def get_company_intelligence(company: str) -> str:
    """
    Get the full intelligence profile for one company from the Companies tab.

    Args:
        company: Company name (partial match supported).
    """
    data = load_data()
    cos = _load_company_intelligence(data)
    if not cos:
        return "No company intelligence data found. Add companies in WarmPath → Companies tab."

    query = company.lower()
    co = next((c for c in cos if query in c.get("name","").lower() or c.get("name","").lower() in query), None)
    if not co:
        names = ", ".join(c.get("name","") for c in cos)
        return f'No company matching "{company}" found. Available: {names}'

    weights = _get_ci_weights(data)
    contacts = data["contacts"]
    warmth = _company_warmth_from_contacts(contacts, co.get("name",""))
    composite = _compute_composite(co, weights, warmth)
    co_contacts = [c for c in contacts if (co.get("name","")).lower() in (c.get("company") or "").lower()]

    lines = [
        f"## 🏢 {co.get('name')} — composite score {composite:.1f}",
        "",
        f"| Signal | Score |",
        f"|---|---|",
        f"| AI investment | {co.get('ai_investment_signal','?')}/10 |",
        f"| Hiring momentum | {co.get('hiring_momentum','?')}/10 |",
        f"| Ecosystem relevance | {co.get('ecosystem_relevance','?')}/10 |",
        f"| India presence | {co.get('india_presence','?')}/10 |",
        f"| My warmth (auto) | {warmth}/10 |",
        "",
        f"**Referral status:** {co.get('referral_status','None')}",
        f"**Last AI refresh:** {co.get('last_refreshed','Never')}",
        f"**Notes:** {co.get('notes','') or '—'}",
        "",
        f"**Contacts in network ({len(co_contacts)}):**",
    ]
    for c in sorted(co_contacts, key=lambda x: -(x.get("score",0)))[:5]:
        lines.append(f"  - {c.get('name')} · {c.get('role') or c.get('position','')} · Grade {c.get('grade','?')} · {c.get('status','Not contacted')}")

    return "\n".join(lines)


@mcp.tool()
def get_todays_company_priority() -> str:
    """
    Return the top 3 companies to focus on today from the Company Intelligence tracker.
    Excludes companies where referral_status is 'Applied'.
    Formatted for use in morning briefing.
    """
    data = load_data()
    cos = _load_company_intelligence(data)
    if not cos:
        return "No company intelligence data. Add companies in WarmPath → Companies tab."

    weights = _get_ci_weights(data)
    contacts = data["contacts"]

    eligible = [co for co in cos if co.get("referral_status","None") != "Applied"]
    if not eligible:
        return "All tracked companies are already in 'Applied' status — great progress!"

    rows = []
    for co in eligible:
        warmth = _company_warmth_from_contacts(contacts, co.get("name",""))
        composite = _compute_composite(co, weights, warmth)
        rows.append((composite, co, warmth))

    rows.sort(key=lambda x: -x[0])
    top3 = rows[:3]

    lines = ["## 🏢 Today's company priorities\n"]
    for i, (composite, co, warmth) in enumerate(top3, 1):
        score_emoji = "🟢" if composite >= 8 else "🟡" if composite >= 6 else "⚪"
        co_contacts = [c for c in contacts if (co.get("name","")).lower() in (c.get("company") or "").lower()]
        warm_contacts = [c for c in co_contacts if c.get("grade") in ("A","B")]
        lines.append(f"{i}. {score_emoji} **{co.get('name')}** — {composite:.1f} pts · {co.get('referral_status','None')}")
        lines.append(f"   {len(warm_contacts)} warm contact{'s' if len(warm_contacts)!=1 else ''} · AI {co.get('ai_investment_signal','?')} · Hiring {co.get('hiring_momentum','?')}")
        if warm_contacts:
            best = sorted(warm_contacts, key=lambda c: -(c.get("score",0)))[0]
            lines.append(f"   → Best contact: **{best.get('name')}** · {best.get('role') or best.get('position','')} · {best.get('status','Not contacted')}")
        lines.append("")

    return "\n".join(lines)


@mcp.tool()
def update_company_score(company: str, field: str, value: int) -> str:
    """
    Update a specific score field for a company and recalculate its composite score.

    Args:
        company: Company name (partial match supported).
        field:   One of: ai_investment_signal, hiring_momentum, ecosystem_relevance, india_presence (all 1–10).
        value:   New score (1–10).
    """
    valid_fields = {"ai_investment_signal", "hiring_momentum", "ecosystem_relevance", "india_presence"}
    if field not in valid_fields:
        return f"Invalid field '{field}'. Must be one of: {', '.join(valid_fields)}"
    if not (1 <= value <= 10):
        return f"Value must be between 1 and 10 (got {value})."

    data = load_data()
    cos = _load_company_intelligence(data)
    query = company.lower()
    co = next((c for c in cos if query in c.get("name","").lower() or c.get("name","").lower() in query), None)
    if not co:
        return f'No company matching "{company}" found.'

    old_val = co.get(field, "?")
    co[field] = value

    weights = _get_ci_weights(data)
    contacts = data["contacts"]
    warmth = _company_warmth_from_contacts(contacts, co.get("name",""))
    co["my_warmth_score"] = warmth
    new_composite = _compute_composite(co, weights, warmth)
    co["composite_score"] = new_composite

    # Save back to warmpath_data.json
    data_file = Path(load_data.__code__.co_consts[0] if False else _find_data_file())  # type: ignore
    try:
        data_file = _find_data_file()
        raw = json.loads(data_file.read_text())
        raw[LS_CO_INTELLIGENCE] = json.dumps(cos)
        data_file.write_text(json.dumps(raw, indent=2))
    except Exception as e:
        return f"Updated in memory but could not save to file: {e}"

    return (
        f"✅ **{co.get('name')}** — `{field}` updated {old_val} → {value}\n"
        f"New composite score: **{new_composite:.1f}**\n"
        f"_(Warmth auto-computed from {len([c for c in contacts if (co.get('name','').lower()) in (c.get('company') or '').lower()])} contacts at this company)_"
    )


def _make_upload_app(mcp_app, data_path: Path, token: str):
    """Wrap the MCP Starlette app with an /upload endpoint and a status page."""
    from starlette.applications import Starlette
    from starlette.requests import Request
    from starlette.responses import HTMLResponse, JSONResponse
    from starlette.routing import Mount, Route

    async def upload(request: Request):
        # Token auth
        auth = request.headers.get("X-Upload-Token", "")
        if token and auth != token:
            return JSONResponse({"error": "Unauthorized — set X-Upload-Token header"}, status_code=401)
        try:
            data = await request.json()
            if "contacts" not in data:
                return JSONResponse({"error": "Invalid WarmPath data (missing 'contacts')"}, status_code=400)
            data_path.parent.mkdir(parents=True, exist_ok=True)
            with open(data_path, "w") as f:
                json.dump(data, f, indent=2)
            return JSONResponse({"ok": True, "contacts": len(data["contacts"])})
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    async def status(request: Request):
        try:
            d = load_data()
            n = len(d["contacts"])
            body = f"<h2>✅ WarmPath MCP</h2><p>{n} contacts loaded.</p><p>MCP endpoint: <code>/mcp</code></p>"
        except Exception as e:
            body = f"<h2>⚠️ WarmPath MCP</h2><p>No data loaded yet: {e}</p>"
        body += (
            "<hr><h3>Upload your data</h3>"
            "<pre>curl -X POST https://YOUR-URL/upload \\\n"
            "  -H 'Content-Type: application/json' \\\n"
            "  -H 'X-Upload-Token: YOUR_TOKEN' \\\n"
            "  --data-binary @warmpath_data.json</pre>"
        )
        return HTMLResponse(f"<html><body style='font-family:sans-serif;max-width:600px;margin:40px auto'>{body}</body></html>")

    app = Starlette(routes=[
        Route("/upload", upload, methods=["POST"]),
        Route("/", status, methods=["GET"]),
        Mount("/", app=mcp_app),
    ])
    return app


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    # Auto-detect cloud deployment: Railway / Render set PORT env var
    cloud_port = int(os.environ.get("PORT", 0))
    http_mode  = "--http" in sys.argv or cloud_port > 0
    port       = cloud_port or 8765
    host       = "0.0.0.0" if cloud_port else "127.0.0.1"
    token      = os.environ.get("WARMPATH_TOKEN", "")

    # Quick data check on startup (skip on cloud if no data yet — upload comes later)
    try:
        data = load_data()
        print(
            f"WarmPath MCP server starting — "
            f"{len(data['contacts'])} contacts loaded from "
            f"{Path(data['source_file']).name}",
            file=sys.stderr,
        )
    except FileNotFoundError as e:
        if not cloud_port:
            print(str(e), file=sys.stderr)
            sys.exit(1)
        print(f"⚠️  No data file yet — upload via /upload endpoint. ({e})", file=sys.stderr)

    if http_mode:
        print(f"WarmPath MCP running in HTTP mode on {host}:{port}", file=sys.stderr)
        if not cloud_port:
            print(f"Expose via: ngrok http {port}", file=sys.stderr)

        mcp.settings.host = host
        mcp.settings.port = port
        if _TRANSPORT_SECURITY is not None:
            mcp.settings.transport_security = _TRANSPORT_SECURITY

        if cloud_port:
            # Cloud: wrap with /upload + status page, run via uvicorn directly
            import uvicorn
            starlette_app = mcp.get_asgi_app(transport="streamable-http")
            data_path = Path("/data/warmpath_data.json") if cloud_port else Path(__file__).parent.parent / "warmpath_data.json"
            app = _make_upload_app(starlette_app, data_path, token)
            uvicorn.run(app, host=host, port=port)
        else:
            mcp.run(transport="streamable-http")
    else:
        mcp.run(transport="stdio")
