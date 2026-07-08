---
name: multi-model-review
description: Cross-model-family PR review — run an independent Claude reviewer (fresh context) AND scripts/deepseek_review.py (DeepSeek) so two model families cross-check the same diff. Covers DEEPSEEK_API_KEY setup and the bundled GitHub Action. Use when setting up or running review on a PR.
---

# Multi-Model Review

A single model has blind spots that are correlated across its own runs — asking the same
model family twice mostly re-confirms its first read. Panel's default is to review a PR
with TWO independent model families so their blind spots don't overlap (the cross-model
family is additive and opt-out — a single-provider repo runs the Claude-side family
alone, and the ledger records the skip):

1. **A Claude-side reviewer** in a FRESH context (an independent subagent, or
   `pr-review-toolkit` / feature-dev's `code-reviewer`) that did NOT write the code.
2. **A DeepSeek reviewer** via `scripts/deepseek_review.py <pr> --post` (default model
   `deepseek-v4-pro`), a different model family entirely.

Run them in parallel. Each is independent of the implementer (implementer ≠ reviewer).
Feed BOTH reviewers' output into `blocker-triage`, then consolidate into one row-per-
finding via `findings-ledger` (findings both families raise dedupe into a single row
listing both sources).

This **complements** the Claude-side reviewers; it does not replace them. DeepSeek is the
cross-check, not the sole reviewer.

## Coverage: which family reviews which dimension

Both **correctness** and **architecture** get a Claude-family AND a cross-model opinion —
so neither dimension rests on a single model's blind spots:

| Dimension | Claude family | Cross-model (DeepSeek) |
|-----------|---------------|------------------------|
| Correctness / bugs / quality | official `claude-code-review` (`/code-review`) | ✅ DeepSeek |
| Architecture / coupling / breaking changes / spec | universal architecture floor (CI: `architecture-review.yml`) | ✅ DeepSeek (architecture lens) |

Note: the official `/code-review` does NOT do a dedicated architecture review, which is
why the architecture lens is a distinct Claude workflow — one workflow per distinct
function, never a duplicate. That workflow is a repo-agnostic `claude-code-action` prompt
distilling the stable patterns from surveyed architecture-review skills (dep-direction/
hexagonal rubric, complexity thresholds, ADR/decision lens, disciplined high-signal
findings); `/panel-init` can additionally suggest a stack-matched skill as an opt-in
upgrade. In-session, the `/panel` loop runs the equivalent Claude reviewers directly.

## The DeepSeek reviewer

`scripts/deepseek_review.py` (stdlib-only Python) fetches the PR metadata and unified
diff via `gh`, sends them to DeepSeek with a repo-agnostic review prompt (it reads the
target repo's own AGENTS.md / CLAUDE.md / CONTRIBUTING conventions and applies generic
engineering lenses), and prints the review. With `--post` it creates or updates ONE
idempotent comment on the PR (matched by a comment marker), so per-push runs refresh a
single comment instead of spamming.

```
python3 scripts/deepseek_review.py <pr-number> [--post] [--model MODEL]
```

## Setup

1. **API key.** `DEEPSEEK_API_KEY` from the environment (or a `.env` the script reads).
   For CI, store it as a repo secret: `gh secret set DEEPSEEK_API_KEY`. The key never
   appears in output. If it is unset, both the script and the Action no-op cleanly rather
   than failing.

2. **GitHub Action (optional, for per-push CI review).** Copy
   `templates/deepseek-review.yml` into the target repo's `.github/workflows/`. It runs
   on pull-request events with least-privilege permissions (`contents: read`,
   `pull-requests: write`), one run per PR with in-progress cancellation, and skips with
   a notice until the `DEEPSEEK_API_KEY` secret is set. Ensure `scripts/deepseek_review.py`
   is present in the target repo (or adjust the workflow's path to the plugin copy).

## Pitfalls

- Do not let the same context both implement and review — that defeats the point. The
  Claude reviewer must be a fresh context.
- The DeepSeek comment is idempotent; do not "clean up" by deleting it between runs — let
  the script update it in place.
- Two families raising the same finding is signal, not duplication — dedupe them into one
  ledger row but note both sources.
