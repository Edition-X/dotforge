# Output template

Reproduce this structure exactly. The header block is fixed; the finding sections repeat.

## Header

```markdown
## Review result

- Reviewed PR: `https://github.com/owner/repo/pull/123`
- Reviewed head: `a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0`
- Existing comments inspected: yes
- PR or repository modified: no
- Comments posted: no
- Recommendation: request changes
- Reason: The retry path treats permanent 4xx failures as transient.
```

`Reviewed head` is the full 40-character SHA, re-confirmed after the review work.
`Recommendation` is one of `approve`, `comment`, `request changes`. `Reason` is one
sentence.

## Each finding

Findings are numbered in priority order — highest risk first.

```markdown
## Finding 1: Retry loop treats 4xx as transient

**Add comment on:** [`src/client/retry.py:88`](https://github.com/owner/repo/blob/a1b2c3d4.../src/client/retry.py#L88)

**Why this is an issue**

`_should_retry` returns true for any non-2xx status, so a 400 from a malformed payload is
retried five times with backoff before surfacing. A caller passing an invalid `filters`
value — the shape an agent-generated call most often gets wrong — waits the full 31s
backoff chain for an error that was permanent on the first attempt.
[The API returns 400 only for payloads it will never accept](https://official.example/docs/errors),
so no retry can succeed.

**Better solution**

Gate on the server-error range, and let client errors fail fast:

    if response.status >= 500 or response.status == 429:
        return True
    return False

**Why this is better**

Removes the wasted backoff chain on permanently invalid requests and stops a malformed
call from occupying a connection for 31s. Tradeoff: 429 has to be listed explicitly, since
it is a 4xx that genuinely is retryable.

**Comment to paste**

> This retries on 4xx as well as 5xx, so a malformed request burns all five attempts before
> failing. [The API returns 400 only for payloads it will never accept](https://official.example/docs/errors)
> — gate the retry on `status >= 500 or status == 429` so client errors fail immediately.
```

Rules for the finding body:

- **Add comment on** — verified `path:line`, linked to the immutable blob URL at the head
  SHA. Only ever produced by `scripts/verify_lines.py`.
- **Why this is an issue** — what the code does now, the realistic trigger, the resulting
  behavior or risk, and why it matters for what this PR set out to do. Inline official
  links for every external claim.
- **Better solution** — a concrete alternative. Code shape when it helps. Never applied to
  the repository.
- **Why this is better** — the failure mode removed, and the tradeoff taken on. A
  suggestion with no stated tradeoff usually means the tradeoff was not thought through.
- **Comment to paste** — blockquoted, in Dan's voice per `references/tone.md`, every link
  in `[text](URL)` form, no raw URL anywhere inside it.

For an omission, the body says so plainly: what is missing, why the anchored line is the
right place to insert it, and what happens today without it.

## Exclusions

```markdown
## Findings intentionally excluded

- **Nested `$(...)` not blocked** — `README.md` documents this check as best-effort against
  flat commands, so the miss is the documented design, not a defect.
- **`config.py` global mutable default** — pre-existing, untouched by this diff.
- **Possible race in the cache warm path** — no reachable caller holds the lock across the
  window; could not establish a concrete failure path.
- **Missing type hints on `_parse`** — cosmetic.
- **`limit` bounds check** — already raised in Dan's existing comment on line 42.
```

One bullet per concern investigated and dropped, each naming the reason: documented
tradeoff, not caused by this PR, too speculative, cosmetic only, or already covered by an
existing comment.

Keep this section even when it is short. It is the evidence that the review looked wider
than what it reported.

## No findings

```markdown
## Review result

- Reviewed PR: `https://github.com/owner/repo/pull/123`
- Reviewed head: `a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0`
- Existing comments inspected: yes
- PR or repository modified: no
- Comments posted: no
- Recommendation: approve
- Reason: No actionable findings; the diff is small and covered by tests.

No actionable findings.

## Findings intentionally excluded
...
```

Never pad a clean review with a manufactured concern.
