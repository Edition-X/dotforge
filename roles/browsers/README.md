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

Generated policy files arrive in B2-B5. Cleanup must remove only exact paths listed in
`browsers_generated_paths`; it must never remove profiles, catalogs, login state or browser
data. Capture remains disabled until B6.

Run `make validate-browser-catalog`, `make browser-test RUN_ARGS='--fixtures --isolated'`,
and `make check RUN_ARGS='--tags browsers'`.
