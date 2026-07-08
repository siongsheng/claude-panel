"""Tests for deepseek_review.py's review-prompt coverage.

The panel design gives the cross-model (DeepSeek) reviewer BOTH correctness and
architecture, so architecture gets a second-model-family opinion (the Claude
family covers it via feature-dev's code-reviewer). These tests pin that the
DeepSeek prompt actually carries the architecture lens.
"""
import importlib.util
import pathlib
import unittest

_HERE = pathlib.Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    "deepseek_review", _HERE / "deepseek_review.py")
dr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dr)


class TestReviewPromptCoverage(unittest.TestCase):
    def test_prompt_covers_architecture_dimensions(self):
        p = dr.SYSTEM_PROMPT.lower()
        self.assertIn("architecture", p)
        for term in ("coupling", "breaking change", "dependency"):
            self.assertIn(term, p,
                          f"architecture lens missing '{term}'")

    def test_output_structure_has_architecture_section(self):
        # The structured review must call for an architecture findings section.
        self.assertIn("architecture", dr.SYSTEM_PROMPT.lower())
        # keep the existing correctness coverage too (no regression)
        self.assertIn("correctness", dr.SYSTEM_PROMPT.lower())


if __name__ == "__main__":
    unittest.main()
