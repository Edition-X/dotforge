---
description: Implement a bounded feature or fix through one whole-ticket worker, verify it, and have a fresh verifier confirm the result.
agent: orchestrator
---
Implement feature or fix: `$ARGUMENTS`.

Inspect first. Establish acceptance criteria, and write a short plan when more than a few
files, multiple components, ambiguity, production impact, or security risk is involved.
Delegate the whole change as one ticket to `worker`: exact allowed and forbidden files,
constraints, acceptance criteria, and verification commands. Delegate any Linear reads or
writes to `documentation`; never call Linear MCP tools yourself.

Inspect the actual diff after the worker returns — do not trust its summary. Dispatch a
fresh `verifier` to check the integrated result read-only. If verifier finds required
fixes, create explicit correction tasks and return them to the same worker; rerun focused
checks and verify again. A second materially similar failure (same failure_fingerprint)
goes to a fresh `rescue` dispatch instead of a third attempt on the same worker.

Return the final diff summary, checks with exit codes, verifier findings, corrections, and
residual risk. Do not push or merge into a trunk branch.
