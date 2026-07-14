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

Implement following strict two-commit TDD — drive it with superpowers'
`test-driven-development` skill (the RED-GREEN-REFACTOR discipline); panel's own
`bin/tdd-check` (step 4) only *enforces* the resulting commit shape, it does not teach
the cycle:
- A `test:` commit lands FIRST — failing tests that pin the intended behavior.
- A `feat:` commit lands SECOND — the implementation that makes them pass.
- The `test:` commit MUST be a git **ancestor** of the `feat:` commit (ancestry, not
  wall-clock time — this is what the gate in step 4 verifies).
- A single bundled commit (tests + implementation together) is a BLOCKER.

Prefer having an implementer subagent do the code so the supervising context stays
clean and can later host an independent reviewer. The implementer does not run the
review.

If a test won't pass or behavior is wrong, have the implementer invoke superpowers'
`systematic-debugging` skill to find the root cause before editing — never guess at
fixes.

### 4. Deterministic TDD gate
Run `bin/tdd-check` (path relative to this plugin) against the branch. A bundled-commit
finding is a BLOCKER that must be fixed (rewrite history into the test-then-impl shape)
BEFORE any review starts. Also re-run the repo's own gates (its test suite, linters,
formatters — discover them from AGENTS.md / CI config) and confirm they are green.
Never trust the implementer's claim that gates pass; verify independently.

### 5. Review panel (parallel, independent)
Open a PR (body in the required five-section format: `## Why`, `## Impact to
Stakeholders`, `## What's in this PR`, `## Notable decision`, `## Validation`). Then run
the reviewer families IN PARALLEL, each independent of the implementer. The Claude-side
family is the **mandatory floor**; the cross-model family is **additive and opt-out**
(see below):
- **Claude-side reviewer(s):** run in a fresh context / subagent that did not write
  the code, and apply the `adversarial-review` skill's dimensions and verdict format.
  These reviewers are NOT interchangeable for architecture — cover BOTH:
  - **Architecture/spec (REQUIRED):** superpowers' `requesting-code-review` or
    feature-dev's `code-reviewer` agent — these are the only ones that review
    architecture & design, coupling/separation, breaking changes, and plan/spec
    compliance. One of them MUST run.
  - **Additive lenses (recommended):** `pr-review-toolkit`'s multi-lens review for its
    specialties (type-design, silent-failure, test-gap, comment accuracy). It does
    NOT review system architecture, so it is an *addition* to the required reviewer
    above, never a substitute for it.
- **Cross-model reviewer (additive, OPT-OUT):** `scripts/deepseek_review.py <pr> --post`
  (path relative to this plugin) so a second model family (DeepSeek) cross-checks with
  different blind spots. Invoke the `multi-model-review` skill if this is the first run
  and setup is needed. **A developer who doesn't want to configure a second provider may
  skip this** — it is NOT one of the non-negotiable invariants. With no
  `DEEPSEEK_API_KEY` configured, the CI Action no-ops and stays green, so skipping never
  fails a gate. When you skip it, say so: the Claude-side floor (including the REQUIRED
  architecture reviewer) still runs, but you forfeit the second-model blind-spot
  coverage — record the skip in the findings ledger so the reduced coverage is visible,
  not silent.

The CI-hosted reviewer (the bundled `templates/deepseek-review.yml` Action) also runs
per-push when a `DEEPSEEK_API_KEY` secret is set; let it. CI must go green (the Action
no-ops green when no key is set, so single-provider repos are unaffected).

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

For any finding whose root cause isn't obvious — a failing test, a regression, wrong
behavior — apply superpowers' `systematic-debugging` before editing, as in step 3.

### 8. Findings ledger (background agent — waits for CI, then composes)
Invoke the `findings-ledger` skill to maintain exactly ONE "📋 Review Findings Ledger"
comment on the PR — a single table (ID | Finding | Source | Severity | Status), findings
deduped across reviewers into one row, updated in place, never a follow-up comment.

