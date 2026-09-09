# Browser capability spike

Date: 2026-09-09
Scope: installed macOS browsers; isolated profiles only
Privacy gate: GitHub repository confirmed private before this work (`isPrivate=true`).

## Method

Capability smoke launched each installed browser against a fresh temporary profile.
Temporary paths were printed before being moved to recoverable Trash. No live profile,
bookmark content, extension identifier, account data, credential store, cookie store,
session store, preference database, or extension storage was opened. Inventory values
below are counts from the pre-B0 sanitized baseline; evidence markers identify that
planning source rather than browser files.

A controlled administrator-authorized test temporarily created only the three allowlisted
Chromium policy plists. Chrome and Brave used the login-scoped managed-preference path;
Edge was tested experimentally at both login and machine scope. Each run restored the complete managed
preference tree to its prior absent state before Firefox or Vivaldi launched. Created
objects remain recoverable in root-owned Trash directories.

Primary vendor references consulted: Chrome Enterprise policy list and managed bookmarks
guidance; Microsoft Edge policy reference and managed favorites guidance; Brave Group
Policy guidance; Mozilla Firefox administrator policy templates; Vivaldi Sync guidance.

## Capability matrix

| Browser | Installed build | Policy page smoke | Non-MDM local evidence | Bookmark policy | Extension policy | Result |
|---|---|---|---|---|---|---|
| Chrome | 152.0.7977.83 | observed internal policy page | fake managed bookmark and nonrestrictive extension policy both valid at mandatory level | `ManagedBookmarks` | `ExtensionSettings`, `ExtensionInstallForcelist` | accepted through temporary login-scoped managed preference |
| Edge | 152.0.4191.66 | observed internal React policy table | fake managed favorite and nonrestrictive extension policy both valid at mandatory level | `ManagedFavorites` | `ExtensionSettings`, `ExtensionInstallForcelist` | accepted through temporary login-scoped managed preference |
| Brave | 152.1.94.117 | observed internal policy page through its Chromium alias | fake managed bookmark and nonrestrictive extension policy both valid at mandatory level | `ManagedBookmarks` | `ExtensionSettings`, `ExtensionInstallForcelist` | accepted through temporary login-scoped managed preference |
| Firefox | 155.0.1 | observed isolated `about:policies` screenshot | fake policy key observed in temporary app-copy distribution policy | `ManagedBookmarks` | `ExtensionSettings` | accepted for app-bundle distribution path; cask restore required |
| Vivaldi | 8.2.4133.47 | isolated internal-page launch observed | enterprise policy unsupported-unverified | best-effort audit/export | best-effort audit/export | unsupported-unverified; evidence gate remains open |

Chrome, Edge and Brave accepted both required fake policy types through temporary local
managed preferences. Edge uses a React ARIA table rather than Chromium's shadow-DOM
policy elements. Earlier zero-row results were extraction failures, not proof of policy
rejection. The corrected adapter matches exact policy-name cells and reads only the
separate status and level cells; payload text cannot produce a false positive. Brave
resolves its internal page through the Chromium alias.

Mandatory policy remains distinct from recommended defaults. Firefox distribution policy
was observed in a temporary app copy; device-management behavior was not assumed.
Vivaldi isolated launch and enterprise support remain separate; policy is unsupported.

Final full smoke exited 0. All temporary system policy paths were restored to absent.
The helper refuses pre-existing managed-policy trees, so this spike is not a production
policy installer. One local administrator dialog authorizes each bounded test; passwords
never enter the script. Historical inventory is retained below without invented hashes.

## Sanitized inventory

| Browser | Profile label | Historical bookmark count | Enabled-state count | System-component count | User-extension candidates | Evidence marker |
|---|---|---:|---:|---:|---:|---|
| Chrome | default | 97 | 0 | 0 | 0 | sanitized-baseline |
| Edge | default | 532 | 0 | 0 | 0 | sanitized-baseline |
| Brave | default | 0 | 0 | 0 | 0 | sanitized-baseline |
| Firefox | default-release | 16 | 0 | 0 | 0 | sanitized-baseline |
| Vivaldi | default | 31 | 0 | 0 | 0 | sanitized-baseline |

Historical counts from approved pre-B0 planning baseline only; no live snapshot was taken
for this report. No title, URL, account, extension ID, or profile-state material is present.

## Duplicate experiment

B0/B1 uses fake records only; concrete fake URLs live in capability fixtures, never in
this research note. Compare normalized browser, folder, title and URL fingerprints in
isolated profiles. Measure whether managed-folder restore
creates an acceptable duplicate beside ordinary bookmarks. No real bookmark is captured
until B1 schema/validator gates pass. If duplicate UX is unacceptable, stop for user
choice; custom extension/native-host work is outside baseline.

## Decision

B0 live capability gate passes. Proceed to B1 schema, fixtures, snapshot validation and
managed-folder duplicate experiment. Chrome, Edge and Brave have proven local mandatory
bookmark and extension-policy acceptance. Firefox uses the proven app-copy distribution
path. Vivaldi remains best-effort audit/export plus one-time interactive Sync login.
Actual bookmark-folder UI behavior and Firefox bookmark/extension fixtures remain B1
and adapter-ticket acceptance work; this spike does not claim those later checks passed.
