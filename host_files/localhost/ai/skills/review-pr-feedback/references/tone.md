# Dan's review-comment voice

This governs the **Comment to paste** block only. The surrounding explanation written for
Dan can be as long as it needs to be.

## Rules

- Direct. Concise. Plain language.
- Usually one short paragraph. Two only when a second is genuinely load-bearing.
- State the problem, then the requested change.
- Include just enough reason to make the comment actionable.
- No severity emoji, no `[MAJOR]`/`[nit]` labels, unless Dan asks for them.
- No "I noticed", "perhaps", "maybe", "it might be worth", "just", "consider possibly".
- No opening pleasantry, no closing thanks.
- Do not over-explain inside the comment. Deeper reasoning goes in the sections above it,
  which Dan reads and does not paste.
- All links in `[descriptive text](URL)` form. A raw URL in a paste-ready comment is a
  defect — Dan has to edit it before posting, which defeats the point.

## Learn from the PR itself

`scripts/pr_context.py` returns existing reviews and review threads with their authors.
Read Dan's own past comments on that repo before writing. If his comments there are
blunter, longer, or use a convention this file does not mention, follow the repository's
observed practice — real examples beat this file.

## Calibration

Bad — hedged, padded, raw URL, tells the author nothing actionable:

> Thanks for this! I noticed that maybe the retry loop here could potentially be an issue
> in some cases. It might be worth considering whether the backoff is correct, since the
> docs (https://docs.example/retries) seem to suggest something different. Just a thought!

Good — problem, consequence, requested change, linked evidence:

> This retries on 4xx as well as 5xx, so a malformed request burns all five attempts
> before failing. [The API returns 400 for permanently invalid payloads](https://docs.example/retries),
> so gate the retry on `status >= 500` and let 4xx fail immediately.

Good — an omission, stated as an omission:

> Nothing validates `limit` before it reaches the query builder, so a negative value
> reaches the database as `LIMIT -1`. Add a bounds check here, before the call.

Good — a design question rather than a defect. Say so, and keep it short:

> Optional: dropping the cache on every write makes the first read after a write slow
> under load. Fine if writes stay rare — worth revisiting if they don't.
