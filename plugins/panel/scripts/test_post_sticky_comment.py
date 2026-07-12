"""Tests for post_sticky_comment.py — the shared sticky-comment poster.

Both CI agent-reviewers (architecture-review, findings-ledger) compose a
markdown body to a file, then post ONE sticky comment (edit-in-place). This
pins the fence-normalization, marker assertion, and existing-comment lookup —
the edge cases that were previously untested inline awk/bash across 4 files.

Pure-function tests only; the gh I/O layer is a thin shell-out, exercised in CI.
"""
import importlib.util
import pathlib
import unittest

_HERE = pathlib.Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    "post_sticky_comment", _HERE / "post_sticky_comment.py")
psc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(psc)

MARK = "## 📋 Marker"


class TestNormalize(unittest.TestCase):
    def test_clean_body_unchanged(self):
        body = f"{MARK}\n\n| a | b |\n"
        self.assertEqual(psc.normalize(body), f"{MARK}\n\n| a | b |")

    def test_strips_wrapping_code_fence(self):
        body = f"```markdown\n{MARK}\n\nrow\n```\n"
        out = psc.normalize(body)
        self.assertTrue(out.startswith(MARK))
        self.assertNotIn("```", out)

    def test_strips_leading_blank_lines(self):
        body = f"\n\n{MARK}\nrow\n"
        self.assertTrue(psc.normalize(body).startswith(MARK))

    def test_preserves_legitimate_trailing_fence(self):
        # A body that is NOT fence-wrapped but legitimately ENDS with a code
        # block must keep its closing ``` intact.
        body = f"{MARK}\nfix:\n```yaml\nx: 1\n```\n"
        out = psc.normalize(body)
        self.assertTrue(out.rstrip().endswith("```"))
        self.assertIn("x: 1", out)

    def test_empty_stays_empty(self):
        self.assertEqual(psc.normalize(""), "")
        self.assertEqual(psc.normalize("\n\n"), "")


class TestHasMarker(unittest.TestCase):
    def test_marker_on_first_line(self):
        self.assertTrue(psc.has_marker(f"{MARK}\nrow", MARK))

    def test_marker_missing(self):
        self.assertFalse(psc.has_marker("Here is the ledger:\n" + MARK, MARK))

    def test_wrong_heading_level(self):
        self.assertFalse(psc.has_marker("# Marker\nrow", MARK))


class TestParseComments(unittest.TestCase):
    """`gh api --paginate --jq '.[]'` emits ONE json object per line (JSONL).

    Regression guard: a plain `--paginate` (no --jq) concatenates arrays
    (`[...][...]`) into invalid JSON, which silently parsed to [] and caused a
    duplicate sticky comment every run on PRs with >1 page of comments.
    """
    def test_parses_jsonl_pages(self):
        text = '{"id": 1, "body": "a"}\n{"id": 2, "body": "b"}\n'
        self.assertEqual(psc.parse_comments(text),
                         [{"id": 1, "body": "a"}, {"id": 2, "body": "b"}])

    def test_parses_single_array_line(self):
        text = '[{"id": 1, "body": "a"}, {"id": 2, "body": "b"}]'
        self.assertEqual(psc.parse_comments(text),
                         [{"id": 1, "body": "a"}, {"id": 2, "body": "b"}])

    def test_empty_returns_empty(self):
        self.assertEqual(psc.parse_comments(""), [])
        self.assertEqual(psc.parse_comments("\n\n"), [])

    def test_skips_unparseable_lines(self):
        text = '{"id": 1, "body": "a"}\nnot json\n{"id": 2, "body": "b"}\n'
        self.assertEqual(psc.parse_comments(text),
                         [{"id": 1, "body": "a"}, {"id": 2, "body": "b"}])

    def test_skips_non_dict_values(self):
        # A bare string/number or an error object must not become a comment
        # (and must never reach find_existing_id as a non-dict).
        text = '"hello"\n123\n{"id": 9, "body": "x"}\n'
        self.assertEqual(psc.parse_comments(text), [{"id": 9, "body": "x"}])


class TestFindExistingId(unittest.TestCase):
    def test_finds_by_marker_prefix(self):
        comments = [
            {"id": 1, "body": "unrelated"},
            {"id": 2, "body": f"{MARK}\nold ledger"},
        ]
        self.assertEqual(psc.find_existing_id(comments, MARK), 2)

    def test_returns_last_when_duplicated(self):
        comments = [
            {"id": 2, "body": f"{MARK}\nfirst"},
            {"id": 5, "body": f"{MARK}\nsecond"},
        ]
        self.assertEqual(psc.find_existing_id(comments, MARK), 5)

    def test_none_when_absent(self):
        self.assertIsNone(psc.find_existing_id([{"id": 1, "body": "x"}], MARK))

    def test_null_body_is_safe(self):
        comments = [{"id": 1, "body": None}, {"id": 2, "body": f"{MARK}\nx"}]
        self.assertEqual(psc.find_existing_id(comments, MARK), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
