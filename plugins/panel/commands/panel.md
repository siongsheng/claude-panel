---
description: Run one feature end-to-end through the review panel — YAGNI gate, plan, two-commit TDD on a branch, deterministic TDD gate, parallel cross-model review, triage, fix (serial or parallel worktree-isolated clusters), findings ledger, deferred-to-issues, then pause for merge.
---

# /panel — orchestrate one feature through the panel loop

Feature request: **$ARGUMENTS**

You are the SUPERVISOR of this loop, not the implementer. Panel is a thin layer: it
adds the gates below and delegates the heavy lifting to the composed plugins
(`obra/superpowers`, `feature-dev`, `pr-review-toolkit`). Run the request through the
sequence below, applying panel's gates at each step. Stay repo-agnostic — read the
target repo's own conventions (AGENTS.md / CLAUDE.md / CONTRIBUTING), never assume a
language or stack.

## Invariants (non-negotiable)

- **implementer ≠ reviewer.** Whoever wrote the code never reviews their own work.
  Reviewers run in a FRESH context (independent subagent / separate model) so they
  are not biased by having watched the implementation.
- **Never auto-merge.** The loop ends at a paused PR. The human merges.
- **Gates are hard.** The deterministic TDD gate (`bin/tdd-check`) and the repo's CI
  must be green before review is considered complete. A red gate blocks; it is not a
  suggestion.

## The loop

### 1. YAGNI pre-gate
Invoke the `ponytail-guard` skill on the request in its planning-phase mode. Read the
codebase first, then pick the lowest rung that solves the problem.
- If it lands on **rung 1–4** (doesn't need to exist / already in the codebase /
  stdlib / native platform feature): **STOP.** Report what already exists and how to
  use it. Do not build. This is a successful outcome, not a failure.
- If it lands on **rung 5–7**: continue, and carry the rung forward as the scope
  ceiling for every later step.

### 2. Plan
Produce a plan scoped to exactly the ponytail rung — no more. Use superpowers'
`brainstorming` then `writing-plans` (or feature-dev's Discovery → Architecture
phases via `/feature-dev`) to explore the approach and settle the design before any
code is written. The plan covers only the gap identified in step 1, not the whole
feature surface.

### 3. Branch + implement (two-commit TDD)
Work on a feature branch (never the default branch). If the work is parallelizable or
you want isolation from the working tree, use superpowers' `using-git-worktrees` to
run it in a dedicated worktree; `dispatching-parallel-agents` if you fan out.

Implement following strict two-commit TDD:
- A `test:` commit lands FIRST — failing tests that pin the intended behavior.
- A `feat:` commit lands SECOND — the implementation that makes them pass.
- The `test:` commit MUST be a git **ancestor** of the `feat:` commit (ancestry, not
  wall-clock time — this is what the gate in step 4 verifies).
- A single bundled commit (tests + implementation together) is a BLOCKER.

Prefer having an implementer subagent do the code so the supervising context stays
clean and can later host an independent reviewer. The implementer does not run the
review.

### 4. Deterministic TDD gate
Run `bin/tdd-check` (path relative to this plugin) against the branch. A bundled-commit
finding is a BLOCKER that must be fixed (rewrite history into the test-then-impl shape)
BEFORE any review starts. Also re-run the repo's own gates (its test suite, linters,
formatters — discover them from AGENTS.md / CI config) and confirm they are green.
Never trust the implementer's claim that gates pass; verify independently.

### 5. Review panel (parallel, independent)
Open a PR (body in the required five-section format: `## Why`, `## Impact to
Stakeholders`, `## What's in this PR`, `## Notable decision`, `## Validation`). Then
run BOTH reviewer families IN PARALLEL, each independent of the implementer:
- **Claude-side reviewer(s):** `pr-review-toolkit`'s multi-lens review, or
  feature-dev's `code-reviewer` agent, or superpowers'
  `requesting-code-review` — run in a fresh context / subagent that did not write the
  code. Apply the `adversarial-review` skill's dimensions and verdict format.
- **Cross-model reviewer:** `scripts/deepseek_review.py <pr> --post` (path relative to
  this plugin) so a second model family (DeepSeek) cross-checks. Invoke the
  `multi-model-review` skill if this is the first run and setup is needed.

The CI-hosted reviewer (the bundled `templates/deepseek-review.yml` Action) also runs
per-push; let it. CI must go green.

### 6. Triage
Apply the `blocker-triage` skill to EVERY finding from EVERY reviewer, BEFORE changing
a single line: analyze-first-fix-second, expect ~30–40% of raised blockers to be
false, and check whether each issue is pre-existing on the base branch. Present the
triage table before any fix. Then apply `adversarial-review`'s inherited-vs-new-debt
rule: only defects this change INTRODUCED can block merge; pre-existing debt matching
the surrounding pattern is a SHOULD FIX, not a blocker.

### 7. Fix (serial by default; parallel clustered when disjoint)
Fix the confirmed BLOCKERs from triage. Default to ONE sequential fix agent. When the
PR came back with **many** confirmed fixes that partition into **disjoint file-clusters**,
invoke the `parallel-clustered-fixes` skill: it gates the fan-out on a heuristic
(numerous AND disjoint — stay serial when fixes overlap the same file, are small, or
must be tightly reconciled), then runs one **worktree-isolated** agent per cluster (via
the Workflow tool). The two-commit TDD cadence still holds per cluster. After merging the
worktrees back, re-run the COMBINED gate (repo test suite + `bin/tdd-check`) on the branch
— both must be green before review is considered resolved.

### 8. Findings ledger
Invoke the `findings-ledger` skill: maintain exactly ONE "📋 Review Findings Ledger"
comment on the PR — a single table (ID | Finding | Source | Severity | Status), findings
shared across reviewers deduped into one row. Update it in place; never post follow-up
comments.

### 9. Deferred → issues
Invoke the `deferred-to-issues` skill: every finding that is real and not fixed in this
PR (Deferred AND Standing) becomes a tracked GitHub issue (`gh issue create`, labeled
`deferred-review-finding`; product/design judgment gets `design-decision`). Only Fixed
and Rejected findings go untracked. Link each issue back into the ledger row.

### 10. Pause for merge
Report the PR link and a summary of the ledger, then **STOP**. Do not merge, and do not
start any follow-up work until the human merges or explicitly says to continue.

## Modes

**Interactive (default):** narrate each step, surface the plan and triage table for the
human, and pause at natural decision points (after the YAGNI gate, after the plan,
before fixing triaged findings, and at the final merge pause).

**Headless (`claude -p "/panel <feature>"`):** run the loop unattended and surface only
gate failures and review outcomes — the YAGNI verdict, a red TDD/CI gate, the triage
table, the ledger summary, and the final paused PR link. Suppress step-by-step
narration. The merge pause still holds: headless mode never merges.
