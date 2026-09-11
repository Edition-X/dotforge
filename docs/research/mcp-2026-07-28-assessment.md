# MCP 2026-07-28 assessment

**Status:** research only. No MCP or OpenCode upgrade recommended yet.

## What released

Model Context Protocol (MCP) specification revision **2026-07-28** became a
stable release on 28 July 2026. This is a protocol-specification release, not
an OpenCode or SDK package version.

Primary sources:

- [MCP 2026-07-28 release](https://github.com/modelcontextprotocol/modelcontextprotocol/releases/tag/2026-07-28)
- [MCP 2026-07-28 specification](https://modelcontextprotocol.io/specification/2026-07-28)
- [MCP 2026-07-28 changelog](https://modelcontextprotocol.io/specification/2026-07-28/changelog)

## Main changes

| Change | Why it matters |
| --- | --- |
| Stateless requests; no protocol session or initialization handshake | Better fit for remote servers behind proxies, restarts, and load balancers. Client and server identify protocol/capabilities per request. |
| `server/discover` | Lets a client select or probe protocol compatibility before use. |
| `subscriptions/listen` replaces HTTP GET plus resource subscriptions | One long-lived stream for opted-in server change notifications. |
| Required cache metadata and deterministic list ordering | Clients can cache tool, prompt, and resource discovery for less polling, latency, and prompt churn. |
| MRTR and Tasks extension | Gives a standard shape for long-running work or work that needs more input without server-initiated requests. |
| OAuth/client-registration tightening | Better issuer binding and client-registration guidance for remote, OAuth-backed MCP servers. |
| Roots, Sampling, Logging, and HTTP+SSE deprecated | New clients and servers should migrate toward explicit tool arguments/resource URIs, provider APIs, stderr/OpenTelemetry, and Streamable HTTP. |

## Current repository position

This repository deploys OpenCode through Ansible. Its managed OpenCode config
defines one local stdio MCP server (`arcane`) and three remote servers:
`grafana`, `linear`, and `notion`.

Sources:

- [`roles/ai_agents/templates/opencode.jsonc.j2`](../../roles/ai_agents/templates/opencode.jsonc.j2)
- [`host_vars/localhost/opencode.yml`](../../host_vars/localhost/opencode.yml)
- [OpenCode MCP server documentation](https://opencode.ai/docs/mcp-servers/)
- [OpenCode configuration precedence](https://opencode.ai/docs/config/)

`opencode_schema_version: "1.18.10"` is this repository's OpenCode
compatibility baseline; it is **not** an MCP protocol version. The repository
does not implement an MCP client or server, so there is no protocol code to
migrate here directly.

The important current compatibility result is negative: OpenCode v1.18.10
depends on `@modelcontextprotocol/sdk` 1.29.0, and that SDK declares
`2025-11-25` as its latest supported protocol revision. Therefore this
installed OpenCode baseline cannot negotiate MCP 2026-07-28 today.

Pinned evidence:

- [OpenCode v1.18.10 package manifest](https://github.com/anomalyco/opencode/blob/v1.18.10/packages/opencode/package.json)
- [MCP TypeScript SDK v1.29.0 protocol constants](https://github.com/modelcontextprotocol/typescript-sdk/blob/v1.29.0/src/types.ts)
- [OpenCode v1.18.10 MCP client implementation](https://github.com/anomalyco/opencode/blob/v1.18.10/packages/opencode/src/mcp/index.ts)

## Likely benefits for this repository

1. **Remote-MCP resilience — with explicit retry design.** Stateless
   Streamable HTTP is useful for Linear, Notion, and Grafana if their servers
   and a future OpenCode client adopt the revision. It reduces dependence on a
   connection-bound session. However, the new revision removes resumable SSE:
   losing a response stream loses the in-flight request, and clients must
   issue a new request ID to retry. A server may have completed a non-idempotent
   write before its response was lost, so retries need idempotency protection
   or human confirmation.
2. **Lower discovery traffic; steadier prompt caching.** TTL/cache scope can
   reduce list polling, while deterministic list ordering can improve prompt
   cache hits. Neither removes enabled MCP tool definitions from model context;
   OpenCode's warning about tool-context cost still applies.
3. **Cleaner long-running integrations.** Tasks and MRTR could improve future
   Grafana investigations or other operations that run for a long time or need
   an input round trip. Benefit requires support by both OpenCode and server.
4. **Safer OAuth evolution — after client support lands.** Linear and Notion
   use OAuth. MCP 2026-07-28 deprecates Dynamic Client Registration (DCR) in
   favour of Client ID Metadata Documents (CIMD), while retaining DCR for
   compatibility. It also requires persisted DCR credentials to be bound to
   the authorization-server issuer. Current OpenCode v1.18.10 uses DCR when a
   configured client ID is absent and stores auth by MCP server URL; do not
   assume the newer issuer binding or CIMD support exists until an OpenCode
   release documents and implements it.

## Compatibility and risk

- **No immediate config change follows from the spec alone.** OpenCode is the
  MCP client. Upgrade it only after its release notes explicitly state support
  for MCP 2026-07-28 or its affected features.
- The local `arcane` stdio server is less exposed to the Streamable-HTTP and
  OAuth changes, but still needs protocol compatibility testing after an
  OpenCode upgrade.
- The `/mcp` path alone does not prove a transport. OpenCode v1.18.10 tries
  Streamable HTTP first and falls back to legacy SSE against the configured
  URL. A separate legacy `/sse` example exists in a Codex skill, so audit it
  before upgrading that harness and verify actual negotiated transport.
- OAuth state is deliberately unmanaged by this repository. A client
  registration or issuer migration can require interactive re-authentication;
  do not commit credentials or OAuth state.
- The new protocol does not relax OpenCode permissions. MCP tool calls remain
  subject to host permission policy and should remain approval-gated where the
  current policy requires it.

## Recommendation

**Wait for an OpenCode release that declares MCP 2026-07-28 support; then run
a bounded compatibility spike.** Do not change production configuration yet.

Spike acceptance criteria:

1. Install the candidate OpenCode binary in an isolated environment, not the
   live user config, and verify its release notes and bundled MCP SDK support
   MCP 2026-07-28.
2. Run `opencode mcp list` and authenticate only if required.
3. Smoke-test the local Arcane server and remote Grafana, Linear, and Notion
   connections with a read-only request each.
4. Confirm no fallback to deprecated HTTP+SSE, no unexpected permission change,
   no retry of a non-idempotent write, and no OAuth credential cross-issuer
   reuse.
5. Upgrade the production OpenCode binary separately after the isolated test.
   Update this repository's OpenCode compatibility baseline only when needed,
   then run `make validate-opencode` and `make test-ai-agents`.
6. Use `make ai` only to deploy the already-validated repository-managed
   configuration; it does not install or upgrade the OpenCode binary.

If the client does not expose discovery, subscriptions, caching, MRTR, or task
support, that is not a blocker: current MCP servers can continue on a prior
protocol revision. The value comes when both endpoints negotiate the new
capabilities.
