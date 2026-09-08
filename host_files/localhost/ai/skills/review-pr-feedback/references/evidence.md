# Evidence bar

A finding is a claim about behavior. It ships only when the claim is demonstrable.

## Validating a candidate finding

1. Read the changed code plus enough surrounding context to know what it actually does.
2. Trace the relevant callers and callees. A bug that no reachable path triggers is not
   a bug in this PR.
3. Check tests, documentation, configuration, and the repository's established patterns.
   A deviation from a repo-wide pattern is evidence; a deviation from your preference is not.
4. Name the concrete failure path: input or state → code path taken → wrong result.
5. Decide whether the behavior is intentional or documented before calling it a defect.
6. For any claim that rests on how an external tool, language, shell, API, framework or
   runtime behaves, find the official documentation that says so.
7. Reproduce it with read-only commands where that is safe and useful — running the
   existing test suite, evaluating a shell expression, checking a regex against a sample.
   Never a command that writes.
8. If the evidence is still speculative, drop it. Move it to the exclusions section.

## Documented behavior triage

When code or a README explicitly documents a limitation, put the finding in exactly one
of these three buckets:

| Situation | Verdict |
|---|---|
| Implementation contradicts documented behavior | Valid bug. Report it. |
| Implementation matches a documented tradeoff | Not a bug. Omit, or raise as an explicitly optional design question. |
| Documentation overstates what the implementation guarantees | Documentation/design mismatch. Report it as that, not as a code bug. |

A README that says "this check is best-effort and will miss nested cases" means a missed
nested case is the design, not a defect. Calling it a bug wastes Dan's time and signals
the review did not read the docs.

## Citing external behavior

Every external behavior claim needs an inline link to the official documentation for that
exact claim.

Acceptable sources:

- Official product documentation
- Official language or library documentation
- The official project repository's own documentation
- The PR's own code or README, read at the exact head SHA

Not acceptable:

- An unlinked assertion ("bash expands this before the redirect")
- A raw URL pasted next to a sentence
- A search-result snippet
- A blog post, Stack Overflow answer, or tutorial when official docs cover it
- Any secondary source for behavior the official docs define

Always GitHub Markdown link syntax, and the linked text must state the claim the
destination actually supports:

- Bad: `The API does this (https://official.example/docs).`
- Bad: `[See the docs](https://official.example/docs).`
- Good: `[The API returns 409 when the resource already exists](https://official.example/docs).`

If official documentation for the claim cannot be found, the claim is not established.
Drop the finding or restate it as something the PR's own code proves.

## Examples in findings

Examples must be realistic and must actually exercise the code path.

- Derive the value from the code. If the threshold is `350`, the smallest breaking example
  is `351`. Use it.
- A larger illustrative number is fine, but label it illustrative and say why you chose it.
  Never let an invented number look like it came from the source.
- Prefer inputs a real caller — a person, or an AI agent driving the tool — would plausibly
  produce. A contrived bypass that no caller would ever construct is weak evidence.

For every example, state three things:

1. Why a caller would naturally produce it.
2. Which condition it triggers.
3. What result follows.
