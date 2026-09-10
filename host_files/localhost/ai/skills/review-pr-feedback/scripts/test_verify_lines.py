#!/usr/bin/env python3
"""Offline coverage for the review-pr-feedback helper scripts.

No network, no billed calls, no GitHub. A fake `gh` is placed on PATH; it
records every invocation so the read-only guarantee is asserted against what
the scripts actually ran, not against what they claim to run.

Covers the mechanically testable acceptance scenarios from
references/acceptance.md: wrong initial line number (1), PR head changing
mid-review (3), and the read-only guarantee (9).
"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
FIXTURES = SCRIPTS.parent / "tests" / "fixtures"
SOURCE = FIXTURES / "sample_source.py"

SHA = "1111111111111111111111111111111111111111"
MOVED_SHA = "2222222222222222222222222222222222222222"
REPO = "acme/widget"
PATH_IN_REPO = "src/client/retry.py"

# Anything matching these in a recorded gh invocation means the read-only
# contract was broken.
FORBIDDEN = (
    "-X POST", "-X PATCH", "-X PUT", "-X DELETE",
    "--method POST", "--method PATCH", "--method PUT", "--method DELETE",
    "pr review", "pr comment", "pr merge", "pr close", "pr edit", "pr ready",
    "pr checkout", "mutation",
)

FAKE_GH = f'''#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
with open(os.environ["GH_LOG"], "a") as log:
    log.write(json.dumps(args) + "\\n")
fixtures = os.environ["GH_FIXTURES"]
head = os.environ.get("GH_HEAD", "{SHA}")
joined = " ".join(args)

if args[:2] == ["repo", "view"]:
    print(json.dumps({{"nameWithOwner": "{REPO}"}}))
elif args[:1] == ["api"] and "graphql" in args:
    print(open(os.path.join(fixtures, "review_threads.json")).read())
elif args[:1] == ["api"] and "contents" in joined:
    if os.environ.get("GH_FETCH_FAIL"):
        sys.stderr.write("HTTP 404: Not Found\\n")
        sys.exit(1)
    print(open(os.path.join(fixtures, "sample_source.py")).read(), end="")
elif args[:2] == ["pr", "diff"]:
    print("diff --git a/{PATH_IN_REPO} b/{PATH_IN_REPO}")
elif args[:2] == ["pr", "view"] and "headRefOid" == args[args.index("--json") + 1]:
    print(json.dumps({{"headRefOid": head}}))
elif args[:2] == ["pr", "view"]:
    view = json.load(open(os.path.join(fixtures, "pr_view.json")))
    view["headRefOid"] = head
    print(json.dumps(view))
else:
    sys.stderr.write("fake gh: unhandled " + joined + "\\n")
    sys.exit(1)
'''


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


verify_lines = load("verify_lines")
pr_context = load("pr_context")


class Harness(unittest.TestCase):
    """Runs the scripts as subprocesses with a fake gh on PATH."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.bin = Path(self._tmp.name)
        gh = self.bin / "gh"
        gh.write_text(FAKE_GH)
        gh.chmod(0o755)
        self.log = self.bin / "gh.log"
        self.addCleanup(self._tmp.cleanup)

    def run_script(self, name, *args, head=SHA, **env_extra):
        env = dict(os.environ)
        env["PATH"] = f"{self.bin}{os.pathsep}{env['PATH']}"
        env["GH_LOG"] = str(self.log)
        env["GH_FIXTURES"] = str(FIXTURES)
        env["GH_HEAD"] = head
        env.update(env_extra)
        return subprocess.run(
            [sys.executable, str(SCRIPTS / f"{name}.py"), *args],
            capture_output=True, text=True, env=env, check=False,
        )

    def gh_calls(self):
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def assert_read_only(self):
        for call in self.gh_calls():
            joined = " ".join(call)
            for bad in FORBIDDEN:
                self.assertNotIn(
                    bad, joined, f"gh invocation broke the read-only contract: {joined}"
                )


