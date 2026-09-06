---
description: Execute an approved, already-written multi-ticket playbook end to end through lead-worker routing.
agent: orchestrator
---
Execute approved playbook: `$ARGUMENTS`.

Load the `execute-playbook` skill before doing any work and follow it exactly. Read the
playbook and its ticket dependency order in full before assigning anything, and maintain a
ticket ledger. Delegate every implementation ticket whole to `worker`; never implement a
ticket yourself. After a worker returns, inspect the actual diff and rerun the ticket's
verification commands yourself — a worker's self-report is not sufficient evidence. One
correction resumes the same worker; a second materially similar failure (same
failure_fingerprint) goes to a fresh `rescue` dispatch instead of a third attempt on the
same worker. After a logical batch of tickets lands, dispatch a fresh `verifier` — never
the worker that implemented the batch — before merge. Delegate any Linear issue-tracker
reads or writes to `documentation`; never call Linear MCP tools yourself.

Merge each accepted ticket branch into the integration branch with a non-fast-forward
merge. Never merge into the trunk branch and never push unless the user explicitly says so
in that message. Production, security, secret, destructive-action, or missing-user-input
boundaries stop for authority; a stronger tier cannot grant itself authority it was not
given.

Return the ticket ledger, files changed per ticket, checks with exit codes, corrections and
rescue use, deviations, and unresolved risks.
