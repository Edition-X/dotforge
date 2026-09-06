---
description: Orchestrate a broad goal by delegating whole tickets to a worker, reviewing evidence, correcting once, and verifying before acceptance.
agent: orchestrator
---
Execute broad goal: `$ARGUMENTS`.

Establish acceptance criteria before assigning anything. Inspect repository conventions and
current Git status. Break the goal into whole, independent tickets and maintain a compact
ledger: objective, dependencies, assigned role, expected output, verification, status,
attempts. Delegate every implementation ticket whole to `worker`; never implement a ticket
yourself. Delegate any Linear issue-tracker reads or writes to `documentation`; never call
Linear MCP tools yourself.

Parallelize only independent tickets with non-overlapping file scopes and no shared test
contention; keep at most three active workers at once. After a worker returns, inspect the
actual diff and rerun its verification commands yourself — a self-report is not sufficient
evidence. One focused correction returns to the same worker; a second materially similar
failure (same failure_fingerprint) goes to a fresh `rescue` dispatch instead of a third
attempt. After a logical batch lands, dispatch a fresh `verifier` — never the worker that
implemented the batch — before merge. Do not push, merge into a trunk branch, publish,
deploy production, or run production load tests.

Return the ticket ledger, files changed per ticket, checks with exit codes, corrections and
rescue use, unresolved risks, and unsupported checks.