**The supervising agent — not the CI auto-ledger — is the primary author here.** It has
strictly more context than the CI job: it holds THIS loop's in-session subagent reviews
(step 5), which are never posted as PR comments and which the CI ledger therefore cannot
see. So compose the ledger from BOTH the in-session reviews AND the CI reviewers' comments.

Because the CI reviewers (DeepSeek, architecture, official `/code-review`) finish
asynchronously, run this as a **background agent** so the loop is not blocked. This one
agent is the **SINGLE in-session writer** of the ledger comment — it also files the
deferred issues (step 9) so there is never a second concurrent writer racing it on the
one sticky comment:

1. **Spawn a background agent** (the Agent tool) carrying this loop's in-session findings.
2. It **waits** (bounded poll on `gh pr checks` / the Actions run status) until the CI
   reviewer checks complete.
3. It **gathers** every CI reviewer comment, **merges** them with the in-session findings
   (dedupe, one row per finding — capture non-blocking Suggestions/Nits too), triages via
   `blocker-triage`, and composes the cumulative ledger + audit log.
4. It **files the deferred/standing issues** (step 9's `deferred-to-issues` policy) — the
   in-session agent HAS `gh`, so it creates the real issues and writes linked
   `📋 Deferred → [#N](url)` rows (the `⚠️ Needs issue` placeholder is only the *CI*
   fallback's honest state, never this agent's, since this agent can actually file).
5. It **stamps the authorship sentinel** as the last line of the ledger body:
   `<!-- ledger: author=panel-agent sha=<PR head SHA> -->`
   (resolve the head SHA with `gh pr view <pr> --json headRefOid`). This is how the CI
   auto-ledger knows to **stand down** — it defers to a current agent-authored ledger for
   the same head SHA and only takes over when there is none (an un-driven PR, or a later
   push that changes the SHA). No double-post: both write the ONE sticky comment.
6. It **posts** via `scripts/post_sticky_comment.py <pr> --marker '## 📋 Review Findings
   Ledger' --body-file <file>` (path relative to this plugin) — the same deterministic,
   marker-asserting poster the CI path uses.

The loop is not blocked *during* the wait — you keep working while the agent polls CI. But
steps 9 and 10 **depend on this agent's output**, so they do not run concurrently with it:
step 9 IS performed inside this agent (item 4 above), and step 10 **awaits** it. (Note: a
background agent lives only as long as this session — that's exactly why the CI auto-ledger
remains the fallback for PRs no one is driving with `/panel`.)

### 9. Deferred → issues (performed by the step-8 agent — one writer)
The `deferred-to-issues` policy is applied **inside** the step-8 background agent, not as a
separate concurrent pass: every finding that is real and not fixed in this PR (Deferred AND
Standing) becomes a tracked GitHub issue (labeled `deferred-review-finding`; product/design
judgment gets `design-decision`; only Fixed and Rejected go untracked), filed via the
`creating-github-issues` mechanics (dedup search first), and linked back into its ledger row
`📋 Deferred → [#N](url)` **before the ledger is posted**. Folding filing into the single
ledger writer is deliberate: it keeps ONE writer on the sticky comment, so the link-backs
can't race the compose.

### 10. Pause for merge
**Await the step-8 background agent** (so the ledger is posted and the deferred issues are
filed + linked), then report the PR link and the ledger summary and **STOP**. Do not merge,
and do not start any follow-up work until the human merges or explicitly says to continue.
(If the human wants to move on before the agent settles, report the PR link immediately and
note the ledger is finalizing asynchronously — but never claim a ledger summary you haven't
confirmed is posted.)

## Modes

**Interactive (default):** narrate each step, surface the plan and triage table for the
human, and pause at natural decision points (after the YAGNI gate, after the plan,
before fixing triaged findings, and at the final merge pause).

**Headless (`claude -p "/panel <feature>"`):** run the loop unattended and surface only
gate failures and review outcomes — the YAGNI verdict, a red TDD/CI gate, the triage
table, the ledger summary, and the final paused PR link. Suppress step-by-step
narration. The merge pause still holds: headless mode never merges.
