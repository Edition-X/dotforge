# Playbook: repository-managed browsers

**Status:** approved for execution
**Written:** 2026-09-08
**Audience:** configured lead orchestrating whole-ticket `gpt-5.6-luna` medium workers, with fresh Luna-medium verification
**Repo:** `~/Projects/macbook-pro` (Edition-X/macbook-pro, private as proven by P0)
**Scope:** Google Chrome, Microsoft Edge, Brave, Firefox and Vivaldi on macOS. Safari is explicitly out of scope.

---

## 0. Read this first

### Goal

Manage browser packages, policy, bookmark capture, extension presence and safe drift reporting from this repository without copying credentials or browser session state. Restore useful bookmarks from a private repository through managed bookmark folders, while preserving ordinary user bookmarks and making browser-specific ownership explicit.

The repository already installs all five browsers through Brewfile. Preserve that package ownership. This playbook adds a browser role after packages; it does not move package installation or create a browser role before execution approval.

### Current baseline

Only installs are managed today; no browser role exists. Sanitized inventory, counts only:

| Browser | Current inventory |
|---|---:|
| Chrome | 97 bookmarks |
| Edge | 532 bookmarks |
| Brave | no `Bookmarks` file |
| Vivaldi | 31 bookmarks |
| Firefox | latest backup indicated 16 bookmarks |

Chromium browsers each have one `Default` profile. Firefox has one active `default-release` profile and an empty `default` profile. Safari data was not inspected.

### Hard privacy gate

The first ticket must confirm GitHub repository privacy before any bookmark URL is read into or written under this repository.

> **Changing repository visibility is an external security action. Before `gh repo edit`, lead must confirm current user authorization in the execution message.**

The user selected “make repo private” during planning. Execution must still record evidence from `gh repo view` and must not treat planning selection as execution authority. Until `gh repo view Edition-X/macbook-pro --json isPrivate` proves `isPrivate: true`, do not inspect bookmark contents, capture URLs, create fixtures containing URLs, or write browser catalog files. A private repository is still not a secret store.

If `isPrivate` is false, stop. Lead asks for current authorization, repeats the warning above, and only then may run `gh repo edit Edition-X/macbook-pro --visibility private`. Recheck `isPrivate: true` immediately afterward. If authorization is absent, ambiguous, or command result is not provable, return `BLOCKED_AUTHORITY`.

### Canonical execution contract

Configured lead orchestrates. Lead reads this playbook in full, owns dependency ledger, reviews real diffs and reruns checks, but never implements a ticket. Every implementation ticket goes whole to configured worker tier: current OpenAI worker is `gpt-5.6-luna`, reasoning effort medium. Worker creates branch from current integration branch, edits only listed files, verifies, inspects diff, commits locally and saves Arcane memory.

One correction resumes same worker on same ticket. A second materially similar failure with same `failure_fingerprint` creates fresh direct rescue dispatch with full evidence; never a third unchanged attempt. Rescue is not self-selected. After each logical batch, fresh verifier—never implementing worker—checks integrated result before merge. Maximum three concurrent workers, only for independent non-overlapping tickets. Shared files and variables run serially.

Every delivery handoff has exactly these fields: `status`, `ticket`, `branch`, `commit`, `files`, `checks`, `failure_fingerprint`, `deviations`, `last_safe_state`, `recommended_next`, `unresolved_risks`.

Allowed statuses: `COMPLETE`, `CORRECTION_REQUIRED`, `HANDOFF_REQUIRED`, `BLOCKED_AUTHORITY`, `BLOCKED_TRANSIENT`.

### Shared safety rules

1. Cut `integration/repo-managed-browsers` from current `main` once. Ticket branches start from current integration branch and merge back with `git merge --no-ff` after lead review. Never commit directly to `main` or integration.
2. No push, PR, auto-merge, repository visibility change, or other external action unless the ticket explicitly grants it and lead confirms current-message authority at execution time. P7 is the explicit exception for the user-selected Git automation flow, but still stops for missing authority.
3. Normal dirty checkout is never used by automation. Automation uses dedicated isolated clone/worktree under `~/.local/state`, refuses dirty or non-fast-forward state, and never touches this checkout.
4. Never use `rm`. For removal, print exact absolute path with `ls -d`, then move to recoverable trash. Never trash profiles or browser data. Exact reproducible generated files may be removed only by managed Ansible task after backup where stated.
5. Stage exact allowlisted paths only. Never `git add -A`, `git add .`, or stage `docs/` broadly. Preserve existing untracked docs files.
6. Never print bookmark URLs, account emails, credentials, extension IDs from local state, cookies, or secret-shaped values in logs or check output. Passing checks are one line each; failing command output is verbatim and must itself contain no URLs or secrets.
7. Never commit or copy cookies, `Login Data`, `key4.db`, `logins.json`, passwords, session stores, OAuth state, account emails, raw profiles, browser preference databases, extension local storage or website sessions. LastPass presence is managed; credentials are not.
8. Read-only snapshots may run while browsers are open, but must use consistency checks and bounded retries. Close browser processes before policy application when vendor mechanism requires it, before reinstall, and before any profile write (profile writes are excluded). Never patch live `Preferences` or `Secure Preferences`. Never uninstall because Brewfile already owns an app. Never use `--zap`.
9. Every implementation ticket has live browser acceptance: actual installed browser against isolated temporary profile, internal policy page evidence, and Playwright or purpose-built read-only smoke script. Static checks alone never count.
10. Security, secret, destructive, production, permission, authority or missing-user-input boundary stops execution for lead/user. Stronger model cannot grant authority.

### Vendor references

Workers must use primary vendor documentation and record URLs in ticket notes or source comments only when needed; do not copy documentation content into catalogs.

