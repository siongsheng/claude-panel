---
name: adversarial-review
description: Review a diff or PR adversarially, ideally from a different model/context than the implementer. Use this when reviewing changes for merge — it checks spec compliance, architectural impact, and code quality; separates inherited debt from newly introduced debt; and ends in a single VERDICT/RISK call. Trigger when asked to review a diff, PR, or branch before merge.
---

# Adversarial Review

A structured review of a change, ideally performed from a different model or a
fresh context than the one that wrote the code (a same-context reviewer is
biased — it saw every step and assumes correctness).

## Pre-Review: TDD Verification

Before reading the code, verify the two-commit TDD pattern:
- There must be a `test:` commit and a separate `feat:` commit.
- The `test:` commit must be an **ancestor** of the `feat:` commit in the git graph (this is what `bin/tdd-check` verifies — ancestry, not wall-clock timestamps).
- A single bundled commit (tests + implementation together) is a BLOCKER regardless of code quality.

**TDD false-positive nuance:** A `feat:`-prefixed commit that changes only CSS, config, or other non-behavioral files does not need a preceding test commit. Don't treat a missing test as a BLOCKER there — instead note that the commit should have been prefixed `chore:` or `style:`. Downgrade to a NIT/SHOULD FIX on the commit message, not a BLOCKER on the change.

## Three Review Dimensions

### 1. Spec Compliance
- Does the approach match the decision the spec settled on?
- Does the API / interface match the proposal?
- Are ALL tasks completed?
- Any scope creep (code not in the spec)?
- README / docs updated if the spec required it?

### 2. Architectural Impact
- New dependencies or coupling introduced?
- Breaking changes to API, DB schema, or types?
- Deployment impact?

### 3. Code Quality
- Correctness: does it do what it claims?
- Security: injection vectors, exposed secrets, missing auth?
- Error handling: edge cases, null checks, uncaught exceptions?
- Performance: N+1 queries, blocking calls where async is needed?

## Severity

| Level | When | Action |
|-------|------|--------|
| **BLOCKER** | Spec violation, architecture break, TDD violation, missing guards, security hole, uncaught exceptions, missing README update the spec required | Fix before merge |
| **SHOULD FIX** | Conventions, naming, redundant code, pre-existing pattern debt | File an issue |
| **NIT** | Formatting, comments, style | Optional |

## Judgment: Inherited vs New Debt

Pre-existing issues matching surrounding codebase pattern → SHOULD FIX, don't block. Only BLOCKER issues INTRODUCED by this change block merge.

## Output Format

Emit exactly one final verdict — do not scatter multiple conflicting verdicts through the review.

```
## Adversarial Review

### Pre-Review: TDD Check
- test: commit <hash>
- feat: commit <hash>
- Ancestry (test is ancestor of feat): PASS / FAIL
- Verdict: PASS / BLOCKED

### Spec Compliance
| Severity | Finding | Location |

### Architectural Impact
| Severity | Finding | Location |

### Code Quality
| Severity | Finding | Location |

### Verdict
VERDICT: APPROVED / CHANGES REQUESTED / BLOCKED
RISK: LOW / MEDIUM / HIGH
```
