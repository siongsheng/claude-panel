#!/usr/bin/env python3
"""Tests for the mutation-check gate.

Runs two ways:

    python3 -m pytest test_mutation_check.py
    python3 test_mutation_check.py

Every test here exercises the PURE core (build-evidence detection, per-mutant
verdict classification, run-level validity, the cargo-mutants outcome parser,
ecosystem detection, report rendering). None of it runs a real mutation tool —
the core operates on normalized fixtures, exactly as tdd-check's classify_commits
operates on hand-built commit dicts. That is what makes a mutation *gate*
trustworthy: the decision layer is deterministic and unit-tested, while the slow
tool invocation is isolated plumbing.
"""

import importlib.machinery
import importlib.util
import os
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPT = os.path.join(_HERE, "mutation-check")


def _load_module():
    """Import the extensionless `mutation-check` script as a module."""
    spec = importlib.util.spec_from_file_location(
        "mutation_check", _SCRIPT,
        loader=importlib.machinery.SourceFileLoader("mutation_check", _SCRIPT),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mc = _load_module()


def mutant(name, built, test_failed):
    return mc.MutantResult(name=name, built=built, test_failed=test_failed)


# --------------------------------------------------------------------------
# Build-evidence detection — the amendment's core lesson.
# A mutant whose log shows the crate was NOT recompiled tested the UNMUTATED
# binary, so its "survived" result is an artefact, not a coverage gap.
# --------------------------------------------------------------------------
class TestBuildEvidence(unittest.TestCase):
    def test_compiling_line_is_evidence(self):
        log = ("Fresh foo v0.1.0\nCompiling huat v0.1.0 (/tmp/x)\n"
               "running 856 tests\ntest result: ok. 855 passed\n")
        self.assertTrue(mc.has_build_evidence(log, "Compiling huat"))

    def test_fresh_only_is_not_evidence(self):
        # The exact failure from the issue amendment: "Fresh huat", never
        # "Compiling huat" -> the mutant was never built.
        log = ("Fresh huat v0.1.0 (/tmp/cargo-mutants-huat-y5DsNQ.tmp)\n"
               "running 856 tests\ntest result: ok. 855 passed; 0 failed\n")
        self.assertFalse(mc.has_build_evidence(log, "Compiling huat"))

    def test_empty_log_is_not_evidence(self):
        self.assertFalse(mc.has_build_evidence("", "Compiling huat"))


# --------------------------------------------------------------------------
# Per-mutant verdict: caught / survived / indeterminate.
# --------------------------------------------------------------------------
class TestClassifyMutant(unittest.TestCase):
    def test_built_and_test_failed_is_caught(self):
        self.assertEqual(
            mc.classify_mutant(mutant("m1", built=True, test_failed=True)),
            mc.CAUGHT)

    def test_built_and_test_passed_is_survived(self):
        self.assertEqual(
            mc.classify_mutant(mutant("m2", built=True, test_failed=False)),
            mc.SURVIVED)

    def test_not_built_is_indeterminate_even_if_tests_passed(self):
        # A mutant that never built ran the UNMUTATED suite; "tests passed"
        # here means nothing. It must NOT be reported as a survivor.
        self.assertEqual(
            mc.classify_mutant(mutant("m3", built=False, test_failed=False)),
            mc.INDETERMINATE)

    def test_not_built_is_indeterminate_even_if_tests_failed(self):
        self.assertEqual(
            mc.classify_mutant(mutant("m4", built=False, test_failed=True)),
            mc.INDETERMINATE)


# --------------------------------------------------------------------------
# Run-level validity + exit code — the hard-gate / advisory split.
#   * validity (did the run execute?) is a FACT -> hard fail (exit 1)
#   * survival (is a survivor a real gap?) is a JUDGEMENT -> advisory (exit 0)
# --------------------------------------------------------------------------
class TestClassifyRun(unittest.TestCase):
    def test_all_caught_selftest_caught_is_valid_clean(self):
        rep = mc.classify_run(
            [mutant("m1", True, True), mutant("m2", True, True)],
            selftest_verdict=mc.CAUGHT)
        self.assertTrue(rep.valid)
        self.assertEqual(rep.exit_code, 0)
        self.assertEqual(rep.caught, 2)
        self.assertEqual(rep.survived, 0)
        self.assertEqual(rep.indeterminate, 0)
        self.assertEqual(rep.survivors, [])

    def test_survivor_with_valid_run_is_advisory_not_blocking(self):
        # A survivor on a VALID run does not fail the gate — it needs a
        # disposition in the ledger, not remediation. exit 0.
        rep = mc.classify_run(
            [mutant("m1", True, True), mutant("keeps-me", True, False)],
            selftest_verdict=mc.CAUGHT)
        self.assertTrue(rep.valid)
        self.assertEqual(rep.exit_code, 0)
        self.assertEqual(rep.survived, 1)
        self.assertEqual(rep.survivors, ["keeps-me"])

    def test_any_indeterminate_is_invalid_hard_fail(self):
        # 19-of-35-never-built incident: an unbuilt mutant makes the whole run
        # untrustworthy. Hard fail (exit 1) regardless of the survivor count.
        rep = mc.classify_run(
            [mutant("built", True, True), mutant("never-built", False, False)],
            selftest_verdict=mc.CAUGHT)
        self.assertFalse(rep.valid)
        self.assertEqual(rep.exit_code, 1)
        self.assertEqual(rep.indeterminate, 1)
        self.assertEqual(rep.indeterminates, ["never-built"])

    def test_selftest_survived_voids_the_run(self):
        # The known-killable mutant came back SURVIVED -> the tool/harness is
        # not actually killing mutants -> the run is void -> hard fail, even
        # though every real mutant looks caught.
        rep = mc.classify_run(
            [mutant("m1", True, True)],
            selftest_verdict=mc.SURVIVED)
        self.assertFalse(rep.valid)
        self.assertEqual(rep.exit_code, 1)

    def test_no_explicit_selftest_relies_on_build_evidence(self):
        # No explicit self-test: validity rests on build evidence ALONE. All
        # mutants built (0 indeterminate) -> VALID, even though nothing was
        # caught. A legitimate coverage gap is an advisory survivor, NEVER a
        # hard fail — this is the bug two reviewers flagged on PR #50: the old
        # implicit self-test collapsed "clean run, 0 kills" into "invalid run".
        rep = mc.classify_run([mutant("m1", True, False)], selftest_verdict=None)
        self.assertTrue(rep.valid)
        self.assertEqual(rep.exit_code, 0)
        self.assertEqual(rep.survivors, ["m1"])

    def test_all_survived_valid_run_is_advisory_not_invalid(self):
        # A --changed run whose every mutant validly built but survived (a real,
        # honestly-earned coverage gap) must NOT be indistinguishable from a
        # corrupted run. Valid, exit 0, survivors carried to the ledger.
        rep = mc.classify_run(
            [mutant("m1", True, False), mutant("m2", True, False)],
            selftest_verdict=None)
        self.assertTrue(rep.valid)
        self.assertEqual(rep.exit_code, 0)
        self.assertEqual(rep.survived, 2)

    def test_empty_run_is_valid_not_invalid(self):
        # Zero mutants (e.g. a docs-only diff on a Rust repo) is a degenerate
        # but VALID state — nothing to corrupt. It must never hard-fail.
        rep = mc.classify_run([], selftest_verdict=None)
        self.assertTrue(rep.valid)
        self.assertEqual(rep.exit_code, 0)

    def test_selftest_indeterminate_voids_the_run(self):
        rep = mc.classify_run(
            [mutant("m1", True, True)],
            selftest_verdict=mc.INDETERMINATE)
        self.assertFalse(rep.valid)


# --------------------------------------------------------------------------
# Crate-name parsing for the build-evidence marker — must read ONLY the
# [package] table, not a [[bin]] name or a [workspace] root, or the marker
# points at the wrong crate and every mutant looks INDETERMINATE (PR #50
# workspace fragility).
# --------------------------------------------------------------------------
class TestParsePackageName(unittest.TestCase):
    def test_reads_package_name(self):
        self.assertEqual(
            mc.parse_package_name('[package]\nname = "huat"\nversion = "0.1"\n'),
            "huat")

    def test_ignores_bin_name_before_package(self):
        toml = '[[bin]]\nname = "the-bin"\n\n[package]\nname = "the-crate"\n'
        self.assertEqual(mc.parse_package_name(toml), "the-crate")

    def test_workspace_root_without_package_is_empty(self):
        # A workspace root Cargo.toml has no [package] name — return "" so the
        # caller falls back / requires --build-marker rather than grabbing a
        # wrong name.
        self.assertEqual(
            mc.parse_package_name('[workspace]\nmembers = ["a", "b"]\n'), "")


# --------------------------------------------------------------------------
# cargo-mutants outcomes.json parser (pure over a parsed dict).
# We must re-derive the verdict from build evidence in each mutant's LOG,
# NOT trust cargo's own summary (which recorded false MissedMutants).
# --------------------------------------------------------------------------
class TestParseCargoOutcomes(unittest.TestCase):
    def test_extracts_name_and_log(self):
        outcomes = {
            "outcomes": [
                {"scenario": {"Mutant": {"name": "src/a.rs: replace + with -"}},
                 "summary": "MissedMutant",
                 "log_path": "log/src__a.log"},
                {"scenario": {"Mutant": {"name": "src/b.rs: replace * with +"}},
                 "summary": "CaughtMutant",
                 "log_path": "log/src__b.log"},
            ]
        }
        got = mc.parse_cargo_outcomes(outcomes)
        self.assertEqual(len(got), 2)
        self.assertEqual(got[0]["name"], "src/a.rs: replace + with -")
        self.assertEqual(got[0]["log_path"], "log/src__a.log")
        self.assertEqual(got[0]["summary"], "MissedMutant")

    def test_skips_non_mutant_scenarios(self):
        # The baseline (unmutated) scenario is not a mutant and must be dropped.
        outcomes = {
            "outcomes": [
                {"scenario": "Baseline", "summary": "Success",
                 "log_path": "log/baseline.log"},
                {"scenario": {"Mutant": {"name": "src/a.rs: x"}},
                 "summary": "CaughtMutant", "log_path": "log/a.log"},
            ]
        }
        got = mc.parse_cargo_outcomes(outcomes)
        self.assertEqual([m["name"] for m in got], ["src/a.rs: x"])


# --------------------------------------------------------------------------
# Ecosystem detection over the set of marker files present at the repo root.
# --------------------------------------------------------------------------
class TestDetectEcosystem(unittest.TestCase):
    def test_cargo(self):
        self.assertEqual(mc.detect_ecosystem({"Cargo.toml", "src"}), "cargo")

    def test_python(self):
        self.assertEqual(mc.detect_ecosystem({"pyproject.toml"}), "python")
        self.assertEqual(mc.detect_ecosystem({"setup.py"}), "python")

    def test_js(self):
        self.assertEqual(mc.detect_ecosystem({"package.json"}), "js")

    def test_unknown_is_none(self):
        self.assertIsNone(mc.detect_ecosystem({"README.md", "Makefile"}))

    def test_cargo_wins_when_both_present(self):
        # A polyglot repo root: cargo is checked first (deterministic order).
        self.assertEqual(
            mc.detect_ecosystem({"Cargo.toml", "package.json"}), "cargo")


# --------------------------------------------------------------------------
# Report rendering — the validity summary must be unfalsifiable, and an
# invalid run must be a LOUD ::error:: (not a quiet survivor count).
# --------------------------------------------------------------------------
class TestRenderReport(unittest.TestCase):
    def test_valid_clean_summary(self):
        rep = mc.classify_run([mutant("m1", True, True)],
                              selftest_verdict=mc.CAUGHT)
        out = mc.render_report(rep)
        self.assertIn("1 tested", out)
        self.assertIn("0 indeterminate", out)
        self.assertIn("VALID", out)

    def test_survivors_are_listed_for_disposition(self):
        rep = mc.classify_run(
            [mutant("m1", True, True), mutant("src/x.rs: gap", True, False)],
            selftest_verdict=mc.CAUGHT)
        out = mc.render_report(rep)
        self.assertIn("src/x.rs: gap", out)
        # Advisory, not blocking -> a warning, never an error.
        self.assertIn("::warning", out)

    def test_invalid_run_is_loud_error(self):
        rep = mc.classify_run(
            [mutant("never-built", False, False)],
            selftest_verdict=mc.CAUGHT)
        out = mc.render_report(rep)
        self.assertIn("::error", out)
        self.assertIn("never-built", out)
        self.assertIn("INVALID", out)

    def test_no_explicit_selftest_is_not_an_error(self):
        # A valid run with no explicit self-test must not emit an ::error just
        # because selftest_verdict is None (it relies on build evidence).
        rep = mc.classify_run([mutant("m1", True, True)], selftest_verdict=None)
        out = mc.render_report(rep)
        self.assertNotIn("::error", out)

    def test_valid_run_that_killed_nothing_warns_advisorily(self):
        # A clean run (all built) that caught 0 mutants and had no explicit
        # self-test is valid, but worth a NON-blocking heads-up that the harness
        # might not be asserting.
        rep = mc.classify_run([mutant("m1", True, False)], selftest_verdict=None)
        out = mc.render_report(rep)
        self.assertTrue(rep.valid)
        self.assertNotIn("::error", out)
        self.assertIn("::warning", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
