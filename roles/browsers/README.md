# Browser role

This role owns declarative, browser-specific catalogs. B1 validates source only; it does
not install policy or touch browser profiles. Chrome, Edge, Brave, Firefox and Vivaldi
remain separate ownership roots. Missing records never mean delete, move or rename.

Chrome, Edge and Brave use mandatory managed preferences. Firefox uses its supported
distribution policy. Vivaldi remains best-effort because its installed build has not
proved a vendor enterprise-policy contract; its role installs only a sanitized read-only
audit/export check.

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

## Publishing captured additions

`scripts/browser-git-automation.py` owns the Git side. `--check` audits the contract with
no network and no clone; `--run` publishes, and refuses to do anything live unless the
activated service passes `BROWSER_AUTOMATION_AUTHORIZED=1`. Every run works in
`~/.local/state/macbook-pro/browser-automation/repo`, never this checkout, and stops on a
non-private repository, dirty or diverged clone, non-fast-forward, push conflict, a
changed path outside the five bookmark catalogs, more than one open automation pull
request, or a force push. Additions stack on one `automation/browser-catalog` pull request
with auto-merge by merge commit; a merged branch restarts from `main`.

The `com.dkelly.browser-capture` launchd job is installed disabled and polls about every
15 minutes by interval rather than watching paths, so it never fires mid-write. Activation
happens separately, after this code is on `main`.

`scripts/browser-automation-smoke.py --fake --no-network` exercises every stop condition
against synthetic catalogs and local fake remotes, and reads the installed launchd job to
confirm it is present, disabled and unloaded.

Run `make validate-browser-catalog`, `make browser-test RUN_ARGS='--fixtures --isolated'`,
and `make check RUN_ARGS='--tags browsers'`.
