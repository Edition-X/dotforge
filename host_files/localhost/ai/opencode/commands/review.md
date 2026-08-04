---
description: Independently review current changes or a revision range and run relevant deterministic checks without editing.
agent: orchestrator
---
Review current working changes or revision range: `$ARGUMENTS`.

Keep review read-only. Inspect status, diff, relevant history, requirements, and repository instructions. Delegate deterministic checks to `test-runner` and independent analysis to `reviewer`. Review requirements coverage, correctness, regressions, tests, error handling, unnecessary complexity, security, operational safety, portability, performance, concurrency, configuration, and claimed versus executed commands.

Return exactly one final verdict from reviewer: `PASS`, `PASS_WITH_REQUIRED_FIXES`, or `FAIL`, followed by prioritized file/line findings, test exit codes, and residual risks. Do not edit, commit, push, merge, or submit external review actions.
