# Playbook: cross-harness lead-worker routing

**Status:** ready to execute
**Written:** 2026-09-06, from OpenCode usage analysis and a successful T3 Code execution trace
**Audience:** a Sol lead at medium reasoning, delegating every implementation ticket to a Luna worker at medium reasoning
**Repo:** `~/Projects/macbook-pro`

---

## 0. Read this first

### Goal

Make every capable harness follow one fast workflow:

```text
Sol/Fable lead at medium
  -> Luna/Sonnet worker owns one complete ticket
  -> lead inspects the real diff and check evidence
  -> one correction goes back to the same worker
  -> fresh Luna/Sonnet verifier checks the integrated result
  -> Sol/Fable high rescue only after a repeated failure
```

Normal work does not pass through explorer, implementer, debugger, architect and reviewer
in sequence. Strong lead owns requirements, playbook quality, review and acceptance. Balanced
worker owns implementation, tests and commit. This is the pattern that worked in T3 Code.

Provider-neutral policy lives under `host_files/localhost/ai/routing/`. Harness renderers in
`roles/ai_agents` compile it into native OpenCode, Claude Code and Codex artefacts. T3 Code
inherits Claude work-profile and Codex configuration. Forge receives shared instructions and
skill only because Forge 2.13.21 exposes built-in agents but no supported custom-agent authoring
surface.

OpenCode keeps a fifth, command-only `documentation` agent. It is not part of engineering
workflow; it preserves current Linear MCP permission boundary. Do not fold Linear access into
general worker.

### Evidence for this design

T3 thread `6e7607a6-0eec-469e-bde7-cd3bf50083f7` executed Phase A of
`arcane-harness-hardening.md` from 2026-09-05 20:46 to 22:05 UTC:

| Evidence | Result |
|---|---:|
| Lead | `claude-fable-5-1`, medium effort |
| Ticket workers | `claude-sonnet-5`, inherited medium effort |
| Ticket tasks | 7 |
| Worker invocations, including corrections | 10 |
| Completed / failed agents | 7 / 0 |
| Worker tool uses | 288 |
| Worker runtime | 68.3 agent-minutes |
| Output tokens | 119,992 Sonnet; 25,732 Fable |
| End state | Seven ticket branches merged `--no-ff`; checks green |

Workers found bad plan assumptions in A1, A3, A4 and A5; A7 found another checker bug.
Lead corrected ticket text and resumed worker instead of adding specialist hops. About 82% of
output came from cheaper worker model. T3's list-cost accounting was $12.95 total
($7.00 Fable, $5.95 Sonnet); subscription usage may differ.

### Rules for every ticket

1. Cut `integration/cross-harness-lead-worker-routing` once from current `main`. Every
   ticket branch starts from current integration branch and merges back `--no-ff` after lead
   review. Never commit to `main` or integration branch directly.
2. Never push, open a PR, publish, or merge integration into `main` unless Dan explicitly says
   so in that message.
3. `docs/` is untracked and remains untracked. Never stage this playbook.
4. Every implementation ticket goes to one `gpt-5.6-luna` worker with
   `reasoning_effort: medium`. Lead does not implement ticket.
5. Worker runs ticket verification, inspects own diff, commits locally, saves Arcane memory,
   then returns compact evidence. Passing logs are summarized; failed command output is
   verbatim.
6. Lead inspects `git diff integration/...<ticket>` and reruns verification. One correction may
   return to same Luna worker. A second materially similar failure goes to fresh
   `gpt-5.6-sol` high rescue agent.
7. Never repeat unchanged failed approach. Permission, secret, production, security,
   destructive and missing-user-input failures return to lead/user; smarter model cannot grant
   authority.
8. Never use `rm`. For an actual filesystem removal, print exact absolute path using `ls -d`,
   then use `trash`. `git mv` is allowed for tracked renames. Ansible
   `ansible.builtin.file: state: absent` is allowed only for exact known generated files that
   are backed up or reproducible from Git.
9. Never `git add -A`. Stage exact paths.
10. Secrets stay only in `host_vars/localhost/vault.yml`, edited using:

    ```bash
    source venv/bin/activate
    unset ANSIBLE_VAULT_PASSWORD_FILE
    ansible-vault edit host_vars/localhost/vault.yml
    ```

    Any Ansible task that writes secret material carries `no_log: true` because
    `ansible.cfg` enables diffs globally. This effort needs no new secret.
11. Preserve user-owned Claude, Codex, OpenCode and T3 state. Manage only named files/keys.
    Never print auth data or whole settings/config files.
12. After each commit run exact Arcane command in ticket. Never save tokens, secrets or raw
    config contents.
13. Every ticket has a live harness call. A static file check alone is not acceptance.
14. Restart OpenCode after deployment. New CLI `opencode run` processes load fresh config,
    but existing interactive sessions do not.

### Lead and worker execution contract

Start execution in T3 Code/Codex with `gpt-5.6-sol` and medium reasoning. Lead creates
integration branch, then dispatches one ticket at a time with a Luna-medium subagent.

Use this assignment shape:

```text
Execute only ticket Rn from
/Users/dkelly/Projects/macbook-pro/docs/playbooks/cross-harness-lead-worker-routing.md.

Model: gpt-5.6-luna. Reasoning: medium.
Read ticket and shared Rules fully. Work in /Users/dkelly/Projects/macbook-pro.
Start from integration/cross-harness-lead-worker-routing and create exact ticket branch.
Do not edit files outside ticket scope. Preserve "?? docs/" and all unrelated changes.
Never use rm or git add -A. Never push.

Run every ticket verification command. If repo state contradicts playbook, a required command
fails twice, or scope/security/production/secret boundary appears, stop and report evidence.
Do not invent another design.

After success, stage exact files, commit with ticket's exact commit message, save Arcane memory,
and return:
status, branch, commit, files, diffstat, checks with exit codes, deviations, unresolved risks.
Include full output only for failures.
```

Lead review after every worker:

```bash
cd /Users/dkelly/Projects/macbook-pro
git status --short
git log --oneline -1 <ticket-branch>
git diff --check integration/cross-harness-lead-worker-routing...<ticket-branch>
git diff --stat integration/cross-harness-lead-worker-routing...<ticket-branch>
git diff integration/cross-harness-lead-worker-routing...<ticket-branch>
```

Expected status: ticket branch checked out or clean integration branch, plus `?? docs/` only.
Lead reruns ticket verification. When satisfied:

```bash
git checkout integration/cross-harness-lead-worker-routing
git merge --no-ff <ticket-branch>
git status --short
```