class LineVerification(Harness):
    def test_wrong_line_is_rejected_and_correct_line_passes(self):
        """Acceptance 1: a guessed line number must fail before it reaches output."""
        wrong = self.run_script(
            "verify_lines", "--repo", REPO, "--sha", SHA, "--path", PATH_IN_REPO,
            "--line", "10", "--expect", "if status != 200:",
        )
        self.assertEqual(wrong.returncode, 2)
        self.assertIn("NOT VERIFIED", wrong.stderr)
        # The failure names the real content of the claimed line, so the model
        # can correct itself rather than guess again.
        self.assertIn("return False", wrong.stderr)
        self.assertNotIn("https://github.com", wrong.stdout)

        right = self.run_script(
            "verify_lines", "--repo", REPO, "--sha", SHA, "--path", PATH_IN_REPO,
            "--line", "8", "--expect", "if status != 200:",
        )
        self.assertEqual(right.returncode, 0)
        self.assertIn(
            f"https://github.com/{REPO}/blob/{SHA}/{PATH_IN_REPO}#L8", right.stdout
        )
        self.assert_read_only()

    def test_range_verifies_both_endpoints(self):
        ok = self.run_script(
            "verify_lines", "--repo", REPO, "--sha", SHA, "--path", PATH_IN_REPO,
            "--line", "8", "--end-line", "10",
            "--expect", "if status", "--expect-end", "return False",
        )
        self.assertEqual(ok.returncode, 0)
        self.assertIn("#L8-L10", ok.stdout)

        bad_end = self.run_script(
            "verify_lines", "--repo", REPO, "--sha", SHA, "--path", PATH_IN_REPO,
            "--line", "8", "--end-line", "10",
            "--expect", "if status", "--expect-end", "return True",
        )
        self.assertEqual(bad_end.returncode, 2)
        self.assertIn("end line 10", bad_end.stderr)

    def test_line_past_end_of_file_is_rejected(self):
        result = self.run_script(
            "verify_lines", "--repo", REPO, "--sha", SHA, "--path", PATH_IN_REPO,
            "--line", "99", "--expect", "anything",
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("the file has 14 lines", result.stderr)

    def test_mutable_ref_is_refused(self):
        """A branch name or short SHA can never anchor a review comment."""
        for ref in ("main", "1111111", "HEAD", "feat/retry-backoff"):
            result = self.run_script(
                "verify_lines", "--repo", REPO, "--sha", ref, "--path", PATH_IN_REPO,
                "--line", "8", "--expect", "if status",
            )
            self.assertEqual(result.returncode, 2, ref)
            self.assertIn("full 40-character commit SHA", result.stderr)
        self.assertEqual(self.gh_calls(), [], "no fetch should happen for a bad ref")

    def test_json_output_carries_verified_anchor(self):
        result = self.run_script(
            "verify_lines", "--repo", REPO, "--sha", SHA, "--path", PATH_IN_REPO,
            "--line", "4", "--expect", "RETRY_THRESHOLD = 350", "--json",
        )
        self.assertEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["verified"])
        self.assertEqual(payload["anchor"], f"{PATH_IN_REPO}:4")
        self.assertEqual(payload["line_text"], "RETRY_THRESHOLD = 350")
        self.assertEqual(payload["sha"], SHA)

    def test_fetch_failure_is_distinct_from_verification_failure(self):
        result = self.run_script(
            "verify_lines", "--repo", REPO, "--sha", SHA, "--path", PATH_IN_REPO,
            "--line", "8", "--expect", "if status", GH_FETCH_FAIL="1",
        )
        self.assertEqual(result.returncode, 3)
        self.assertIn("FETCH FAILED", result.stderr)

    def test_offline_from_file_matches_fetched_result(self):
        result = self.run_script(
            "verify_lines", "--repo", REPO, "--sha", SHA, "--path", PATH_IN_REPO,
            "--line", "8", "--expect", "if status != 200:",
            "--from-file", str(SOURCE), "--json",
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(self.gh_calls(), [], "--from-file must not call gh")


class NumberingUnits(unittest.TestCase):
    """The numbering is generated from the file, never transcribed by hand."""

    def setUp(self):
        self.lines = SOURCE.read_text().split("\n")
        if self.lines and self.lines[-1] == "":
            self.lines.pop()

    def test_numbering_matches_the_file(self):
        rendered = verify_lines.numbered(self.lines).split("\n")
        self.assertEqual(len(rendered), 14)
        self.assertEqual(rendered[7], " 8:     if status != 200:")
        self.assertEqual(rendered[3], " 4: RETRY_THRESHOLD = 350")

    def test_numbering_window_is_clamped_to_the_file(self):
        rendered = verify_lines.numbered(self.lines, start=-5, end=99).split("\n")
        self.assertEqual(len(rendered), 14)
        self.assertTrue(rendered[0].strip().startswith("1:"))

    def test_blob_url_shapes(self):
        self.assertEqual(
            verify_lines.blob_url(REPO, SHA, PATH_IN_REPO, 8, None),
            f"https://github.com/{REPO}/blob/{SHA}/{PATH_IN_REPO}#L8",
        )
        self.assertEqual(
            verify_lines.blob_url(REPO, SHA, PATH_IN_REPO, 8, 10),
            f"https://github.com/{REPO}/blob/{SHA}/{PATH_IN_REPO}#L8-L10",
        )


class HeadPinning(Harness):
    def test_head_only_prints_full_sha(self):
        result = self.run_script("pr_context", "--pr", "123", "--repo", REPO)
        self.assertEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["head_sha"], SHA)
        self.assertEqual(payload["base_branch"], "main")
        self.assertEqual(payload["repo"], REPO)
        self.assertEqual(len(payload["review_threads"]), 1)
        self.assertEqual(payload["reviews"][0]["author"]["login"], "dkelly")
        self.assert_read_only()

    def test_assert_head_detects_a_moved_head(self):
        """Acceptance 3: the PR moving mid-review must be detected, not assumed."""
        result = self.run_script(
            "pr_context", "--pr", "123", "--repo", REPO,
            "--assert-head", SHA, head=MOVED_SHA,
        )
        self.assertEqual(result.returncode, 4)
        self.assertIn("HEAD MOVED", result.stderr)
        self.assertIn("re-verify every line number", result.stderr)
        self.assertEqual(result.stdout.strip(), MOVED_SHA)

    def test_assert_head_passes_when_unchanged(self):
        result = self.run_script(
            "pr_context", "--pr", "123", "--repo", REPO, "--assert-head", SHA,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("HEAD UNCHANGED", result.stderr)
        self.assertEqual(result.stdout.strip(), SHA)

    def test_stale_sha_still_serves_the_old_blob(self):
        """After a move, the old permalink is still fetchable - which is exactly
        why the head must be re-asserted rather than inferred from a link
        that keeps resolving."""
        moved = self.run_script(
            "pr_context", "--pr", "123", "--repo", REPO,
            "--assert-head", SHA, head=MOVED_SHA,
        )
        self.assertEqual(moved.returncode, 4)
        stale = self.run_script(
            "verify_lines", "--repo", REPO, "--sha", SHA, "--path", PATH_IN_REPO,
            "--line", "8", "--expect", "if status != 200:",
        )
        self.assertEqual(stale.returncode, 0)
        self.assertIn(SHA, stale.stdout)

    def test_short_assert_head_is_refused(self):
        result = self.run_script(
            "pr_context", "--pr", "123", "--repo", REPO, "--assert-head", "1111111",
        )
        self.assertEqual(result.returncode, 3)
        self.assertIn("full 40-character SHA", result.stderr)


class TargetResolution(unittest.TestCase):
    def test_url_and_number_resolve_the_same(self):
        self.assertEqual(
            pr_context.resolve_target(f"https://github.com/{REPO}/pull/123", None),
            (REPO, "123"),
        )
        self.assertEqual(
            pr_context.resolve_target("https://github.com/acme/widget/pull/7/files", None),
            (REPO, "7"),
        )
        self.assertEqual(pr_context.resolve_target("#123", REPO), (REPO, "123"))

    def test_garbage_target_is_refused(self):
        for bad in ("not-a-pr", "https://gitlab.com/a/b/pull/1", ""):
            with self.assertRaises(pr_context.GhError):
                pr_context.resolve_target(bad, REPO)


class ReadOnlyContract(Harness):
    def test_full_flow_issues_only_read_verbs(self):
        """Acceptance 9: assert against recorded invocations, not intent."""
        self.run_script("pr_context", "--pr", f"https://github.com/{REPO}/pull/123")
        self.run_script(
            "verify_lines", "--repo", REPO, "--sha", SHA, "--path", PATH_IN_REPO,
            "--line", "8", "--expect", "if status != 200:",
        )
        calls = self.gh_calls()
        self.assertTrue(calls, "expected the flow to call gh at least once")
        allowed_heads = {("pr", "view"), ("pr", "diff"), ("repo", "view"), ("api",)}
        for call in calls:
            head = tuple(call[:2]) if call[0] != "api" else ("api",)
            self.assertIn(head, allowed_heads, f"unexpected gh verb: {call}")
        self.assert_read_only()

    def test_graphql_query_contains_no_mutation(self):
        query = pr_context.THREADS_QUERY.lower()
        self.assertNotIn("mutation", query)
        self.assertTrue(query.strip().startswith("query"))

    def test_scripts_never_reference_write_endpoints(self):
        for script in ("verify_lines.py", "pr_context.py"):
            body = (SCRIPTS / script).read_text()
            for bad in ("-X POST", "-X PATCH", "-X PUT", "-X DELETE", "git push"):
                # The prose in the module docstring may name what is forbidden;
                # only executable lines are checked.
                code = "\n".join(
                    line for line in body.split("\n")
                    if not line.lstrip().startswith("#")
                )
                self.assertNotIn(f'"{bad}"', code, f"{script} builds a write call")


if __name__ == "__main__":
    unittest.main(verbosity=2)
