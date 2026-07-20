#!/usr/bin/env python3
"""Post ONE sticky comment on a PR — create it, edit it in place, self-heal dupes.

Shared by panel's CI agent-reviewers (architecture-review, findings-ledger):
the agent composes a markdown body to a file, then this script normalizes it
(strips a wrapping ``` code fence + leading blank lines so the marker lands on
line 1), asserts the marker, and posts it as a single comment identified by that
marker (its exact first line). On a later run it finds that comment by the marker
and PATCHes it, so the PR carries exactly ONE of each reviewer's comments instead
of a new one per push.

Two independent writers (the CI auto-ledger and the /panel agent) post the same
marker and list-then-post is not atomic, so a race can leave more than one. To
converge, each post also DELETEs the older *bot-authored* duplicates (never a
human comment — see find_stale_duplicate_ids), so a raced twin is transient
rather than permanent.

It replaces the awk/bash "Post" state machine that was previously inlined and
duplicated across four workflow files, with the fence/marker/dedup edge cases
unit-tested (see test_post_sticky_comment.py). Matches this repo's
scripts/deepseek_review.py convention: stdlib only, shells out to `gh`.

Usage:
    python3 scripts/post_sticky_comment.py <pr-number> \
        --marker "## 📋 Review Findings Ledger" --body-file path/to/body.md

ADVISORY: the reviewers are non-blocking, so a missing/malformed body or a
transient `gh api` failure is surfaced as a loud GitHub Actions ::error:: /
::warning:: annotation but still exits 0 -- it must never fail the build.
"""

import argparse
import json
import os
import pathlib
import subprocess
import sys
import tempfile


def normalize(text: str) -> str:
    """Strip a wrapping ``` code fence and leading blank lines.

    An over-formatted agent may wrap the whole body in a fenced block or add
    leading blanks, which would push the marker off line 1. Strip a leading
    fence + leading blanks; strip the matching trailing fence ONLY when a
    leading fence was stripped, so a body that legitimately ENDS with a code
    block keeps its closing fence. Returns the body with no trailing newline.
    """
    lines = text.split("\n")
    stripped_lead = False
    out: list[str] = []
    started = False
    for line in lines:
        if not started:
            if line.strip().startswith("```"):
                stripped_lead = True
                continue
            if line.strip() == "":
                continue
            started = True
        out.append(line)
    # Drop trailing blank lines first, so the closing fence (if any) is last.
    while out and out[-1].strip() == "":
        out.pop()
    if stripped_lead and out and out[-1].strip() == "```":
        out.pop()
        while out and out[-1].strip() == "":
            out.pop()
    return "\n".join(out)


def has_marker(text: str, marker: str) -> bool:
    """True iff the FIRST line of text starts with marker."""
    first = text.split("\n", 1)[0]
    return first.startswith(marker)


def parse_comments(text: str) -> list[dict]:
    """Parse the output of `gh api ... --paginate --jq '.[]'` into a list of dicts.

    That command streams ONE json object per line (JSONL). Parsing line-by-line
    avoids the trap of a plain `--paginate` (no --jq), which concatenates each
    page's array (`[...][...]`) into invalid JSON -- a single json.loads on that
    fails, and swallowing the error to [] silently posts a duplicate sticky
    comment every run. Also tolerates a single JSON array (one line) for
    robustness, skips unparseable lines, and keeps only dict items (so an error
    object / bare value can never reach find_existing_id as a non-dict).
    """
    out: list[dict] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            val = json.loads(line)
        except json.JSONDecodeError:
            continue
        items = val if isinstance(val, list) else [val]
        out.extend(x for x in items if isinstance(x, dict))
    return out


def find_existing_ids(comments: list[dict], marker: str) -> list[int]:
    """Return the ids of ALL comments whose body starts with marker, in order.

    Two independent writers (the CI auto-ledger and the /panel supervising
    agent) post this comment, and list-then-post is not atomic — so a post-vs-post
    race can leave more than one. Returning every match lets the caller keep one
    and DELETE the rest, so the sticky converges back to exactly one on the next
    post. `comments` is assumed to be in chronological (ascending-creation) order
    — the default of the GitHub list-comments API — so the last match is the
    newest. Null-body-safe (a deleted/empty comment body is skipped).
    """
    return [c["id"] for c in comments if (c.get("body") or "").startswith(marker)]


def find_stale_duplicate_ids(comments: list[dict], marker: str,
                             keep_id) -> list[int]:
    """Bot-authored marker matches other than keep_id — the ids safe to DELETE.

    Deletion is irreversible, so it is confined to *machine-posted* duplicates
    (`user.type == "Bot"`): the sticky ledger/reviews are written by CI bots, so
    a human comment that merely quotes the marker line — or any comment with no
    provable bot author — must never be deleted. keep_id (the survivor we PATCH)
    is always excluded. main() passes find_existing_id's result, which is None
    only when there are no matches at all (so the loop is a no-op); the None case
    is kept as a defensive default (sweep every bot twin) rather than special-cased.
    """
    out: list[int] = []
    for c in comments:
        if c.get("id") == keep_id:
            continue
        if not (c.get("body") or "").startswith(marker):
            continue
        if (c.get("user") or {}).get("type") == "Bot":
            out.append(c["id"])
    return out


