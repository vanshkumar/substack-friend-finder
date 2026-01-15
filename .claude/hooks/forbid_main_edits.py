#!/usr/bin/env python3
import json, subprocess, sys

data = json.load(sys.stdin)
project = subprocess.check_output(["bash","-lc","pwd"]).decode().strip()

def current_branch():
    try:
        return subprocess.check_output(["git","-C",project,"branch","--show-current"]).decode().strip()
    except Exception:
        return ""

branch = current_branch()
if branch in ("main", "master"):
    # Exit code 2 blocks the tool call and shows stderr to Claude for PreToolUse. :contentReference[oaicite:9]{index=9}
    print("Blocked: you're on main/master. Run /branch <slug> first.", file=sys.stderr)
    sys.exit(2)

sys.exit(0)

