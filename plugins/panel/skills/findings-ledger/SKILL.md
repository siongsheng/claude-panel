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

**Capture EVERY finding from EVERY reviewer — including non-blocking ones.** A reviewer's
"Suggestions", "Nits", "Non-blocking", or "Minor" subsection contains findings too: each
gets its own row (Severity `NIT` or `SHOULD FIX` after triage), same as blockers. Do not
read only the BLOCKER / "Request changes" list and drop the rest — a reviewer that raised
6 items must produce 6 rows (minus dedup), not 3. Silently omitting a reviewer's
lower-severity section is the same defect as dropping the reviewer entirely: the reader
trusts the table is complete across every reviewer and every severity.

## Statuses

| Status | Meaning | Needs an issue? |
|--------|---------|-----------------|
| ✅ Fixed `<sha>` | Confirmed defect, fixed in this PR; pin with a test | No |
| 📋 Deferred → [#N](url) | Valid, but belongs to later work | **Yes** |
| 📌 Standing → [#N](url) | Real pre-existing defect this change did not cause | **Yes** |
| 🤔 Owner decision → [#N](url) | Product / design judgment call | **Yes** (`design-decision`) |
| ⚠️ Needs issue | Real Deferred/Standing finding **not yet filed** — a visible, unresolved gap | **Yes — not yet done** |
| ❌ Rejected | False positive — state the reason inline | No |

**Every non-Fixed, non-Rejected row MUST resolve to one of exactly two honest states:**

1. **Tracked** — a **markdown link to the issue** in the Status column, not a bare number:
   `📋 Deferred → [#31](https://github.com/<owner>/<repo>/issues/31)` — so the reader can
   jump straight to it. (A bare `#31` auto-links only within the same repo's comments; an
   explicit link always resolves and works cross-repo, so prefer it.)
2. **`⚠️ Needs issue`** — the finding is real and deferred but an issue has NOT been filed
   yet. Use this whenever you cannot file the issue in the current context (see the
   advisory note below). It is an explicit, visible admission that tracking is still owed.

**Never write a vague "tracked separately", "see other issue", or a bare number that
implies tracking without a link.** That reads as handled when it is not — the exact silent
gap this ledger exists to prevent. A finding is either linked (state 1) or loudly
`⚠️ Needs issue` (state 2); there is no third, hand-wavy option. The only rows with no
issue at all are ✅ Fixed and ❌ Rejected. (See the `deferred-to-issues` skill for filing —
once filed, upgrade a `⚠️ Needs issue` row to `📋 Deferred → [#N](url)`.)

> **Advisory automated ledger (CI):** the auto-posted ledger runs advisory-only and
> **cannot file issues** (no `gh`/write scope). It MUST therefore mark every real
> Deferred/Standing finding `⚠️ Needs issue` — never invent a link or a "tracked
> separately" placeholder. The `/panel` loop (or a human) then files the issue via
> `deferred-to-issues` and upgrades the row to the linked form.

## Record which reviewers ran

The ledger is also the record of coverage. Under the table, note which reviewer families
ran — and, critically, which were **skipped**. If the cross-model (DeepSeek) family was
skipped (e.g. single-provider repo with no `DEEPSEEK_API_KEY`), state it explicitly:

> _Reviewers: Claude-side (adversarial + architecture) ✅ · Cross-model (DeepSeek) ⏭️
> skipped — single-provider mode, no second-model coverage this PR._

This keeps reduced coverage visible instead of letting a reader assume both families
reviewed. Never omit a skipped family silently.

A family may be skipped for two distinct reasons — keep both visible and distinct:

- `⏭️ skipped — single-provider mode` — no `DEEPSEEK_API_KEY` (cross-model only).
- `⏭️ skipped — low blast radius (inert diff)` — CI `paths-ignore` right-sizing on a
  docs/prose-only diff (every changed file matches `**.md`/`.markdown`/`.rst`/
  `.adoc`, `LICENSE`). This can skip **both** the architecture and DeepSeek
  families — the deterministic gate (`tdd-check`) and the official `claude-code-review`
  still run. Example coverage line for an inert diff:

> _Reviewers: Claude Code Review (correctness) ✅ · TDD gate ✅ · Architecture +
> Cross-model (DeepSeek) ⏭️ skipped — low blast radius (docs-only diff, no code changed)._

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

## Two authors, one comment — the authorship sentinel

The ledger can be written by two mechanisms, and they must not clobber each other:

- The **supervising `/panel` agent** (primary when a loop is running) — it also holds the
  in-session subagent reviews the CI job can't see, so its ledger is the most complete.
- The **CI auto-ledger** (fallback) — for PRs no one is driving with `/panel`, and for
  later pushes.

To hand off cleanly, an agent-authored ledger carries an **authorship sentinel** as the
last line of the body (an HTML comment — invisible when rendered):

```
<!-- ledger: author=panel-agent sha=<PR head SHA> -->
```

The CI auto-ledger checks for it: **if a `panel-agent` sentinel matches the current head
SHA, CI stands down** (no re-compose, no post) — the agent's ledger is authoritative for
that commit. CI only takes over when there is no such sentinel (an un-driven PR) or it is
stale (a later push changed the SHA, so the agent's ledger no longer covers the new code).
Both write the SAME sticky comment, so there is never a duplicate — the sentinel just
decides who composes it. This prevents a second, less-informed re-compose from silently
degrading the agent's richer ledger.

## Audit log — who changed what, when (append-only)

The ledger is edited in place, so a naive PATCH erases the history of *how it got here* —
GitHub's comment-edit view shows only raw body diffs, not a semantic trail. Keep an
**append-only Audit log** section below the table so every status change is attributable.
This is the accountability layer: "understand, then merge" means a reader can see who
decided what before the merge.

Under the table, maintain an append-only bulleted list (one backticked line per edit) —
**never rewrite or reorder existing lines; only append**. Do not wrap it in a ``` code
fence (a fence around the whole ledger body would collide with the sticky-comment marker
normalization):

> **Audit log**
> - `2026-07-14 · auto-ledger (CI) · R1,R2 added; R2 ❌ Rejected`
> - `2026-07-14 · auto-ledger (CI) · R1 Open→✅ Fixed @3177094`
> - `2026-07-14 · human (siongsheng) · R3 Open→📋 Deferred → #31`

Each entry records:

- **When** — the date (an ISO date is enough; the comment already carries a timestamp).
- **Actor — who made THIS edit.** Distinguish the automated CI ledger (`auto-ledger (CI)`)
  from a person editing during the `/panel` loop (`human (<login>)`), and from a named
  reviewer if relevant. This is the "who" the audit is for: an automated triage pass and a
  human override must not look identical.
- **What** — which row IDs changed and the transition (`Open→✅ Fixed @<sha>`,
  `Open→❌ Rejected`, `→📋 Deferred → #N`), or `Rn added` for new rows.

Rules:

- **Append-only.** Every update adds one line for what that update did; it never edits or
  removes earlier lines. This is what makes it an audit trail rather than a status field.
- **Survives the cumulative merge.** Like the table, the log is preserved on every re-run
  (see "Cumulative" above) — the compose step reads the existing log and appends, never
  regenerates it.
- **One line per edit session**, summarizing that session's changes — not one line per
  row per run (keep it readable).

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