- Chrome enterprise policy list: https://chromeenterprise.google/policies/
- Chrome managed bookmarks: https://support.google.com/chrome/a/answer/2657289
- Microsoft Edge policy reference: https://learn.microsoft.com/deployedge/microsoft-edge-policies
- Microsoft Edge managed favorites: https://learn.microsoft.com/deployedge/microsoft-edge-policies#managedfavorites
- Brave enterprise policy reference: https://support.brave.com/hc/en-us/articles/360039248271-Group-Policy
- Mozilla Firefox policy templates: https://github.com/mozilla/policy-templates
- Firefox distribution policies: https://mozilla.github.io/policy-templates/
- Vivaldi Sync: https://help.vivaldi.com/desktop/tools/sync/
- Homebrew bundle: https://docs.brew.sh/Manpage#bundle-subcommand
- GitHub CLI repository visibility: https://cli.github.com/manual/gh_repo_edit
- GitHub Actions auto-merge: https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/incorporating-changes-from-a-pull-request/automatically-merging-a-pull-request
- Playwright browser automation: https://playwright.dev/docs/intro

---

## 1. Decisions and boundaries

### Browser policy support

Chrome, Edge and Brave support managed policy. Use browser/user/device policy scope, not per-profile assumptions:

| Browser | Policy domain | Bookmark policy | Extension policy |
|---|---|---|---|
| Chrome | `com.google.Chrome` | `ManagedBookmarks` | `ExtensionSettings`, `ExtensionInstallForcelist` |
| Edge | `com.microsoft.Edge` | `ManagedFavorites` | `ExtensionSettings`, `ExtensionInstallForcelist` |
| Brave | `com.brave.Browser` | `ManagedBookmarks` | `ExtensionSettings`, `ExtensionInstallForcelist` |
| Firefox | macOS configuration profile or `Firefox.app/Contents/Resources/distribution/policies.json` | `ManagedBookmarks` in current Mozilla templates | `ExtensionSettings` in current Mozilla templates |
| Vivaldi | no verified official enterprise policy contract | best effort only | best effort only |

Distinguish mandatory managed policy from recommended defaults in catalog schema and rendered policy. Policies may apply browser/user/device-wide and are not reliably profile-specific.

Firefox app-bundle policy files may be overwritten by cask updates. Ansible restores them after packages. Role order in `site.yml` is packages -> browsers -> later roles.

Vivaldi is best effort by explicit user choice. Early spike checks installed Vivaldi build for a working policy domain and live `vivaldi://policy` evidence. If both work, record exact evidence and use only verified policy. Otherwise support declarative audit/export, LastPass extension presence, bookmark capture and documented one-time Sync login. Never infer Chromium policy support from Vivaldi and never patch live preference files.

### Bookmarks

Catalogs remain dedicated per browser. No cross-browser union unless same bookmark is explicitly entered in multiple browser files. Stable fingerprint uses normalized title, URL, folder path and browser. Normalize title, URL, folder path and browser before comparison.

Read-only snapshots:

- Chromium: atomically copy `Bookmarks` JSON into a mode-0600 temporary snapshot, then validate file size, JSON parse and stable hash before reading.
- Firefox: create a read-only SQLite backup with WAL consistency, then validate SQLite integrity and stable hash before reading.

Never write profile files. Fail closed on snapshot integrity failure. Suspicious or rejected URLs go only to local mode-0600 quarantine with local notification; never Git. Validator rejects userinfo, `javascript:`, `data:`, `file:` schemes, known credential query keys, OAuth callback/token patterns and secret-like values. Logs and checks never print URLs.

Initial release captures additions only. Absence never implies deletion, move or rename. Managed bookmark folders provide reliable from-scratch restore, but policy bookmarks are separate/managed; later ordinary bookmarks may remain as ordinary copies.

B0/B1 live experiment measures duplicate behavior with fake URLs and isolated profiles. Stop for user choice if duplicate UX is unacceptable. Custom WebExtension/native host is not baseline; any such design needs separate approval.

### Extensions and LastPass

Discovery reads only sanitized enabled-state metadata from consistent snapshots. Initial catalog separates browser components/system add-ons from user extensions. Adopt current enabled user extensions as allowlisted candidates, but do not block unlisted extensions until a generated report is reviewed once. Final policy may block all except catalog only after explicit migration approval.

Verify official extension ID and update URL per browser using vendor/add-on store evidence; never trust a directory ID alone. The playbook must not place local extension IDs in this document or logs.

LastPass is selected everywhere. Manage extension/app presence only. Fresh browser or machine still needs one interactive LastPass login and MFA/passkey. Website sessions cannot be deployed. No credentials, cookies, passwords or local extension storage enter repository.

---

## 2. Ticket order and ledger

Tickets are serial where role files, schemas, variables or automation paths overlap. A fresh verifier runs after B2-B5 browser-policy batch, after B6-B8 integration batch, at B9 pre-merge acceptance, and after B10 activation.

| Order | Ticket | Branch | Worker | Dependency |
|---:|---|---|---|---|
| 0 | P0 Privacy/repository gate | no branch | lead | none; hard gate |
| 1 | B0 Vendor capability spike and sanitized inventory | `spike/browser-capabilities-inventory` | Luna medium | P0 |
| 2 | B1 Schema, validator, fixtures and role scaffold | `feat/browser-schema-role` | Luna medium | B0 |
| 3 | B2 Shared Chromium renderer and Chrome adapter | `feat/browser-chrome-policy` | Luna medium | B1 |
| 4 | B3 Edge and Brave adapters | `feat/browser-edge-brave-policy` | Luna medium | B2 |
| 5 | B4 Firefox adapter | `feat/browser-firefox-policy` | Luna medium | B1; serial with B2-B3 due role paths |
| 6 | B5 Vivaldi best-effort adapter | `feat/browser-vivaldi-policy` | Luna medium | B1; serial |
| 7 | verifier | B2-B5 integrated browser-policy batch | no commit | fresh Luna verifier | B2-B5 merged |
| 8 | B6 Capture and reconciliation | `feat/browser-capture-reconcile` | Luna medium | B1, B2-B5 |
| 9 | B7 launchd, isolated Git automation, GitHub CI and auto-merge | `feat/browser-git-automation` | Luna medium | B6; authority gate |
| 10 | B8 LastPass/extension allowlist migration and reinstall drill | `feat/browser-extension-migration` | Luna medium | B2-B7; authority gates |
| 11 | verifier | B6-B8 integrated automation batch | no commit | fresh Luna verifier | B6-B8 merged |
| 12 | B9 final fresh verifier and acceptance | no commit | fresh Luna verifier, Sol lead | all prior tickets; pre-merge |
| 13 | B10 Post-merge activation exercise | no branch | lead + fresh Luna verifier | B9 PASS plus separately authorized merge to main |

