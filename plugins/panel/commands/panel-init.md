---
description: One-shot setup that wires a target repo for the full panel loop — installs the composed plugins, guarantees an architecture-covering reviewer, runs /install-github-app for the Claude reviewer, vendors the DeepSeek CI Action + review script, sets the API-key secrets, and verifies the tdd-check gate. Idempotent; interactive by default.
---

# /panel-init — wire a repo for the panel loop

You are the SUPERVISOR of a one-shot repo setup. Panel's premise is **independent review
with a deterministic TDD gate**, ideally cross-checked by a second model family — the
cross-model leg is additive and opt-out (step 4), the Claude-side floor and the gate are
not. This command makes a target repo satisfy that premise. Set up each leg below, in
order, **idempotently** —
detect what already exists and skip it, never clobber. Stay repo-agnostic; read the
target repo's own conventions.

Your working directory is the TARGET repo, not this plugin. Files referred to below as
"this plugin's `<path>`" live in the panel plugin's install directory — the directory
that contains this command file (resolve it once, e.g. `PLUGIN_ROOT`, and read the
template/script/gate files from there). Do not look for them relative to the target
repo.

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
repo slug (`gh repo view --json nameWithOwner`). Also confirm this plugin's own vendored
resources exist under `PLUGIN_ROOT` — `templates/deepseek-review.yml`,
`templates/architecture-review.yml`, `templates/tdd-gate.yml`,
`scripts/deepseek_review.py`, `bin/tdd-check` — so init
triages itself up front instead of crashing mid-run. If any precondition fails, report
exactly what's missing / what the human must do and stop.

## The setup

### 1. Composed plugins
Ensure panel's composed plugins are installed (they carry the heavy lifting):
`superpowers` (brainstorming, plans, TDD, worktrees, systematic-debugging),
`feature-dev` (the build spine), `pr-review-toolkit` (additive review lenses). Detect
what's installed by listing the plugins directory (each installed plugin has its own
subdir with a `.claude-plugin/plugin.json`) or by checking whether the skills they
provide resolve. If any are missing, print the exact `/plugin marketplace add` /
`/plugin install` commands from panel's README and have the user run them.

### 2. Architecture-covering reviewer (REQUIRED)
Verify at least one reviewer that reviews architecture/design, coupling, breaking
changes, and spec compliance is installed: superpowers' `requesting-code-review` **or**
feature-dev's `code-reviewer`. Check concretely — look for the skill/agent file in the
installed plugin dir (e.g. superpowers' `skills/requesting-code-review/SKILL.md`, or
feature-dev's `code-reviewer` agent) rather than inferring from the plugin name alone.
`pr-review-toolkit` ships NO architecture agent, so it does not count. If only `pr-review-toolkit` is present, this is a GAP — flag it loudly
and require the user to install one of the two above before setup is considered done.

### 3. Claude-side reviewers — `/install-github-app` (+ architecture)
Invoke Claude Code's built-in `/install-github-app`. It installs the Claude GitHub App,
sets `CLAUDE_CODE_OAUTH_TOKEN`, and adds two workflows under `.github/workflows/`:
`claude.yml` (the `@claude` responder) and `claude-code-review.yml` (an automatic PR
review running `/code-review` = **correctness/quality**). **Leave these untouched** —
don't edit Anthropic's provided files.

That official review does NOT do a dedicated **architecture** review, so also vendor this
plugin's `templates/architecture-review.yml` → `.github/workflows/architecture-review.yml`.
It runs `feature-dev`'s `code-reviewer` (architecture/design, coupling, breaking changes,
spec compliance) via `claude-code-action`, reusing the `CLAUDE_CODE_OAUTH_TOKEN` set
above and no-opping cleanly without it.

The rule is **one workflow per DISTINCT review function, never a duplicate**: correctness
(official `claude-code-review`) and architecture (vendored) are complementary, so both
are warranted — do not add a workflow that repeats a function already covered. Together
they are the CI counterpart to the in-session Claude reviewers the `/panel` loop runs;
either satisfies the Claude-side floor.

- **Interactive (default):** run it; the human completes the OAuth consent.
- **Headless:** you cannot complete OAuth. Detect prior setup by checking for the
  App's workflow file under `.github/workflows/` (e.g. a `claude`/`claude-code`
  workflow) — this is the reliable signal. Do NOT rely on
  `gh api /repos/{owner}/{repo}/installation`: that endpoint authenticates as the App
  (JWT) and typically 403/404s with a user token. If no workflow is found, instruct the
  user to run `/install-github-app` interactively and continue — do NOT fail the run.

