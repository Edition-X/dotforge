---
name: fetch-notion-context
description: Fetch and summarize Notion page context for engineering work. Use when a user provides a Notion URL/page ID, says context is in Notion, asks to inspect a Notion doc, or needs requirements/decisions extracted from Notion before implementation.
---

# Fetch Notion Context

Use Notion MCP first when available. If unavailable, use `scripts/fetch_page.py` with `NOTION_API_KEY` from `~/.env_secrets`.

## Workflow

1. Get a Notion page URL or page ID from the user, Linear issue, branch notes, or linked resources.
2. Ensure the page has been shared with Dan's Notion integration.
3. Fetch page metadata and blocks recursively where useful.
4. Extract engineering-relevant information:
   - goal/problem statement
   - requirements
   - decisions and constraints
   - design notes
   - rollout/test notes
   - open questions
5. Avoid dumping full docs unless explicitly requested.
6. If the Notion doc materially informs a code/config change, save durable context to Arcane before finishing.

## API fallback

Run the bundled script when MCP is unavailable:

```bash
python /Users/dkelly/forge/skills/fetch-notion-context/scripts/fetch_page.py '<notion-url-or-page-id>'
```

Requirements:

- `NOTION_API_KEY` must be set in `~/.env_secrets`.
- The target page must be shared with the Notion integration.
- Do not print or persist API keys.

## Output shape

Return:

- Notion page title/link
- Short summary
- Requirements and constraints
- Decisions already made
- Open questions
- Suggested next actions
