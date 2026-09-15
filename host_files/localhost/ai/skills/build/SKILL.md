---
name: build
description: Hand an approved implementation to an OpenCode worker through the oc-ticket bridge and review what comes back. Use only when Dan explicitly asks for OpenCode to build it — "send it to opencode", "dispatch the ticket to opencode", "have opencode build it", "oc-ticket". Never on a plain "go ahead", "do it", "approved" or "build it": Claude implements those itself. Not inside OpenCode or Codex, which have their own worker.
---

# Build

Opt-in only: Claude in T3 Code implements directly by default. When Dan asks for
OpenCode to build a ticket, Claude plans and reviews and OpenCode, running the
Codex-side worker tier, builds. This skill is the loop between them. It implements the
`claude -> opencode` bridge declared in `host_files/localhost/ai/routing/workflow.yml`
and follows the same lead procedure as `execute-playbook`; read that skill for the
rules this one does not repeat.

## When Claude edits directly instead

A quick task is up to three source files in one session, and the work profile's edit
guard enforces exactly that budget (docs, plans, scratch and `~/Projects/dotforge` are
never counted). Under the budget, or when Dan says to do it yourself, edit directly.
When Dan says "don't use opencode" or "do it yourself" for wider work, run
`claude-edit-guard off` in the repo first; it expires after twelve hours. Everything
else goes through the steps below.

## 1. Plan first

Use plan mode for anything beyond a quick task. The plan must name the tickets, their
order, and per ticket the files, acceptance criteria, verification commands and commit
message. Dan approves the plan before any ticket is dispatched. Save an Arcane
`decision` if the plan carries one.

## 2. Write one self-contained ticket file per ticket

The OpenCode worker sees nothing of this conversation. Write the ticket into the
session scratchpad (never into the repo) with every field below. A ticket missing any
of them is the most common cause of a wrong build.

```markdown
# Ticket <ID>: <one-line goal>

Branch: `<ticket-branch>` from `<integration branch>`.
Allowed files: <exact paths>. Forbidden: everything else.
Context: <why; the relevant part of the approved plan; conventions to follow>.
Change: <what to build, precisely>.
Acceptance criteria: <bullet list>.
Verification: `<command>` must exit 0 (one line per command).
Commit message: `<type>(<scope>): <subject>`
Constraints: never push; never read `.env`; do not create or move files outside the repo; commit hooks must pass.
Return the handoff block with all eleven evidence fields as your final message.
```

When a repository hook is known to reject an edit the ticket requires (the changelog hook
on a `CHANGELOG.md` rollback, say), name that one hook in Constraints instead: `commit
hooks: <hook id> may be skipped with --no-verify`. The worker stops on any other hook, and
on a secret or credential finding whatever the ticket says.

## 3. Dispatch

Run `oc-ticket --lint --ticket <scratch>/ticket-01.md` first and fix anything listed
under `missing` before dispatching — a worker dispatch lints anyway and refuses (exit 3)
on missing required fields (`--no-lint` overrides). Rescue and verifier tickets are an
evidence trail, not the template; they are linted for information only and always dispatch.

```bash
oc-ticket --role worker --ticket <scratch>/ticket-01.md --dir <repo>
```

Run it in the foreground; a ticket takes minutes. It prints one JSON object with
`session_id`, `status`, the parsed `handoff`, `missing_fields`, `permission_denials`
and `final_text`, and exits 0 only on `COMPLETE`. Keep the `session_id`: a correction
must resume that session. Dispatch at most three tickets in parallel, only when their
file scopes do not overlap, and prefer `git worktree` per ticket when you do.

## 4. Review like the lead

- Read the actual diff on the ticket branch. The handoff is a claim, not evidence.
- Rerun every verification command yourself and record exit codes.
- Check the diff stayed inside the allowed files and the commit message matches.
- Decide, in this order:
  - **COMPLETE and the diff is right** — accept; move to the next ticket, or to `ship`
    when the repo is `~/Projects/dotforge`.
  - **First failure** — one correction, to the same session:
    `oc-ticket --role worker --resume <session_id> --message "Correction 1 of 1 on
    ticket <ID>: <exact finding, exact expected result, rerun the verification>"`.
  - **Second materially similar failure** (same `failure_fingerprint`) — a fresh
    rescue, with the evidence trail pasted into a new ticket file:
    `oc-ticket --role rescue --ticket <scratch>/ticket-01-rescue.md`.
  - **BLOCKED_AUTHORITY, BLOCKED_TRANSIENT, NO_HANDOFF, or anything touching secrets,
    production or a destructive action** — stop and report to Dan with the handoff.
- Optional: `oc-ticket --role verifier --ticket ...` for a read-only deterministic
  re-check of an integrated batch. Claude's own review is the verdict either way.

## 5. Report

Tell Dan per ticket: branch, commit, files, checks with exit codes, corrections and
rescue used, unresolved risks, and the OpenCode session ids. Save Arcane memory for
any bug or pattern the build surfaced.

## Facts about the bridge

- `opencode run --agent` only addresses worker, rescue and verifier (they are `mode:
  all`); the orchestrator is never bridged.
- A headless run never prompts: an `ask` permission is auto-rejected and the run may
  end there. `oc-ticket` reports it as `BLOCKED_AUTHORITY` with the denial text. Keep
  repos under `~/Projects` and keep `.env` out of tickets.
- Resuming without `--role` would run the session as the orchestrator; `oc-ticket`
  always passes the role.
