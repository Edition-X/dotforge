#!/usr/bin/env python3
"""
Collect everything a read-only PR review needs, in one shot, pinned to the
exact head commit.

Returns repo, PR number, base and head branch, the full 40-character head SHA,
changed files, the diff, check results, and every existing review, inline
review thread, and conversation comment.

Read-only by construction. Every gh invocation is built here from a fixed
allowlist of read verbs - no caller-supplied subcommand, no HTTP method other
than GET, no GraphQL mutation. It cannot post, approve, merge, or edit.

Usage:
  pr_context.py --pr https://github.com/owner/repo/pull/123 > /tmp/pr.json
  pr_context.py --pr 123 --repo owner/repo > /tmp/pr.json

  # re-check the head before writing the review; prints the SHA alone
  pr_context.py --pr 123 --repo owner/repo --head-only

  # fail loudly if the PR moved since you pinned it
  pr_context.py --pr 123 --repo owner/repo --assert-head <40-hex>

Exit codes:
  0  success
  3  gh call failed
  4  --assert-head mismatch: the PR moved, re-run the review against the new head
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys

PR_URL = re.compile(
    r"^https?://(?:www\.)?github\.com/"
    r"(?P<repo>[A-Za-z0-9._-]+/[A-Za-z0-9._-]+)/pull/(?P<number>\d+)"
)
REPO_SLUG = re.compile(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$")
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")

VIEW_FIELDS = ",".join(
    [
        "number",
        "url",
        "title",
        "body",
        "state",
        "isDraft",
        "author",
        "baseRefName",
        "headRefName",
        "headRefOid",
        "additions",
        "deletions",
        "changedFiles",
        "files",
        "reviewDecision",
        "reviews",
        "comments",
        "statusCheckRollup",
    ]
)

THREADS_QUERY = """
query($owner: String!, $repo: String!, $number: Int!, $cursor: String) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $number) {
      reviewThreads(first: 100, after: $cursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          isResolved
          isOutdated
          path
          line
          originalLine
          diffSide
          comments(first: 50) {
            nodes {
              body
              createdAt
              outdated
              author { login }
            }
          }
        }
      }
    }
  }
}
"""


class GhError(Exception):
    """A read-only gh call failed."""


def gh(args: list[str]) -> str:
    """Run a gh command. Callers only ever pass read verbs assembled below."""
    try:
        result = subprocess.run(
            ["gh", *args], capture_output=True, text=True, check=False
        )
    except FileNotFoundError as exc:  # pragma: no cover - environment specific
        raise GhError("gh CLI not found on PATH; run `brew install gh`") from exc
    if result.returncode != 0:
        raise GhError(f"gh {' '.join(args)} failed:\n{result.stderr.strip()}")
    return result.stdout


def resolve_target(pr: str, repo: str | None) -> tuple[str, str]:
    """Turn a URL or a bare number into (repo, number)."""
    match = PR_URL.match(pr)
    if match:
        return match.group("repo"), match.group("number")
    if not pr.lstrip("#").isdigit():
        raise GhError(f"--pr must be a PR URL or number, got {pr!r}")
    if not repo:
        repo = json.loads(gh(["repo", "view", "--json", "nameWithOwner"]))[
            "nameWithOwner"
        ]
    if not REPO_SLUG.match(repo):
        raise GhError(f"--repo must be owner/repo, got {repo!r}")
    return repo, pr.lstrip("#")


def fetch_view(repo: str, number: str) -> dict:
    return json.loads(
        gh(["pr", "view", number, "--repo", repo, "--json", VIEW_FIELDS])
    )


def fetch_threads(repo: str, number: str) -> list[dict]:
    owner, name = repo.split("/")
    threads: list[dict] = []
    cursor: str | None = None
    while True:
        args = [
            "api",
            "graphql",
            "-f",
            f"query={THREADS_QUERY}",
            "-F",
            f"owner={owner}",
            "-F",
            f"repo={name}",
            "-F",
            f"number={number}",
        ]
        if cursor:
            args += ["-F", f"cursor={cursor}"]
        page = json.loads(gh(args))["data"]["repository"]["pullRequest"][
            "reviewThreads"
        ]
        threads.extend(page["nodes"])
        if not page["pageInfo"]["hasNextPage"]:
            return threads
        cursor = page["pageInfo"]["endCursor"]


def fetch_diff(repo: str, number: str) -> str:
    return gh(["pr", "diff", number, "--repo", repo])


def head_sha(repo: str, number: str) -> str:
    sha = json.loads(
        gh(["pr", "view", number, "--repo", repo, "--json", "headRefOid"])
    )["headRefOid"]
    if not FULL_SHA.match(sha):
        raise GhError(f"gh returned a head SHA that is not 40 hex chars: {sha!r}")
    return sha


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only PR context for a review, pinned to the head SHA.",
    )
    parser.add_argument("--pr", required=True, help="PR URL or number")
    parser.add_argument("--repo", help="owner/repo (inferred from a URL or cwd)")
    parser.add_argument(
        "--head-only", action="store_true", help="print the head SHA and exit"
    )
    parser.add_argument(
        "--assert-head",
        metavar="SHA",
        help="exit 4 if the current head differs from this SHA",
    )
    parser.add_argument(
        "--no-diff", action="store_true", help="omit the diff from the payload"
    )
    args = parser.parse_args(argv)

    try:
        repo, number = resolve_target(args.pr, args.repo)

        if args.head_only or args.assert_head:
            current = head_sha(repo, number)
            if args.assert_head:
                if not FULL_SHA.match(args.assert_head):
                    raise GhError(
                        f"--assert-head must be a full 40-character SHA, "
                        f"got {args.assert_head!r}"
                    )
                if current != args.assert_head:
                    print(
                        f"HEAD MOVED: pinned {args.assert_head} but head is now "
                        f"{current}.\nRe-fetch the diff and re-verify every line "
                        "number before returning findings.",
                        file=sys.stderr,
                    )
                    print(current)
                    return 4
                print(f"HEAD UNCHANGED: {current}", file=sys.stderr)
            print(current)
            return 0

        view = fetch_view(repo, number)
        sha = view["headRefOid"]
        if not FULL_SHA.match(sha):
            raise GhError(f"head SHA is not 40 hex chars: {sha!r}")

        payload = {
            "repo": repo,
            "number": view["number"],
            "url": view["url"],
            "title": view["title"],
            "body": view["body"],
            "state": view["state"],
            "is_draft": view["isDraft"],
            "author": (view.get("author") or {}).get("login"),
            "base_branch": view["baseRefName"],
            "head_branch": view["headRefName"],
            "head_sha": sha,
            "additions": view["additions"],
            "deletions": view["deletions"],
            "changed_files": view["changedFiles"],
            "files": view["files"],
            "review_decision": view["reviewDecision"],
            "reviews": view["reviews"],
            "comments": view["comments"],
            "checks": view["statusCheckRollup"],
            "review_threads": fetch_threads(repo, number),
        }
        if not args.no_diff:
            payload["diff"] = fetch_diff(repo, number)

        print(json.dumps(payload, indent=2))
        return 0
    except GhError as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
