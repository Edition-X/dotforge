---
name: linear
description: Manage issues, projects & team workflows in Linear. Use to read/fetch a ticket by issue key (e.g. INF-123) or Linear URL, answer "what does INF-… say", resume ticket work, understand requirements/comments/blockers/acceptance criteria; to create a ticket with Sunrise defaults; or to update a ticket, comment on it, change status, labels, or cycle.
---

# Linear

## When to use

- The user references a Linear issue key (e.g. `INF-123`) or a Linear URL.
- The user asks to fetch, inspect, or summarize a ticket ("what does INF-280 say", "resume ticket work", requirements/comments/linked docs/blockers/acceptance criteria).
- The user asks to create a ticket ("create a ticket", "file an issue", "open a Linear ticket").
- The user asks to update, comment on, re-assign, re-label, re-cycle, or change the status of a ticket.
- In OpenCode, all Linear reads and writes run through the `documentation` agent; no other agent touches Linear MCP tools there.

## Defaults (Sunrise)

When acting for Dan Kelly, apply these unless the user explicitly overrides them:

- Team/type: `INF` (Digital Infrastructure)
- Assignee: `Dan Kelly`
- Cycle: current active cycle for the INF team
- Description style: concise, action-oriented, implementation-focused — not verbose

Known Sunrise IDs (use directly, skip lookup):
- Team key: `INF`, team name: `Digital Infrastructure`
- Team ID: `c39305a8-8b12-4047-b51a-740411f2d9d2`
- Dan Kelly user ID: `014fa50d-c55c-4e89-85fb-ccd6cc2a66a6`

Fast path for ticket creation:
1. Use the known INF team ID directly.
2. Use Dan Kelly's known user ID directly.
3. Resolve only the current active cycle for the INF team (still requires a lookup — it changes over time).
4. Create the ticket with a short title and concise implementation-focused description.

Only fall back to broader search (team, user, or cycle lookups) if:
- the team changes
- the assignee changes
- the workspace no longer recognizes the saved IDs

## Fetch and summarize an issue

1. Identify the issue key or URL from the user request, branch name, commit messages, or PR title.
2. Use the Linear get_issue tool (and list_comments) to pull: title, description, status, priority, labels, assignee, cycle, comments, attachments, related/blocking issues, and linked project or Notion docs.
3. Summarize into:
   - purpose (what the work is trying to achieve)
   - acceptance criteria / done definition
   - implementation notes and relevant prior decisions
   - blockers / open questions
   - linked resources (docs, PRs, Notion URLs)
4. Keep the summary concise and implementation-focused — enough to start work, not a transcript dump.
5. If the issue materially informs a code/config change, save durable context to Arcane before finishing.

## Create an issue

1. Summarize the work into a short, specific title.
2. Write a brief description:
   - one-sentence summary
   - 2-5 bullets for the required work, only if needed
   - no long background section or context dump unless requested
3. Apply the Sunrise defaults above (team INF, assignee Dan Kelly, current active cycle) unless the user names a different team, assignee, or cycle — then follow the user instead.
4. If scope is ambiguous, ask only the minimum clarifying question before creating.
5. Use the Linear create_issue tool (or an equivalent save/create tool) with all resolved fields (team, assignee, cycle, title, description).

Example shape:

Title: `Set up dedicated Jetson arm64 GitHub runner lane`

Description:
- Stand up a dedicated on-prem Jetson arm64 self-hosted GitHub runner for Jetson-native workloads.
- Reuse the existing runner bootstrap/runtime where practical.
- Keep capacity fixed for now with no autoscaling.
- Add appropriate hardware-specific labels and runner group scoping.
- Onboard the first target workflow/repo safely.

## State, estimate and closing conventions

- Estimate: 1 point unless the user names another.
- State: `In Progress` while working, `In Review` from the moment a PR is open.
- Linear flips a ticket to `Done` on its own when any linked PR merges. That includes
  rehearsal PRs into `sim_integration` and seed or fixture PRs that carry the ticket key
  in the branch name. After every merge, read the state again and set it back to
  `In Review` or `In Progress` when work remains. Do not treat an auto `Done` as a signal
  that the work is finished.
- Closing comment, posted when the work is really done, in this shape:

  ```markdown
  **Root cause:** <one or two sentences>
  **Fix:** <what changed, PR links>
  **Verification:** <what was run or observed, run ids or URLs>
  **Follow-ups:** <ticket keys, or "none">
  ```

- Follow-up tickets: create them with the same defaults and link them to the parent with
  `relatedTo`, not `blocks` or `blockedBy`, unless the user asks for a blocking relation.

## Update / comment

1. Read the issue first (get_issue / list_comments) to confirm current state before changing anything.
2. Apply the requested change with the Linear update_issue tool (status, labels, assignee, cycle, description) or add a comment with the Linear create_comment tool.
3. Keep updates and comments concise and specific — state what changed and why.
4. Batch related changes together; explain the grouping logic before applying bulk updates.
5. Summarize the result: what changed, remaining gaps, and any proposed next actions.

## Never

- Delete issues, projects, labels, or comments.
- Apply bulk edits across many issues without the user confirming the batch first.
- Change the status, assignee, or content of another person's issue without the user's explicit go-ahead.
