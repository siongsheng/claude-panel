---
description: On-demand compose-and-post of the ONE 📋 Review Findings Ledger for a PR — gathers every reviewer comment/review + the diff, triages, cumulatively merges into the existing ledger, stamps the authorship sentinel, and posts via post_sticky_comment.py. Runs on your credentials, so it works on PRs CI can't service (workflow-editing PRs, or PRs opened outside a /panel session). Advisory and idempotent.
---

# /panel-ledger — compose the review findings ledger on demand

You are the SUPERVISOR of a one-shot ledger pass for pull request **$ARGUMENTS**. This is
`/panel` step 8 (the findings ledger) extracted and pointed at an arbitrary PR — nothing
else from the loop runs. Use it when a PR has reviewer output but no up-to-date ledger:
e.g. a PR opened **without** `/panel`, or one that **modifies the reviewer workflows**
(where the CI auto-ledger's `workflow_run` job can't post). Because it runs on your creds,
it can post where CI cannot.

## Invariants (non-negotiable)

- **Advisory — never blocks.** This only reports; it never fails anything.
- **Exactly ONE ledger comment.** Edit the existing `📋 Review Findings Ledger` in place;
  never open a second. Always post via `scripts/post_sticky_comment.py` (path relative to
  this plugin) — never hand-roll the PATCH/POST.
- **Cumulative — never regenerate.** Read the existing ledger first and MERGE: preserve
  every prior row and its ID, change only Status, append new rows, never drop a row.
- **Record the TRIAGED severity**, not the reviewer's raw claim (apply `blocker-triage`).
- **This command does NOT file issues.** A real Deferred/Standing finding gets the
  `⚠️ Needs issue` status (the honest "tracked-but-not-yet-filed" marker). Filing stays the
  `/panel` loop's job (step 9) — a re-runnable command must not spawn duplicate issues.

## Preflight

Confirm `gh auth status` is authenticated. Resolve the repo slug
(`gh repo view --json nameWithOwner`). Confirm PR `$ARGUMENTS` exists and is open. If any
fails, report exactly what's missing and stop.

## The pass

### 1. Gather (deterministic)
Pull every reviewer input for PR `$ARGUMENTS`, mirroring the `templates/findings-ledger.yml`
"Gather ledger inputs" step (or reuse `scripts/deepseek_review.py`'s `fetch_pr` for meta +
diff):
- `gh api repos/<slug>/issues/$ARGUMENTS/comments --paginate` — issue comments (incl. the
  DeepSeek review and any prior ledger).
- `gh api repos/<slug>/pulls/$ARGUMENTS/reviews --paginate` — PR reviews.
- `gh api repos/<slug>/pulls/$ARGUMENTS/comments --paginate` — inline review comments.
- `gh pr diff $ARGUMENTS` — the diff, for context.
Read the existing `📋 Review Findings Ledger` comment (match by that marker) for the
cumulative merge, and EXCLUDE it from the reviewer inputs (don't treat the ledger as a
finding source).

### 2. Coverage (visible downgrade)
Note which reviewer families produced output. If the diff is **provably inert** — every
changed file matches the docs/prose allowlist `**.md`/`.markdown`/`.rst`/`.txt`/`.adoc`,
`docs/**`, `LICENSE` — the Architecture + DeepSeek reviewers were skipped by CI
`paths-ignore`; record `⏭️ skipped — low blast radius (docs-only diff)`, not silence. If any
file is non-inert, a missing reviewer means it genuinely produced nothing — don't claim a
blast-radius skip. (See the `findings-ledger` skill's "Record which reviewers ran".)

### 3. Triage + merge
Apply `blocker-triage` then `findings-ledger`: triage every finding (real vs false; expect
~30–40% false; check pre-existing-on-base), **capture every finding including non-blocking
Suggestions/Nits**, and dedupe findings multiple reviewers raised into ONE row (list all
sources). Cumulatively merge into the existing ledger, preserving IDs; real unfiled defers
get `⚠️ Needs issue`. Append ONE audit-log line dated with `date -u +%F`, actor
`panel-ledger (on-demand, <your gh login>)`, ONLY if a row or status actually changed.

### 4. Sentinel
Stamp the authorship sentinel as the LAST line of the ledger body:
`<!-- ledger: author=panel-agent sha=<head> -->`, resolving the head SHA with
`gh pr view $ARGUMENTS --json headRefOid`. **Reuse the exact `author=panel-agent` string** —
the CI auto-ledger's stand-down check greps for it, so this makes CI correctly DEFER to
your ledger for that commit (no clobber). A different actor string would let CI recompose
over your ledger.

### 5. Post
Write the composed body to a file and post it:
```
python3 scripts/post_sticky_comment.py $ARGUMENTS \
  --marker '## 📋 Review Findings Ledger' --body-file <file>
```
(path relative to this plugin). It normalizes the body, asserts the marker is line 1, and
edits the existing comment in place or creates it — idempotent, so re-running is safe.

## Modes

**Interactive (default):** narrate the triage table before posting; surface the final PR
comment link.

**Headless (`claude -p "/panel-ledger <pr>"`):** compose + post unattended; surface only
the ledger summary and the PR link.
