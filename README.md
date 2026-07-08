# claude-panel

A Claude Code plugin for **prevention-first agentic development**. It doesn't reinvent the development workflow — it wraps Anthropic's official [`feature-dev`](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/feature-dev) plugin and adds the layers that stop the common failure modes of autonomous coding:

- **A YAGNI gate *before* code exists** (`ponytail-guard`) — a 7-rung ladder that asks "does this need to exist? is it already in the codebase? does the stdlib do it?" before a spec is written. Overbuilding is the #1 agentic-dev failure; this catches it at the source.
- **Spec discipline** (`spec-strategist`) — a template that forces a Test Plan (concrete edge cases + failure modes), a Risk Register, an explicit Anti-Creep section, and a COTS build-vs-buy check.
- **Deterministic two-commit TDD** (`bin/tdd-check`) — verifies a test-only commit is an *ancestor* of its implementation commit and rejects bundled commits. Ancestry-based, so it survives rebase (wall-clock timestamps don't).
- **Cross-model adversarial review** — an independent Claude reviewer *plus* a DeepSeek reviewer, so findings are cross-checked by two model families with different blind spots.
- **Reviewer skepticism** (`blocker-triage`) — ~30-40% of raised blockers are false; analyze-first-fix-second with an explicit triage table, and an **inherited-vs-new-debt** rule so pre-existing issues get a tracked issue instead of blocking your PR.
- **One findings ledger** — every reviewer's findings in a single edited-in-place table per PR, and every real-but-unfixed finding becomes a tracked GitHub issue.

## Install

```
/plugin marketplace add siongsheng/claude-panel
/plugin install panel@claude-panel
```

Recommended companions from the official marketplace (the panel composes these):

```
/plugin install feature-dev@claude-plugins-official
/plugin install pr-review-toolkit@claude-plugins-official
/plugin install code-simplifier@claude-plugins-official
```

## Use

- `/panel <feature description>` — run the full loop: YAGNI gate → spec → feature-dev build → TDD gate → cross-model review → triage → ledger → pause for merge.
- Individual skills auto-trigger by context, or invoke explicitly: `/panel:ponytail-guard`, `/panel:spec-strategist`, `/panel:blocker-triage`, `/panel:adversarial-review`.

## Attribution

`ponytail-guard` is based on the ponytail ladder (DietrichGebert/ponytail, MIT).

## Status

MVP under construction. See the marketplace manifest for the shipped skill set.
