# WarmPath MCP Server

Connect your LinkedIn network data directly to **Claude Desktop** or **claude.ai** (web).  
Ask Claude things like _"Who should I message today?"_ or _"Draft a message to Priya about the PM role at Stripe"_ — and Claude answers using your real WarmPath data.

---

## What this does

WarmPath already scores and organises your LinkedIn contacts in the browser.  
This MCP server exposes that data to Claude as **20 tools** across 5 categories:

| Category | Tools |
|---|---|
| **Read** | `score_connection`, `find_warm_connections_at_company`, `draft_outreach_message`, `list_connections` |
| **Plan** | `get_todays_plan`, `get_followup_list`, `get_weekly_summary`, `morning_briefing` |
| **Act** | `open_linkedin_profile`, `copy_message_to_clipboard`, `send_outreach`, `find_open_role` |
| **Log** | `log_message_sent`, `log_reply`, `prepare_resume_response` |
| **Settings** | `set_ex_companies` |
| **Company Intel** | `list_target_companies`, `get_company_intelligence`, `get_todays_company_priority`, `update_company_score` |

Everything runs **locally on your computer**. No extra accounts, no API keys, no data sent anywhere new.

---

## Requirements

- **Claude Desktop** installed and signed in ([download here](https://claude.ai/download))
- **Python 3.10 or higher** (see installation below if you're not sure)
- A **WarmPath backup file** exported from the app

---

## Step 1 — Check if Python is installed

Open **Terminal** (Mac) or **Command Prompt** (Windows) and type:

```
python3 --version
```

You should see something like `Python 3.12.2`.

If you see `command not found` or a version below 3.10:

**Mac:** Download from [python.org/downloads](https://www.python.org/downloads/) and install.  
**Windows:** Download from [python.org/downloads](https://www.python.org/downloads/) — during install, tick **"Add Python to PATH"**.

After installing, close and reopen your Terminal/Command Prompt, then check the version again.

---

## Step 2 — Export your WarmPath data

The MCP server reads from a file called `warmpath_data.json` in your WarmPath folder.

1. Open WarmPath in your browser
2. Go to **Setup → Settings**
3. Under **Backup & Restore**, click **Download backup**
4. Your browser will download a file named something like `warmpath-backup-2026-05-05.json`
5. **Rename it** to `warmpath_data.json`
6. Move it into your **WarmPath folder** (the same folder that contains `index.html`)

> **Tip:** You don't have to rename it — the server will also pick up any `warmpath-backup-*.json` file automatically. But keeping it named `warmpath_data.json` makes it clear which file is in use.

> **Keeping it fresh:** Re-export and replace this file every time you want Claude to see your latest outreach activity. The MCP server reads the file fresh each time you ask a question — no restart needed.

---

## Step 3 — Run the installer

The installer does everything automatically: installs the required Python package, finds your Claude Desktop config file, and adds the WarmPath server entry.

Open **Terminal** (Mac) or **Command Prompt** (Windows).

Navigate to your WarmPath folder:
```
cd /path/to/your/WarmPath
```
> **Mac tip:** Type `cd ` (with a space), then drag your WarmPath folder into the Terminal window. It will fill in the path. Press Enter.

Run the installer:
```
python3 mcp-server/install.py
```

**Windows users:** Use `python` instead of `python3`:
```
python mcp-server\install.py
```

You should see output like:
```
  [1] Checking Python version…
      ✅  Python 3.12.2 — good.

  [2] Installing the 'mcp' package…
      ✅  'mcp' package installed successfully.

  [3] Locating Claude Desktop config file…
      ✅  Config path: /Users/you/Library/Application Support/Claude/claude_desktop_config.json

  [4] Reading Claude Desktop config…
      ✅  Existing config found and loaded.

  [5] Adding WarmPath entry to Claude Desktop config…
      ✅  Config updated successfully.

  [6] Checking for WarmPath data file…
      ✅  Found: warmpath_data.json

  ✅  Installation complete!
```

If you see any ❌ errors, read the message — it will tell you exactly what to do.

---

## Step 4 — Restart Claude Desktop

The config change only takes effect after a **full restart**:

- **Mac:** Press `Cmd + Q` to fully quit, then reopen Claude Desktop
- **Windows:** Right-click the Claude icon in the taskbar → Quit, then reopen

> Just closing the window is not enough — Claude Desktop needs to be fully quit and relaunched.

---

## Step 5 — Try it out

Open Claude Desktop and start a new conversation. Try asking:

- _"List my warmest LinkedIn connections"_
- _"Who do I know at Chargebee?"_
- _"What's Priya's warmth score and interaction history?"_
- _"Find warm contacts at Stripe and draft a message to the best one"_
- _"List all my Grade A connections I haven't messaged yet"_
- _"Draft an outreach message to Rohan about the Staff PM role at Razorpay"_

Claude will use your real WarmPath data to answer.

---

## Updating your data

Whenever you've sent new messages in WarmPath and want Claude to see the latest:

1. Open WarmPath → Setup → Settings → Download backup
2. Rename it `warmpath_data.json` and replace the old file in your WarmPath folder

No restart of Claude Desktop or the server is needed — it reads the file fresh on every request.

---

## How the four tools work

### `score_connection`
Look up any contact by name. Returns:
- Warmth score (0–200+) and grade (A/B/C)
- Warmth tier (recommender, close-colleague, colleague, active-contact, known, warm-unknown, cold)
- All messages exchanged and interaction history
- Scoring signals (what drove the score)
- Notes you've added in WarmPath

### `find_warm_connections_at_company`
Give it a company name — even partial ("razor" matches "Razorpay"). Returns:
- Every contact at that company
- Sorted by grade then score
- Grade summary (e.g. 2A · 1B)
- Target company badge if it's in your target list

### `draft_outreach_message`
Give it a name and optional context (job title, angle, or URL). Returns:
- A ready-to-send draft message
- Tone adapts to warmth tier (warmer = more direct, colder = more formal)
- Framing adapts to your Primary Goal (Job Search / Recruiting / Advisory / Networking)
- Warning if you've already messaged this contact before

### `list_connections`
Browse your full network with filters:
- `company` — filter by company name
- `warmth_level` — "A", "B", or "C"
- `keyword` — search names, roles, notes, relationship fields
- `limit` — number of results (default 25, max 100)

---

## Troubleshooting

**"No WarmPath data file found"**  
The server can't find `warmpath_data.json`. Export a backup from WarmPath and put it in the WarmPath folder (the one with `index.html`). See Step 2.

**Tools don't appear in Claude Desktop**  
- Make sure you fully quit and restarted Claude Desktop after running the installer
- On Mac, check `~/Library/Application Support/Claude/claude_desktop_config.json` — it should contain a `"warmpath"` entry under `"mcpServers"`
- Run `python3 mcp-server/server.py` directly in Terminal — any errors will print there

**"Python not found" or wrong version**  
Download Python 3.10+ from [python.org](https://www.python.org/downloads/). On Windows, make sure you ticked "Add Python to PATH" during installation.

**"Permission denied" running the installer on Mac**  
Run this first, then try again:
```
chmod +x mcp-server/install.py
```

**The data seems out of date**  
Re-export your backup from WarmPath and replace `warmpath_data.json`. No restart needed.

---

## Manual config (if the installer doesn't work)

If you'd prefer to add the entry yourself, open (or create) this file:

- **Mac:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

Add this (replacing the path with the actual absolute path to `server.py`):

```json
{
  "mcpServers": {
    "warmpath": {
      "command": "python3",
      "args": ["/absolute/path/to/WarmPath/mcp-server/server.py"]
    }
  }
}
```

On Windows, use `python` instead of `python3`, and use double backslashes in the path:
```json
{
  "mcpServers": {
    "warmpath": {
      "command": "python",
      "args": ["C:\\Users\\you\\Documents\\WarmPath\\mcp-server\\server.py"]
    }
  }
}
```

---

## File structure

```
WarmPath/
├── index.html                   # WarmPath app (do not modify)
├── warmpath_data.json           # Your exported network data ← you create this
├── mcp-server/
│   ├── server.py                # MCP server (four tools)
│   ├── install.py               # One-command installer
│   ├── requirements.txt         # Python dependencies
│   └── README.md                # This file
```

---

## Privacy

- The MCP server runs **entirely on your machine** — no data is sent to any external server by the server itself
- Claude Desktop connects to the server via a local stdio pipe — your contact data never leaves your computer
- The only network calls are the ones Claude Desktop already makes to Anthropic's API for conversation responses (the same as any Claude Desktop conversation)
- Your `warmpath_data.json` stays on your disk and is only read locally
