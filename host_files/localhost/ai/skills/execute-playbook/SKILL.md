---
name: execute-playbook
description: Execute an approved, already-written multi-ticket playbook or roadmap end to end — lead reads the ticket order, delegates each ticket whole to a worker, reviews the real diff and reruns checks, allows one correction, escalates a repeated similar failure to rescue, and runs a fresh verifier before merge. Use when asked to execute, run, or work through an approved playbook, roadmap, or multi-ticket effort, or to resume it ticket by ticket.
---

# Execute playbook

This is normative procedure for running an approved playbook across multiple tickets with
a lead/worker split. It is not advisory — every point below is a requirement, not a
suggestion. Canonical role/tier/limit policy lives under
`host_files/localhost/ai/routing/` (`models.yml`, `workflow.yml`, `prompts/*.md`); this
skill states the procedure that policy implements. If this file and the routing policy
ever disagree, fix the disagreement rather than picking one silently.

## Roles

Five roles, defined by tier in `workflow.yml`:

- **lead** (orchestrator) — reads the playbook, owns the ticket ledger, reviews real diffs
  and check evidence, merges, and never implements a ticket itself.
- **worker** — owns one whole ticket end to end: branch, edit, verify, commit, memory.
- **verifier** — read-only; checks an already-integrated result, never implements.
- **rescue** — direct lead dispatch only, after a repeated similar failure trip-wire.
- **documentation** — auxiliary; documentation/Markdown edits and tracker tools only.
- **scout** — optional native read-only leaf for bounded factual discovery; returns
  findings, evidence, coverage, and unknowns, then stops. It never edits, commits,
  delegates, calls trackers, or replaces whole-ticket workers.

## Normative procedure

1. Lead reads the approved playbook in full and establishes (or reads) its ticket
   dependency order before assigning anything.
2. Implementation always delegates one whole ticket to a configured worker. Lead does not
   implement a ticket itself, even a small one.
3. Worker creates the ticket's branch from the current integration branch, edits only the
   files the ticket lists, runs every verification command, inspects its own diff, commits
   locally, saves durable engineering memory, and returns the structured handoff.
4. Lead reads the actual diff — not the worker's summary of it — and reruns the ticket's
   verification commands itself before accepting anything.
5. One correction resumes the same worker on the same ticket. Do not swap to a different
   worker or model for a first correction.
6. A second materially similar failure (same failure_fingerprint) creates a fresh rescue
   dispatch with the full evidence trail attached, instead of a third attempt on the same
   worker. Rescue is never self-selected and never the default path.
7. After a logical batch of tickets lands, a fresh verifier — never the worker that
   implemented the batch — tests the integrated result before merge.
8. Production, security, secret, destructive-action or missing-user-input boundaries stop
   execution for authority at any role. A stronger tier cannot grant itself authority it
   was not given; these return to the lead/user, never to a "smarter" agent.
9. Passing output stays compact — one line per check. Failing command output is reported
   verbatim, in full.
10. At most three workers run at once, and only for independent, non-overlapping tickets.
    Tickets with shared files or variables run serially instead.

For broad independent factual discovery, lead should dispatch native `scout` when available
and worth overhead. Keep small known reads direct. Lead owns reasoning, decisions, edits,
and delivery routing; if scout unavailable, continue direct without escalation or a
specialist chain.

## Handoff contract

Every delivery role returns exactly one of these statuses: `COMPLETE`,
`CORRECTION_REQUIRED`, `HANDOFF_REQUIRED`, `BLOCKED_AUTHORITY`, `BLOCKED_TRANSIENT`.

Every delivery handoff carries exactly these eleven evidence fields: `status`, `ticket`, `branch`,
`commit`, `files`, `checks`, `failure_fingerprint`, `deviations`, `last_safe_state`,
`recommended_next`, `unresolved_risks`.

Scout instead returns only `findings`, `evidence`, `coverage`, and `unknowns`.

## Shared safety rules (apply to every role)

- Never remove a file outright; print the absolute path first, then move it to a
  recoverable trash location. A tracked rename is fine.
- Stage exact file paths only; never stage everything blindly.
- Never push, publish, or merge into a trunk branch unless explicitly told to in that
  message. Ticket branches merge into the integration branch only, non-fast-forward.
- Never commit directly to the trunk or integration branch — only onto a ticket branch,
  merged back after lead review.
- Secrets are edited only through the repo's existing vault workflow; no role ever prints
  secret material.
- A ticket's live, read-only harness call is required acceptance evidence; a static file
  check alone never counts as done.

## When this does not apply

A single small, self-contained change with no ticket structure does not need this
procedure — use normal judgment. This skill is for an *approved* playbook already broken
into tickets; it does not itself decide what the tickets should be.
