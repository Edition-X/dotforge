# Measured scout routing rollout

## Decision and scope

Dan authorized implementation, Mac deployment, testing, review, merge and push on
2026-09-07. Source checkpoint: `b29fdf0`, retained as
`checkpoint/pre-scout-rollout`. The initial HTML assessment lives at
`/Users/dkelly/Projects/html/agent-routing-spotify-assessment-2026-09-07.html`.

Keep whole-ticket delivery ownership and existing model tiers. Add an optional
native scout for bounded factual discovery, using worker tier: OpenAI Luna medium,
Anthropic Sonnet medium. Small known reads stay direct. Scout has four handoff
sections (findings, evidence, coverage, unknowns), a roughly 500-word target, no
playbook preload, and no delivery responsibilities. No Portal dependency or hooks.

This is a measured pilot, not a demonstrated cost reduction. After delegated work
exhausted usage, Dan explicitly requested more efficient execution and permitted
the lead to finish directly. Repeated paid benchmarks and another review agent
were omitted under that instruction. The lead reviewed real diffs, corrected the
implementation and evidence parser, and performed final checks directly.

## Implementation ledger

| Work | Outcome |
| --- | --- |
| Native routing, Luna medium | Reviewed and corrected; commit `d9ddc98`, integrated via `0b115a9` |
| Initial measurement and canaries, Terra medium | Rejected after correction: weak model correlation and broken benchmark execution |
| Rescue | Interrupted by exhausted credits; no rescue implementation accepted |
| Final evidence and documentation | Lead replacement: recursive usage reporter, correlated native records, offline tests, opt-in single-call smoke |
| Deployment | Scoped Ansible apply succeeded; second apply `changed=0` |
| Review | Direct review after user's efficiency correction; no claim of independent verifier acceptance |

Rejected benchmark/canary branches remain separate and were not merged. Original
untracked documentation was preserved; its original hashes and backup are under
`/var/folders/th/j8rggtjj6kld4ddmcc815b000000gn/T/scout-rollout-kh9m71il/`.
Raw transcripts, databases, credentials, and machine caches are not committed.

## Verification evidence — 2026-09-07

| Check | Result |
| --- | --- |
| `make validate-opencode` | Passed against generated source in isolated home, including effective scout permissions |
| `make test-ai-agents` | Passed; second isolated deployment changed zero files; Codex settings sync surgical and idempotent |
| `make test-scout` | Passed recursive accounting, cohort filtering, unknown models, false child attribution and inherited Codex context cases |
| `make ci` (includes lint) | Passed; two existing vendored YAML line-length warnings, no errors |
| Scoped preview with `--tags ai --diff` | Reviewed; only routing docs, agents and plan command changed |
| First `make ai` | Passed: `ok=88 changed=5 failed=0` |
| Second `make ai` | Passed: `ok=88 changed=0 failed=0` |
| `bash scripts/check-agent-config-drift.sh` | Exit 0, no drift output |

Final scoped dry run passed: `ok=88 changed=0 failed=0`. Verification reused the
existing installed Ansible environment with `make -o venv`; a fresh worktree
environment bootstrap using ambient Python 3.10 could not satisfy the existing
Ansible lint dependency. No dependency versions were changed. The new offline
`make test-scout` target uses the standard library and needs no environment setup.

### Live routing and actual models

- **OpenCode natural discovery:** root `ses_f8390c3a9ffeQhiLWKCI3JL2GY` dispatched
  scout `ses_f838fdaacffenEzGpZ5Thr6qZk`. Native session row confirms
  `openai/gpt-5.6-luna`, variant `medium`; CLI exited 0. Answer correctly traced
  model and permission rendering. Parent did repeat reads, so this is not savings
  evidence. Local transcript: temporary folder `scout-live-wx3uqi9_`.
- **Claude work direct control:** session `5e28eced-135a-4ad7-931a-076a3ec91f21`
  intentionally kept six known file reads direct. Natural-routing probe returned
  nonzero because there was no scout; this is not counted as scout proof.
- **Claude work explicit scout:** session `e9aa02cd-1dd2-4a03-aa20-cc5e802447dd`
  has an Agent tool call/result tied to child `a71e14397c48374a0`. Child assistant
  records confirm `claude-sonnet-5`; medium effort is verified in generated config.
  CLI and evidence parser exited 0. Local folder: `scout-live-ajwhwo7r`.
