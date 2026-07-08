---
name: deferred-to-issues
description: Turn every real-but-unfixed review finding into a tracked GitHub issue — Deferred and Standing findings get an issue (labeled deferred-review-finding); product/design calls get design-decision; only Fixed and Rejected go untracked. Use when a review produces valid findings that will not be fixed in the current change.
---

# Deferred → Issues

The rule is simple and absolute: **every finding that is real and not fixed in this
change gets a tracked GitHub issue.** The only findings that stay untracked are the ones
already resolved (Fixed) and the ones that were never real (Rejected). Anything valid you
choose not to fix here MUST land in an issue, or it silently disappears.

## What gets an issue

| Disposition | Issue? | Label |
|-------------|--------|-------|
| **Deferred** — valid, belongs to later work | Yes | `deferred-review-finding` |
| **Standing** — real pre-existing defect this change did not cause | Yes | `deferred-review-finding` |
| **Owner decision** — product / design judgment | Yes | `design-decision` |
| Fixed in this change | No | — |
| Rejected (false positive) | No | — |

**Standing is the trap.** A Standing finding is a genuine defect that already existed on
the base branch — out of scope to fix in this change, but still a real bug. It is easy to
log it as a ledger note and move on; don't. Standing findings get an issue exactly like
Deferred ones. If you didn't fix it and it's real, it is tracked.

**Design/product judgment never blocks.** When a finding is really a decision the owner
should make (a tradeoff, a scope question, a UX call), file it with the `design-decision`
label and leave it for the owner. It does not gate the merge.

## Filing

```
gh issue create \
  --title "<terse finding>" \
  --label deferred-review-finding \
  --body "<what, where (file:line), why it's real, why deferred, link back to the PR>"
```

- Ensure the label exists first (`gh label create deferred-review-finding` if needed;
  same for `design-decision`).
- Reference the originating PR in the body so the trail is bidirectional.
- If an issue already covers this area, extend it (add a checklist item) rather than
  opening a duplicate.
- Put the resulting issue number back into the `findings-ledger` row (`📋 Deferred → #N`
  / `📌 Standing → #N` / `🤔 Owner decision → #N`).

## Pitfalls

- Do not fix a Deferred finding just to avoid filing an issue — scope creep. If it's out
  of scope, track it and move on.
- Do not batch several unrelated findings into one issue; one tracked defect per issue
  keeps them actionable and closeable.
- Rejected means you can explain WHY it's a false positive. If you can't, it isn't
  rejected — it's Standing or Deferred, and it gets an issue.
