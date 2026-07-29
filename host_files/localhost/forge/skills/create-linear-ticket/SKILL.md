---
name: create-linear-ticket
description: Create Linear tickets for Dan Kelly with Sunrise defaults. Use when asked to create or update a Linear ticket so the ticket defaults to INF, is assigned to Dan Kelly, targets the current active cycle, and keeps the description concise and implementation-focused.
---

# Create Linear Ticket

When creating Linear tickets for Dan, apply these defaults unless the user explicitly overrides them:

- Team/type: `INF`
- Assignee: `Dan Kelly`
- Cycle: current active cycle
- Description style: concise, action-oriented, not overly verbose

## Sunrise workspace quick defaults

Use these known Sunrise defaults to avoid unnecessary lookups:

- Team key: `INF`
- Team name: `Digital Infrastructure`
- Team ID: `c39305a8-8b12-4047-b51a-740411f2d9d2`
- Dan Kelly user ID: `014fa50d-c55c-4e89-85fb-ccd6cc2a66a6`

Fast path for ticket creation:
1. Use the known INF team ID directly.
2. Use Dan Kelly's known user ID directly.
3. Resolve only the current active cycle for the INF team.
4. Create the ticket with a short title and concise implementation-focused description.

Only fall back to broader search if:
- the team changes
- the assignee changes
- the workspace no longer recognizes the saved IDs

## Workflow

1. Summarize the work into a short, specific title.
2. Use a brief description with:
   - one sentence summary
   - 2-5 bullets for the required work, only if needed
3. Avoid long background sections unless requested.
4. If scope is ambiguous, ask only the minimum clarifying question.
5. If the user asks for a different team, assignee, or cycle, follow the user instruction instead of the defaults.

## Default ticket shape

Title:
- short and implementation-focused

Description:
- one short summary line
- brief bullet list of what needs to be done
- no unnecessary context dump

## Example

Title:
- Set up dedicated Jetson arm64 GitHub runner lane

Description:
- Stand up a dedicated on-prem Jetson arm64 self-hosted GitHub runner for Jetson-native workloads.
- Reuse the existing runner bootstrap/runtime where practical.
- Keep capacity fixed for now with no autoscaling.
- Add appropriate hardware-specific labels and runner group scoping.
- Onboard the first target workflow/repo safely.

## Implementation note

When working from an environment without a ready Linear tool, a direct GraphQL fallback can still be efficient:
- use the stored team ID
- use the stored assignee ID
- query only the team's active cycle
- then create the issue
