#!/usr/bin/env python3
"""Tests for the deterministic, revision-bound delivery gate."""

import importlib.machinery
import importlib.util
import json
import pathlib
import unittest


def load_gate():
    path = pathlib.Path(__file__).with_name("delivery-gate")
    loader = importlib.machinery.SourceFileLoader("delivery_gate", str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


gate = load_gate()


POLICY = {
    "version": 1,
    "risk": {
        "default": "low",
        "rules": [
            {"level": "medium", "paths": ["src/api/**"]},
            {"level": "high", "paths": ["migrations/**", "auth/**"]},
        ],
    },
    "requirements": {
        "low": [
            {"kind": "functional", "name": "tests"},
            {"kind": "security", "name": "security-review"},
        ],
        "medium": [
            {"kind": "functional", "name": "tests"},
            {"kind": "security", "name": "security-review"},
            {
                "kind": "performance",
                "name": "performance",
                "require_environment": True,
            },
        ],
        "high": [
            {"kind": "functional", "name": "tests"},
            {"kind": "security", "name": "security-review"},
            {
                "kind": "performance",
                "name": "performance",
                "require_environment": True,
            },
            {
                "kind": "endurance",
                "name": "endurance",
                "require_environment": True,
                "require_artifact": True,
            },
        ],
    },
}
POLICY_DIGEST = gate.policy_digest(POLICY)


def evidence(changed_files=None, checks=None, declared_risk=None):
    digest = "sha256:" + "a" * 64
    data = {
        "version": 1,
        "revision": {
            "repository": "acme/widget",
            "head_sha": "abc123",
            "spec_digest": digest,
            "policy_digest": POLICY_DIGEST,
        },
        "changed_files": changed_files or ["src/widget.py"],
        "checks": checks or [
            {
                "kind": "functional",
                "name": "tests",
                "status": "pass",
                "head_sha": "abc123",
                "spec_digest": digest,
                "source_url": "https://ci.example/tests/1",
            },
            {
                "kind": "security",
                "name": "security-review",
                "status": "pass",
                "head_sha": "abc123",
                "spec_digest": digest,
                "source_url": "https://ci.example/security/1",
            },
        ],
    }
    if declared_risk:
        data["declared_risk"] = declared_risk
    return data


class TestRisk(unittest.TestCase):
    def test_highest_matching_rule_wins(self):
        self.assertEqual(
            gate.classify_risk(POLICY, ["src/api/routes.py", "auth/token.py"]),
            "high",
        )

    def test_declared_risk_can_raise_but_not_lower_risk(self):
        self.assertEqual(
            gate.evaluate(POLICY, evidence(["auth/token.py"], declared_risk="low"))["risk"],
            "high",
        )
        self.assertEqual(
            gate.evaluate(POLICY, evidence(declared_risk="medium"))["risk"],
            "medium",
        )

    def test_higher_risk_policy_cannot_drop_lower_tier_requirement(self):
        policy = json.loads(json.dumps(POLICY))
        policy["requirements"]["medium"] = policy["requirements"]["medium"][1:]
        item = evidence()
        item["revision"]["policy_digest"] = gate.policy_digest(policy)
        with self.assertRaisesRegex(ValueError, "cannot drop"):
            gate.evaluate(policy, item)


class TestEvidence(unittest.TestCase):
    def test_low_risk_complete_evidence_passes(self):
        report = gate.evaluate(POLICY, evidence())
        self.assertTrue(report["ok"])
        self.assertEqual(report["decision"], "PASS")

    def test_missing_required_check_blocks(self):
        item = evidence()
        item["checks"] = item["checks"][:1]
        report = gate.evaluate(POLICY, item)
        self.assertFalse(report["ok"])
        self.assertIn("missing required security/security-review", report["failures"])

    def test_inert_docs_can_skip_review_requirements_by_policy(self):
        policy = json.loads(json.dumps(POLICY))
        inert = ["**.md", "LICENSE"]
        for level in ("low", "medium", "high"):
            for requirement in policy["requirements"][level]:
                if requirement["kind"] == "security":
                    requirement["skip_when_all_paths"] = inert
        item = evidence(changed_files=["docs/guide.md"])
        item["checks"] = item["checks"][:1]
        item["revision"]["policy_digest"] = gate.policy_digest(policy)
        report = gate.evaluate(policy, item)
        self.assertTrue(report["ok"])
        self.assertEqual(report["skipped"], ["security/security-review"])

    def test_stale_head_is_rejected(self):
        item = evidence()
        item["checks"][0]["head_sha"] = "oldsha"
        report = gate.evaluate(POLICY, item)
        self.assertFalse(report["ok"])
        self.assertTrue(any("head_sha" in failure for failure in report["failures"]))

    def test_stale_spec_digest_is_rejected(self):
        item = evidence()
        item["checks"][0]["spec_digest"] = "sha256:" + "b" * 64
        report = gate.evaluate(POLICY, item)
        self.assertFalse(report["ok"])
        self.assertTrue(any("spec_digest" in failure for failure in report["failures"]))

    def test_evidence_is_bound_to_policy_digest(self):
        item = evidence()
        item["revision"]["policy_digest"] = "sha256:" + "b" * 64
        with self.assertRaisesRegex(ValueError, "policy_digest"):
            gate.evaluate(POLICY, item)

    def test_medium_risk_requires_environment_bound_performance(self):
        item = evidence(changed_files=["src/api/routes.py"])
        item["checks"].append(
            {
                "kind": "performance",
                "name": "performance",
                "status": "pass",
                "head_sha": "abc123",
                "spec_digest": item["revision"]["spec_digest"],
                "source_url": "https://ci.example/perf/1",
            }
        )
        report = gate.evaluate(POLICY, item)
        self.assertFalse(report["ok"])
        self.assertTrue(any("environment" in failure for failure in report["failures"]))

    def test_high_risk_endurance_requires_artifact_digest(self):
        item = evidence(changed_files=["auth/token.py"])
        env = {"os": "ubuntu-24.04", "arch": "x86_64", "runtime": "python-3.12", "hardware": "2-core runner"}
        for kind in ("performance", "endurance"):
            item["checks"].append(
                {
                    "kind": kind,
                    "name": kind,
                    "status": "pass",
                    "head_sha": "abc123",
                    "spec_digest": item["revision"]["spec_digest"],
                    "source_url": f"https://ci.example/{kind}/1",
                    "environment": env,
                }
            )
        report = gate.evaluate(POLICY, item)
        self.assertFalse(report["ok"])
        self.assertTrue(any("artifact_digest" in failure for failure in report["failures"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
