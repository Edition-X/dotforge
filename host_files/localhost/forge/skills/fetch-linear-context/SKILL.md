---
name: fetch-linear-context
description: Fetch and summarize Linear issue context for implementation work. Use when a user references a Linear issue key or URL, asks to inspect Linear context, resume ticket work, understand requirements, comments, linked docs, blockers, or acceptance criteria from Linear.
---

# Fetch Linear Context

Use Linear MCP tools first when available. If unavailable, use direct GraphQL with `LINEAR_API_KEY` from `~/.env_secrets`.

## Workflow

1. Identify the issue key or URL from the user request, branch name, commit messages, or PR title.
2. Fetch issue title, description, status, priority, labels, assignee, cycle, comments, attachments, related issues, and project links when available.
3. Summarize into:
   - purpose
   - acceptance criteria
   - implementation notes
   - blockers/open questions
   - linked resources, including Notion URLs
4. Keep summaries concise and implementation-focused.
5. If the Linear issue materially informs a code/config change, save durable context to Arcane before finishing.

## Direct GraphQL fallback

Use this only when Linear MCP is unavailable.

- Load secrets with `set -a; source ~/.env_secrets; set +a`.
- Use `LINEAR_API_KEY`.
- Query by issue identifier first, e.g. `INF-280`.
- Do not print or persist API keys.

Useful GraphQL shape:

```graphql
query Issue($id: String!) {
  issue(id: $id) {
    identifier
    title
    description
    status { name }
    priority
    labels { nodes { name } }
    assignee { name id }
    cycle { name number startsAt endsAt }
    comments { nodes { body createdAt user { name } } }
    attachments { nodes { title url } }
    relations { nodes { type relatedIssue { identifier title status { name } } } }
  }
}
```

## Output shape

Return:

- Linear issue and status
- What the work is trying to achieve
- Relevant context and decisions
- Acceptance criteria / done definition
- Open questions
- Links to follow next
