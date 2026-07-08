---
name: blocker-triage
description: ANALYZE FIRST, FIX SECOND. Use this immediately after ANY reviewer (a human, /code-review, pr-review-toolkit, or DeepSeek) produces findings, and BEFORE you change a single line in response. Roughly 30-40% of raised blockers are false; this skill makes you present a triage table justifying each verdict before fixing anything.
---

# BLOCKER Triage — ANALYZE FIRST, FIX SECOND

**THIS IS THE MOST VIOLATED RULE.** Agents repeatedly fix false BLOCKERs on reflex before anyone catches it. Every session that receives reviewer findings MUST apply this section before touching code.

**DO NOT FIX BLIND.** Reviewers over-escalate: roughly **30-40% of raised blockers are false** — miscategorized as more severe than they actually are. Explicit analysis is expected before any fix. Failing to challenge false BLOCKERs wastes time and erodes trust.

## Your first action is a table, not an edit

After a reviewer (human, `/code-review`, pr-review-toolkit, or DeepSeek) produces findings, your FIRST action is NOT to start fixing — it's to present a table that analyzes every raised BLOCKER:

| # | reviewer says | Real defect? | Already handled? | Pre-existing (on main)? | Verdict |
|---|---------------|--------------|------------------|-------------------------|---------|
| 1 | ... | Yes/No | Guard at line X / no | Yes/No (`git show main:path`) | BLOCKER / False alarm |

Only after this table is visible do you fix the REAL BLOCKERs. Miscategorized ones get challenged and deferred.

## The four triage questions

For every raised BLOCKER, answer:

1. **Is it a real defect?** Would it actually cause wrong results, crashes, or data loss?
2. **Is it already handled?** Does an upstream guard, existing fallback, or code pattern already cover this?
3. **Does the fix add complexity for no real gain?** Some findings propose belt-and-suspenders that add code with zero safety improvement.
4. **Is it pre-existing?** Did this issue exist on `main` BEFORE this change? Check with `git show main:path/to/file`. If yes, it's a false BLOCKER for this change — file a separate issue instead of blocking the merge.

State explicitly for each: "Valid BLOCKER — fixing because X" or "False alarm — Y already handles this because Z."

## Concrete false-BLOCKER examples (these happen frequently)

| Reviewer says | Reality | Why it's not a BLOCKER |
|---------------|---------|------------------------|
| "Silent error — no error_code field" | Code already falls back to a default gracefully | Error produces correct behavior; only downside is a worse log message. SHOULD FIX at most. |
| "Stale default — bound at import time" | Default only affects a cosmetic display value, not any computed result | The computed output is unchanged; nobody overrides this default in practice. SHOULD FIX at most. |
| "Subprocess missing a CLI flag" | Only matters in a workflow the user never uses | Normal flow runs the tools separately and passes output between them. Edge case. SHOULD FIX at most. |
| "Partial file left on write error" | The error already propagates and the library's cleanup handles the file on drop | Adding a delete-on-error guard is ~10 lines for zero real improvement. Not a BLOCKER. |
| "Placeholder token in a code block" | Exists on main before this change — `git show main:file` confirms | Pre-existing issue. File a separate SHOULD FIX; do not block this change. |
