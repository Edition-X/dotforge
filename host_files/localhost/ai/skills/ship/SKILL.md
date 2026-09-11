---
name: ship
description: Land any change to the dotforge repo end to end without Dan in the loop — cut a branch from main, verify, push, open the PR, self-review it as an AI reviewer, fix what the review finds, wait for CI, merge through the PR, deploy to this Mac and verify the deploy. Use for every commit-worthy change in ~/Projects/dotforge, including work another skill (macbook, arcane-dev) has already edited on a branch. Triggers on "ship it", "land this", "open a PR and merge it", "get this onto main", or any repo change that is ready to leave the working tree.
---

# Ship

Work in `~/Projects/dotforge` lands through a pull request, never a direct push to
`main`. This skill is the whole path from "edit is ready" to "running on this Mac", and
it is meant to run without asking Dan anything. Ask only at the boundaries in section 7.

Every step prints one line of evidence on pass and the full output on failure. Never
report a step you skipped as done.

## 1. Branch

```bash
cd ~/Projects/dotforge
git status --short            # must be clean, or only the files you are about to commit
git checkout main && git pull --ff-only
git checkout -b <type>/<kebab-description>   # feat/ fix/ chore/ docs/ refactor/
```

If a branch already exists for this work (another skill cut it), stay on it and rebase
it on `main` first: `git rebase main`. Never rebase a branch that is already pushed and
has a PR — add commits instead.

## 2. Change and verify

Make the edit. Then, before any commit:

1. `make lint` — every pre-commit hook, exit 0.
2. `make ci` — lint, offline tests, syntax check. This is exactly what GitHub runs.
3. If the change touches a role: `make check RUN_ARGS='--tags <tag>'`, read the diff,
   then `make <tag>` to apply it here, then `make <tag>` again and confirm `changed=0`.
   Tags: `ai`, `browsers`, `dotfiles`, `mcp`, `neovim`, `packages`, `ssh`, `tmux`.
4. Area verify from the `macbook` skill (brew list, new shell, drift script, mcp-test,
   `make browser-test ...` when browsers changed).

## 3. Commit and push

Conventional Commits, one logical change per commit. Stage files by name, never `-A`.

```bash
git add <files>
git commit -m "<type>(<scope>): <subject>" -m "<why, not what>"
git push -u origin HEAD
```

## 4. Open the PR

```bash
gh pr create --base main --title "<type>(<scope>): <subject>" --body-file <(cat <<'BODY'
## What changed
...
## Why
...
## Verification
- `make ci` — pass
- `make check RUN_ARGS='--tags X'` reviewed, `make X` applied, second run changed=0
- browser / GUI evidence that cannot run in CI, if any
## Risk and rollback
...
BODY
)
```

Fill every section of `.github/pull_request_template.md`. Not a draft.

## 5. Review, iterate, merge

**AI review.** Review the PR yourself with fresh eyes, as a reviewer who did not write
it: in Claude Code run `/code-review <pr-number>`; in any harness, load the
`review-pr-feedback` skill against the PR (it is read-only and pins the head SHA).
Treat every finding as real until you have checked the code:

- A correctness, security or idempotency finding: fix it, rerun section 2, commit, push.
- A finding you disagree with: say why in a PR comment, with the evidence.
- A pure style nit: fix it if it is a one-liner, otherwise note it and move on.

Re-review after each push until a pass produces no correctness findings. Then post the
outcome so the PR carries the review record:

```bash
gh pr comment <n> --body "AI review: <k> findings, <fixed> fixed in <sha..sha>, <declined> declined (see thread). No open correctness findings."
```

**CI.** Wait with `scripts/pr-checks-green.sh <n>`. It exits 0 only when every check
in the rollup is complete and green, and prints the failed ones otherwise. Do not use
`gh pr checks --watch` as the gate: it can return 0 while a sibling run is still pending
or red, and a merge chained on it once landed a red pull request. On a failure, load
`gh-fix-ci`, fix on this branch, push, wait again. Never merge red, never retry a flaky
job more than once without reading its log.

**Merge.** Merge commit — the repo's history is merge-based and the browser automation
depends on that. Chain the merge only onto the gate above, whose exit code is
trustworthy — never onto `gh pr checks --watch`:

```bash
scripts/pr-checks-green.sh <n> && gh pr merge <n> --merge --delete-branch
```

After the merge, confirm the `main` push run is green too:
`gh run list --branch main --limit 1 --json conclusion`.

The `main` ruleset requires a pull request, the `Lint, test & validate` and `Secret scan`
checks, a merge commit, and forbids force-pushes and deletion. So the merge can also be
queued as soon as the review is done: `gh pr merge <n> --merge --auto --delete-branch`,
then wait with `gh pr view <n> --json state,mergedAt` — GitHub merges the moment the
checks go green and refuses otherwise. Never `--admin`, never `--squash` or `--rebase`,
never force-push.

## 6. Deploy and verify on this Mac

```bash
git checkout main && git pull --ff-only
make <tag>            # or make apply when the change spans roles
make <tag>            # expect changed=0
```

Then the area verify from step 2.4 once more, against `main`. If it fails, the fix is a
new branch through this same skill — do not patch the machine by hand.

Save an Arcane memory (`decision`, `bug`, `pattern` or `context`) if the change carries
one. Report: PR URL, merge commit, what was applied here, and the command Dan can run to
see it.

## 7. Stop and ask

These are Dan's decisions. Stop with the PR open (or before pushing) and ask:

- A change to repository visibility, branch rulesets, secrets, or GitHub settings.
- Anything that rewrites history, force-pushes, or deletes a branch that is not the PR's.
- A secret that does not exist yet in the vault, or any plaintext credential.
- A `make apply` that would remove an app, key, or config that Dan did not name.
- A review finding that changes what the PR does, not how — scope is Dan's call.

## Verify this skill

```bash
make ai
ls -la ~/.claude/skills/ship ~/.codex/skills/ship ~/.config/opencode/skills/ship \
       ~/forge/skills/ship ~/.claude-work/skills/ship
cd ~/Projects/dotforge && timeout 300 claude-work -p "Add a one-line comment to the top of Brewfile explaining that it is the single source of truth, and ship it."
```

Expect: a branch, `make lint`/`make ci`, a push, `gh pr create`, a self-review comment,
`scripts/pr-checks-green.sh`, `gh pr merge --merge`, `git pull` on main, `make packages`.
No question back to Dan.