def find_existing_id(comments: list[dict], marker: str):
    """Return the id of the LAST comment whose body starts with marker, else None.

    Last-match so that if duplicates ever exist, we converge on the newest and
    keep editing it (the older duplicates are deleted by the caller — see
    find_existing_ids). Null-body-safe (a deleted/empty comment body is skipped).
    """
    ids = find_existing_ids(comments, marker)
    return ids[-1] if ids else None


def gh(args: list[str]) -> tuple[int, str, str]:
    """Run `gh` and return (returncode, stdout, stderr). Never raises.

    stderr is returned (not just printed) so callers can classify a failure —
    e.g. a DELETE that 404s because a concurrent run already removed the comment
    is convergence, not an error.
    """
    r = subprocess.run(["gh", *args], capture_output=True, text=True, check=False)
    return r.returncode, r.stdout, r.stderr


def _repo() -> str:
    repo = os.environ.get("GITHUB_REPOSITORY")
    if repo:
        return repo
    rc, out, err = gh(["repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"])
    if rc != 0:
        # Surface the failure instead of returning "" (which would make every
        # later gh call target repos//… with a confusing error).
        print(f"::error title=Sticky comment::could not resolve repo "
              f"(set GITHUB_REPOSITORY or run in a repo): {err.strip()}")
    return out.strip()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pr", type=int, help="PR number")
    ap.add_argument("--marker", required=True,
                    help="sticky marker; must be the body's exact first line")
    ap.add_argument("--body-file", required=True, help="path to the markdown body")
    args = ap.parse_args()

    path = pathlib.Path(args.body_file)
    raw = path.read_text() if path.is_file() else ""
    if not raw.strip():
        # Advisory: the compose step produced nothing usable -- loud but green.
        print(f"::error title=Sticky comment::no body at {args.body_file} -- "
              "nothing posted (see the compose step log).")
        return 0

    body = normalize(raw)
    if not has_marker(body, args.marker):
        # Marker MUST be line 1, or a later run can't find this comment and
        # would post a duplicate every run. Fail loud instead of duplicating.
        print(f"::error title=Sticky comment::body missing marker '{args.marker}' "
              "on line 1 -- NOT posting (would duplicate next run).")
        return 0

    repo = _repo()
    # --jq '.[]' streams one comment object per line (JSONL); see parse_comments
    # for why plain --paginate on an array is unsafe. The API returns comments in
    # ascending `created` order (its default), which is what makes "last match =
    # newest" hold in find_existing_id / find_stale_duplicate_ids.
    rc, out, err = gh(["api", f"repos/{repo}/issues/{args.pr}/comments",
                       "--paginate", "--jq", ".[]"])
    if rc != 0:
        print(f"::error title=Sticky comment::failed to list comments: "
              f"{err.strip()} (advisory, not blocking).")
        return 0
    comments = parse_comments(out)
    # Keep the newest match (the one we PATCH); it's overwritten with `body`, so
    # which we keep doesn't affect content.
    existing = find_existing_id(comments, args.marker)
    # Self-heal a raced duplicate: both writers (CI + /panel agent) unblock on
    # the same reviewer checks and can each POST before seeing the other, leaving
    # two ledgers. DELETE the older BOT-authored twins, so the PR converges back
    # to ONE sticky comment on this very post -- transient, not permanent (before
    # this the stale twin lingered forever). Human comments are never deleted
    # (see find_stale_duplicate_ids).
    for dup in find_stale_duplicate_ids(comments, args.marker, existing):
        rc, _, err = gh(["api", "--method", "DELETE",
                         f"repos/{repo}/issues/comments/{dup}"])
        if rc == 0:
            print(f"deleted duplicate sticky comment {dup} on PR #{args.pr}")
        elif "http 404" in err.lower() or "not found" in err.lower():
            # A concurrent run already removed it -- that IS convergence, not an
            # error, so don't raise a misleading ::warning::. Match gh's actual
            # "gh: Not Found (HTTP 404)" wording; worst case a wording change just
            # mislabels a cosmetic warning, never affecting convergence.
            print(f"duplicate comment {dup} already removed (concurrent self-heal).")
        else:
            print(f"::warning title=Sticky comment::failed to delete duplicate "
                  f"comment {dup}: {err.strip()} (advisory, not blocking).")

    tmp = pathlib.Path(tempfile.gettempdir()) / f"sticky-{args.pr}-{os.getpid()}.md"
    tmp.write_text(body)
    if existing is not None:
        rc, _, err = gh(["api", "--method", "PATCH",
                         f"repos/{repo}/issues/comments/{existing}",
                         "-F", f"body=@{tmp}"])
        if rc != 0:
            print(f"::error title=Sticky comment::failed to update comment "
                  f"{existing}: {err.strip()} (advisory, not blocking).")
            return 0
        print(f"updated sticky comment {existing} on PR #{args.pr}")
    else:
        rc, _, err = gh(["api", "--method", "POST",
                         f"repos/{repo}/issues/{args.pr}/comments",
                         "-F", f"body=@{tmp}"])
        if rc != 0:
            print(f"::error title=Sticky comment::failed to post comment: "
                  f"{err.strip()} (advisory, not blocking).")
            return 0
        print(f"posted new sticky comment on PR #{args.pr}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
