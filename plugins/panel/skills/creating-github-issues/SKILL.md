---
name: creating-github-issues
description: File a well-formed, non-duplicate GitHub issue — search open issues FIRST (extend, don't duplicate), match the repo's issue template and title style, and write an actionable body (problem, repro, file:line, severity, definition-of-done) with a link back to its source. Use whenever you need to create a GitHub issue — a bug you found, a feature request, a TODO, or a tracked follow-up.
---

# Creating GitHub issues

A good issue is **findable, non-duplicate, and actionable** — someone (a human or an
agent) can pick it up and know when it's done. A bare `gh issue create --title --body`
gives you none of that: it duplicates freely, ignores the repo's template, and files a
vague paragraph. This skill is the discipline the CLI leaves out.

The one rule that matters most: **search before you create.** Everything else is
structure.

## 1. Dedup — search FIRST, always (hard gate)

Before creating anything, search the repo's **open** issues for the same problem:

```
gh search issues "<stable keywords>" --repo <owner>/<repo> --state open
```

(or equivalently `gh issue list --repo <owner>/<repo> --search "<keywords>" --state open`.
Note: there is no `gh issue search` subcommand — use one of these two forms.)

- Key the search on a **stable signal**, not a fuzzy title: the `file:line`, the error
  signature / rule-id, the symbol name, the failing command.
- **Match OPEN issues only.** A closed issue for the same thing may be intentionally
  closed (wontfix, already shipped) — reopening the topic there needs judgment; a stale
  closed match is not a duplicate.
- **If a match exists → extend it, don't duplicate.** Add a comment (or a checklist item)
  to the existing issue with the new occurrence/context, and STOP. Report the existing
  issue number instead of a new one.
- Only when there is no open match do you create.

Skipping this is how a repo accumulates five issues for one bug. It is not optional.

## 2. Title — natural language, repo style

- Descriptive and specific: a reader should know the problem from the title alone.
- **No conventional-commit prefixes** (`feat:` / `fix:` / `chore:`) — those are for
  commits, not issues.
- Match the existing repo's title conventions (scan a few open issues first).

## 3. Body — template-aware, actionable

**Check for a repo template first:** if `.github/ISSUE_TEMPLATE/` exists, pick the
matching template (bug vs feature vs …), fill EVERY required section, and preserve its
headers and order. `gh issue create` does NOT apply templates automatically — you must
read the template dir yourself and also pass its default labels explicitly (see §4).

If there is no template, use this default structure:

- **Problem / summary** — one or two lines: what's wrong or wanted, and the impact.
- **Reproduction / context** — for a bug: the exact command, expected vs actual. For a
  feature: the motivating scenario.
- **Where** — specific `file:line` references, not module names.
- **Severity** — the triaged severity (BLOCKER / SHOULD FIX / NIT, or the repo's scale).
- **Definition of done** — acceptance criteria as explicit pass/fail checks ("`bin/x`
  exits 0 on a bundled commit", "the flag is removed", "test added covering Y"). This is
  what makes the issue actionable by a human OR an agent.
- **Links** — the originating PR / commit / review comment, so the trail is bidirectional.

Do **not** add `- [ ]` checklists unless the template calls for them or the user asks —
they create noise and false "progress."

## 4. Labels — validate and ensure-exist

- `--label` fails on a label that doesn't exist. Validate against `gh label list`; create
  a missing one you intend to use (`gh label create <name>`).
- Apply the template's default labels **explicitly** — `gh` won't add them for you.

## 5. Metadata — apply what the repo supports, degrade gracefully

- `--assignee @me` (or a validated collaborator), `--milestone`, org issue-types — use
  them when the repo has them; skip silently when it doesn't. Never fail the filing
  because an optional feature is absent on a user repo.

## 6. Traceability & scope

- **One defect / request per issue** — keep issues actionable and closeable. Don't batch
  unrelated findings into one.
- Backlink the source (PR/commit/`file:line`); use a closing keyword ("Closes #N") only
  when a change actually resolves it.

## Filing (once dedup passes)

```
gh issue create \
  --title "<natural, specific title>" \
  --label "<validated labels>" \
  --body "<structured body per §3>"
```

Report the new issue number back to whatever referenced it (e.g. a `findings-ledger`
row, a plan, or the caller).

## Pitfalls

- **Creating before searching.** The dedup gate is the whole point; a fast `gh issue
  create` that duplicates is worse than no skill.
- **Dedup against closed issues.** Match open only; a closed duplicate needs a human call.
- **Assuming the template applied.** It didn't — you filled it and passed its labels.
- **A vague body.** "X is broken" with no repro, no `file:line`, no definition-of-done is
  not actionable. If you can't state how you'd know it's fixed, sharpen it before filing.
- **Conventional-commit prefixes in the title.** Issues are not commits.

## Related

- `deferred-to-issues` — the review-finding **specialization** of this skill: it decides
  WHICH findings must become issues (Deferred / Standing / Owner-decision) and with which
  panel labels, then files them using the mechanics here (dedup, title, body, labels).
- `findings-ledger` — records the resulting issue number in the finding's row so the
  ledger and the issue point at each other.
