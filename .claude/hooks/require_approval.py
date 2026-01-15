#!/usr/bin/env python3
import json, os, sys

data = json.load(sys.stdin)
tool = data.get("tool_name")
inp = data.get("tool_input", {})
path = inp.get("file_path", "") or ""

approved = os.path.exists(".claude/state/approved.json")

# Allow always: writing approval state itself
if ".claude/state/approved.json" in path:
    sys.exit(0)

# If not approved, allow only Markdown/docs edits (tweak this to your taste)
if not approved:
    if path.endswith(".md") or "/docs/" in path or path.endswith("CLAUDE.md"):
        sys.exit(0)
    print("Blocked: code edits require explicit approval. Run /plan then /approve.", file=sys.stderr)
    sys.exit(2)

sys.exit(0)

