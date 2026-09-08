#!/usr/bin/env python3
"""
Mechanically verify a source line at an exact commit, and build the immutable
GitHub blob link for it.

This exists because line numbers guessed from a diff hunk header, a patch
position, or truncated output are wrong often enough to make a review comment
land on the wrong statement. Nothing here estimates: it fetches the file at a
full 40-character SHA, numbers it, and asserts the expected code is on the
line you claim.

Read-only. It issues a single `gh api` GET for the blob and nothing else.

Usage:
  # print the whole file, numbered, at an exact SHA
  verify_lines.py --repo owner/repo --sha <40-hex> --path src/app.py

  # verify one line and emit its permalink
  verify_lines.py --repo owner/repo --sha <40-hex> --path src/app.py \\
      --line 88 --expect 'if response.status != 200:'

  # verify a range (both endpoints are checked)
  verify_lines.py --repo owner/repo --sha <40-hex> --path src/app.py \\
      --line 88 --end-line 94 --expect 'if response' --expect-end 'return False'

  # offline: verify against a local file instead of fetching
  verify_lines.py --repo owner/repo --sha <40-hex> --path src/app.py \\
      --line 88 --expect 'foo' --from-file /tmp/app.py

Exit codes:
  0  verification passed (or a plain listing was printed)
  2  verification failed - do not use this anchor in a review
  3  the file could not be fetched
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys

FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
REPO_SLUG = re.compile(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$")


class VerifyError(Exception):
    """Verification failed. The caller must not use the anchor."""


class FetchError(Exception):
    """The blob could not be retrieved."""


def fetch_blob(repo: str, sha: str, path: str) -> str:
    """Fetch file contents at an exact commit via a read-only gh API GET."""
    cmd = [
        "gh",
        "api",
        f"repos/{repo}/contents/{path}?ref={sha}",
        "-H",
        "Accept: application/vnd.github.raw",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError as exc:  # pragma: no cover - environment specific
        raise FetchError("gh CLI not found on PATH; run `brew install gh`") from exc

    if result.returncode != 0:
        raise FetchError(
            f"gh api failed for {repo}@{sha[:12]}:{path}\n{result.stderr.strip()}"
        )
    return result.stdout


def numbered(lines: list[str], start: int = 1, end: int | None = None) -> str:
    """Render source with mechanically generated line numbers."""
    end = len(lines) if end is None else min(end, len(lines))
    start = max(1, start)
    width = len(str(end))
    return "\n".join(
        f"{n:>{width}}: {lines[n - 1]}" for n in range(start, end + 1)
    )


def blob_url(repo: str, sha: str, path: str, line: int, end_line: int | None) -> str:
    anchor = f"#L{line}" if end_line is None else f"#L{line}-L{end_line}"
    return f"https://github.com/{repo}/blob/{sha}/{path}{anchor}"


def check_line(lines: list[str], line: int, expect: str | None, label: str) -> str:
    """Assert a line exists and contains the expected snippet. Returns the line."""
    if line < 1:
        raise VerifyError(f"{label} {line} is not a valid line number")
    if line > len(lines):
        raise VerifyError(
            f"{label} {line} does not exist; the file has {len(lines)} lines at this SHA"
        )
    content = lines[line - 1]
    if expect is not None and expect not in content:
        raise VerifyError(
            f"{label} {line} does not contain the expected snippet.\n"
            f"  expected to find: {expect!r}\n"
            f"  actual line {line}: {content!r}"
        )
    return content


def validate_args(args: argparse.Namespace) -> None:
    if not REPO_SLUG.match(args.repo):
        raise VerifyError(f"--repo must be owner/repo, got {args.repo!r}")
    if not FULL_SHA.match(args.sha):
        raise VerifyError(
            f"--sha must be a full 40-character commit SHA, got {args.sha!r}. "
            "A branch name or short SHA is not immutable and must not anchor a review."
        )
    if args.end_line is not None:
        if args.line is None:
            raise VerifyError("--end-line requires --line")
        if args.end_line < args.line:
            raise VerifyError(
                f"--end-line {args.end_line} is before --line {args.line}"
            )
    if args.expect is not None and args.line is None:
        raise VerifyError("--expect requires --line")
    if args.expect_end is not None and args.end_line is None:
        raise VerifyError("--expect-end requires --end-line")


def run(args: argparse.Namespace) -> int:
    validate_args(args)

    if args.from_file:
        try:
            with open(args.from_file, encoding="utf-8") as handle:
                content = handle.read()
        except OSError as exc:
            raise FetchError(f"could not read {args.from_file}: {exc}") from exc
    else:
        content = fetch_blob(args.repo, args.sha, args.path)

    lines = content.split("\n")
    if lines and lines[-1] == "":
        lines.pop()

    if args.line is None:
        print(numbered(lines))
        return 0

    start_text = check_line(lines, args.line, args.expect, "line")
    end_text = None
    if args.end_line is not None:
        end_text = check_line(lines, args.end_line, args.expect_end, "end line")

    url = blob_url(args.repo, args.sha, args.path, args.line, args.end_line)

    if args.json:
        print(
            json.dumps(
                {
                    "verified": True,
                    "repo": args.repo,
                    "sha": args.sha,
                    "path": args.path,
                    "line": args.line,
                    "end_line": args.end_line,
                    "line_text": start_text,
                    "end_line_text": end_text,
                    "url": url,
                    "anchor": (
                        f"{args.path}:{args.line}"
                        if args.end_line is None
                        else f"{args.path}:{args.line}-{args.end_line}"
                    ),
                },
                indent=2,
            )
        )
        return 0

    window_end = args.end_line if args.end_line is not None else args.line
    print(
        numbered(
            lines,
            start=args.line - args.context,
            end=window_end + args.context,
        )
    )
    print()
    print(f"VERIFIED {args.path}:{args.line}" + (
        f"-{args.end_line}" if args.end_line is not None else ""
    ))
    print(url)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify a source line at an exact SHA and build its permalink.",
    )
    parser.add_argument("--repo", required=True, help="owner/repo")
    parser.add_argument("--sha", required=True, help="full 40-character head SHA")
    parser.add_argument("--path", required=True, help="repo-relative file path")
    parser.add_argument("--line", type=int, help="1-indexed line to verify")
    parser.add_argument("--end-line", type=int, help="end of a verified range")
    parser.add_argument("--expect", help="substring that must appear on --line")
    parser.add_argument("--expect-end", help="substring that must appear on --end-line")
    parser.add_argument(
        "--context", type=int, default=3, help="context lines to print (default 3)"
    )
    parser.add_argument("--from-file", help="read a local file instead of fetching")
    parser.add_argument("--json", action="store_true", help="emit JSON")
    args = parser.parse_args(argv)

    try:
        return run(args)
    except VerifyError as exc:
        print(f"NOT VERIFIED: {exc}", file=sys.stderr)
        print(
            "Do not anchor a review comment here until this passes.", file=sys.stderr
        )
        return 2
    except FetchError as exc:
        print(f"FETCH FAILED: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