No ticket may skip its dependency, conceal a failed live smoke, or broaden its listed files without lead correction and recorded deviation.

---

## 3. P0. Privacy/repository gate

**Branch:** no branch; lead-owned gate

**Why:** Bookmark URLs are sensitive personal data. No bookmark URL may enter repo until GitHub confirms private visibility.

**Files:**

- No browser catalog or bookmark file before privacy proof.
- If evidence must be retained, only this playbook or a separate lead-approved non-URL gate note; never bookmark data.

**Steps:**

1. Inspect status without reading docs content: `git status --short`. Preserve all existing untracked `docs/` files.
2. Run `gh repo view Edition-X/macbook-pro --json nameWithOwner,isPrivate`. Record only command and sanitized result. Expected JSON has `nameWithOwner` and `isPrivate: true`; do not print URL or repository contents.
3. If false, stop and repeat: “Changing repository visibility is an external security action. Before `gh repo edit`, lead must confirm current user authorization in the execution message.” Do not run `gh repo edit` without current-message authority.
4. With explicit authority only, run `gh repo edit Edition-X/macbook-pro --visibility private --accept-visibility-change-consequences`; immediately rerun step 2. Any permission, confirmation or ambiguous output is `BLOCKED_AUTHORITY`.
5. Lead records privacy evidence in ledger: timestamp, command, `isPrivate=true`, actor authorization source. No bookmark URL.

**Stop conditions:** public or unknown visibility; missing `gh` auth; repository mismatch; any request to capture bookmark content before proof; dirty tracked work beyond pre-existing untracked docs.

**Verify:**

```bash
git status --short
gh repo view Edition-X/macbook-pro --json nameWithOwner,isPrivate
```

Expected: existing untracked docs only; `isPrivate` is `true`. No live browser smoke is permitted before this gate; privacy command is live acceptance evidence.

**Arcane memory trigger:** After successful visibility change or confirmed private state, lead saves decision memory: repository privacy is a hard precondition for bookmark URL handling; private GitHub is not a secret store. P0 has no commit.

---

## 4. B0. Vendor capability spike and sanitized migration inventory

**Branch:** `spike/browser-capabilities-inventory`

**Why:** Pin vendor behavior before schema or policy code. Capture only counts, fingerprints and sanitized metadata.

**Files:**

- New `scripts/browser-capability-spike.py`
- New `docs/research/browser-capabilities-2026-09.md` (only sanitized evidence; no URLs, account data or local extension IDs)
- New `tests/fixtures/browsers/capability/` fake fixture data only
- No role or canonical catalog files

**Steps:**

1. Confirm P0 evidence still says `isPrivate=true`; stop if not.
2. Read primary vendor policy references. Record tested installed versions and capability result, not profile contents.
3. Use `scripts/browser-capability-spike.py` to launch each installed browser with an isolated temporary profile, inspect policy capability and internal policy page, and report only browser, version, capability and count. The script never opens or touches live profiles. It moves temporary state to recoverable trash after printing its absolute path; it never uses `rm`.
4. Test Chrome, Edge and Brave policy domains and determine per vendor whether local CFPreferences/plist, managed preferences or configuration profile is accepted on this non-MDM Mac. Record whether managed bookmark and extension policies render as expected. Separate mandatory policy from recommended defaults.
5. Test Firefox using supported local mechanisms and determine whether app-bundle distribution policy is overwritten by cask updates. Do not assume `.mobileconfig` installation works without MDM; if browser accepts only MDM/configuration profile, stop for user decision rather than pretending local support.
6. Check installed Vivaldi build for policy domain and live `vivaldi://policy`. If unavailable or unverified, record unsupported and define audit/export plus one-time Sync login path. Do not patch preferences.
7. Create sanitized inventory: browser, non-sensitive profile label, bookmark count, enabled-state count, system-component count, user-extension candidate count and snapshot hash. No titles or URLs.
8. Record B0/B1 duplicate experiment design using fake URLs only. Do not capture real bookmarks until schema/validator exists.

**Stop conditions:** privacy proof missing; snapshot integrity failure; vendor capability unclear; Vivaldi policy inferred without evidence; any credential/session/profile data exposed; duplicate experiment requires real URLs.

**Verify:**

```bash
gh repo view Edition-X/macbook-pro --json isPrivate
source venv/bin/activate
python scripts/browser-capability-spike.py --all-installed --isolated --no-user-data
python scripts/browser-capability-spike.py --check-report docs/research/browser-capabilities-2026-09.md
make lint
make ci
```

Expected: `isPrivate=true`; isolated installed-browser smoke reports one compact line per browser; report check passes and prints no URL; repo checks pass. Temporary profiles are printed by absolute path, then moved to recoverable trash.

**Live browser smoke:** actual installed Chrome, Edge, Brave, Firefox and Vivaldi against isolated temporary profiles; internal policy pages read-only. Isolated profiles may mutate; before/after hashes prove every live user profile remains unchanged.

**Commit:** `docs(browsers): record vendor capabilities and sanitized inventory`

**Arcane memory trigger:** Save pattern memory after commit: browser capability evidence and sanitized inventory contain counts only; Vivaldi policy support remains gated by live evidence.

---

## 5. B1. Schema, validator, fixtures and role scaffold

**Branch:** `feat/browser-schema-role`

**Why:** Establish explicit per-browser ownership and fail-closed input validation before any real bookmark capture or policy rendering.

**Files:**

- New `host_files/localhost/browsers/chrome/bookmarks.yml`
- New `host_files/localhost/browsers/chrome/extensions.yml`
- New `host_files/localhost/browsers/chrome/policies.yml`
- New equivalent `bookmarks.yml`, `extensions.yml`, `policies.yml` under `edge`, `brave`, `firefox`, `vivaldi`
- New `roles/browsers/defaults/main.yml`
- New `roles/browsers/tasks/main.yml`
- New `roles/browsers/README.md`
- New `scripts/validate-browser-catalog.py`
- New `scripts/browser-snapshot.py`
- New `scripts/browser-smoke.py`
- New `tests/fixtures/browsers/` fixture profiles containing fake URLs only
- `site.yml` (role placement after package roles)
- `Makefile` (`browsers`, `browser-test`, `browser-drift`, `browser-capture`, `validate-browser-catalog`; target stubs wired only when scripts exist)

