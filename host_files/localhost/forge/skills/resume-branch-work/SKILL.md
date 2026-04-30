---
name: resume-branch-work
description: Resume stale or forgotten branch work by inspecting git state, changed files, commits, Linear context, Notion docs, and saved Arcane memory. Use when a user says they cannot remember where they left off, asks what is in-progress on a branch, or wants to continue old work safely.
---

# Resume Branch Work

Build a concise "where we are" summary before making changes.

## Workflow

1. Load relevant Arcane context for the project and issue key if known.
2. Inspect git state:
   - current branch
   - clean/dirty worktree
   - commits ahead/behind base
   - diff against base branch
3. Infer issue key from branch name, commits, PR title, or user input.
4. Fetch Linear context using `fetch-linear-context` behavior.
5. Follow linked Notion URLs using `fetch-notion-context` behavior.
6. Read changed code/config files only after identifying them from git/diff.
7. Produce a handoff summary before implementation:
   - branch and worktree state
   - what changed already
   - why the work exists
   - requirements/acceptance criteria
   - suspected current status
   - risks or unknowns
   - recommended next steps
8. Ask before making changes if the next step is ambiguous.

## Git defaults

- Prefer comparing feature branches against their tracked upstream and default base (`main`, `master`, or repo-specific default).
- Do not assume a dirty worktree is disposable.
- Do not reset, rebase, or discard work unless explicitly asked.

## Output shape

Return:

- Current branch status
- Summary of existing branch changes
- Linear/Notion context summary
- Where work appears to be left
- Recommended next action
