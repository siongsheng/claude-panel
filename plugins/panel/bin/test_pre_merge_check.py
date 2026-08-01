#!/usr/bin/env python3
"""Tests for the pre-merge remote-verification gate.

Runs two ways:

    python3 -m pytest test_pre_merge_check.py
    python3 test_pre_merge_check.py

The pure core (ls-remote parsing, SHA parity, grep-presence checks, test-count
parity, report/exit-code aggregation) is exercised with fixtures — no network,
no git. The slow git/CI invocation is isolated plumbing.
"""

import importlib.machinery
import importlib.util
import os
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPT = os.path.join(_HERE, "pre-merge-check")


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "pre_merge_check", _SCRIPT,
        loader=importlib.machinery.SourceFileLoader("pre_merge_check", _SCRIPT),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


pmc = _load_module()


# --------------------------------------------------------------------------
# ls-remote parsing: pull the branch head SHA out of `git ls-remote` output.
# --------------------------------------------------------------------------
class TestParseLsRemote(unittest.TestCase):
    OUT = (
        "9f8e7d6c5b4a39281706f5e4d3c2b1a09f8e7d6c\trefs/heads/main\n"
        "1122334455667788990011223344556677889900\trefs/heads/feature/x\n"
        "aabbccddeeff00112233445566778899aabbccdd\trefs/tags/v1.0\n"
    )

    def test_finds_branch_head(self):
        self.assertEqual(
            pmc.parse_ls_remote(self.OUT, "feature/x"),
            "1122334455667788990011223344556677889900")

    def test_accepts_full_ref(self):
        self.assertEqual(
            pmc.parse_ls_remote(self.OUT, "refs/heads/main"),
            "9f8e7d6c5b4a39281706f5e4d3c2b1a09f8e7d6c")

    def test_missing_branch_is_none(self):
        # A branch that was never pushed has no remote head — the caller treats
        # that as a parity FAIL, not a crash.
        self.assertIsNone(pmc.parse_ls_remote(self.OUT, "feature/never-pushed"))

    def test_empty_output_is_none(self):
        self.assertIsNone(pmc.parse_ls_remote("", "main"))


# --------------------------------------------------------------------------
# SHA parity — the check that catches "committed locally, never pushed".
# --------------------------------------------------------------------------
class TestShaParity(unittest.TestCase):
    def test_equal_shas_pass(self):
        c = pmc.sha_parity_check("abc123", "abc123")
        self.assertTrue(c.ok)

    def test_mismatch_fails(self):
        # The exact #45 failure: local head has commits the remote ref lacks.
        c = pmc.sha_parity_check("localnew", "remoteold")
        self.assertFalse(c.ok)
        self.assertIn("localnew", c.detail)
        self.assertIn("remoteold", c.detail)

    def test_missing_remote_fails(self):
        c = pmc.sha_parity_check("localnew", None)
        self.assertFalse(c.ok)


# --------------------------------------------------------------------------
# Grep-presence checks against a ref. "The new string is present" is not
# enough — #45 requires asserting the OLD buggy line is gone too.
# --------------------------------------------------------------------------
class TestPresenceCheck(unittest.TestCase):
    def test_present_when_expected_present(self):
        self.assertTrue(pmc.presence_check("fix", 2, must_be_present=True).ok)

    def test_absent_when_expected_present_fails(self):
        c = pmc.presence_check("fix", 0, must_be_present=True)
        self.assertFalse(c.ok)

    def test_absent_when_expected_absent(self):
        # The old buggy line: count must be 0.
        self.assertTrue(pmc.presence_check("old", 0, must_be_present=False).ok)

    def test_present_when_expected_absent_fails(self):
        c = pmc.presence_check("old", 3, must_be_present=False)
        self.assertFalse(c.ok)
        self.assertIn("3", c.detail)


# --------------------------------------------------------------------------
# Test-count parity — the only cheap end-to-end check that the thing reviewed
# is the thing merged (a squash that dropped commits shows up as a lower count).
# --------------------------------------------------------------------------
class TestCountParity(unittest.TestCase):
    def test_equal_counts_pass(self):
        self.assertTrue(pmc.count_parity_check(767, 767).ok)

    def test_lower_count_fails(self):
        # 763 instead of 767 — commits were lost in the merge (#45's incident).
        c = pmc.count_parity_check(767, 763)
        self.assertFalse(c.ok)
        self.assertIn("767", c.detail)
        self.assertIn("763", c.detail)

    def test_higher_count_also_fails(self):
        # A mismatch in EITHER direction means the merged state differs from
        # what was gated — surface it, don't wave it through.
        self.assertFalse(pmc.count_parity_check(767, 800).ok)


# --------------------------------------------------------------------------
# Report aggregation + exit code.
# --------------------------------------------------------------------------
class TestReport(unittest.TestCase):
    def test_all_pass_is_ok_exit_0(self):
        rep = pmc.build_report([
            pmc.sha_parity_check("a", "a"),
            pmc.presence_check("fix", 1, must_be_present=True),
        ])
        self.assertTrue(rep.ok)
        self.assertEqual(rep.exit_code, 0)

    def test_any_fail_is_not_ok_exit_1(self):
        rep = pmc.build_report([
            pmc.sha_parity_check("a", "a"),
            pmc.sha_parity_check("local", "remote"),  # fails
        ])
        self.assertFalse(rep.ok)
        self.assertEqual(rep.exit_code, 1)

    def test_render_marks_failures_loudly(self):
        rep = pmc.build_report([pmc.sha_parity_check("local", "remote")])
        out = pmc.render_report(rep)
        self.assertIn("::error", out)
        self.assertIn("FAIL", out)

    def test_render_clean_is_pass(self):
        rep = pmc.build_report([pmc.sha_parity_check("a", "a")])
        out = pmc.render_report(rep)
        self.assertIn("PASS", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