**Schema requirements:**

- Per-browser catalog root; no implicit union.
- Bookmark record: normalized title, URL, folder path, browser and stable fingerprint.
- Policy entries explicitly mark `mandatory` or `recommended`.
- Extension catalog separates system components from user candidates and records verified vendor source/update URL, not local directory evidence.
- LastPass entry expresses presence/force policy without credentials or website sessions.
- Capture mode is additions-only; deletion/move/rename inference impossible by schema.
- Validator rejects userinfo, `javascript:`, `data:`, `file:`, credential query keys, OAuth callback/token patterns and secret-like values.

**Steps:**

1. Create empty, schema-valid per-browser catalogs. Real current bookmarks are seeded only in B6 after privacy, schema and validation gates pass.
2. Build fake fixture profiles for each browser. Every fixture URL is clearly non-real and must never be copied from local state.
3. Implement read-only snapshot abstraction. Chromium snapshot uses pre/post metadata and stable-hash checks with bounded retries; Firefox uses SQLite online read-only backup with WAL consistency. Validate parse and integrity before extraction.
4. Implement URL validator and stable fingerprint. Rejected values go to local mode-0600 quarantine interface only; validator output prints reason/count, never URL.
5. Add role scaffold and put `browsers` immediately after `packages` in `site.yml`. Cleanup manages only exact generated policy and launchd files, never profiles or catalogs.
6. Add Make targets with isolated temporary home/profile defaults. Keep `browser-capture` disabled unless explicit runtime flag is supplied.
7. Run managed-folder duplicate experiment with fake URLs. If duplicates are unacceptable, STOP before B2 for user choice. A custom WebExtension/native host is a separately approved follow-up, never baseline.

**Stop conditions:** any real URL in fixture/catalog/research; validator prints URL; profile write; non-WAL-consistent Firefox read; schema permits cross-browser union by default; duplicate UX unacceptable without user choice; role appears before package role.

**Verify:**

```bash
source venv/bin/activate
python scripts/validate-browser-catalog.py --all
python scripts/browser-snapshot.py --fixtures tests/fixtures/browsers --check-only
make browser-test RUN_ARGS='--fixtures --isolated'
make lint
make ci
make check RUN_ARGS='--tags browsers'
```

Expected: validator passes with URL count hidden; fixture snapshot checks pass; Ansible check shows role after packages; every command exits 0 with one-line passing output.

**Live browser smoke:** each installed browser opens isolated temporary profile, reads a fake managed bookmark/policy fixture, and verifies internal policy page access where supported. Isolated profiles may mutate and are moved to recoverable trash; live user-profile hashes must remain byte-for-byte unchanged.

**Commit:** `feat(browsers): add validated per-browser catalog role scaffold`

**Arcane memory trigger:** Save decision memory after commit: per-browser canonical catalogs, fail-closed snapshots and additions-only reconciliation prevent accidental cross-browser or profile-state migration.

---

## 6. B2. Shared Chromium renderer and Chrome adapter

**Branch:** `feat/browser-chrome-policy`

**Why:** Render Chrome policy declaratively from validated catalog while keeping package ownership in Brewfile and profile files untouched.

**Files:**

- `roles/browsers/tasks/main.yml`
- New `roles/browsers/tasks/chromium.yml`
- New `roles/browsers/templates/chromium-policy.plist.j2` or other B0-proven local payload template
- New `roles/browsers/templates/chromium-managed-bookmarks.json.j2`
- New `roles/browsers/templates/chromium-extension-policy.json.j2`
- `host_files/localhost/browsers/chrome/bookmarks.yml`
- `host_files/localhost/browsers/chrome/extensions.yml`
- `host_files/localhost/browsers/chrome/policies.yml`
- `scripts/browser-smoke.py`

**Steps:**

1. Use only B0-proven local deployment mechanism for this non-MDM Mac. Render Chrome `com.google.Chrome` policy using mandatory/recommended distinction. Any sudo or managed-preference write requires current authority.
2. Render `ManagedBookmarks`, `ExtensionSettings` and `ExtensionInstallForcelist` only from verified catalog entries. LastPass is mandatory presence, never credential deployment.
3. Use managed bookmark folder restore and document separate managed UX. Do not write Chrome `Bookmarks` file.
4. Test with isolated Chrome profile, internal `chrome://policy`, and policy refresh. Capture policy status only, not bookmark URLs.
5. Ensure cask/package check happens before policy restore.

**Stop conditions:** local mechanism not proven or requires MDM; policy writes profile preferences; unverified extension ID/update URL; policy claims per-profile reliability; URLs printed; vendor-required browser closure missing; package ownership moved out of Brewfile. An MDM-only result stops for user decision.

**Verify:**

```bash
make check RUN_ARGS='--tags browsers'
make browsers
make browser-test RUN_ARGS='--browser chrome --isolated --policy'
python scripts/validate-browser-catalog.py --browser chrome --all
make browser-drift
```

Expected: Ansible applies policy after package task; Chrome isolated smoke reads `chrome://policy` and reports expected policy names/status; validator and drift pass without URL output.

**Live browser smoke:** installed Chrome, isolated temporary profile, real policy page, Playwright/read-only smoke confirms managed folder visible and profile remains unchanged.

**Commit:** `feat(browsers): manage Chrome policy and bookmarks`

**Arcane memory trigger:** Save pattern memory after commit: managed Chrome bookmarks are separate from ordinary profile bookmarks; renderer never writes profile files.

---

## 7. B3. Edge and Brave adapters

**Branch:** `feat/browser-edge-brave-policy`

**Why:** Reuse shared Chromium safety and rendering while preserving distinct policy domains and bookmark keys.

**Files:**

- `roles/browsers/tasks/chromium.yml`
- `roles/browsers/templates/chromium-policy.plist.j2` or other B0-proven local payload template
- `roles/browsers/templates/chromium-managed-bookmarks.json.j2`
- `roles/browsers/templates/chromium-extension-policy.json.j2`
- `host_files/localhost/browsers/edge/{bookmarks.yml,extensions.yml,policies.yml}`
- `host_files/localhost/browsers/brave/{bookmarks.yml,extensions.yml,policies.yml}`
- `scripts/browser-smoke.py`
- `scripts/validate-browser-catalog.py`

