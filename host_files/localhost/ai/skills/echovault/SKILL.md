---
name: arcane
description: Persistent engineering memory and decision intelligence. You MUST retrieve memories at session start and save memories before session end. This is not optional.
---

# Arcane — Engineering Intelligence & Memory

You have persistent memory across sessions. The `memory` command is an alias for `arcane` — use either. USE IT.

## Session start — MANDATORY

Before doing ANY work, retrieve context from previous sessions:

```bash
memory context --project
```

If the user's request relates to a specific topic, also search for it:

```bash
memory search "<relevant terms>"
```

When search results show "Details: available", fetch them:

```bash
memory details <memory-id>
```

Do not skip this step. Prior sessions contain decisions, bugs, and context that directly affect your current task.

## Session end — MANDATORY

Before ending your response to ANY task that involved making changes, debugging, deciding, or learning something, you MUST save a memory. This is not optional.

```bash
memory save \
  --title "Short descriptive title" \
  --what "What happened or was decided" \
  --why "Reasoning behind it" \
  --impact "What changed as a result" \
  --tags "tag1,tag2,tag3" \
  --category "<category>" \
  --related-files "path/to/file1,path/to/file2" \
  --source "codex" \
  --details "Context:

             Options considered:
             - Option A
             - Option B

             Decision:
             Tradeoffs:
             Follow-up:"
```

Categories: `decision`, `bug`, `pattern`, `learning`, `context`, `poc`, `milestone`.

Use `--source codex` to tag which agent created the memory.

## Decision journeys — for multi-step investigations

When starting a POC, spike, or investigation spanning multiple steps:

```bash
# At the start
memory journey start --title "Evaluating X vs Y" --project <project>
# → prints journey id

# Link each memory to the journey while investigating
memory save --title "..." --what "..." --journey-id <id>

# Complete when done
memory journey complete <id> --summary "Chose X because..."
```

Journeys capture the "how I got there" narrative and power blog post generation.

## What to save

You MUST save when any of these happen:

- You made an architectural or design decision
- You fixed a bug (include root cause and solution)
- You discovered a non-obvious pattern or gotcha
- You set up infrastructure, tooling, or configuration
- You chose one approach over alternatives
- You completed a POC or spike (`category: poc`)
- You shipped something significant (`category: milestone`)
- You learned something about the codebase not obvious from reading the code
- The user corrected you or clarified a requirement

## What NOT to save

- Trivial changes (typo fixes, formatting)
- Information already obvious from reading the code
- Duplicates — search first with `memory search`

## Other commands

```bash
memory stats              # show counts across all entity types
memory journey list       # see active journeys
memory journey show <id>  # see a journey with linked memories
memory sessions           # list session vault files
memory reindex            # rebuild vector search index
memory delete <id>        # remove a memory
```

## Rules

- Retrieve before working. Save before finishing. No exceptions.
- Always capture thorough details — write for a future agent with no context.
- Never include API keys, secrets, or credentials. Wrap sensitive values in `<redacted>`.
- Search before saving to avoid duplicates.
- One memory per distinct decision or event. Don't bundle unrelated things.