### 4. DeepSeek-side reviewer (cross-model CI) — OPTIONAL
This leg is **opt-out**: cross-model review is additive, not one of panel's
non-negotiable invariants. If the developer doesn't want to configure a second provider,
ask once and, on decline, skip steps 4's secret setup — still vendor the Action (it
no-ops cleanly with no key, so it's harmless and ready if they add a key later), note
"single-provider mode" in the final checklist, and continue. The Claude-side floor
(step 2/3) remains required.

The CI Action runs `python3 scripts/deepseek_review.py` **inside the target repo's CI**,
which cannot see plugin-local paths. So **vendor** both files into the target repo:
- Copy this plugin's `templates/deepseek-review.yml` → `.github/workflows/deepseek-review.yml`.
- Copy this plugin's `scripts/deepseek_review.py` → `scripts/deepseek_review.py`.
  (The script is stdlib-only but shells out to the `gh` CLI at runtime — fine on
  GitHub-hosted runners where `gh` is preinstalled; on self-hosted runners the workflow
  must install `gh` first.)

Then set the API key secret. First **check** `gh secret list` and skip if already set —
but if the existing secret is **org-level and the target repo is public**, verify its
visibility (`gh secret list --org <org>`); a `private`-visibility org secret is silently
withheld from public repos, so re-scope it with `--visibility all` rather than assuming
"present == working". Otherwise **obtain the value** — never call `gh secret set` with no
value, it will hang on stdin:
- **Interactive:** ask the user to paste the DeepSeek API key (or read it from a
  `DEEPSEEK_API_KEY` environment variable if present), then
  `printf '%s' "$KEY" | gh secret set DEEPSEEK_API_KEY [scope]`.
- **Headless:** use the `DEEPSEEK_API_KEY` environment variable if present; if not,
  skip with a note (do not fail).

Offer BOTH scopes: **repo-level** (`--repo <owner>/<repo>`) or **org-level**
(`--org <org>`). For org scope on any **public** repo you MUST pass
`--visibility all` (or `--visibility selected --repos <list>`) — `gh` defaults org
secrets to `private` visibility, which silently withholds the key from public repos and
makes the DeepSeek reviewer no-op with no error. The vendored workflow itself no-ops
cleanly until the secret exists, so a missing key never breaks CI.

### 5. Deterministic TDD gate
CI cannot see plugin-local paths, so vendor BOTH the checker and its workflow:
- Copy this plugin's `bin/tdd-check` → `bin/tdd-check` in the target repo (`chmod +x`),
  and confirm it runs: `python3 bin/tdd-check --help`.
- Copy this plugin's `templates/tdd-gate.yml` → `.github/workflows/tdd-gate.yml`. That
  template already checks out full history (`fetch-depth: 0`, required for ancestry) and
  runs against the PR's ACTUAL base ref (`pull_request.base.sha`) — never a hardcoded
  `main`, which would misfire on any repo whose default branch isn't `main` or on PRs
  targeting a release branch.

If the repo already has a `pull_request` workflow you'd rather extend, add an equivalent
step there instead of a second workflow (never clobber the existing one). The gate must
fail a bundled-commit / broken-ancestry branch.

### 6. Verify + report
Print a checklist of every leg with its state — ✅ done / ⏭️ already present /
🚫 opted out / ⚠️ needs human action (with the exact command) / ❌ gap (e.g. no
architecture reviewer). The setup is COMPLETE when steps 2 and 5 are ✅/⏭️ and step 4 is
✅/⏭️/🚫 (opting out of cross-model counts as satisfied — single-provider mode is a valid
complete outcome); step 3 may remain ⚠️ in headless mode (the human finishes the OAuth).
End with the one-line command to run the loop: `/panel <feature>`.

## Modes

**Interactive (default):** walk each step, run `/install-github-app` live, ask before
overwriting any existing file, and offer the org-vs-repo secret choice.

**Headless (`claude -p "/panel-init"`):** do every non-interactive step (vendor files,
set secrets if a key is available in the environment, verify the gate), detect the
interactive-only ones (`/install-github-app`), and surface a final checklist of what the
human must still do. Never fail solely because an interactive step is pending.
