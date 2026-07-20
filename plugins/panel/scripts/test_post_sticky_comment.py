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


class TestFindExistingIds(unittest.TestCase):
    """Returns ALL marker matches so the caller can collapse raced duplicates."""

    def test_returns_all_matches_in_order(self):
        comments = [
            {"id": 2, "body": f"{MARK}\nfirst"},
            {"id": 1, "body": "unrelated"},
            {"id": 5, "body": f"{MARK}\nsecond"},
        ]
        self.assertEqual(psc.find_existing_ids(comments, MARK), [2, 5])

    def test_survivor_is_newest_extras_are_older(self):
        # The caller keeps ids[-1] (newest) and deletes ids[:-1] (older twins).
        ids = psc.find_existing_ids([
            {"id": 2, "body": f"{MARK}\na"},
            {"id": 5, "body": f"{MARK}\nb"},
            {"id": 9, "body": f"{MARK}\nc"},
        ], MARK)
        self.assertEqual(ids[-1], 9)
        self.assertEqual(ids[:-1], [2, 5])

    def test_empty_when_none_match(self):
        self.assertEqual(psc.find_existing_ids([{"id": 1, "body": "x"}], MARK), [])

    def test_null_body_is_safe(self):
        comments = [{"id": 1, "body": None}, {"id": 2, "body": f"{MARK}\nx"}]
        self.assertEqual(psc.find_existing_ids(comments, MARK), [2])

    def test_order_follows_input_not_id_value(self):
        # Contract guard: the result preserves INPUT order (the caller assumes
        # the input is chronological), NOT ascending id. If GitHub ever returned
        # comments in a different order, "newest = last" would follow that order,
        # not the numerically-largest id. Here the higher id (9) comes FIRST in
        # input, so it is NOT the survivor — 2 is.
        comments = [
            {"id": 9, "body": f"{MARK}\nolder-but-higher-id"},
            {"id": 2, "body": f"{MARK}\nnewer-but-lower-id"},
        ]
        self.assertEqual(psc.find_existing_ids(comments, MARK), [9, 2])
        self.assertEqual(psc.find_existing_id(comments, MARK), 2)


def _bot(cid, body):
    return {"id": cid, "body": body, "user": {"login": "github-actions[bot]",
                                              "type": "Bot"}}


def _human(cid, body):
    return {"id": cid, "body": body, "user": {"login": "siongsheng",
                                             "type": "User"}}


class TestFindStaleDuplicateIds(unittest.TestCase):
    """Only BOT-authored marker matches (minus the survivor) are safe to delete."""

    def test_returns_bot_duplicates_except_survivor(self):
        comments = [_bot(2, f"{MARK}\na"), _bot(5, f"{MARK}\nb")]
        # keep the newest (5); delete the older bot twin (2).
        self.assertEqual(psc.find_stale_duplicate_ids(comments, MARK, keep_id=5), [2])

    def test_never_deletes_a_human_comment(self):
        # A human comment that merely quotes the marker must NOT be deleted,
        # even though it matches -- deletion is irreversible.
        comments = [_bot(5, f"{MARK}\nledger"), _human(9, f"{MARK}\nquoted!")]
        self.assertEqual(psc.find_stale_duplicate_ids(comments, MARK, keep_id=5), [])

    def test_excludes_the_survivor(self):
        comments = [_bot(5, f"{MARK}\na")]
        self.assertEqual(psc.find_stale_duplicate_ids(comments, MARK, keep_id=5), [])

    def test_ignores_non_matching_bodies(self):
        comments = [_bot(1, "unrelated"), _bot(2, f"{MARK}\na"), _bot(5, f"{MARK}\nb")]
        self.assertEqual(psc.find_stale_duplicate_ids(comments, MARK, keep_id=5), [2])

    def test_missing_user_is_safe(self):
        # A comment with no user object is not provably a bot -> never deleted.
        comments = [{"id": 2, "body": f"{MARK}\nx"}, _bot(5, f"{MARK}\ny")]
        self.assertEqual(psc.find_stale_duplicate_ids(comments, MARK, keep_id=5), [])

    def test_none_survivor_deletes_all_bot_matches(self):
        # keep_id=None (nothing to keep yet) still deletes stray bot twins.
        comments = [_bot(2, f"{MARK}\na"), _bot(5, f"{MARK}\nb")]
        self.assertEqual(psc.find_stale_duplicate_ids(comments, MARK, keep_id=None),
                         [2, 5])


if __name__ == "__main__":
    unittest.main(verbosity=2)