**Steps:**

1. Add Edge `com.microsoft.Edge` and `ManagedFavorites` through its B0-proven local mechanism; prove policy naming from current vendor reference.
2. Add Brave `com.brave.Browser` and `ManagedBookmarks` through its B0-proven local mechanism; do not infer unsupported settings from Chromium.
3. Keep extension policies separate per browser and verify official IDs/update URLs independently.
4. Run isolated test profiles for both browsers, including Brave no-source-bookmark baseline.

**Stop conditions:** Edge/Brave policy domain or local mechanism mismatch; MDM-only result without user decision; shared catalog union; extension directory ID used without vendor proof; ordinary bookmarks overwritten; any browser process/profile safety violation; sudo write without current authority.

**Verify:**

```bash
make browsers
make browser-test RUN_ARGS='--browser edge --isolated --policy'
make browser-test RUN_ARGS='--browser brave --isolated --policy'
python scripts/validate-browser-catalog.py --browser edge --all
python scripts/validate-browser-catalog.py --browser brave --all
make browser-drift
```

Expected: both internal policy pages show expected browser-specific keys; no profile writes; counts and drift lines pass without URL output.

**Live browser smoke:** actual installed Edge and Brave, isolated profiles, policy pages and Playwright/read-only checks.

**Commit:** `feat(browsers): add Edge and Brave policy adapters`

**Arcane memory trigger:** Save pattern memory after commit: Chromium adapters share renderer only; browser policy domains and bookmark catalogs remain distinct.

---

## 8. B4. Firefox adapter

**Branch:** `feat/browser-firefox-policy`

**Why:** Firefox policy distribution differs from Chromium and app-bundle policy can be overwritten by cask updates.

**Files:**

- `roles/browsers/tasks/main.yml`
- New `roles/browsers/tasks/firefox.yml`
- New `roles/browsers/templates/firefox-policies.json.j2`
- `host_files/localhost/browsers/firefox/{bookmarks.yml,extensions.yml,policies.yml}`
- `scripts/browser-snapshot.py`
- `scripts/browser-smoke.py`
- `scripts/validate-browser-catalog.py`

**Steps:**

1. Render supported macOS configuration profile or `Firefox.app/Contents/Resources/distribution/policies.json`; select path from installed/vendor-supported evidence, not guesswork.
2. Render `ManagedBookmarks` and `ExtensionSettings`, distinguish mandatory policy from recommended defaults.
3. Restore app-bundle policy after package task. Never edit Firefox profile databases or preference files.
4. Test active `default-release` and empty `default` only through isolated copies; do not inspect or migrate website/session state.
5. Validate WAL-consistent read-only SQLite snapshot behavior.

**Stop conditions:** cask update overwrites policy without Ansible restore; SQLite backup not integrity-checked; `key4.db`, `logins.json`, cookies or OAuth state read; policy assumed profile-scoped.

**Verify:**

```bash
make check RUN_ARGS='--tags browsers'
make browsers
make browser-test RUN_ARGS='--browser firefox --isolated --policy'
python scripts/validate-browser-catalog.py --browser firefox --all
make browser-drift
```

Expected: Firefox internal `about:policies` shows expected policy status; package-then-policy order is proven; no forbidden files read; no URLs printed.

**Live browser smoke:** installed Firefox against isolated temporary profile and `about:policies`; live user-profile hashes remain unchanged while isolated profile mutation is allowed and later moved to recoverable trash.

**Commit:** `feat(browsers): manage Firefox distribution policies`

**Arcane memory trigger:** Save pattern memory after commit: Firefox distribution policy must be restored after cask updates; read-only SQLite backup must preserve WAL consistency.

---

## 9. B5. Vivaldi best-effort adapter

**Branch:** `feat/browser-vivaldi-policy`

**Why:** Vivaldi Sync offers useful migration but no verified official enterprise policy contract. Explicitly avoid silent Chromium inference.

**Files:**

- `roles/browsers/tasks/main.yml`
- New `roles/browsers/tasks/vivaldi.yml`
- New `roles/browsers/templates/vivaldi-audit.sh.j2`
- `host_files/localhost/browsers/vivaldi/{bookmarks.yml,extensions.yml,policies.yml}`
- `scripts/browser-smoke.py`
- `scripts/validate-browser-catalog.py`
- `roles/browsers/README.md`

**Steps:**

1. Inspect installed Vivaldi build only in isolated profile. Check for a working policy domain and live `vivaldi://policy` evidence.
2. If verified, implement only documented, live-proven policies and record exact capability. If not verified, implement declarative audit/export, bookmark capture, LastPass presence and one-time Sync login instructions only.
3. Document Sync capabilities: bookmarks, some settings, passwords, extensions, web apps, reading list, tabs and notes. Sync login is interactive and never automated; passwords are never exported by this role.
4. Never patch live `Preferences` or `Secure Preferences`; never deploy Sync credentials or website sessions.

**Stop conditions:** policy domain not proven; worker infers policy from Chromium; live preference patch requested; Sync login/password/session data requested; duplicate UX unresolved.

**Verify:**

```bash
make browser-test RUN_ARGS='--browser vivaldi --isolated --policy'
python scripts/validate-browser-catalog.py --browser vivaldi --all
make browser-drift
```

Expected: output says `policy verified` only with live evidence, otherwise `best-effort audit/export`; no live preference changes and no URL output.

**Live browser smoke:** installed Vivaldi isolated profile, `vivaldi://policy` evidence when available, otherwise audit/export smoke plus bookmark read-only smoke.

**Commit:** `feat(browsers): add evidence-gated Vivaldi support`

**Arcane memory trigger:** Save decision memory after commit: Vivaldi remains best effort unless installed build proves policy support; Sync login is one-time interactive and never state deployment.

---

## 10. Fresh verifier: B2-B5 policy batch

**No branch or commit. Fresh Luna-medium verifier only.**

Verifier reads integrated diff and reruns every B2-B5 command. It must test actual installed Chrome, Edge, Brave, Firefox and Vivaldi where installed against isolated profiles, read internal policy pages, and confirm no profile write. It must not edit, delegate, call trackers, or approve unsupported Vivaldi behavior.

