# Spotify Shunt / Portal research

Date: 2026-09-07
Retrieved: 2026-09-07
Repository revision inspected: [`3c24ca30ff63e1f5bbad1c43fe5324daff579123`](https://github.com/spotify/portal-ai-plugins/tree/3c24ca30ff63e1f5bbad1c43fe5324daff579123)

Question: does Spotify's Portal/Shunt pattern suggest improvements to this repository's agent and model-routing setup, prioritizing lower cost with equal reliability for T3 Code and OpenCode?

## Sources

- Article: <https://engineering.atspotify.com/2026/9/portal-by-spotify-cut-my-claude-code-token-usage-by-90>
- Repository at inspected revision: <https://github.com/spotify/portal-ai-plugins/tree/3c24ca30ff63e1f5bbad1c43fe5324daff579123>
- README: <https://github.com/spotify/portal-ai-plugins/blob/3c24ca30ff63e1f5bbad1c43fe5324daff579123/plugins/shunt/README.md>
- Hook registration: <https://github.com/spotify/portal-ai-plugins/blob/3c24ca30ff63e1f5bbad1c43fe5324daff579123/plugins/shunt/hooks/hooks.json>
- File hook: <https://github.com/spotify/portal-ai-plugins/blob/3c24ca30ff63e1f5bbad1c43fe5324daff579123/plugins/shunt/hooks/check-file-size>
- Bash hook: <https://github.com/spotify/portal-ai-plugins/blob/3c24ca30ff63e1f5bbad1c43fe5324daff579123/plugins/shunt/hooks/check-bash-read>
- Transport: <https://github.com/spotify/portal-ai-plugins/blob/3c24ca30ff63e1f5bbad1c43fe5324daff579123/plugins/shunt/scripts/lib/aika.sh>
- Eval runner: <https://github.com/spotify/portal-ai-plugins/blob/3c24ca30ff63e1f5bbad1c43fe5324daff579123/plugins/shunt/evals/run.sh>
- Claude Code hooks: <https://code.claude.com/docs/en/hooks>
- Claude Code subagents: <https://code.claude.com/docs/en/sub-agents>

## Article-derived claims (under 200 words)

Spotify describes two Portal AiKA modes: `bulk-reader` summarizes large/multiple files; `code-writer` generates predictable boilerplate from a specification and reference file. The examples use Gemini 2.5 Flash, but the worker model is configurable. Portal invocations are ephemeral. The author says CLAUDE.md routing was advisory, then moved routing into a Claude Code plugin named Shunt. `PreToolUse` hooks block full reads above a line threshold and redirect Claude to a skill. The article reports roughly 90% mean bulk-read savings across four scenarios in a Java monorepo. It says summaries are unsuitable for exact editing, debugging, architectural decisions, and safety-critical code; latency is typically 10–30 seconds and large generations may need splitting. [Spotify Engineering article](https://engineering.atspotify.com/2026/9/portal-by-spotify-cut-my-claude-code-token-usage-by-90)

## Repository-confirmed implementation

At inspected revision, `hooks.json` registers `PreToolUse` handlers for `Read` and `Bash`. `check-file-size` blocks full-file `Read` calls above `SHUNT_MIN_LINES` (default 350), while allowing `offset`/`limit` reads, small/missing files, and empty paths. `check-bash-read` handles only leading `cat`, `head`, `tail`, `less`, and `more`; it allows pipes, redirections, unrelated commands, and files at or below threshold. [hooks.json](https://github.com/spotify/portal-ai-plugins/blob/3c24ca30ff63e1f5bbad1c43fe5324daff579123/plugins/shunt/hooks/hooks.json), [check-file-size](https://github.com/spotify/portal-ai-plugins/blob/3c24ca30ff63e1f5bbad1c43fe5324daff579123/plugins/shunt/hooks/check-file-size), [check-bash-read](https://github.com/spotify/portal-ai-plugins/blob/3c24ca30ff63e1f5bbad1c43fe5324daff579123/plugins/shunt/hooks/check-bash-read)

`bulk-read` validates paths, wraps files in XML tags, and delegates through `aika:invoke-chat`. `code-write` requires a reference file, strips markdown fences, and can write to a target. `aika.sh` enforces payload ceilings, validates JSON and returned mode identity, reports errors, and uses temporary files. These are transport implementation facts, independent of the article. [bulk-read](https://github.com/spotify/portal-ai-plugins/blob/3c24ca30ff63e1f5bbad1c43fe5324daff579123/plugins/shunt/scripts/bulk-read), [code-write](https://github.com/spotify/portal-ai-plugins/blob/3c24ca30ff63e1f5bbad1c43fe5324daff579123/plugins/shunt/scripts/code-write), [aika.sh](https://github.com/spotify/portal-ai-plugins/blob/3c24ca30ff63e1f5bbad1c43fe5324daff579123/plugins/shunt/scripts/lib/aika.sh)

The README publishes 82%, 94%, and 94% for three bulk-read scenarios and describes a 40,614-token-plus-generation versus 833-lines-to-disk code-write row. Its limitations say code-writer has no hook enforcement, requests travel through argv with a size ceiling, and action invocations have a 30-second cap. [README](https://github.com/spotify/portal-ai-plugins/blob/3c24ca30ff63e1f5bbad1c43fe5324daff579123/plugins/shunt/README.md)

## Benchmark caveats

`evals/run.sh` estimates tokens as characters/4. Bulk-read totals compare source corpus characters with returned summary characters and omit worker billing, latency, retries, and correction reads. Code-write weights output tokens 5× input tokens, then assigns zero primary-model tokens to direct-to-disk output. These are heuristics, not provider billing. Checked-in benchmark definitions use small TypeScript fixtures, while README's published table says 162K-line Java monorepo; do not generalize either to this repository without local tests. [eval runner](https://github.com/spotify/portal-ai-plugins/blob/3c24ca30ff63e1f5bbad1c43fe5324daff579123/plugins/shunt/evals/run.sh), [benchmark definitions](https://github.com/spotify/portal-ai-plugins/blob/3c24ca30ff63e1f5bbad1c43fe5324daff579123/plugins/shunt/evals/benchmarks.json)

## Comparison with native subagents

Anthropic documents that `Explore` is read-only and keeps exploration results out of main conversation context. Custom subagents can set model, tools, permission mode, hooks, and skills; scope may be project, user, plugin, managed, or session. A subagent is not inherently cheap: model inheritance varies, so set an explicit worker model when cost matters. [Subagents](https://code.claude.com/docs/en/sub-agents)

`PreToolUse` runs before tool execution and can block a call. Hooks also run inside subagents, so a global large-file gate must identify intended scout/worker calls or it may block them too. [Hooks](https://code.claude.com/docs/en/hooks)

Independent comparison:

| Work | Better first fit | Reason |
| --- | --- | --- |
| Large-file factual digest | Native read-only scout with explicit cheap model | Isolated context, iterative search, no external Portal dependency. |
| Parallel research requiring reasoning | Native subagents | Separate contexts and native orchestration. |
| Highly predictable generation from a reference | Shunt-style worker, if measured worthwhile | Direct-to-disk output can avoid returning boilerplate to primary agent. |
| Debugging, exact edits, architecture, safety-sensitive code | Capable primary agent | Lossy summaries are unsafe for judgment and line-precise changes. |

## Recommendation for this repository

Start with parent plan's lightweight native read-only scout, pinned to a lower-cost worker model, as first experiment. It matches current T3 Code/OpenCode role routing, preserves reliability through an existing capable lead, and avoids Portal authentication, external code transfer, network latency, and provider-specific CLI coupling. Do not build a provider-neutral transport as a prerequisite.

Measure completed-task totals, not only lead-agent tokens: primary tokens, scout tokens, latency, correction/re-read rate, task success, and worker cost. Use representative tasks and compare current routing against native scout. Only if repeated large-file I/O remains material and quality holds should an advisory read-budget hook be considered. A hard Shunt-style gate or external transport is a later utility experiment, not default architecture.

This ordering preserves current whole-ticket native routing and treats Spotify's enforcement idea as optional follow-up. Reusable lesson: delegate deterministic context gathering or boilerplate, while keeping reasoning, edits, and verification with capable agent.
