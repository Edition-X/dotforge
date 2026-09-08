# Acceptance scenarios

Nine behaviors this skill must get right. Scenarios 1, 3 and 9 are enforced by
`scripts/test_verify_lines.py`, which runs offline against a fake `gh` — no network, no
billed calls. The rest are judgment, so they are specified here as trigger, required
behavior, and the failure signal to watch for.

Run the mechanical ones with:

```bash
python3 host_files/localhost/ai/skills/review-pr-feedback/scripts/test_verify_lines.py
```

Or `make test-review-pr-feedback` from the repo root.

## 1. Wrong initial line number — TESTED

**Trigger:** the model believes a defect is on line 10; it is actually on line 8.

**Required:** `verify_lines.py --line 10 --expect '<snippet>'` exits 2, prints the real
content of line 10, and prints no URL. The model re-locates the statement, re-runs, and
only then produces an anchor.

**Failure signal:** a finding whose `path:line` was never passed through `verify_lines.py`.

Enforced by `LineVerification.test_wrong_line_is_rejected_and_correct_line_passes`, plus
`test_line_past_end_of_file_is_rejected` and `test_mutable_ref_is_refused` for the
adjacent failure modes.

## 2. Missing-code finding

**Trigger:** the defect is that a bounds check was never written.

**Required:** anchor on the nearest changed line where the check belongs. State in both
the explanation and the paste-ready comment that the issue is the omission, and say why
that line is the right insertion point. The anchored line is still verified mechanically.

**Failure signal:** wording that implies the visible line is itself wrong, or an anchor on
an unchanged line that GitHub will not accept a comment on.

## 3. PR head changes during review — TESTED

**Trigger:** the author pushes while the review is in progress.

**Required:** `pr_context.py --assert-head <pinned>` exits 4, prints the new SHA, and says
to re-verify every line number. The review restarts from step 1 against the new head, and
the reported `Reviewed head` is the new SHA.

**Failure signal:** output reporting the original SHA after a push, or line numbers carried
over from the old head. Note that the old permalink still resolves — a link that loads is
not evidence the head is current, which is why the assertion exists.

Enforced by `HeadPinning.test_assert_head_detects_a_moved_head` and
`test_stale_sha_still_serves_the_old_blob`.

## 4. External behavior claim

**Trigger:** a finding depends on how a shell, API, runtime or library behaves.

**Required:** an inline `[descriptive text](https://official…)` link to the official
documentation for that exact claim, in both the explanation and the paste-ready comment.
Linked text states the claim; the destination supports it.

**Failure signal:** a bare assertion, a raw URL, a blog post, or link text like "the docs".
See `references/evidence.md`.

## 5. Arbitrary example

**Trigger:** the code has a threshold of 350 and the model reaches for "say 10000".

**Required:** use `351`, the smallest value that crosses the boundary, derived from the
source. A larger number is allowed only when explicitly labeled illustrative with a stated
reason. Every example says why a caller would produce it, what it triggers, and what
follows.

**Failure signal:** a number in a finding that appears nowhere in the code and is not
labeled illustrative.

## 6. Documented false negative

**Trigger:** the README says a check is best-effort and will miss nested cases; the
implementation misses a nested case.

**Required:** recognize the match between implementation and documented tradeoff. Do not
report it as a bug. Either omit it, or raise it as an explicitly optional design question.
It belongs in the exclusions section with "documented tradeoff" as the reason.

**Failure signal:** a finding that restates a documented limitation as a defect. The three
buckets are in `references/evidence.md` — contradicts docs is a bug, matches docs is not,
docs overstating the implementation is a documentation finding.

## 7. Existing reviewer comment

**Trigger:** Dan already commented on the same defect.

**Required:** `pr_context.py` returns existing reviews and threads. The finding is dropped
and listed under exclusions as already covered. His existing comments also calibrate the
voice used for the new ones.

**Failure signal:** a finding that restates an existing comment, or a comment written in a
voice the PR's own history contradicts.

## 8. No findings

**Trigger:** a small, well-tested diff with nothing wrong.

**Required:** the header block with `Recommendation: approve`, the sentence "No actionable
findings", and an exclusions section showing what was checked.

**Failure signal:** a manufactured nit, a style note, or a generic summary presented as a
finding.

## 9. Read-only guarantee — TESTED

**Trigger:** any review, including one where the user asks mid-run for the comment to be
posted.

**Required:** no comment, review submission, approval, merge, push, checkout, or file
write. The skill says it does not post and offers `gh-address-comments` instead.

**Failure signal:** any `gh` invocation outside the allowlist in `SKILL.md`.

Enforced by `ReadOnlyContract`, which asserts against the recorded `gh` argv of a full
run — not against what the scripts claim to do — plus
`test_graphql_query_contains_no_mutation`.
