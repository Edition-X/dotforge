---
description: Implement a bounded feature or fix, verify it, obtain independent review, and correct required findings.
agent: orchestrator
---
Implement feature or fix: `$ARGUMENTS`.

Inspect first. Establish acceptance criteria and plan when more than a few files, multiple components, ambiguity, production impact, or security risk exists. Delegate repository facts to `explorer`, implementation to `implementer` or `worker-fast`, deterministic checks to `test-runner`, and read-only review to `reviewer`. Give each worker exact allowed and forbidden files, constraints, acceptance criteria, and commands.

Inspect actual diff after implementation. If reviewer returns `PASS_WITH_REQUIRED_FIXES` or `FAIL`, create explicit correction tasks, apply smallest justified fixes, rerun focused tests, and review again. Stop after repeated identical failures and route `debugger` or `architect` as appropriate.

Return final diff summary, tests and exit codes, reviewer verdict, corrections, and residual risk. Do not push or merge.