Expected status after merge: `?? docs/` only.

### Environment facts

| Surface | Current fact |
|---|---|
| OpenCode | 1.18.20 installed. Native agents support model, variant, permissions, mode and steps. Current config has nine managed agents. |
| OpenCode state | `~/.local/share/opencode/opencode.db`. Read-only evidence may use `sqlite3 -readonly`. Never write to it. |
| Claude terminal | `~/.local/bin/claude` currently reports 2.1.76. It exposes `agents`, `--agent`, `--model` and `--effort`. |
| Claude through T3 | Recent provider trace reported Claude Code 2.1.260. T3 launches `~/.local/bin/claude-work`; environment PATH can therefore matter. Validate both paths rather than assuming versions match. |
| Claude custom agents | User agents are Markdown under `~/.claude/agents/*.md`. Frontmatter supports model, effort, permission mode, max turns and preloaded skills. |
| Codex | 0.153.2 installed. Custom agents are TOML under `~/.codex/agents/*.toml`. Required keys: `name`, `description`, `developer_instructions`. |
| Codex config | `~/.codex/config.toml` is app-owned. Existing sync uses `tomlkit` to preserve unrelated keys and comments. |
| T3 | Claude uses `claude-work`. Codex uses `~/.codex/config.toml`. T3 needs no duplicate agent files. |
| Forge | 2.13.21. `forge agent` only lists built-in Forge, Muse and Sage; no create/config subcommand. |
| Shared instructions | `host_files/localhost/ai/AGENTS.md` symlinked into Claude personal/work, Codex, Forge and OpenCode. |
| Shared skills | `host_files/localhost/ai/skills/*` auto-discovered and symlinked into all five harness directories. |

Official format references:

- Codex custom agents and model precedence:
  https://learn.chatgpt.com/docs/agent-configuration/subagents
- Claude Code subagents:
  https://code.claude.com/docs/en/sub-agents
- Claude Code effort:
  https://code.claude.com/docs/en/model-config
- OpenCode agents:
  https://opencode.ai/docs/agents

### Integration branch

Create once:

```bash
cd /Users/dkelly/Projects/macbook-pro
git checkout main
git pull --ff-only
git status --short
git checkout -b integration/cross-harness-lead-worker-routing
```

Expected before branch: `## main...origin/main` and `?? docs/` only. If tracked changes exist,
stop. Do not stash unknown work.

### Ticket order

Tickets are intentionally serial. R3-R5 share Ansible variables/tasks and are cheap enough that
parallel write branches would create merge overhead.

| Order | Ticket | Branch | Worker |
|---|---|---|---|
| 1 | R1 Canonical policy and execution skill | `feat/agent-routing-policy` | Luna medium |
| 2 | R2 Policy loader and source validator | `feat/agent-routing-validation` | Luna medium |
| 3 | R3 OpenCode lead-worker migration | `feat/opencode-lead-worker-routing` | Luna medium |
| 4 | R4 Claude personal/work agents | `feat/claude-lead-worker-agents` | Luna medium |
| 5 | R5 Codex agents and app-owned config sync | `feat/codex-lead-worker-agents` | Luna medium |
| 6 | R6 T3/Forge inheritance, drift and docs | `feat/cross-harness-routing-drift` | Luna medium |
| 7 | R7 Reusable live acceptance runner | `test/agent-routing-live-canaries` | Luna medium |
| 8 | Final integration acceptance | no new commit | Fresh Luna verifier, then Sol lead |

---

## R1. Canonical provider-neutral policy and execution skill

**Branch:** `feat/agent-routing-policy`

**Why:** Role prompts and model IDs currently live in OpenCode-specific vars/templates. Create
one provider-neutral source before changing any harness.

**Files:**

- New `host_files/localhost/ai/routing/models.yml`
- New `host_files/localhost/ai/routing/workflow.yml`
- New `host_files/localhost/ai/routing/prompts/orchestrator.md`
- New `host_files/localhost/ai/routing/prompts/worker.md`
- New `host_files/localhost/ai/routing/prompts/verifier.md`
- New `host_files/localhost/ai/routing/prompts/rescue.md`
- New `host_files/localhost/ai/routing/prompts/documentation.md`
- New `host_files/localhost/ai/skills/execute-playbook/SKILL.md`
- `host_files/localhost/ai/AGENTS.md`

**Required model policy:**

```yaml
schema_version: 1
harnesses:
  opencode:
    provider: openai
    model_prefix: openai/
  codex:
    provider: openai
  claude:
    provider: anthropic

tiers:
  utility:
    openai: {model: gpt-5.4-mini, effort: low}
    anthropic: {model: claude-haiku-4-5-20251001, effort: null}
  worker:
    openai: {model: gpt-5.6-luna, effort: medium}
    anthropic: {model: claude-sonnet-5, effort: medium}
  senior:
    openai: {model: gpt-5.6-terra, effort: high}
    anthropic: {model: claude-opus-5, effort: high}
  lead:
    openai: {model: gpt-5.6-sol, effort: medium}
    anthropic: {model: claude-fable-5-1, effort: medium}
  rescue:
    openai: {model: gpt-5.6-sol, effort: high}
    anthropic: {model: claude-fable-5-1, effort: high}
```

`utility` and `senior` are mapped for provider completeness but are not in normal engineering
path. Haiku effort must render as omitted, never as `null` or `low`.

**Required workflow policy:**

- `max_parallel_workers: 3`
- `correction_limit: 1`
- `identical_failure_limit: 2`
- `rescue_limit: 1`
- Core roles:
  - orchestrator: primary, tier lead, reviews and merges, no normal source edits
  - worker: subagent, tier worker, owns one complete ticket
  - verifier: subagent, tier worker, read-only
  - rescue: subagent, tier rescue, only after trip-wire
- Auxiliary role:
  - documentation: subagent, tier worker, documentation edits and Linear tools only
- Handoff statuses:
  - `COMPLETE`
  - `CORRECTION_REQUIRED`
  - `HANDOFF_REQUIRED`
  - `BLOCKED_AUTHORITY`
  - `BLOCKED_TRANSIENT`
- Exact evidence fields:
  - status, ticket, branch, commit, files, checks, failure_fingerprint, deviations,
    last_safe_state, recommended_next, unresolved_risks

`execute-playbook/SKILL.md` is normative procedure. Keep under 300 lines. It must state:

1. Lead reads/creates approved playbook and dependency order.
2. Implementation always delegates one whole ticket to configured worker.
3. Worker creates branch, edits, verifies, commits and saves memory.
4. Lead reads actual diff and reruns checks.
5. One correction resumes same worker.
6. Repeated similar failure creates fresh rescue task with evidence.
7. Fresh verifier tests integration after logical batch.
8. Production/security/secret/destructive/permission boundaries stop for authority.
9. Passing output stays compact; failure output is verbatim.
10. Maximum three workers and only for independent non-overlapping tickets.

Add one short row/paragraph to `AGENTS.md` routing approved playbook execution to
`execute-playbook`. Do not copy procedure into always-loaded file.

**Verify:**

```bash
cd /Users/dkelly/Projects/macbook-pro
source venv/bin/activate
python - <<'PY'
from pathlib import Path
import yaml

root = Path("host_files/localhost/ai/routing")
models = yaml.safe_load((root / "models.yml").read_text())
workflow = yaml.safe_load((root / "workflow.yml").read_text())
assert models["schema_version"] == 1
assert models["tiers"]["lead"]["openai"] == {
    "model": "gpt-5.6-sol", "effort": "medium"
}
assert models["tiers"]["worker"]["openai"] == {
    "model": "gpt-5.6-luna", "effort": "medium"
}
assert models["tiers"]["lead"]["anthropic"]["model"] == "claude-fable-5-1"
assert models["tiers"]["worker"]["anthropic"]["model"] == "claude-sonnet-5"
assert models["tiers"]["utility"]["anthropic"]["effort"] is None
assert workflow["max_parallel_workers"] == 3
assert workflow["correction_limit"] == 1
assert workflow["identical_failure_limit"] == 2
assert set(workflow["roles"]) == {
    "orchestrator", "worker", "verifier", "rescue", "documentation"
}
print("canonical routing policy valid")
PY
bash scripts/check-skills.sh
rg -n 'gpt-|claude-' host_files/localhost/ai/routing/prompts \
  host_files/localhost/ai/skills/execute-playbook/SKILL.md
```

Expected:

- Python prints `canonical routing policy valid`.
- Skill checker prints `OK: all skills passed`.
- Final `rg` has no output; prompts/procedure use tiers, not provider IDs.

Live read-only skill trigger:

```bash
timeout 240 codex exec --ephemeral \
  -C /Users/dkelly/Projects/macbook-pro \
  -m gpt-5.6-sol \
  -c 'model_reasoning_effort="medium"' \
  'Read-only question. An approved playbook has two implementation tickets. Explain which role owns planning, implementation, review, correction, rescue, and final verification under current global instructions. Do not edit or run tests.'
git status --short
```

Expected response names lead, Luna-medium worker, lead review, one correction, direct rescue
and fresh verifier. Expected Git status remains `?? docs/` plus R1 source changes only.

**Commit:**

```text
feat(ai): add provider-neutral lead-worker routing policy
```

**Arcane memory:**

```bash
/Users/dkelly/.local/bin/arcane save --project macbook-pro --source claude-code \
  --category decision \
  --title "Adopt lead-worker routing across AI harnesses" \
  --what "Added provider-neutral model tiers, role prompts, and execute-playbook procedure: Sol/Fable medium lead, Luna/Sonnet medium workers, one correction, fresh verifier, direct strong rescue." \
  --why "A T3 Fable-to-Sonnet run completed seven ticket branches reliably while OpenCode specialist chains added latency and rarely escalated causally." \
  --impact "Normal engineering uses two model classes and whole-ticket ownership. Provider IDs live in one mapping; harness prompts share one workflow." \
  --tags "agents,routing,opencode,claude,codex,t3"
```

---

## R2. Load and validate canonical routing source

**Branch:** `feat/agent-routing-validation`

**Why:** Renderers must fail before deployment when policy has missing tiers, bad efforts,
unknown roles, cyclic escalation, or provider IDs leaked into prompts.

**Files:**

- New `roles/ai_agents/tasks/routing.yml`
- `roles/ai_agents/tasks/main.yml`
- New `scripts/validate-agent-routing.py`
- `Makefile`
- `.pre-commit-config.yaml`

**Steps:**

1. At start of `roles/ai_agents/tasks/main.yml` include `routing.yml`.
2. `routing.yml` loads both YAML files with `ansible.builtin.include_vars` under names
   `ai_routing_models` and `ai_routing_workflow`, then asserts required providers, tiers,
   roles, prompt files and numeric limits. No task logs secrets; files contain none.
3. `validate-agent-routing.py` performs same source checks without Ansible:
   - exact schema version
   - every role references existing tier and prompt
   - orchestrator primary; others subagents
   - verifier read-only
   - rescue not in normal assignment routes
   - correction/rescue limits equal one; identical failure limit equals two
   - all four required Claude IDs and four OpenAI IDs appear only in `models.yml`
   - every prompt exists and contains required evidence/status markers
   - `execute-playbook` frontmatter name matches directory
4. Add `make validate-agent-routing`.
5. Run it from `make lint` before Ansible lint, and add focused pre-commit hook covering
   routing YAML/prompts, skill and validator.

**Verify:**

```bash
make validate-agent-routing
make lint
make ci
source venv/bin/activate
ansible-playbook -i inventory -l local --check tests/ai_agents.yml \
  -e '{"ai_external_skills":[]}'
```

Expected first command: `Agent routing source valid`. Remaining commands exit 0.

Live call after deploying R1/R2 integration state:

```bash
make check RUN_ARGS='--tags ai'
make ai
timeout 240 claude-work -p \
  'Read-only. Load execute-playbook skill and return only its five allowed handoff statuses.'
```

Expected reply contains exactly `COMPLETE`, `CORRECTION_REQUIRED`, `HANDOFF_REQUIRED`,
`BLOCKED_AUTHORITY` and `BLOCKED_TRANSIENT`. Run `make ai` again; recap must show
`changed=0`.

**Commit:** `feat(ai): validate canonical agent routing policy`

**Arcane memory:**

```bash
/Users/dkelly/.local/bin/arcane save --project macbook-pro --source claude-code \
  --category pattern \
  --title "Validate agent routing before harness rendering" \
  --what "Added source validator and Ansible assertions for provider tiers, roles, prompts, escalation limits and the execute-playbook contract." \
  --why "One malformed canonical policy would otherwise break every generated harness at deploy time." \
  --impact "make lint and pre-commit reject routing drift before live configs change." \
  --tags "agents,validation,ansible"
```

---

## R3. Migrate OpenCode to lead-worker routing

**Branch:** `feat/opencode-lead-worker-routing`

