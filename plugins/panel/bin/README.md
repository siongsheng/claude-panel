# `bin/tdd-check` — deterministic two-commit-TDD checker

`tdd-check` inspects the commits a branch/PR adds over a base branch
(`base..head`) and verifies **two-commit TDD discipline**: a failing test
(RED) is committed *before*, and separately from, the implementation that
makes it pass (GREEN). It is a hard, deterministic gate that complements
superpowers' TDD *discipline* — where that teaches the practice, this
mechanically rejects the two ways the practice is most often broken.

Stdlib-only Python 3, no dependencies.

## What it enforces

Run over every commit in `base..head`:

1. **RED-before-GREEN by ANCESTRY, not timestamps.** A test-only commit
   (touches only test files) must be an *ancestor* of the implementation
   commit(s). If an implementation commit precedes its test commit in
   ancestry — "GREEN before RED" — that is a **BLOCKER**.
2. **No bundled commits.** A single commit that touches *both* test files and
   non-test files is a **BLOCKER**. This is the primary, most reliable check:
   split the RED test commit from the GREEN implementation commit.
3. **CSS/config-only `feat:` downgrade.** A `feat:` commit touching only
   cosmetic/config files (css, scss, json, yaml, toml, `config`, `constants`,
   …) with no test is downgraded from BLOCKER to a **SHOULD-FIX** warning
   suggesting a `chore:`/`style:` prefix. It does not fail the run.
4. **Missing test (soft).** Implementation with no preceding test commit
   anywhere in the range is a **SHOULD-FIX** warning, not a hard fail — some
   changes legitimately have no tests, but it is flagged.

Each commit is classified as one of: `test-only`, `impl-only`, `bundled`,
`cosmetic`, or `empty`, and gets a verdict of `ok`, `SHOULD-FIX`, or `BLOCKER`.

**Exit status:** `0` when clean or only SHOULD-FIX warnings; `1` on any
BLOCKER; `2` on an invalid ref / git error.

## Why ancestry, not wall-clock time

Committer and author timestamps are **not reliable**: `git rebase`,
`git commit --amend`, and cherry-picks rewrite them, and a machine's clock can
be wrong. What survives all of those is the **ancestry graph** — the
parent/child ordering of commits. `tdd-check` orders commits with
`git rev-list --topo-order --reverse` (oldest ancestor first) and never reads a
single date. So a branch that was rebased still passes as long as the test
commit remains an ancestor of the implementation.

## Run it locally

```sh
# from inside the repo, defaults: base=main head=HEAD
plugins/panel/bin/tdd-check

# explicit refs
plugins/panel/bin/tdd-check --base main --head my-feature-branch
plugins/panel/bin/tdd-check --base origin/main --head HEAD
```

## Run it in CI

Compare the PR branch against its merge base. GitHub Actions example:

```yaml
name: tdd-check
on: pull_request
jobs:
  tdd-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0            # full history so ancestry is available
      - name: Two-commit TDD check
        run: |
          git fetch origin "${{ github.base_ref }}" --depth=0
          plugins/panel/bin/tdd-check \
            --base "origin/${{ github.base_ref }}" \
            --head "${{ github.event.pull_request.head.sha }}"
```

`fetch-depth: 0` matters — a shallow clone hides the ancestry the check
depends on.

## Test-file patterns and how to extend them

Test-file detection is a documented constant near the top of `tdd-check`,
`TEST_PATH_PATTERNS` — a list of regexes matched against each path's
forward-slash form. A path is a test file if *any* pattern matches. Current
coverage:

| Pattern | Matches |
| --- | --- |
| `(^\|/)(tests?\|specs?\|__tests__\|__test__)(/\|$)` | any `test/`, `tests/`, `spec/`, `__tests__/` directory (covers Rust `tests/*.rs`, Ruby `spec/`, etc.) |
| `(^\|/)test_[^/]+\.py$` | Python `test_foo.py` |
| `(^\|/)[^/]+_test\.[^/]+$` | Go `foo_test.go`, Python `foo_test.py`, … |
| `(^\|/)[^/]+\.test\.[^/]+$` | JS/TS `foo.test.ts` |
| `(^\|/)[^/]+\.spec\.[^/]+$` | JS/TS `foo.spec.tsx` |
| `(^\|/)[^/]+_spec\.[^/]+$` | Ruby `foo_spec.rb` |
| `(^\|/)[^/]+Tests?\.(java\|kt\|kts\|cs\|scala)$` | Java/Kotlin/C#/Scala `FooTest.java`, `FooTests.kt` |

To add a language, append one regex to `TEST_PATH_PATTERNS`. Cosmetic/config
detection is likewise a pair of constants, `COSMETIC_EXTENSIONS` (extensions)
and `COSMETIC_NAME_HINTS` (basename substrings) — extend either.

## Architecture / testability

All classification lives in the **pure** function
`classify_commits(commits) -> Report`, where `commits` is a list of dicts
`{sha, message, files}` in ancestry order (oldest first). It touches no git
and no I/O, so it is unit-tested with hand-built fixtures. Git plumbing
(`collect_commits`, `_git`, …) is isolated from it.

## Tests

`test_tdd_check.py` runs two ways (pytest optional — it is `unittest`-based):

```sh
python3 plugins/panel/bin/test_tdd_check.py     # plain, no deps
python3 -m pytest plugins/panel/bin/test_tdd_check.py
```

It covers the pure helpers with fixtures (RED→GREEN clean, bundled BLOCKER,
missing-test SHOULD-FIX, CSS-feat downgrade, GREEN-before-RED BLOCKER,
multi-language test-file detection) plus integration tests that build a
throwaway git repo in a tempdir and run the real script for passing,
bundled-failing, and invalid-ref cases.