```bash
make validate-browser-catalog
make browser-test RUN_ARGS='--all-installed --isolated --policy'
make browsers
make browser-drift
make lint
make ci
make check RUN_ARGS='--tags browsers'
git diff --check
```

Expected: one line per passing command, no URL output, all installed-browser smokes pass, unsupported Vivaldi path explicitly recorded if applicable. Any failure returns `CORRECTION_REQUIRED` to original ticket worker; repeated same fingerprint dispatches rescue.

---

## 11. B6. Capture and reconciliation

**Branch:** `feat/browser-capture-reconcile`

**Why:** Capture additions safely without treating missing records as deletion or reading forbidden browser state.

**Files:**

- New `scripts/browser-capture.py`
- New `scripts/browser-reconcile.py`
- New `scripts/browser-quarantine.py`
- `scripts/browser-snapshot.py`
- `scripts/validate-browser-catalog.py`
- `Makefile` (`browser-capture`)
- `roles/browsers/defaults/main.yml`
- `roles/browsers/README.md`
- `host_files/localhost/browsers/*/bookmarks.yml` for first real catalog seed, only after privacy, schema and validator gates pass

**Steps:**

1. Take consistent read-only snapshots while browsers may be running. Chromium capture compares pre/post metadata and stable hashes with bounded retries; Firefox uses SQLite online read-only backup with WAL consistency. Fail closed after bounded retries on hash, JSON, SQLite or WAL integrity issue.
2. Normalize title, URL, folder path and browser; compute stable fingerprint.
3. Compare against that browser’s catalog only. Append additions. Never infer delete, move or rename from absence.
4. Send rejected/suspicious records to local mode-0600 quarantine with notification. Never commit quarantine.
5. Ensure logs/checks print only browser, profile label, count, reason and hash prefix where safe—not URL, title containing account data, or extension ID.
6. Run fake fixture cases for valid addition, duplicate, deletion absence, move absence, suspicious URL, concurrent browser write and snapshot failure.
7. Seed each real browser catalog from current live bookmarks for first migration. This is first ticket allowed to write real bookmark URLs, and only exact `host_files/localhost/browsers/*/bookmarks.yml` paths may contain them. Print counts only.

**Stop conditions:** forbidden file read; URL in output or unexpected Git path; quarantine mode not 0600; absence removes catalog data; snapshot remains inconsistent after bounded retries; cross-browser union.

**Verify:**

```bash
python scripts/browser-capture.py --fixtures tests/fixtures/browsers --check-only
python scripts/browser-reconcile.py --fixtures tests/fixtures/browsers --additions-only --check-only
python scripts/validate-browser-catalog.py --all
make browser-test RUN_ARGS='--all-installed --isolated --capture-read-only'
make browser-capture RUN_ARGS='--dry-run --isolated'
```

Expected: fixture cases pass; rejected count goes to local quarantine only; dry run produces no catalog/profile change; seeded real URLs occur only in exact per-browser bookmark catalogs; no URLs print.

**Live browser smoke:** each installed browser may remain open while read-only snapshot/capture dry run proves bounded consistency behavior. Live profile hashes and files remain unchanged; output contains counts only.

**Commit:** `feat(browsers): capture bookmark additions safely`

**Arcane memory trigger:** Save bug/pattern memory after commit: additions-only reconciliation avoids destructive deletion inference; browser snapshots fail closed when integrity is uncertain.

---

## 12. B7. launchd, isolated Git automation, GitHub CI and auto-merge

**Branch:** `feat/browser-git-automation`

**Why:** Automate safe bookmark-addition capture without touching dirty checkout or publishing to main directly.

**Authority gate:** P0 already proves private repository. Lead must confirm current user authorization before any branch push, PR creation/update, auto-merge request or repository-setting change. B7 installs launchd disabled and performs no live push or activation; B10 owns activation after code lands on `main`.

**Files:**

- New `roles/browsers/templates/com.dkelly.browser-capture.plist.j2`
- New `roles/browsers/templates/browser-capture-run.sh.j2`
- New `scripts/browser-git-automation.py`
- New `scripts/browser-automation-smoke.py`
- New `.github/workflows/browser-catalog.yml`
- `roles/browsers/tasks/main.yml`
- `Makefile` (`browser-capture`, `browser-drift`)
- `README.md`
- `roles/browsers/README.md`
- `roles/cleanup/tasks/main.yml` (exact generated launchd/policy files only; never profiles or catalogs)

**Automation contract:**

- Dedicated clone/worktree under `~/.local/state`, not normal checkout.
- Recheck `gh repo view Edition-X/macbook-pro --json isPrivate` and require `true` on every run.
- Validate only allowlisted bookmark catalog paths; reject any path outside per-browser catalog roots and validator scripts.
- Snapshot and capture additions only; settings/extensions drift is notification/report-only.
- When activated in B10, stage exact allowlisted paths, create/update one dedicated automation branch and one PR, request GitHub auto-merge with merge method, never squash/rebase.
- No force push. Stop on conflict, non-fast-forward, dirty state, failed privacy proof, unexpected path, validator failure or changed package/source files.
- Send local notification for capture, rejection, drift, stop and PR state.
- No extension/settings auto-adoption.
- Stable automation branch can fast-forward after merge; integration/main is never directly edited by run.

**Steps:**

1. Add launchd service scheduled about every 15 minutes by interval; use hash-based polling, not `WatchPaths`. Install it disabled by default and do not bootstrap it before B10.
2. Ensure service uses consistent live read-only snapshots, bounded retries and mode-0700 scripts/directories. Capture only bookmark additions.
3. Implement isolated automation clone behavior: recheck privacy and clean state, run validator, inspect exact allowlist, stage exact files, commit, and prepare dedicated branch operations. Exercise network operations only against fake remotes in this ticket.
4. Implement creation/update of exactly one PR and auto-merge request using merge commit. Do not squash/rebase. Stop if PR conflict or branch moved unexpectedly. Real GitHub exercise waits for B10.
5. Add GitHub Actions validation for PRs: schema, validators, fake fixtures, secret scan, allowlist and no-URL-output checks. CI never runs live capture or accesses browser profiles.
6. Test failure paths by fake fixture/state only: public repo, dirty worktree, unexpected path, non-fast-forward, conflict and suspicious URL. Restore test state; never delete profiles or use `rm`.