**Why:** OpenCode currently carries nine agents and advisory escalation prose. Normal work
should use Sol-medium lead and Luna-medium whole-ticket workers, with independent verifier and
direct Sol-high rescue.

**Files:**

- `host_vars/localhost/opencode.yml`
- `group_vars/macbooks.yml`
- `roles/ai_agents/tasks/main.yml`
- `roles/cleanup/tasks/main.yml`
- `roles/ai_agents/templates/opencode/agent.md.j2`
- `roles/ai_agents/templates/opencode.jsonc.j2`
- `roles/ai_agents/templates/opencode-routing.md.j2`
- `host_files/localhost/ai/opencode/commands/orchestrate.md`
- `host_files/localhost/ai/opencode/commands/implement-reviewed.md`
- `host_files/localhost/ai/opencode/commands/debug-loop.md`
- `host_files/localhost/ai/opencode/commands/load-test-loop.md`
- `host_files/localhost/ai/opencode/commands/review.md`
- `host_files/localhost/ai/opencode/commands/plan.md`
- New `host_files/localhost/ai/opencode/commands/execute-playbook.md`
- `scripts/check-opencode-source.sh`
- `scripts/validate-opencode-config.sh`
- `scripts/test-ai-agents-idempotency.sh`
- `scripts/check-agent-config-drift.sh`

**Required agents:**

| Agent | Mode | Tier | OpenCode model/variant | Edit | Delegates |
|---|---|---|---|---|---|
| `orchestrator` | primary | lead | `openai/gpt-5.6-sol` / medium | playbook docs only | worker, verifier, rescue, documentation |
| `worker` | subagent | worker | `openai/gpt-5.6-luna` / medium | allowed | none |
| `verifier` | subagent | worker | `openai/gpt-5.6-luna` / medium | denied | none |
| `rescue` | subagent | rescue | `openai/gpt-5.6-sol` / high | allowed | none |
| `documentation` | subagent | worker | `openai/gpt-5.6-luna` / medium | docs only | none |

`documentation` alone gets `linear_*: allow`. All other generated agents deny Linear.
Verifier also denies Notion/Grafana writes. Preserve external-directory and destructive-command
rules.

**Steps:**

1. Remove `opencode_agent_models` from `host_vars/localhost/opencode.yml`. Keep installed
   schema compatibility and maximum parallel workers there only if host-specific; otherwise
   consume canonical workflow.
2. Replace `opencode_agents` registry with five agents above. Each entry references canonical
   role/prompt; no model ID appears in `group_vars`.
3. Add exact `opencode_retired_agents` list:
   `architect.md`, `explorer.md`, `worker-fast.md`, `implementer.md`, `debugger.md`,
   `reviewer.md` and `test-runner.md`.
4. Before removing retired deployed files, stat and back up any exact regular file not already
   preserved under `~/.ai-config-backup/opencode/retired/`. Then use
   `ansible.builtin.file: state: absent` on only those exact paths. Never sweep agent directory;
   user-owned agents remain untouched.
5. Render model and effort by resolving role tier -> OpenAI mapping and adding `openai/` prefix.
   Render common execute-playbook contract from canonical skill/body, plus role-specific prompt.
6. Orchestrator steps: 32. Worker: 32. Verifier: 16. Rescue: 32. Documentation: 16.
7. Orchestrator must not do routine implementation. It creates task ledger, assigns whole
   tickets, inspects real diff/check evidence, gives one correction, merges accepted ticket,
   and starts fresh verifier.
8. Worker returns structured handoff. Same failure fingerprint twice or second failed edit
   returns `HANDOFF_REQUIRED`; it does not pick another agent.
9. Rescue description says never select by default. Validator asserts only orchestrator may
   invoke it.
10. Rewrite normal engineering commands around lead-worker loop. `/plan` becomes orchestrator
    read-only planning. `/linear` remains bound to documentation. Add `/execute-playbook` bound
    to orchestrator.
11. Keep OpenCode built-ins available as manual escape hatches. `default_agent` remains
    orchestrator. Do not bundle OpenCode upgrade or built-in disabling.
12. Update all hardcoded agent/command arrays and loops in four scripts. Idempotency fixture
    must create one retired managed file, prove first apply removes it after backup, and prove
    second apply `changed=0`.
13. Replace existing temp cleanup traps that this ticket touches with printed absolute path plus
    `trash` to comply with no-`rm` rule. Do not broaden into unrelated scripts.

**Verify:**

```bash
make validate-agent-routing
make validate-opencode
make test-ai-agents
make lint
make ci
```

Expected all exit 0. `make validate-opencode` must print:

```text
Agents: orchestrator worker verifier rescue documentation
```

Apply:

```bash
make check RUN_ARGS='--tags ai'
make ai
make ai
bash scripts/check-agent-config-drift.sh
opencode debug config | jq '{
  default_agent,
  subagent_depth,
  agents: (.agent | with_entries(
    select(.key == "orchestrator" or .key == "worker" or .key == "verifier" or
           .key == "rescue" or .key == "documentation") |
    .value |= {model, variant, mode}
  ))
}'
```

Expected second apply `changed=0`. Expected resolved agents:

```text
orchestrator  openai/gpt-5.6-sol   medium  primary
worker        openai/gpt-5.6-luna  medium  subagent
verifier      openai/gpt-5.6-luna  medium  subagent
rescue        openai/gpt-5.6-sol   high    subagent
documentation openai/gpt-5.6-luna  medium  subagent
```

Confirm retired generated agents absent and user-owned files untouched:

```bash
for name in architect explorer worker-fast implementer debugger reviewer test-runner; do
  test ! -e "$HOME/.config/opencode/agents/$name.md" || {
    echo "retired agent still present: $name"
    exit 1
  }
done
```

**Live worker delegation:**

```bash
canary="routing-r3-worker-$(date +%s)"
timeout 300 opencode run \
  --agent orchestrator \
  --dir /Users/dkelly/Projects/macbook-pro \
  --format json \
  --title "$canary" \
  'Read-only routing canary. Delegate exactly one bounded task to worker: report first Markdown heading in README.md and git status exit code. Do not inspect README yourself. Worker must not edit, commit, merge, push, deploy, or delegate. Return worker evidence, then accept or reject it.'

root_id=$(sqlite3 -readonly /Users/dkelly/.local/share/opencode/opencode.db \
  "SELECT id FROM session WHERE title='$canary' ORDER BY time_created DESC LIMIT 1")
sqlite3 -readonly -header -column /Users/dkelly/.local/share/opencode/opencode.db "
SELECT DISTINCT
  json_extract(m.data, '$.agent') AS agent,
  json_extract(m.data, '$.modelID') AS model,
  json_extract(m.data, '$.variant') AS variant
FROM message m
WHERE m.session_id IN (
  SELECT id FROM session WHERE parent_id='$root_id'
)
AND json_extract(m.data, '$.role')='assistant';
"
git diff --exit-code
```

