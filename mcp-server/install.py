#!/usr/bin/env python3
"""
WarmPath MCP Server — one-command installer.

What this does:
  1. Checks that Python 3.10+ is available
  2. Installs the 'mcp' Python package if it isn't already
  3. Locates your Claude Desktop config file
  4. Adds the WarmPath server entry to it (or creates the file if it doesn't exist)
  5. Prints clear next-steps instructions

Run with:
    python3 mcp-server/install.py
"""

import json
import os
import platform
import subprocess
import sys
from pathlib import Path


# ─── Helpers ──────────────────────────────────────────────────────────────────

def print_step(n: int, text: str) -> None:
    print(f"\n  [{n}] {text}")

def print_ok(text: str) -> None:
    print(f"      ✅  {text}")

def print_warn(text: str) -> None:
    print(f"      ⚠️   {text}")

def print_err(text: str) -> None:
    print(f"\n  ❌  {text}\n")


# ─── Step 1: Python version ───────────────────────────────────────────────────

print("\n" + "─" * 60)
print("  WarmPath MCP Server — installer")
print("─" * 60)

print_step(1, "Checking Python version…")

if sys.version_info < (3, 10):
    print_err(
        f"Python 3.10 or higher is required. "
        f"You have Python {sys.version_info.major}.{sys.version_info.minor}.\n"
        f"  Download the latest Python from: https://www.python.org/downloads/"
    )
    sys.exit(1)

print_ok(f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro} — good.")


# ─── Step 2: Install mcp package ─────────────────────────────────────────────

print_step(2, "Installing the 'mcp' package…")

try:
    import mcp  # noqa: F401
    import importlib.metadata
    version = importlib.metadata.version("mcp")
    print_ok(f"'mcp' package already installed (version {version}).")
except ImportError:
    print("      Installing… (this may take 30–60 seconds)")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "mcp>=1.0.0", "--quiet"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print_err(
            f"Failed to install 'mcp'.\n\n"
            f"  Error output:\n{result.stderr}\n\n"
            f"  Try running manually:\n"
            f"    pip3 install mcp"
        )
        sys.exit(1)
    print_ok("'mcp' package installed successfully.")


# ─── Step 3: Find Claude Desktop config ───────────────────────────────────────

print_step(3, "Locating Claude Desktop config file…")

system = platform.system()

if system == "Darwin":  # macOS
    config_path = Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
elif system == "Windows":
    appdata = os.environ.get("APPDATA", "")
    config_path = Path(appdata) / "Claude" / "claude_desktop_config.json"
elif system == "Linux":
    config_path = Path.home() / ".config" / "Claude" / "claude_desktop_config.json"
else:
    print_err(f"Unsupported operating system: {system}")
    sys.exit(1)

print_ok(f"Config path: {config_path}")

# Create parent directories if they don't exist
config_path.parent.mkdir(parents=True, exist_ok=True)


# ─── Step 4: Read or create the config ────────────────────────────────────────

print_step(4, "Reading Claude Desktop config…")

if config_path.exists():
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        print_ok("Existing config found and loaded.")
    except json.JSONDecodeError:
        print_warn("Existing config file has invalid JSON — creating a fresh one.")
        config = {}
else:
    print_ok("No config file yet — will create one.")
    config = {}

if "mcpServers" not in config:
    config["mcpServers"] = {}


# ─── Step 5: Build the server entry ───────────────────────────────────────────

server_script = str(Path(__file__).parent / "server.py")

# Use the absolute path to the Python interpreter running this script
python_executable = sys.executable

new_entry = {
    "command": python_executable,
    "args":    [server_script],
}

existing = config["mcpServers"].get("warmpath")
if existing == new_entry:
    print_step(5, "WarmPath entry already up to date — no changes needed.")
else:
    if existing:
        print_step(5, "Updating existing WarmPath entry in Claude Desktop config…")
    else:
        print_step(5, "Adding WarmPath entry to Claude Desktop config…")

    config["mcpServers"]["warmpath"] = new_entry

    # Write back with pretty formatting
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

    print_ok("Config updated successfully.")
    print(f"\n      Entry added:\n")
    print(f'        "warmpath": {{')
    print(f'          "command": "{python_executable}",')
    print(f'          "args": ["{server_script}"]')
    print(f'        }}')


# ─── Step 6: Data file check ──────────────────────────────────────────────────

print_step(6, "Checking for WarmPath data file…")

parent_dir = Path(__file__).parent.parent
data_file  = parent_dir / "warmpath_data.json"
backups    = sorted(parent_dir.glob("warmpath-backup*.json"), reverse=True)

if data_file.exists():
    print_ok(f"Found: {data_file.name}")
elif backups:
    print_warn(
        f"Found backup file: {backups[0].name}\n"
        f"      The server will use this automatically.\n"
        f"      Tip: rename it to 'warmpath_data.json' to make it the default."
    )
else:
    print_warn(
        "No WarmPath data file found yet.\n\n"
        "      To fix this before using the server:\n"
        "        1. Open WarmPath in your browser\n"
        "        2. Go to Setup → Settings → Backup → Download backup\n"
        f"        3. Rename the file to: warmpath_data.json\n"
        f"        4. Move it to: {parent_dir}"
    )


# ─── Done ─────────────────────────────────────────────────────────────────────

print("\n" + "─" * 60)
print("  ✅  Installation complete!")
print("─" * 60)
print("""
  Next steps:

  1. Quit Claude Desktop completely (Cmd+Q on Mac / close from taskbar on Windows)
  2. Reopen Claude Desktop
  3. Start a new conversation and try:

       "List my warmest LinkedIn connections"
       "Who do I know at Stripe?"
       "Draft a message to [contact name]"

  If the tools don't appear, check that:
    • Claude Desktop is fully restarted (not just the window)
    • The data file exists in the WarmPath folder
    • Python is accessible at the path shown above

  For help, see: mcp-server/README.md
""")
