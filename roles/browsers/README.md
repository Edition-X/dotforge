# Browser role

This role owns declarative, browser-specific catalogs. B1 validates source only; it does
not install policy or touch browser profiles. Chrome, Edge, Brave, Firefox and Vivaldi
remain separate ownership roots. Missing records never mean delete, move or rename.

Chrome, Edge, Brave and Firefox all use mandatory managed preferences. Firefox reads the
`org.mozilla.firefox` domain with `EnterprisePoliciesEnabled`, so its policy lives beside
the Chromium ones instead of inside the application bundle: a file under `Firefox.app`
breaks the bundle signature, and macOS refuses to launch a freshly installed bundle whose
seal no longer matches — it reports the app as damaged. The role asserts the bundle has no
`distribution` directory, and the smoke verifies `codesign` still passes.

Firefox policy evidence comes from the policy engine itself. The smoke launches the
installed application against an isolated profile, connects over Marionette in chrome
context, and reads `Services.policies` status and active policy values. Firefox refuses
script evaluation on privileged pages, and screenshot text recognition proved fragile —
it silently failed when the page rendered in dark mode.

Vivaldi remains best-effort because its installed build has not proved a vendor
enterprise-policy contract; its role installs only a sanitized read-only audit/export
check.

Vivaldi Sync can migrate bookmarks and Speed Dials, some settings, stored passwords,
autofill data, history, extensions, web apps, reading list, open tabs and notes without
attachments. Login and encryption-password entry remain one-time interactive steps. This
role never deploys Sync credentials, exports passwords or copies website sessions.

`make browser-capture RUN_ARGS='--dry-run --isolated'` takes bounded, read-only
snapshots and reports counts only. `--enable-capture --isolated` appends validated
records to each browser's own bookmark catalog. Missing bookmarks never remove, move or
rename catalog entries. Rejected records go to a local mode-0600 quarantine outside repo;
their values never appear in command output.

Cleanup removes only exact generated paths — the launchd job, the capture runner and the
staged policy files under `~/.local/state/macbook-pro`. It never removes profiles,
catalogs, login state, quarantine, the isolated automation clone or browser data. The
root-owned copies in `/Library/Managed Preferences` and inside `Firefox.app` are left for
a deliberate, privileged removal.

## Extensions and LastPass

`scripts/browser-extension-report.py --all --sanitized --isolated` reads each browser's
live extension state in memory — the preference store is never copied or written — and
classifies browser components apart from user extensions. Output is counts only: no
extension identifiers, names or URLs. The detailed candidate list lands in a local
mode-0600 report under `~/.local/state/macbook-pro/browser-policy/`, outside the
repository, for one explicit migration review.

Catalogs manage presence only. `enforcement` stays `report_only`, so unlisted extensions
keep working; blocking everything except the catalog needs that review first, and the
role refuses any other value. Presence entries carry a vendor-verified id and store
update URL — Chrome Web Store for Chrome and Brave, Microsoft Edge Add-ons for Edge,
addons.mozilla.org for Firefox — and a directory id alone is never enough. Vivaldi has no
proven policy contract, so its LastPass presence is audited, never enforced.

LastPass presence is managed; credentials are not. A fresh browser or machine still needs
one interactive LastPass login with MFA or a passkey. Passwords, local extension storage
and website sessions are never read, copied or deployed.

Browsers are Brewfile-managed, so this role never installs or uninstalls one, and never
uses `--zap`.

## Privilege escalation

Root-owned policy files are installed by `sudo -n` against one root-owned
helper, `/usr/local/libexec/macbook-pro/install-managed-preference`, granted by
`/etc/sudoers.d/macbook-pro-browsers`. Run `make browsers-authorize` once per
machine to install both; every apply after that is non-interactive, and the
capture service can install policy without a GUI session.

The sudoers rule deliberately contains no wildcards — wildcard command
arguments are a known escalation route. The helper enforces the argument space
itself: one flag plus a domain from a fixed allowlist, with every path baked in
at render time. It refuses an unknown domain, a missing or symlinked staged
file, a staged file owned by another account, a file that is not a valid plist,
and a target directory that is not root-owned. It is `/bin/sh` plus `plutil` on
purpose, so nothing root runs depends on an interpreter inside a user-writable
repository.

The smoke suite uses the same helper. It saves the live policy, installs a
fixture through `--install`, runs its probe, then puts the original bytes back
(or `--remove`s the file if there was none) and checks the result is
byte-identical. No root process outlives a single call, and the whole matrix
runs unattended — it previously needed an administrator dialog per browser and
would stall indefinitely if nobody answered.

