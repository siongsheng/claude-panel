---
name: findings-ledger
description: Maintain ONE "📋 Review Findings Ledger" comment per PR — a single table of every reviewer's findings with IDs and statuses, deduped and edited in place. Use when consolidating or reporting review findings on a PR so the human reads one table instead of reconciling scattered comments.
---

# Review Findings Ledger

Every PR carries exactly ONE ledger comment. It is the single place a human looks to
see what every reviewer found and where each finding stands. The goal: the reader never
has to cross-reference scattered review comments against fix commits and issues by hand.

**Always post the ledger — even when the review is clean.** A PR with zero findings still
gets the ledger, stating which reviewers ran and that nothing was found, e.g.:

> ## 📋 Review Findings Ledger
> ✅ **Reviewed — no issues found.** Reviewers: Claude adversarial + architecture, DeepSeek (cross-model). Gates: `bin/tdd-check` PASS.
> _(no findings)_

This way a clean review is visible confirmation ("it was reviewed and the code is clear"),
never silence — the reader can tell "reviewed, nothing found" apart from "not reviewed."

## The one comment

Post a single comment titled **📋 Review Findings Ledger** containing one table:

| ID | Finding | Source | Severity | Status |
|----|---------|--------|----------|--------|
| R1 | <one-line description> | <reviewer(s)> | BLOCKER / SHOULD FIX / NIT | <status> |

- **ID** — sequential `R1`, `R2`, … assigned as findings arrive.
- **Finding** — one line. Enough to identify it, not the full analysis.
- **Source** — which reviewer(s) raised it (e.g. `Claude`, `DeepSeek`, `GitHub app`,
  `human`). If several reviewers raised the same finding, list them all in one row (see
  Dedupe).
- **Severity** — the triaged severity after `blocker-triage`, not the reviewer's raw
  claim.
- **Status** — one of the values below.

## Statuses

| Status | Meaning | Needs an issue? |
|--------|---------|-----------------|
| ✅ Fixed `<sha>` | Confirmed defect, fixed in this PR; pin with a test | No |
| 📋 Deferred → #N | Valid, but belongs to later work | **Yes** |
| 📌 Standing → #N | Real pre-existing defect this change did not cause | **Yes** |
| 🤔 Owner decision → #N | Product / design judgment call | **Yes** (`design-decision`) |
| ❌ Rejected | False positive — state the reason inline | No |

**Every non-Fixed, non-Rejected row MUST carry an issue link.** The only rows without an
issue are ✅ Fixed and ❌ Rejected. Do not leave a Standing or Deferred finding as a
ledger note only — that lets real defects go untracked. (See the `deferred-to-issues`
skill for filing them.)

## Record which reviewers ran

The ledger is also the record of coverage. Under the table, note which reviewer families
ran — and, critically, which were **skipped**. If the cross-model (DeepSeek) family was
skipped (e.g. single-provider repo with no `DEEPSEEK_API_KEY`), state it explicitly:

> _Reviewers: Claude-side (adversarial + architecture) ✅ · Cross-model (DeepSeek) ⏭️
> skipped — single-provider mode, no second-model coverage this PR._

This keeps reduced coverage visible instead of letting a reader assume both families
reviewed. Never omit a skipped family silently.

## Dedupe across reviewers

When two reviewers (say Claude and DeepSeek) raise the same finding, it is ONE row with
both listed in Source — not two rows. Deduping is what makes the table readable when a
cross-model panel produces overlapping findings.

## Cumulative — never regenerate from scratch

The ledger is a living **audit trail** for the PR, not a per-run snapshot. On every
update — including automated re-runs after new commits — FIRST read the existing ledger,
then MERGE:

- **Preserve every prior row and its ID.** Never drop a finding because a later review no
  longer reports it — a fixed finding stays as a `✅ Fixed <sha>` row.
- **Change only the Status** of existing rows as things resolve (`Open → ✅ Fixed`,
  `❌ Rejected`, `📋 Deferred → #N`). Keep the ID stable.
- **Append new findings** as new rows with the next ID.
- A clean re-run does NOT erase history: a PR that found 8 issues and fixed them all
  reads "8 rows, all ✅ Fixed", not "no issues found".

So the ledger only ever **grows and updates in place** — it is never overwritten with the
latest review's snapshot.

## Update in place — never post follow-ups

As fixes land and issues get filed, EDIT the existing ledger comment. Do not post new
comments the reader must reconcile.

1. Find the comment id:
   `gh api repos/{owner}/{repo}/issues/{pr}/comments --paginate`
   and match the one whose body starts with `📋 Review Findings Ledger`.
2. Patch it:
   `gh api --method PATCH repos/{owner}/{repo}/issues/comments/{id} -F body=@ledger.md`

Post the ledger once review completes — including a clean "no issues found" ledger when
there are zero findings — and edit it in place thereafter.

## Pitfalls

- Do not record the reviewer's raw severity — record the triaged severity.
- Do not open a second ledger comment because editing felt awkward. One comment, always.
- A row can change status over the loop (Deferred → Fixed if you decide to fix it in
  scope after all). Edit the row; keep the ID stable.
- The ledger is the human's view. Keep the Finding column terse; the analysis lives in
  the triage discussion, not the table.