- **Fresh T3 Codex thread:** UI thread `16965d8d-7345-491c-8653-4aa19aa9d65a`,
  root rollout `01a07c70-f563-7111-b959-d0658838f5e4`, scout child
  `01a07c71-1a34-7423-a22c-75b7c4bbe73c`. Root used Sol medium; child used Luna
  medium and returned correct values and file references in four sections.
  Parent spawn call ID is correlated with SubAgentActivity and child token-record
  turn IDs. Inherited parent contexts are excluded from model attribution.
  Child executed only a bounded `nl` read of the two requested policy files.

### Permission and support limits

OpenCode's resolved permissions allow native read/search and deny shell, writes,
delegation, skills, and MCP through default deny. Claude exposes only Read/Grep/Glob
and excludes shell, writes and Agent. These are configuration/runtime tool-surface
checks; no paid attempt to force an agent to violate its instructions was needed.

Codex agent config requests read-only, but the fresh T3 thread ran **Full access**.
The child's recorded sandbox was `danger-full-access`. Its actions were read-only;
OS-enforced read-only behavior was **not** established. Do not describe prompt
restrictions as an enforced sandbox, or assume T3 and CLI runtime modes are equal.
The installed `codex sandbox` diagnostic rejected a legacy config invocation and
then required a permissions table; that write-denial probe is unsupported, not a
pass. The disposable sentinel remained unchanged because the probe never ran.

T3's active task backend was not restarted. A fresh provider thread was tested
instead. Personal Claude inherits byte-identical config; no separate paid personal
Claude or Codex CLI run was made. Forge remains shared-instruction fallback only.
No claim of full cross-harness security parity or exhaustive behavioral coverage.

## Reproduce without automatic spending

```bash
make test-scout
venv/bin/python scripts/scout-usage-report.py --directory "$PWD" --limit 20
# Opt-in paid smoke: one bounded scout dispatch. Never included in CI.
venv/bin/python scripts/test-scout-routing-live.py --harness opencode
# Other values: claude-work, codex. --natural probes discretionary selection;
# a direct-read result returns nonzero because it supplies no scout proof.
```

The smoke stores raw output in a local temporary directory and prints correlated
session/model evidence. It checks repository content hashes before/after. The
standalone `scout-routing-evidence.py` parser can validate existing records without
another model call. Its `--help` describes required exact parent/model arguments.

## Measurement and future adoption gate

The read-only usage reporter selects recent managed OpenCode roots, optionally
filters directory and `--since-ms`, and recursively includes all descendants.
Input, output, reasoning, cache reads and cache writes remain separate. Per-model
totals include unknown models. Role attribution is only a historical proxy.
T3 database selections are separate evidence, never treated as token accounting;
use `--t3-project-id` and `--exclude-t3-thread` to scope them.

Historical local baseline: 17 roots, 52 sessions, input 7,959,437; output 202,471;
reasoning 158,438; cache read 82,203,392. Recorded cost was zero, which means billing
unavailable, not free. This mixed historical cohort is not a paired scout baseline.

After 20 ordinary sessions, inspect complete-task usage, corrections and quality.
If a controlled economic comparison is needed, freeze one fixture commit with six
cases: tiny lookup, subsystem map, config consumers, log diagnosis, routine edit,
and subtle bug. Predeclare expected facts/tests. Run each baseline/scout variant
three times, alternating order, with identical root model/effort and fixture hash.
Capture all children, cache counters, elapsed time, retries and test outcomes.
Do not compare different snapshots or count scout prose as passing a test.

Proposed gate: unchanged quality, at least 20% lower median completed-task cost,
no more than 20% median latency increase. Use actual billing coverage or published
prices matched to measured model/cache counters; never turn zero exported costs
into claimed savings. Repeated paired runs were deliberately deferred to avoid
another burst of paid usage. Keep this pilot optional pending that evidence.

Final pre-commit run passed all 14 hooks, including secret scanning, drift,
source routing validation, Codex sync, Ansible lint and YAML lint. Original
untracked documentation hashes remained unchanged. Fresh T3 scout inherited
parent context (`fork_turns=all`), so lean role instructions alone do not establish
minimal input cost; monitor that overhead during the ordinary-use review.
