# claude-panel

A Claude Code plugin for **prevention-first agentic development**. It is a deliberately **thin layer** — it does not reinvent brainstorming, planning, TDD, worktrees, or debugging (mature plugins already do those). It **composes** [`superpowers`](https://github.com/obra/superpowers) and the official [`feature-dev`](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/feature-dev), and adds only the five things neither of them has:

- **A YAGNI gate *before* code exists** (`ponytail-guard`) — a concrete 7-rung ladder ("does this need to exist? already in the codebase? stdlib does it?") applied before a spec is written and again as a post-build overbuild review. Sharper than a general "keep it simple" ethos.
- **Reviewer skepticism** (`blocker-triage`) — ~30-40% of raised blockers are false; analyze-first-fix-second with a mandatory triage table, plus a **pre-existing-check** so inherited debt doesn't block your change.
- **Inherited-vs-new-debt** (`adversarial-review`) — only issues *introduced* by a change block merge; pre-existing pattern debt gets a tracked issue instead. Plus spec-compliance / architecture / quality dimensions and a single VERDICT.
- **Cross-model-family review** (`scripts/deepseek_review.py` + Action) — an independent DeepSeek reviewer alongside Claude reviewers, so findings are cross-checked by two model families with different blind spots. Everything else in the ecosystem is Claude-only.
- **Deterministic two-commit TDD** (`bin/tdd-check`) — verifies a test-only commit is an *ancestor* of its implementation commit and rejects bundled commits. Ancestry-based, so it survives rebase (wall-clock timestamps don't) — a hard gate complementing superpowers' TDD *discipline*.

Plus a **findings-ledger** discipline (one edited-in-place table per PR, with an append-only audit log of who changed what), **creating-github-issues** (dedup-first, template-aware, actionable issue filing), and **deferred→issues** (every real-but-unfixed finding becomes a tracked GitHub issue).

## Install

```
/plugin marketplace add siongsheng/claude-panel
/plugin install panel@claude-panel
```

Panel composes these — install them too:

```
/plugin marketplace add obra/superpowers                    # brainstorming, plans, TDD, worktrees, systematic-debugging
/plugin install superpowers@superpowers
/plugin marketplace add anthropics/claude-plugins-official  # official plugin marketplace
/plugin install feature-dev@claude-plugins-official         # Understand → Design → Implement → Review spine
/plugin install pr-review-toolkit@claude-plugins-official   # Claude-side review lenses
```

## Use

- `/panel-init` — one-shot setup that wires a repo for the loop: installs the composed plugins, guarantees an architecture-covering reviewer, runs `/install-github-app` (Claude reviewer), vendors the DeepSeek CI Action + review script, sets the API-key secrets, and verifies the `tdd-check` gate. Idempotent; interactive by default.
- `/panel <feature description>` — run the full loop: YAGNI gate → (superpowers/feature-dev build) → TDD gate → cross-model review → triage → fix (serial, or **parallel clustered** when findings are numerous and file-disjoint) → ledger → pause for merge.
- Individual skills auto-trigger by context, or invoke explicitly: `/panel:ponytail-guard`, `/panel:blocker-triage`, `/panel:adversarial-review`, `/panel:parallel-clustered-fixes`.

The `parallel-clustered-fixes` skill fans the fix stage out — one **worktree-isolated** agent per disjoint file-cluster (via the Workflow tool) — but only when it pays off; small or overlapping fixes stay serial, and the combined branch must still pass `bin/tdd-check`.

**After updating the plugin, re-run `/panel-init`.** The CI reviewers (Claude, DeepSeek, architecture, tdd-gate) are **vendored** into each repo's `.github/workflows/` — a plugin update refreshes the *templates*, not the copies already in your repo. Re-running `/panel-init` is idempotent (it adds newly-shipped CI reviewers and skips what's present), so it's how an existing repo picks up new checks like the architecture review. The in-session `/panel` loop, by contrast, upgrades immediately with the plugin.

## In CI, automatically

Once wired, the panel runs on every PR without anyone driving a `/panel` session:

- **Reviewers post their own findings.** The architecture reviewer edits **one sticky comment** (posting a clean "no issues found" when sound, so a silent reviewer is never mistaken for a clean one), and DeepSeek posts its cross-model review.
- **The findings-ledger posts itself** once all reviewers finish — a single triaged, cumulative table that merges across re-runs. It composes on a small model and posts deterministically, so it stays cheap.
- **Advisory, never blocking.** Reviewer/ledger steps surface problems loudly (`::error::`/`::warning::`) but never fail the build; the only hard gate is the deterministic `bin/tdd-check`.

## Attribution

`ponytail-guard` is based on the ponytail ladder (DietrichGebert/ponytail, MIT).

## Status

MVP under construction. See the marketplace manifest for the shipped skill set.
