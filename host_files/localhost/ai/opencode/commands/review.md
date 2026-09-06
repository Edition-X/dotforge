---
description: Independently review current changes or a revision range through a fresh read-only verifier and run relevant deterministic checks.
agent: orchestrator
---
Review current working changes or revision range: `$ARGUMENTS`.

Keep review read-only. Inspect status, diff, relevant history, requirements, and
repository instructions yourself first. Dispatch `verifier` to run relevant deterministic
checks and independently review requirements coverage, correctness, regressions, missing
tests, error handling, complexity, security, operational safety, portability, performance
assumptions, concurrency hazards, configuration boundaries, and claimed versus executed
commands.

Return exactly one final verdict from verifier's evidence — `PASS`, `PASS_WITH_REQUIRED_FIXES`,
or `FAIL` — followed by prioritized file/line findings, check exit codes, and residual
risks. Do not edit, commit, push, merge, or submit external review actions.
