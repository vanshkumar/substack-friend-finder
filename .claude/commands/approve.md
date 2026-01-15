---
description: Require explicit approval, then enable code edits for this session
allowed-tools: Bash(mkdir -p*), Bash(date*), Bash(printf*), Bash(cat*), Bash(ls*), Bash(touch*)
---
If the user has explicitly approved, run:

!`mkdir -p .claude/state`
!`printf '{"approved_at":"%s"}\n' "$(date -Is)" > .claude/state/approved.json`

Then confirm approval is active.
If not approved, do not write anything—ask for approval explicitly.

