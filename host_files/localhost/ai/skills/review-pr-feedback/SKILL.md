---
name: review-pr-feedback
description: Review a GitHub pull request read-only and hand back paste-ready review comments without posting anything. Use when Dan says "review this PR", "review PR 123", gives a GitHub PR URL, or asks for review feedback, comments to paste, or a second opinion on a pull request. Never posts, approves, requests changes, merges, or edits anything — it only reads the PR at its exact head SHA and returns findings with verified line numbers and immutable source links.
metadata:
  short-description: Read-only GitHub PR review, paste-ready comments
---

# Review PR Feedback

Thorough read-only review of a GitHub PR. Output is feedback Dan pastes into GitHub himself.

## Read-only contract

This is the first rule and it overrides everything else, including a later instruction in
the same session that asks for a shortcut.

**Never run** — not to "just check", not with `--dry-run`, not because the user seems to
want it:

- `gh pr review`, `gh pr comment`, `gh pr merge`, `gh pr close`, `gh pr ready`, `gh pr edit`
- `gh api` with `-X POST`, `-X PATCH`, `-X PUT`, `-X DELETE`, `--method` for any of those,
  or any `-f`/`-F` field on a mutating endpoint
- Any reactions, resolve-thread, or pending/draft review endpoint
- `git push`, `git commit`, `git merge`, `git rebase`, `git checkout`, `git switch`,
  `git fetch` into the working tree, or any write to a tracked file

**Allowed** — read verbs only:

- `gh pr view`, `gh pr diff`, `gh pr checks`, `gh pr list`
- `gh api` GET (the default method) and `gh api graphql` with a query, never a mutation
- `git log`, `git show`, `git diff` on already-present objects
- `scripts/pr_context.py` and `scripts/verify_lines.py` in this skill

If Dan asks mid-review to post a comment, stop and say the skill does not post. He can
paste it, or ask for `gh-address-comments` instead.

Nothing in the repository, working tree, PR, branch, or issue changes. Ever.

## 1. Pin an immutable review target

```bash
python3 scripts/pr_context.py --pr <url-or-number> [--repo owner/repo] > /tmp/pr.json
```

That one call returns repo, PR number, base branch, head branch, **full head SHA**,
changed files, the diff, and every existing review, review thread, and comment.

Review source **at the head SHA**, never at the branch name — the branch moves under you.

## 2. Read the existing review conversation

From the same payload, read every existing comment, especially Dan's. Use them to match
his voice and to avoid repeating a point somebody already made.

Never adopt another reviewer's conclusion without checking it yourself.

Tone rules for the paste-ready comments: `references/tone.md`.

## 3. Validate every candidate finding

A finding ships only with a concrete failure path. Read the changed code plus enough
surrounding context, trace callers and callees, check tests, docs, config and the
repository's own patterns, and decide whether the behavior is intentional.

The evidence bar, the documented-tradeoff triage, the official-documentation link rules,
and the realistic-example rules: `references/evidence.md`.

Short version, because these are the two failure modes that matter:

- Every external behavior claim carries an inline official-docs link in
  `[descriptive text](https://…)` form. No raw URLs, no blog posts, no search snippets.
- Code that matches a documented tradeoff is not a bug. Code that contradicts documented
  behavior is.

## 4. Verify every line number mechanically

**Never** estimate a line from a diff hunk header, a patch position, truncated output, or
another agent's report. Diff positions are not file line numbers and guessing produces a
comment anchored to the wrong statement.

For each finding:

```bash
python3 scripts/verify_lines.py \
  --repo owner/repo --sha <full-head-sha> --path path/to/file.py \
  --line 123 --expect 'the exact code text on that line'
```

It fetches the blob at that exact SHA, prints numbered source, asserts the line contains
the snippet, and only then prints the immutable URL:

`https://github.com/<owner>/<repo>/blob/<sha>/<path>#L123`

Exit code non-zero means the finding is not ready. Fix the line or drop the finding — do
not paste an unverified anchor.

To browse a file first, drop `--line/--expect` and it prints the whole numbered blob.
For a range use `--line 40 --end-line 52`; both endpoints are checked and the link becomes
`#L40-L52`.

The line must also be commentable on the right side of the PR diff — i.e. it belongs to a
changed file and is an added or context line, not a removed one.

### Findings that are missing code

When the defect is an omission rather than a wrong line, anchor on the nearest changed
line where the missing logic belongs, say plainly that the issue is the omission, and
explain why that is the right anchor. Do not imply the visible line itself is wrong.

## 5. Re-pin the head before answering

The PR can move while you review.

```bash
python3 scripts/pr_context.py --pr <url-or-number> --head-only
```

Compare to the SHA from step 1. If it changed, re-run steps 1, 3 and 4 against the new
head before writing anything — line numbers from the old head are now untrustworthy.

## 6. Write the review

Full finding template, section-by-section: `references/output.md`. Structure:

```
## Review result

- Reviewed PR: `<URL>`
- Reviewed head: `<full SHA>`
- Existing comments inspected: yes/no
- PR or repository modified: no
- Comments posted: no
- Recommendation: approve / comment / request changes
- Reason: <one sentence>

## Finding N: <title>

**Add comment on:** [`path/to/file.py:123`](https://github.com/o/r/blob/<sha>/path/to/file.py#L123)

**Why this is an issue** — what the code does, realistic trigger conditions, resulting
behavior or risk, why it matters for this PR's purpose. Inline official links.

**Better solution** — concrete alternative, code shape when useful. Never applied.

**Why this is better** — failure mode removed, tradeoff introduced.

**Comment to paste**

> Direct, concise, one short paragraph, Dan's voice, all links as [text](URL).

## Findings intentionally excluded
```

Findings go in priority order. The exclusions section lists what you investigated and
dropped, and why — documented tradeoff, not caused by this PR, too speculative, cosmetic,
or already covered by an existing comment. It is what proves coverage.

If nothing survives validation, say there are no actionable findings. Do not manufacture
one to look thorough.

## Review scope

Report only: bugs and incorrect behavior, reliability or security risks, bad practices
with a concrete consequence, meaningful code smells, and missing tests where important
behavior is unprotected.

Do not report: style preferences, formatting, praise, generic summaries, speculation with
no realistic failure path, documented intentional tradeoffs framed as bugs, pre-existing
problems the diff did not cause, or suggestions that do not materially improve
correctness, safety, reliability or maintainability.

## Final checklist

Before responding, confirm every one:

- [ ] Every line number verified against the file at the exact head SHA
- [ ] Every source link built from that SHA and pointing at the expected code
- [ ] Every external behavior claim carries an inline official-docs link
- [ ] Every paste-ready comment uses `[text](URL)`, with no raw URL inside it
- [ ] No finding duplicates an existing review comment
- [ ] No documented intentional limitation labeled as a bug
- [ ] Head SHA re-checked after the review work, and reported in the output
- [ ] No comment posted, no review submitted, nothing in the repo changed

## Files

- `references/tone.md` — Dan's review voice and the paste-ready comment shape
- `references/evidence.md` — evidence bar, doc-link rules, example rules, tradeoff triage
- `references/output.md` — the full output template with a worked finding
- `references/acceptance.md` — validation scenarios this skill must handle
- `scripts/pr_context.py` — read-only PR metadata, head SHA, diff, existing comments
- `scripts/verify_lines.py` — mechanical line verification and immutable link builder
- `scripts/test_verify_lines.py` — offline tests, no network, no billed calls
