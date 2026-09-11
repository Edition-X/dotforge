## What changed

<!-- One or two sentences. What does this make true that was not true before? -->

## Why

<!-- The problem, not the patch. If it fixes something broken, say how it broke. -->

## Verification

<!-- What you ran, and what it showed. "make ci" alone is rarely enough for a
     change that touches this machine's configuration — say whether you applied
     it, whether a second apply reported changed=0, and which evidence needs
     real browsers or a GUI session and therefore cannot run in CI. -->

- [ ] `make ci`
- [ ] `make check` reviewed, then `make apply`
- [ ] Second apply reports `changed=0`
- [ ] Browser evidence, if touched: `make browser-test RUN_ARGS='--all-installed --isolated --policy --extensions --capture-read-only'`

## Risk and rollback

<!-- What could this break on a machine that is not this one, and how would you
     put it back? Note anything needing `make browsers-authorize` or a vault
     password. -->