**Stop conditions:** launchd activation before B10; live push/PR before feature lands on main; `isPrivate` false/unknown; normal checkout touched; dirty isolated clone; force push requested; conflict/non-fast-forward; non-allowlisted path; PR count not exactly one; settings/extensions auto-adopted; URL appears in log/notification.

**Verify:**

```bash
make browser-test RUN_ARGS='--automation --isolated --fake-github'
make browser-drift
make check RUN_ARGS='--tags browsers'
python scripts/browser-git-automation.py --check --isolated-root "$HOME/.local/state"
python scripts/browser-automation-smoke.py --fake --no-network
actionlint .github/workflows/browser-catalog.yml
```

Expected: fake automation validates privacy/path/dirty/conflict stops; no real push or PR; launchd remains disabled, interval is about 15 minutes and does not use `WatchPaths`; local workflow validation passes; no URLs print.

**Live browser smoke:** actual installed browsers against isolated profiles, capture dry run only, policy pages read-only, no normal checkout mutation. Live GitHub actions require lead-confirmed authority and private proof; if not granted, stop after fake smoke.

**Commit:** `feat(browsers): automate private catalog capture through isolated PRs`

**Arcane memory trigger:** Save decision memory after commit: automation uses isolated state, private-repo recheck, exact allowlist and merge-commit auto-merge; it captures bookmark additions only and reports other drift.

---

## 13. B8. LastPass/extension allowlist migration and reinstall drill

**Branch:** `feat/browser-extension-migration`

**Why:** Manage extension presence safely while preserving user credentials and existing Brewfile package ownership.

**Files:**

- `host_files/localhost/browsers/chrome/extensions.yml`
- `host_files/localhost/browsers/edge/extensions.yml`
- `host_files/localhost/browsers/brave/extensions.yml`
- `host_files/localhost/browsers/firefox/extensions.yml`
- `host_files/localhost/browsers/vivaldi/extensions.yml`
- `roles/browsers/templates/chromium-extension-policy.json.j2`
- `roles/browsers/templates/firefox-policies.json.j2`
- `roles/browsers/tasks/chromium.yml`
- `roles/browsers/tasks/firefox.yml`
- `roles/browsers/tasks/vivaldi.yml`
- `scripts/browser-extension-report.py`
- `scripts/browser-smoke.py`
- `roles/browsers/README.md`

**Steps:**

1. Generate sanitized enabled-state report from consistent snapshots. Separate browser/system components from user extensions.
2. Add LastPass presence/force entries using official vendor ID and update URL evidence. Never copy credentials, local storage or website sessions.
3. Adopt current enabled user extensions as allowlisted candidates in report only. Do not block unlisted extensions until report receives one explicit migration review.
4. Keep final block-all-except-catalog policy behind explicit migration approval; no extension/settings auto-adoption.
5. Do not uninstall browsers already Brewfile-managed. Test policy in isolated profiles first.
6. Reinstall drill: after browser closed and lead confirms authority, run plain `brew reinstall --cask <one-browser>` one browser at a time, never `--zap`; verify profiles, LastPass state and bookmark source are preserved. Full five-browser reinstall only if needed.
7. Require one interactive LastPass login plus MFA/passkey on fresh machine/browser. Record presence only.

**Stop conditions:** credentials/session data read; local extension storage copied; unverified official ID/update URL; block policy enabled before report review; browser open during reinstall; `--zap`; profile deletion/trash; reinstall changes Brewfile ownership.

**Verify:**

```bash
python scripts/browser-extension-report.py --all --sanitized --isolated
make browser-test RUN_ARGS='--all-installed --isolated --extensions --policy'
make browsers
make browser-drift
```

Expected: report contains only counts, component/user classification and verified catalog references; LastPass presence passes without login data; reinstall drill evidence preserves profiles/source; no URLs or account emails printed.

**Live browser smoke:** every installed browser isolated profile, extension policy page/internal add-on manager read-only, LastPass presence check without sign-in automation; fresh-machine login remains manual.

**Commit:** `feat(browsers): manage extension presence and reinstall safety`

**Arcane memory trigger:** Save decision memory after commit: extension allowlist starts as reviewed candidates; LastPass presence is managed, but credentials and sessions remain interactive/user-owned.

---

## 14. Fresh verifier: B6-B8 automation batch

**No branch or commit. Fresh Luna-medium verifier only.**

```bash
make validate-browser-catalog
make browser-test RUN_ARGS='--all-installed --isolated --capture-read-only --extensions --policy'
make browser-drift
make lint
make ci
make check RUN_ARGS='--tags browsers'
python scripts/browser-git-automation.py --check --isolated-root "$HOME/.local/state"
```

Expected: all checks pass one line each; no URL output; isolated automation does not touch normal checkout; launchd and GitHub validation are present; verifier records any unsupported Vivaldi path and any authority-gated live GitHub step.

---

## 15. B9. Final fresh verifier and acceptance

**No branch or commit. Fresh Luna-medium verifier; Sol lead makes final decision.**

### Repository and history

```bash
git status --short
git log --oneline --decorate main..integration/repo-managed-browsers
git diff --check main...integration/repo-managed-browsers
git diff --stat main...integration/repo-managed-browsers
```

Expected: only pre-existing untracked `docs/` plus explicitly documented untracked research; no direct integration commits. Real bookmark URLs may exist only in exact private-repo paths `host_files/localhost/browsers/*/bookmarks.yml`; no URL-bearing data exists in logs, fixtures, research, extension/policy files or unexpected paths, and no secret-shaped material exists anywhere in managed source.

### Required checks, exact order

```bash
make validate-browser-catalog
make browser-test RUN_ARGS='--all-installed --isolated --policy --extensions --capture-read-only'
make browser-drift
make lint
make ci
make check RUN_ARGS='--tags browsers'
make browsers
make browsers
make check RUN_ARGS='--tags browsers'
```

Expected: every command exits 0; second apply and final check report `changed=0`; drift output is empty or explicitly documented Vivaldi best-effort/authority-gated state; every installed browser has live isolated-profile smoke evidence.

### Privacy and forbidden material checks

