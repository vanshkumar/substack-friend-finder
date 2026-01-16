cription: Create PR (commit + push + gh pr create) with a clean summary
allowed-tools: Bash(git status:*), Bash(git diff:*), Bash(git add:*), Bash(git commit:*), Bash(git push:*), Bash(git branch:*), Bash(git log:*), Bash(gh pr create:*), Bash(gh pr view:*)
---
## Context
- Branch: !`git branch --show-current`
- Status: !`git status`
- Diff: !`git diff`

## Task
1) Propose a good PR title + body (why, what, how tested).
2) Create a single commit (or small set if justified).
   - Always include the full `.claude/` folder in commits (learnings, settings, commands).
3) Push branch.
4) Open a PR with `gh pr create` using the title/body.

