# Browser role

This role owns declarative, browser-specific catalogs. B1 validates source only; it does
not install policy or touch browser profiles. Chrome, Edge, Brave, Firefox and Vivaldi
remain separate ownership roots. Missing records never mean delete, move or rename.

Generated policy files arrive in B2-B5. Cleanup must remove only exact paths listed in
`browsers_generated_paths`; it must never remove profiles, catalogs, login state or browser
data. Capture remains disabled until B6.

Run `make validate-browser-catalog`, `make browser-test RUN_ARGS='--fixtures --isolated'`,
and `make check RUN_ARGS='--tags browsers'`.