```bash
gh repo view Edition-X/macbook-pro --json isPrivate
python scripts/validate-browser-catalog.py --all --no-url-output
git log -p main..integration/repo-managed-browsers -- ':!docs/' | python scripts/validate-browser-catalog.py --history-stdin --no-url-output
```

Expected: `isPrivate=true`; history input may contain catalog URLs but validator never echoes them; URL-bearing records are confined to exact bookmark catalogs. No cookies, Login Data, key4.db, logins.json, passwords, OAuth state, raw profile, preference database, extension storage, account email or website session material exists.

### Fresh browser matrix

| Browser | Evidence |
|---|---|
| Chrome | installed app, isolated profile, `chrome://policy`, managed bookmark/extension smoke |
| Edge | installed app, isolated profile, `edge://policy`, managed favorite/extension smoke |
| Brave | installed app, isolated profile, `brave://policy`, managed bookmark/extension smoke |
| Firefox | installed app, isolated profile, `about:policies`, distribution policy/extension smoke |
| Vivaldi | installed app, isolated profile, `vivaldi://policy` only if proven; else audit/export and explicit best-effort evidence |

### Acceptance decision

Lead returns one verdict in execution notes: `PASS`, `PASS_WITH_REQUIRED_FIXES`, or `FAIL`. Report integration HEAD, ticket merge list, exact files, checks with exit codes, second-apply changed count, one row per browser, corrections/rescue, authority-gated steps, unsupported Vivaldi behavior, extension migration decision and residual risks.

No PR to main or merge to main occurs without separate current-message authority. User reviews integration diff before publication. Launchd remains disabled through B9.

---

## 16. B10. Post-merge activation exercise

**No ticket branch. Lead owns external actions; fresh Luna-medium verifier owns read-only post-activation checks.**

**Preconditions:** B9 verdict is `PASS`; user gives current-message authority to push integration, merge it to `main`, enable GitHub auto-merge/repository settings if needed, activate launchd, and run one real automation exercise. P0 still reports `isPrivate=true`. Missing authority returns `BLOCKED_AUTHORITY` without partial activation.

**Steps:**

1. Lead inspects status, full integration diff and included commits again. Push only with current authority, create PR from `integration/repo-managed-browsers` to `main`, wait for checks, then merge using normal repository merge policy. Never force push.
2. Check out and fast-forward local `main`. Run `make browsers`, then run it again and require `changed=0`. Confirm no profile was removed and Vivaldi limitation remains explicit.
3. Enable repository auto-merge only if needed and authorized. Recheck private visibility immediately before enabling launchd.
4. Bootstrap disabled browser-capture launchd service. Confirm interval, mode, executable path, isolated clone root and logs contain no URLs.
5. In an isolated browser profile, create one fake bookmark using an `https://example.invalid/` URL. Run one real capture cycle. Verify exact allowlisted catalog changed in isolated clone, automation branch pushed, exactly one PR opened, GitHub Actions passed, and PR auto-merged with a merge commit.
6. Fetch `main` in isolated clone and prove stable automation branch fast-forwards without reset, rebase, squash or force push.
7. Remove fake bookmark from source through a normal explicit source commit/PR. This cleanup is not deletion inference and never reads or edits a live user profile. Wait for checks and merge with current authority.
8. Fresh verifier reruns read-only private-repo, launchd, branch, PR-history, browser drift and catalog confinement checks. It never edits or performs GitHub actions.

**Stop conditions:** missing current authority; repository not private; B9 not PASS; main moved unexpectedly; required check failure; auto-merge unavailable; more than one automation PR; URL appears in logs; unexpected path staged; launchd runs before main contains feature; stable branch needs reset/rebase/force; live user profile touched.

**Verify:**

```bash
gh repo view Edition-X/macbook-pro --json isPrivate,defaultBranchRef
gh workflow view browser-catalog.yml
make browsers
make browser-test RUN_ARGS='--all-installed --isolated --policy --extensions'
make browser-drift
python scripts/browser-git-automation.py --check --isolated-root "$HOME/.local/state"
launchctl print "gui/$(id -u)/com.dkelly.browser-capture"
git -C "$HOME/.local/state/macbook-pro-browser-sync" status --short --branch
```

Expected: private main contains browser feature; second apply was `changed=0`; workflow and launchd are active; fake bookmark PR merged via merge commit then explicit cleanup merged; stable automation branch fast-forwarded; no URL printed; normal checkout untouched; fresh verifier returns `COMPLETE` or blocks with exact evidence.

**Arcane memory trigger:** Save milestone memory after successful activation: five-browser policy/capture system landed, automatic additions use private allowlisted merge-commit PRs, LastPass presence is managed, credentials/sessions remain excluded, and Vivaldi support level is recorded.

---

## 17. Handoff format

Every delivery role returns exactly eleven fields and no extras:

```yaml
status: COMPLETE
ticket: B1
branch: feat/browser-schema-role
commit: <local commit or null>
files:
  - <exact path>
checks:
  - command: <exact command>
    exit_code: 0
    result: <one-line result>
failure_fingerprint: null
deviations: []
last_safe_state: committed
recommended_next: lead_review
unresolved_risks: []
```

Passing output is one line per check. Failing command output is verbatim, in full, after sanitizing only forbidden secret/URL material by stopping before output can occur. Authority boundaries use `BLOCKED_AUTHORITY`; transient infrastructure uses `BLOCKED_TRANSIENT`; implementation defects use `CORRECTION_REQUIRED` or `HANDOFF_REQUIRED` according to correction/fingerprint rules.

---

## Appendix: explicit exclusions

- Safari data, installation, policy, bookmarks, extensions and sessions.
- Moving browser package ownership out of Brewfile.
- Cross-browser bookmark union by default.
- Profile-file writes, live `Preferences`/`Secure Preferences` patching and profile deletion.
- Cookies, `Login Data`, `key4.db`, `logins.json`, passwords, session stores, OAuth state, account emails, raw profiles and extension local storage.
- Website-session deployment or automated LastPass login/MFA/passkey.
- Extension/settings auto-adoption.
- Custom WebExtension/native host baseline.
- Vivaldi enterprise-policy claims without live installed-build evidence.
- `--zap`, force push, squash/rebase, direct main edits, or destructive cleanup.
- Production/security/authority actions delegated to stronger model instead of lead/user.
