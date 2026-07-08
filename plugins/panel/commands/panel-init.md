---
description: One-shot setup that wires a target repo for the full panel loop — installs the composed plugins, guarantees an architecture-covering reviewer, runs /install-github-app for the Claude reviewer, vendors the DeepSeek CI Action + review script, sets the API-key secrets, and verifies the tdd-check gate. Idempotent; interactive by default.
---

# /panel-init — wire a repo for the panel loop

You are the SUPERVISOR of a one-shot repo setup. Panel's premise is **two review
families with different blind spots** plus a deterministic TDD gate; this command makes
a target repo satisfy that premise. Set up each leg below, in order, **idempotently** —
detect what already exists and skip it, never clobber. Stay repo-agnostic; read the
target repo's own conventions.

## Invariants (non-negotiable)

- **Idempotent.** Before every step, check whether its artifact already exists (plugin
  installed, workflow file present, secret set, App installed, gate reachable). If it
  does, report "already present" and move on. Re-running `/panel-init` must be safe.
- **Never clobber.** If a file exists but differs from the template, show the diff and
  ask before overwriting — do not silently replace a repo's existing workflow.
- **Architecture coverage is REQUIRED.** The setup is not complete unless a reviewer
  that actually reviews architecture is installed (see step 2). `pr-review-toolkit`
  alone does NOT satisfy this.
- **`/install-github-app` is interactive and cannot be forced headless** (it needs a
  browser OAuth consent + repo-admin approval). Headless runs detect-and-instruct; they
  never fail the run just because the App isn't installed.

## Preflight

Confirm: `gh auth status` is authenticated, the working directory is the target git
repo, and the user has admin on the repo (secrets + App install need it). Determine the
repo slug (`gh repo view --json nameWithOwner`). If any precondition fails, report
exactly what the human must do and stop.

## The setup

### 1. Composed plugins
Ensure panel's composed plugins are installed (they carry the heavy lifting):
`superpowers` (brainstorming, plans, TDD, worktrees, systematic-debugging),
`feature-dev` (the build spine), `pr-review-toolkit` (additive review lenses). If any
are missing, print the exact `/plugin marketplace add` / `/plugin install` commands
from panel's README and have the user run them.

### 2. Architecture-covering reviewer (REQUIRED)
Verify at least one reviewer that reviews architecture/design, coupling, breaking
changes, and spec compliance is installed: superpowers' `requesting-code-review` **or**
feature-dev's `code-reviewer`. `pr-review-toolkit` ships NO architecture agent, so it
does not count. If only `pr-review-toolkit` is present, this is a GAP — flag it loudly
and require the user to install one of the two above before setup is considered done.

### 3. Claude-side reviewer — `/install-github-app`
Invoke Claude Code's built-in `/install-github-app`. It installs the Claude GitHub App,
adds its workflow, and sets `ANTHROPIC_API_KEY` so `@claude` works on PRs/issues.
- **Interactive (default):** run it; the human completes the OAuth consent.
- **Headless:** you cannot complete OAuth. Detect whether the App/workflow already
  exist (`gh api /repos/{owner}/{repo}/installation` or check for the workflow file);
  if absent, instruct the user to run `/install-github-app` interactively and continue
  — do NOT fail the run.

### 4. DeepSeek-side reviewer (cross-model CI)
The CI Action runs `python3 scripts/deepseek_review.py` **inside the target repo's CI**,
which cannot see plugin-local paths. So **vendor** both files into the target repo:
- Copy this plugin's `templates/deepseek-review.yml` → `.github/workflows/deepseek-review.yml`.
- Copy this plugin's `scripts/deepseek_review.py` → `scripts/deepseek_review.py`.
Then set the API key secret: `gh secret set DEEPSEEK_API_KEY`. Offer BOTH scopes —
**org-level** (`--org <org>`, one secret covers all repos) or **repo-level** — and skip
if it is already set (`gh secret list`). The vendored workflow no-ops cleanly until the
secret exists, so a missing key never breaks CI.

### 5. Deterministic TDD gate
Make `bin/tdd-check` reachable to the repo's CI (CI cannot see plugin-local paths
either): vendor `bin/tdd-check` into the target repo (e.g. `bin/tdd-check`) or add a CI
step that fetches it, and confirm it runs (`python3 bin/tdd-check --help`). Wire it into
the repo's PR CI so a bundled-commit / broken-ancestry branch fails the gate.

### 6. Verify + report
Print a checklist of every leg with its state — ✅ done / ⏭️ already present / ⚠️ needs
human action (with the exact command) / ❌ gap (e.g. no architecture reviewer). The
setup is COMPLETE only when steps 2, 4, and 5 are ✅/⏭️; step 3 may remain ⚠️ in
headless mode (the human finishes the OAuth). End with the one-line command to run the
loop: `/panel <feature>`.

## Modes

**Interactive (default):** walk each step, run `/install-github-app` live, ask before
overwriting any existing file, and offer the org-vs-repo secret choice.

**Headless (`claude -p "/panel-init"`):** do every non-interactive step (vendor files,
set secrets if a key is available in the environment, verify the gate), detect the
interactive-only ones (`/install-github-app`), and surface a final checklist of what the
human must still do. Never fail solely because an interactive step is pending.
