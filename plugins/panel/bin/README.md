# `bin/tdd-check` — deterministic two-commit-TDD checker

`tdd-check` inspects the commits a branch/PR adds over a base branch
(`base..head`) and verifies **two-commit TDD discipline**: a failing test
(RED) is committed *before*, and separately from, the implementation that
makes it pass (GREEN). It is a hard, deterministic gate that complements
superpowers' TDD *discipline* — where that teaches the practice, this
mechanically rejects the two ways the practice is most often broken.

Stdlib-only Python 3, no dependencies.

## Classification is prefix-primary, path-secondary

The **conventional-commit prefix is the primary classifier** of a commit's
role; the file paths it touches are only a corroborating signal.

| Prefix | Role |
| --- | --- |
| `test:` / `test(scope):` | **TEST (RED)** |
| `feat:` `fix:` `perf:` `refactor:` | **IMPL (GREEN)** |
| `chore:` `style:` `docs:` `build:` `ci:` | **cosmetic / non-code** (excluded from the RED/GREEN discipline) |
| unrecognized / no prefix | inferred from file paths (test-path-only → test, cosmetic-only → cosmetic, else impl) |

**Why prefix, not path?** Many languages **co-locate** unit tests with source:
Rust puts `#[cfg(test)] mod tests` *inside* `src/foo.rs`; Python often keeps
tests (and doctests) beside the code. A path-only classifier calls every such
commit "impl", never sees the tests, reports *"no test commit found"*, and
**silently passes for the wrong reason** — a no-op that gives false assurance
on any Rust/Python repo. (This is exactly what happened dogfooding edge-radar
M3: 8 commits of clean `test:`→`feat:` TDD, all misread as impl.) The commit
message is the one signal that survives co-location, so it leads. A `test:`
commit is RED **regardless of which files it touches**; a `feat:` commit is
trusted not to smuggle in new tests.

## What it enforces

Run over every commit in `base..head`:

1. **RED-before-GREEN by ANCESTRY, not timestamps.** A `test:` commit must be
   an *ancestor* of the `feat:`/`fix:` implementation commit(s). If an
   implementation commit precedes its test commit in ancestry — "GREEN before
   RED" — that is a **BLOCKER**.
2. **No bundled commits — when paths are decisive.** A single commit that
   touches *both* a clearly-test-path file (`tests/`, `*_test.*`, `*.spec.*`,
   …) *and* a clearly-non-test code file is a **BLOCKER**: split the RED test
   commit from the GREEN implementation commit. Paths **cannot** reveal
   co-located-test bundling (a `test:` commit editing `src/foo.rs` has no
   test-path file), so **there the prefix convention is the enforcement** — a
   `feat:` commit is trusted not to add new tests, and a `test:` commit
   touching only `src/foo.rs` is **not** flagged bundled.
3. **CSS/config-only `feat:` downgrade.** A `feat:` commit touching only
   cosmetic/config files (css, scss, json, yaml, toml, `config`, `constants`,
   …) with no test is downgraded from BLOCKER to a **SHOULD-FIX** warning
   suggesting a `chore:`/`style:` prefix. It does not fail the run.
4. **Missing test (soft).** An implementation commit with no preceding
   `test:` commit anywhere in the range is a **SHOULD-FIX** warning, not a
   hard fail — some changes legitimately have no tests, but it is flagged.
5. **Possible mislabel (soft).** A `test:` commit that touches *no*
   recognizable test code — no test path **and** no co-located-test source
   (`.rs`, `.py`) — plus some plain non-test file is a **SHOULD-FIX** warning.

Each commit is classified as one of: `test`, `impl`, `cosmetic`, `bundled`,
or `empty`, and gets a verdict of `ok`, `SHOULD-FIX`, or `BLOCKER`.

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

Path detection is now a **secondary / corroborating** signal (the commit
prefix is primary — see above). It powers the path-decisive bundling check
and the possible-mislabel warning. Test-file detection is a documented
constant near the top of `tdd-check`, `TEST_PATH_PATTERNS` — a list of regexes
matched against each path's forward-slash form. A path is a test file if *any*
pattern matches. Current coverage:

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
`COLOCATED_TEST_EXTENSIONS` (`.rs`, `.py`) lists source extensions whose files
may legitimately *contain* a test, so a `test:` commit touching one is not
treated as a mislabel — add an extension there for another co-located-test
language. The prefix→role sets `TEST_PREFIXES`, `IMPL_PREFIXES`, and
`COSMETIC_PREFIXES` are likewise easy to extend.

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

It covers the pure helpers with fixtures (RED→GREEN clean, **Rust/Python
co-located `test:` commits recognized as RED**, prefix-beats-path bundling,
path-decisive bundling BLOCKER, possible-mislabel SHOULD-FIX, missing-test
SHOULD-FIX, CSS-feat downgrade, `chore:`-touching-code excluded,
GREEN-before-RED BLOCKER, multi-language test-file detection) plus integration
tests that build a throwaway git repo in a tempdir and run the real script for
passing, Rust-co-located-passing, bundled-failing, and invalid-ref cases.