Expected one child row `worker | gpt-5.6-luna | medium` and no diff.

**Live verifier delegation:**

```bash
canary="routing-r3-verifier-$(date +%s)"
timeout 300 opencode run \
  --agent orchestrator \
  --dir /Users/dkelly/Projects/macbook-pro \
  --format json \
  --title "$canary" \
  'Read-only routing canary. Delegate exactly one task to verifier: run make validate-agent-routing and report command, exit code, and result. Do not run it yourself. Verifier must not edit or delegate. Inspect its evidence and return final acceptance.'
```

Query database as above. Expected `verifier | gpt-5.6-luna | medium`. Git diff unchanged.

**Commit:** `feat(ai): replace OpenCode specialist chain with lead-worker routing`

**Arcane memory:**

```bash
/Users/dkelly/.local/bin/arcane save --project macbook-pro --source claude-code \
  --category decision \
  --title "OpenCode uses Sol lead and Luna whole-ticket workers" \
  --what "Replaced normal nine-agent specialist chain with orchestrator, worker, verifier and rescue; retained documentation only as a Linear permission boundary." \
  --why "Usage showed specialist escalation was not causal and orchestrator did too much shell/edit work. T3 lead-worker execution was faster and reliable." \
  --impact "OpenCode defaults to Sol medium planning/review, Luna medium ticket execution and verification, direct Sol high rescue after one correction." \
  --tags "opencode,routing,sol,luna"
```

---

## R4. Render Claude personal/work agents

**Branch:** `feat/claude-lead-worker-agents`

**Why:** Claude supports native user subagents. Both personal Claude and `claude-work` should
load same generated workers. T3 Claude inherits work profile without duplicate T3 config.

**Files:**

- `group_vars/macbooks.yml`
- New `roles/ai_agents/tasks/claude_agents.yml`
- `roles/ai_agents/tasks/claude_settings.yml`
- `roles/ai_agents/tasks/main.yml`
- New `roles/ai_agents/templates/claude/agent.md.j2`
- `scripts/test-ai-agents-idempotency.sh`
- `scripts/check-agent-config-drift.sh`

**Steps:**

1. Add managed `agents_dir` to personal and work entries:
   `~/.claude/agents` and `~/.claude-work/agents`.
2. Render `worker.md`, `verifier.md`, `rescue.md` and `documentation.md` into both. Do not set a
   custom primary `orchestrator` agent; successful T3 run used normal Claude root with Fable
   selected and explicit Sonnet workers.
3. Frontmatter:
   - worker: `model: claude-sonnet-5`, `effort: medium`, `maxTurns: 40`
   - verifier: same model/effort, `permissionMode: plan`, `maxTurns: 24`
   - rescue: `model: claude-fable-5-1`, `effort: high`, `maxTurns: 40`
   - documentation: Sonnet medium, `maxTurns: 24`
4. Preload `execute-playbook` through `skills` frontmatter. Body adds only role-specific prompt.
   Claude subagents do not receive full primary system prompt, so do not rely on root context.
5. Manage default `model: claude-fable-5-1` and `effortLevel: medium` in both Claude
   `settings.json` files through existing preserved merge. Keep `no_log: true` on every read,
   merged fact and write.
6. Preserve every unrelated settings key and existing permission/hook behavior.
7. Back up colliding non-managed agent files once before first replacement. Manage only exact
   four filenames; never sweep `agents/`.
8. Extend isolated-home test to assert both profiles receive identical rendered agent files and
   second run changes zero tasks.
9. Test both installed Claude entry points. If `~/.local/bin/claude` and T3-launched Claude
   report different versions, record it; do not change binaries in this ticket.

**Verify:**

```bash
make validate-agent-routing
make test-ai-agents
make lint
make ci
make check RUN_ARGS='--tags ai'
make ai

for f in worker verifier rescue documentation; do
  test -f "$HOME/.claude/agents/$f.md" || { echo "missing personal agent: $f"; exit 1; }
  test -f "$HOME/.claude-work/agents/$f.md" || { echo "missing work agent: $f"; exit 1; }
  diff -q "$HOME/.claude/agents/$f.md" "$HOME/.claude-work/agents/$f.md" || { echo "profiles differ: $f"; exit 1; }
done
```

`claude agents` is not a static check for this ticket: on installed Claude Code 2.1.263 that
subcommand manages background *sessions*, not file-based subagents, and requires a TTY. Do not
use it to assert worker/verifier/rescue/documentation exist. The file-existence-plus-diff check
above, together with the direct native-agent canary below, is the acceptance evidence instead.

Direct native-agent checks:

```bash
personal_out=$(mktemp "${TMPDIR:-/tmp}/claude-personal-worker.XXXXXX")
work_out=$(mktemp "${TMPDIR:-/tmp}/claude-work-worker.XXXXXX")

env -u CLAUDE_CONFIG_DIR timeout 300 claude \
  --agent worker --output-format json -p \
  'Read-only canary. Return first Markdown heading in README.md and git status exit code. Do not edit.' \
  >"$personal_out"
timeout 300 claude-work \
  --agent worker --output-format json -p \
  'Read-only canary. Return first Markdown heading in README.md and git status exit code. Do not edit.' \
  >"$work_out"

jq -r '.modelUsage | keys[]' "$personal_out"
jq -r '.modelUsage | keys[]' "$work_out"
git diff --exit-code

ls -d "$personal_out" "$work_out"
trash "$personal_out" "$work_out"
```

Expected both include `claude-sonnet-5` and make no diff. If a profile's call fails with
HTTP 429 (spend/session limit), that is an account-level boundary, not a config defect: record
it and do not retry. A single profile's canary succeeding, combined with the byte-identical
rendered-file check above, is sufficient live evidence for this ticket.

