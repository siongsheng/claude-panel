#!/usr/bin/env python3
"""Post ONE sticky comment on a PR — create it, or edit it in place.

Shared by panel's CI agent-reviewers (architecture-review, findings-ledger):
the agent composes a markdown body to a file, then this script posts it as a
single comment identified by a marker (its exact first line). On a later run it
finds that comment by the marker and PATCHes it, so the PR carries exactly ONE
of each reviewer's comments instead of a new one per push.

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


def find_existing_id(comments: list[dict], marker: str):
    """Return the id of the LAST comment whose body starts with marker, else None.

    Last-match so that if duplicates ever exist, we converge on the newest and
    keep editing it. Null-body-safe (a deleted/empty comment body is skipped).
    """
    found = None
    for c in comments:
        body = c.get("body") or ""
        if body.startswith(marker):
            found = c["id"]
    return found


def gh(args: list[str]) -> tuple[int, str]:
    """Run `gh` and return (returncode, stdout). Never raises."""
    r = subprocess.run(["gh", *args], capture_output=True, text=True, check=False)
    if r.returncode != 0 and r.stderr.strip():
        print(r.stderr.strip(), file=sys.stderr)
    return r.returncode, r.stdout


def _repo() -> str:
    repo = os.environ.get("GITHUB_REPOSITORY")
    if repo:
        return repo
    _, out = gh(["repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"])
    return out.strip()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pr", type=int, help="PR number")
    ap.add_argument("--marker", required=True,
                    help="sticky marker; must be the body's exact first line")
    ap.add_argument("--body-file", required=True, help="path to the markdown body")
    args = ap.parse_args()

    path = pathlib.Path(args.body_file)
    if not path.is_file() or not path.read_text().strip():
        # Advisory: the compose step produced nothing usable -- loud but green.
        print(f"::error title=Sticky comment::no body at {args.body_file} -- "
              "nothing posted (see the compose step log).")
        return 0

    body = normalize(path.read_text())
    if not has_marker(body, args.marker):
        # Marker MUST be line 1, or a later run can't find this comment and
        # would post a duplicate every run. Fail loud instead of duplicating.
        print(f"::error title=Sticky comment::body missing marker '{args.marker}' "
              "on line 1 -- NOT posting (would duplicate next run).")
        return 0

    repo = _repo()
    rc, out = gh(["api", f"repos/{repo}/issues/{args.pr}/comments", "--paginate"])
    if rc != 0:
        print("::error title=Sticky comment::failed to list comments "
              "(advisory, not blocking).")
        return 0
    try:
        comments = json.loads(out) if out.strip() else []
    except json.JSONDecodeError:
        comments = []
    existing = find_existing_id(comments, args.marker)

    tmp = pathlib.Path(tempfile.gettempdir()) / f"sticky-{args.pr}.md"
    tmp.write_text(body)
    if existing is not None:
        rc, _ = gh(["api", "--method", "PATCH",
                    f"repos/{repo}/issues/comments/{existing}",
                    "-F", f"body=@{tmp}"])
        if rc != 0:
            print(f"::error title=Sticky comment::failed to update comment "
                  f"{existing} (advisory, not blocking).")
            return 0
        print(f"updated sticky comment {existing} on PR #{args.pr}")
    else:
        rc, _ = gh(["api", "--method", "POST",
                    f"repos/{repo}/issues/{args.pr}/comments",
                    "-F", f"body=@{tmp}"])
        if rc != 0:
            print("::error title=Sticky comment::failed to post comment "
                  "(advisory, not blocking).")
            return 0
        print(f"posted new sticky comment on PR #{args.pr}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