`browsers_escalation` selects the mechanism: `auto` (helper when authorized,
dialog otherwise), `sudo` (require the helper, fail rather than prompt) or
`dialog`. The dialog path now carries `browsers_escalation_timeout`, because an
unanswered prompt used to stall a play until something else killed it — which
once left a browser half-configured.

## One description of the fleet

`host_files/localhost/browsers/manifest.yml` describes each browser once:
catalog name, label, engine, application and executable, profile directory, and
its policy contract. The role defaults derive `browsers_catalog_names`,
`browsers_chromium_adapters`, the Firefox policy domain and
`browsers_generated_paths` from it; the Python package derives `BROWSERS`, the
Chromium profile map, the capability application records and the smoke's page
map from the same file. `validate-browser-catalog.py --all` fails if the
manifest and the catalog directories disagree.

These facts previously lived in about eight places, so adding a browser was an
eight-file change that failed silently if one was missed — the browser simply
went unmanaged. The cleanup role kept its own hand-written copy of the
generated paths, which had already drifted: it missed Firefox's managed
preference in both locations.

## Where the code lives

The implementation is a package under `lib/browsers/`; `scripts/` holds a thin
entry point per command, so every existing invocation — Makefile targets, this
role, the launchd job, CI — is unchanged. The entry point puts `lib/` on
`sys.path` relative to itself, deliberately: the publishing automation runs the
*isolated clone's* copy of the code, and an installed package would have
resolved back to the main checkout instead.

Before this, the files were hyphenated scripts that cannot be imported, so six
of them carried a private copy of an `importlib` loader. That loader also gave
one file two module identities — `browser-snapshot.py` was loaded as both
`browser_snapshot` and `browser_snapshot_cleanup`, so a single process held two
copies with separate state. The browser list, the profile map and the repository
root were each defined in several places; they are defined once now, in
`browsers/__init__.py`.

## One interpreter, declared

`browsers_python` in the role defaults names the interpreter every
non-interactive entry point uses, and it is rendered into both the capture
runner and the launchd job. `python3` from `PATH` is not a contract: this
machine carries four (repo venv 3.13, pyenv 3.10, Homebrew 3.14, `/usr/bin`
3.9) and only the venv has the dependencies these scripts import. The service
was resolving to a different one than every test, so it could never have run.

Three guards keep it that way. The role fails an apply when the pinned
interpreter cannot import `yaml` or is older than `browsers_python_minimum`.
The runner repeats that preflight and exits 78 (`EX_CONFIG`) before touching a
browser. `browser-git-automation.py --run` takes `--python` and refuses an
interpreter that fails the same probe, so the capture child process can never
re-derive a different one from `sys.executable`.

## Publishing captured additions

`scripts/browser-git-automation.py` owns the Git side. `--check` audits the contract with
no network and no clone; `--run` publishes, and refuses to do anything live unless the
activated service passes `BROWSER_AUTOMATION_AUTHORIZED=1`. Every run works in
`~/.local/state/macbook-pro/browser-automation/repo`, never this checkout, and stops on a
non-private repository, dirty or diverged clone, non-fast-forward, push conflict, a
changed path outside the five bookmark catalogs, more than one open automation pull
request, or a force push. Additions stack on one `automation/browser-catalog` pull request
with auto-merge by merge commit; a merged branch restarts from `main`.

Every git call goes through one helper that sets `GIT_TERMINAL_PROMPT=0` and
refuses force flags. The clone used to bypass it — and the clone is the first
thing that runs under launchd, where a credential prompt has no terminal to
answer it and would block until the timeout.

Before committing, the automation runs the repository's own secret gate over
the staged paths. The commit still carries `--no-verify`, but only because a
throwaway clone has no hooks installed; the check it would have skipped now
happens explicitly, so the one commit path that runs unattended is no longer
the only one exempt from it.

The `com.dkelly.browser-capture` launchd job is installed disabled and polls about every
15 minutes by interval rather than watching paths, so it never fires mid-write. Activation
happens separately, after this code is on `main`.

`scripts/browser-automation-smoke.py --fake --no-network` exercises every stop condition
against synthetic catalogs and local fake remotes, and reads the installed launchd job to
confirm it is present, disabled and unloaded.

Run `make validate-browser-catalog`, `make browser-test RUN_ARGS='--fixtures --isolated'`,
and `make check RUN_ARGS='--tags browsers'`.