Root delegation check (personal profile; cheaper to run than through `claude-work`, and
avoids burning the work profile's spend limit twice for the same proof):

```bash
env -u CLAUDE_CONFIG_DIR timeout 300 claude --output-format json -p \
  'Read-only routing canary. Use worker agent for exactly one task: return first heading in README.md. Review its evidence yourself. Do not edit.'
```

Expected model usage contains Fable 5.1 and Sonnet 5, proving strong lead -> balanced worker.
If it 429s, stop and record that; do not retry.

Run `make ai` again. Expected `changed=0`.

**Commit:** `feat(ai): render lead-worker agents for both Claude profiles`

**Arcane memory:**

```bash
/Users/dkelly/.local/bin/arcane save --project macbook-pro --source claude-code \
  --category decision \
  --title "Claude profiles use Fable lead and Sonnet workers" \
  --what "Rendered worker, verifier, rescue and documentation agents into personal and work Claude profiles from shared routing policy." \
  --why "This reproduces the successful T3 Fable-medium lead and Sonnet-medium whole-ticket execution pattern." \
  --impact "Claude CLI and T3 Claude share native agents without duplicated prompts or T3-specific files." \
  --tags "claude,t3,routing,agents"
```

---

## R5. Render Codex agents and manage agent defaults safely

**Branch:** `feat/codex-lead-worker-agents`

**Why:** Codex supports native custom agents. T3 Codex inherits `~/.codex`. Its app-owned
`config.toml` must preserve all unrelated settings while routing normal subagents to Luna
medium.

**Files:**

- `group_vars/macbooks.yml`
- New `roles/ai_agents/tasks/codex_agents.yml`
- `roles/ai_agents/tasks/main.yml`
- New `roles/ai_agents/templates/codex/agent.toml.j2`
- New `scripts/codex-agent-settings-sync.py`
- New `scripts/test-codex-agent-settings-sync.sh`
- `scripts/test-ai-agents-idempotency.sh`
- `scripts/check-agent-config-drift.sh`
- `Makefile`
- `.pre-commit-config.yaml`

**Steps:**

1. Render exact files under `~/.codex/agents/`:
   `worker.toml`, `verifier.toml`, `rescue.toml` and `documentation.toml`.
2. Every file contains required `name`, `description` and multiline
   `developer_instructions`. Resolve:
   - worker: `gpt-5.6-luna` / medium
   - verifier: `gpt-5.6-luna` / medium, read-only sandbox where supported
   - rescue: `gpt-5.6-sol` / high
   - documentation: `gpt-5.6-luna` / medium
3. Embed canonical execute-playbook procedure plus role prompt into
   `developer_instructions`. Escape TOML through template; do not concatenate unescaped text.
4. `codex-agent-settings-sync.py` manages only:
   - top-level `model = "gpt-5.6-sol"`
   - top-level `model_reasoning_effort = "medium"`
   - `agents.enabled = true`
   - `agents.max_concurrent_threads_per_session = 3`
   - `agents.default_subagent_model = "gpt-5.6-luna"`
   - `agents.default_subagent_reasoning_effort = "medium"`
5. Use `tomlkit` and replace only those named keys. Preserve all other top-level keys, agent
   keys, comments, MCP servers, projects, plugins and ordering byte-for-byte.
6. Support `--check` and print exactly `changed` or `unchanged`. No config contents printed.
7. Back up `config.toml` once under `~/.ai-config-backup/`. Ansible command task does not contain
   secrets, but do not enable diff of app-owned config.
8. Unit fixture includes comments, unknown `[agents]` key, MCP server, project trust setting and
   plugin table. Assert managed keys change, every unrelated slice remains unchanged, check mode
   writes nothing, second run reports unchanged.
9. Manage only four exact agent filenames. Preserve any other user-created custom agents.
10. Add unit script to `make test-ai-agents` and focused pre-commit hook.

**Verify:**

```bash
source venv/bin/activate
bash scripts/test-codex-agent-settings-sync.sh
make test-ai-agents
make lint
make ci
make check RUN_ARGS='--tags ai'
make ai
codex --strict-config --version
```

Expected sync test passes, all repo checks exit 0, and Codex accepts config without warnings.

Inspect only managed non-secret keys:

```bash
python - <<'PY'
from pathlib import Path
import tomlkit

doc = tomlkit.parse(Path.home().joinpath(".codex/config.toml").read_text())
print(doc["model"])
print(doc["model_reasoning_effort"])
for key in (
    "enabled",
    "max_concurrent_threads_per_session",
    "default_subagent_model",
    "default_subagent_reasoning_effort",
):
    print(key, doc["agents"][key])
PY
```

Expected Sol medium root, Luna medium default child, concurrency three.

Live delegation:

```bash
codex_out=$(mktemp "${TMPDIR:-/tmp}/codex-routing.XXXXXX")
timeout 300 codex exec --ephemeral --json \
  -C /Users/dkelly/Projects/macbook-pro \
  -m gpt-5.6-sol \
  -c 'model_reasoning_effort="medium"' \
  'Read-only routing canary. Delegate exactly one task to custom worker: return first Markdown heading in README.md and git status exit code. Worker must not edit or delegate. Review its evidence, then finish.' \
  >"$codex_out"

jq -e 'select(.type == "item.completed" or .type == "turn.completed")' \
  "$codex_out" >/dev/null
rg -n 'worker|gpt-5.6-luna|spawn_agent' "$codex_out"
git diff --exit-code
ls -d "$codex_out"
trash "$codex_out"
```

Expected JSON contains a worker spawn/completion and Luna evidence. If current Codex JSON event
schema does not expose child model, inspect new child through `codex agents` and record model
there. Self-reported model without a harness event/config trace is not sufficient.

Run `make ai` again; expect `changed=0`.

**Commit:** `feat(ai): render Sol-led Luna workers for Codex`

**Arcane memory:**

```bash
/Users/dkelly/.local/bin/arcane save --project macbook-pro --source claude-code \
  --category decision \
  --title "Codex defaults to Sol lead and Luna workers" \
  --what "Added native Codex worker/verifier/rescue agents and surgically managed only model and agents defaults in app-owned config.toml." \
  --why "T3 Codex should reproduce Fable-to-Sonnet workflow with Sol-to-Luna while preserving ChatGPT desktop settings." \
  --impact "New Codex/T3 sessions default to Sol medium; delegated tickets default to Luna medium with max concurrency three." \
  --tags "codex,t3,routing,sol,luna"
```

---

## R6. T3/Forge inheritance, drift checks and documentation

**Branch:** `feat/cross-harness-routing-drift`

**Why:** T3 should inherit rather than duplicate. Forge must advertise reduced support honestly.
Drift checker must cover every generated native-agent file.

**Files:**

- `scripts/check-agent-config-drift.sh`
- `scripts/test-ai-agents-idempotency.sh`
- `host_files/localhost/ai/README.md`
- `README.md`
- `group_vars/macbooks.yml` only if path metadata needs adjustment
- `roles/ai_agents/tasks/t3.yml` only if inheritance test exposes bug

**Steps:**

1. Drift checker asserts exact managed files exist:
   - OpenCode five agents and managed commands
   - Claude personal/work four native agents
   - Codex four native agents
2. For generated files, compare embedded canonical policy version/hash marker. Do not scan or
   print full settings files.
3. Keep drift checker advisory exit 0, matching current contract; print one actionable line per
   mismatch.
4. Isolated-home test proves T3 still points only to `claude-work` binary with no `homePath`.
   It also proves Claude work agent files and Codex agent files exist after first run and are
   byte-identical after second.
5. README support matrix:
   - OpenCode: full native lead/worker/verifier/rescue
   - Claude personal/work: full native workers, normal root selected Fable medium
   - Codex: full native workers and defaults
   - T3 Claude/Codex: inherited full support, no duplicate definitions
   - Forge: shared skill only; built-in model/agent controls remain Forge-owned
6. Document `documentation` exception and Linear boundary.
7. Document that T3 composer or explicit CLI flags may override root model/effort for one
   session; native worker files still pin worker model.
8. Do not edit T3 state database. Read with `sqlite3 -readonly` only.

**Verify:**

```bash
make test-ai-agents
make lint
make ci
make check RUN_ARGS='--tags ai'
make ai
bash scripts/check-agent-config-drift.sh

jq -e --arg binary "/Users/dkelly/.local/bin/claude-work" \
  '.providers.claudeAgent.binaryPath == $binary and
   (.providers.claudeAgent | has("homePath") | not)' \
  /Users/dkelly/.t3/userdata/settings.json

forge agent list
```

Expected drift output empty, T3 query true, Forge list still contains built-in Forge/Muse/Sage
only.

Live Forge reduced-mode call:

```bash
timeout 240 forge \
  -C /Users/dkelly/Projects/macbook-pro \
  --agent forge \
  -p 'Read-only. An approved playbook is ready. Explain current global execute-playbook workflow and state honestly whether this Forge version can create a Luna custom worker. Do not edit or run tests.'
git diff --exit-code
```

Expected it describes lead-worker procedure and says Forge cannot provide native managed Luna
worker. It must not claim full parity.

T3 evidence:

- This playbook's R1-R6 Luna workers, when run from a T3 Code Codex session, are themselves live
  T3 -> Codex -> Luna delegation evidence.
- After R5 deployment, start one fresh T3 Codex thread set to Sol medium and issue:
  `Read-only routing canary. Delegate README heading check to worker and review it.`
- Start one fresh T3 Claude thread set to Fable medium and issue same prompt.
- Query `~/.t3/userdata/state.sqlite` read-only to confirm both new threads' provider and model
  selection. Inspect matching provider event logs for worker start/completion and Luna/Sonnet
  model. If UI cannot be driven automatically, this is only manual checkpoint in playbook; stop
  and ask Dan to submit two prepared prompts.

**Commit:** `docs(ai): document cross-harness lead-worker support and drift`

**Arcane memory:**

```bash
/Users/dkelly/.local/bin/arcane save --project macbook-pro --source claude-code \
  --category context \
  --title "T3 inherits routing while Forge uses reduced mode" \
  --what "Documented and validated T3 inheritance from claude-work and Codex, plus Forge shared-skill-only support." \
  --why "Duplicating T3 definitions would drift; Forge 2.13.21 has no supported custom-agent authoring surface." \
  --impact "Capability claims now match live harness behavior and drift checks cover native managed agents." \
  --tags "t3,forge,routing,drift"
```

---

## R7. Reusable live routing canaries

**Branch:** `test/agent-routing-live-canaries`

**Why:** Static validators cannot prove model actually delegates. Add an opt-in, read-only,
usage-consuming runner; never run it automatically in CI.

**Files:**

- New `scripts/test-agent-routing-live.sh`
- `README.md`

**Required interface:**

```text
scripts/test-agent-routing-live.sh --harness opencode|claude-personal|claude-work|codex|forge|all
```

**Behavior:**

1. Require clean tracked worktree before start; allow only `?? docs/`. A `--self-test` flag may
   additionally allow the pending `README.md` and runner changes while R7 verifies itself. In
   both modes capture status before execution and require byte-identical status afterward.
2. Use `timeout 300` per harness.
3. Prompt only read-only README heading and `git status` checks.
4. OpenCode: require orchestrator -> worker child evidence from JSON and read-only database query.
5. Claude personal/work: run custom worker directly and one root delegation; require expected
   model keys in JSON result. Never use `claude agents` as evidence of a custom subagent's
   existence; on installed Claude Code it lists background sessions, not file-based subagents.
6. Codex: require spawn/completion event and inspect child session when model is absent from
   JSON.
7. Forge: verify reduced-mode answer, not native delegation.
8. T3: print exact two manual prompts and read-only evidence query; never mutate T3 SQLite.
9. Capture logs in `mktemp -d`. Before cleanup print directory with `ls -d`, then `trash` exact
   absolute directory. Trap must call a cleanup function using `trash`; never `rm`.
10. After each harness, require `git diff --exit-code` and same tracked status as before.
11. Print concise `PASS <harness>: <evidence>` or `FAIL <harness>: <reason>`. Non-zero if any
    requested harness fails.
12. Do not place script in `make lint`, `make ci` or pre-commit execution path because it spends
    model usage. Shell syntax/static lint may still cover it.

**Verify:**

```bash
bash -n scripts/test-agent-routing-live.sh
scripts/test-agent-routing-live.sh --help
scripts/test-agent-routing-live.sh --self-test --harness opencode
scripts/test-agent-routing-live.sh --self-test --harness claude-work
scripts/test-agent-routing-live.sh --self-test --harness codex
git diff --check integration/cross-harness-lead-worker-routing...HEAD
```

Expected three `PASS` lines and no worktree mutation. Forge and both T3 paths run in final
acceptance.

**Commit:** `test(ai): add opt-in live routing canaries`

**Arcane memory:**

```bash
/Users/dkelly/.local/bin/arcane save --project macbook-pro --source claude-code \
  --category pattern \
  --title "Live canaries prove agent routing behavior" \
  --what "Added opt-in read-only canaries for OpenCode, Claude, Codex, T3 evidence and Forge reduced mode." \
  --why "Rendered files can be valid while models ignore delegation prompts or harnesses load stale config." \
  --impact "Routing acceptance now proves actual child selection and model use without changing repositories." \
  --tags "agents,testing,canary,routing"
```

---

## Final integration acceptance

No new implementation branch or commit. Fresh Luna-medium verifier runs all commands; Sol-medium
lead reruns critical checks, inspects integration diff, and makes final acceptance decision.

### 1. Repository and history

```bash
cd /Users/dkelly/Projects/macbook-pro
git checkout integration/cross-harness-lead-worker-routing
git status --short
git log --oneline --decorate main..HEAD
git diff --check main...HEAD
git diff --stat main...HEAD
git diff main...HEAD
```

Expected status `?? docs/` only. Expected one `--no-ff` integration merge per ticket and no
direct integration commits.

### 2. Required checks, exact order

```bash
make lint
make ci
make validate-opencode
make test-ai-agents
make check RUN_ARGS='--tags ai'
make ai
make ai
bash scripts/check-agent-config-drift.sh
pre-commit run --all-files
```

Expected every command exits 0. First `make ai` may change deployment. Second `make ai` must
report `changed=0`. Drift checker prints nothing. Then run final dry run:

```bash
make check RUN_ARGS='--tags ai'
```

Expected `changed=0`.

### 3. Live harness matrix

```bash
scripts/test-agent-routing-live.sh --harness all
```

Expected:

| Harness | Required evidence |
|---|---|
| OpenCode | Sol-medium orchestrator spawned Luna-medium worker, reviewed response; Luna verifier works; no edit |
| Claude personal | Fable-medium root and Sonnet-medium worker visible in model usage; native worker file loads |
| Claude work | Same as personal through `claude-work` |
| Codex | Sol-medium root spawned custom Luna-medium worker; child completion visible |
| T3 Claude | Fresh T3 thread shows Fable-medium root and Sonnet worker |
| T3 Codex | Fresh T3 thread shows Sol-medium root and Luna worker |
| Forge | Shared workflow understood; reduced native-agent support stated honestly |

Run direct rescue smoke tests once because normal canaries must not escalate:

```bash
timeout 240 opencode run \
  --agent rescue \
  --dir /Users/dkelly/Projects/macbook-pro \
  'Read-only rescue registration canary. Return your role, configured model tier, and first README heading. Do not edit.'

timeout 240 claude-work \
  --agent rescue --output-format json -p \
  'Read-only rescue registration canary. Return first README heading. Do not edit.'
```

Expected Sol high and Fable high respectively. Do not simulate destructive or production
failures.

### 4. Permission and safety checks

```bash
opencode debug agent verifier | jq '.permission'
opencode debug agent worker | jq '.permission'
opencode debug agent documentation | jq '.permission'
```

Expected:

- verifier has no edit allow and cannot delegate
- worker can edit but cannot delegate or call Linear
- documentation can edit docs/Markdown and call Linear, but not general source
- only orchestrator can dispatch worker/verifier/rescue/documentation

Confirm no secret-shaped material entered managed source:

```bash
rg -n --hidden \
  'BEGIN [A-Z ]*PRIVATE KEY|Bearer[[:space:]]+[A-Za-z0-9._-]{16,}|lin_api_|ntn_|glsa_' \
  host_files/localhost/ai roles/ai_agents scripts
```

Expected no secret values. Documentation mentioning patterns may match; inspect every hit.

### 5. Usage and latency acceptance

Record timestamps and model usage from live canaries. Acceptance is behavioral, not a hard
benchmark:

- Root performs planning/review, not long implementation shell loops.
- One whole-ticket worker per ticket.
- No explorer -> implementer -> debugger -> architect chain in normal canary.
- Passing output compact; full logs only on failure.
- At most one correction before rescue.
- No more than three independent workers.
- No worker model above Luna/Sonnet unless rescue trip-wire fired.

After real use accumulates, repeat OpenCode database analysis after 20 new managed root sessions.
Compare:

- orchestrator shell/edit count
- worker share of implementation messages and input/cache tokens
- elapsed time per completed ticket
- correction and rescue rates
- sessions that never delegate

Do not build automatic cost analytics or model-price tables into Arcane; prior spike was parked as
off-mission.

### 6. Final lead decision

Lead returns one verdict:

- `PASS`: every required check and live harness path passed
- `PASS_WITH_REQUIRED_FIXES`: only explicit bounded fixes remain; do not merge to main
- `FAIL`: routing, model evidence, permissions, idempotency, drift or live behavior failed

Report:

- integration HEAD
- ticket merge list
- files changed
- required checks with exit codes
- second-apply changed count
- one row per live harness
- corrections and rescue use
- unsupported behavior
- residual risk

Do not push. Dan reviews integration diff and decides whether to open/merge one PR into `main`.

---

## Appendix: deliberate exclusions

- No normal mini -> Luna -> Terra -> Sol escalation ladder.
- No separate explorer, debugger, architect, reviewer or test-runner hop in routine execution.
- No Fable/Sol implementation by default.
- No automatic production, security, credential, destructive or publishing authority.
- No universal background daemon watching conversations.
- No T3-specific prompt copies.
- No claim of native Forge parity.
- No OpenCode upgrade or built-in-agent disablement.
- No dynamic mid-conversation effort optimizer.
- No full passing logs returned to lead.
- No changes to OpenCode, T3, Claude or Codex session databases.

## Appendix: handoff examples

Successful worker:

```yaml
status: COMPLETE
ticket: R3
branch: feat/opencode-lead-worker-routing
commit: abc1234
files:
  - roles/ai_agents/templates/opencode/agent.md.j2
checks:
  - command: make validate-opencode
    exit_code: 0
    result: OpenCode config valid
failure_fingerprint: null
deviations: []
last_safe_state: committed
recommended_next: lead_review
unresolved_risks: []
```

Worker finding bad ticket:

```yaml
status: HANDOFF_REQUIRED
ticket: R4
branch: feat/claude-lead-worker-agents
commit: null
files: []
checks:
  - command: claude agents
    exit_code: 1
    result: installed CLI rejects effort frontmatter
failure_fingerprint: claude-agents|unsupported-effort-frontmatter
deviations:
  - installed Claude version differs from T3 provider version
last_safe_state: no files changed
recommended_next: correct_ticket_or_pin_supported_syntax
unresolved_risks:
  - terminal and T3 Claude may load different binaries
```

Authority boundary:

```yaml
status: BLOCKED_AUTHORITY
ticket: R6
branch: feat/cross-harness-routing-drift
commit: null
files: []
checks: []
failure_fingerprint: null
deviations: []
last_safe_state: no external action taken
recommended_next: ask_user
unresolved_risks:
  - fresh T3 UI thread requires user interaction
```
