# Browser capability spike

Date: 2026-09-08
Scope: installed macOS browsers; isolated profiles only
Privacy gate: GitHub repository confirmed private before this work (`isPrivate=true`).

## Method

Capability smoke launched each installed browser against a fresh temporary profile.
Temporary paths were printed before being moved to recoverable Trash. No live profile,
bookmark content, extension identifier, account data, credential store, cookie store,
session store, preference database, or extension storage was opened. Inventory values
below are counts from the pre-B0 sanitized baseline; hashes identify sanitized records,
not browser files.

Primary vendor references consulted: Chrome Enterprise policy list and managed bookmarks
guidance; Microsoft Edge policy reference and managed favorites guidance; Brave Group
Policy guidance; Mozilla Firefox administrator policy templates; Vivaldi Sync guidance.

## Capability matrix

| Browser | Installed build | Policy page smoke | Non-MDM local evidence | Bookmark policy | Extension policy | Result |
|---|---|---|---|---|---|---|
| Chrome | 152.0.7977.82 | isolated page launch/read-only probe | user plist readable; policy payload not installed by B0 | `ManagedBookmarks` | `ExtensionSettings`, `ExtensionInstallForcelist` | documented local mechanism; policy rendering needs B2 |
| Edge | 152.0.4191.66 | isolated page launch/read-only probe | user plist absent; policy payload not installed by B0 | `ManagedFavorites` | `ExtensionSettings`, `ExtensionInstallForcelist` | documented local mechanism; policy rendering needs B3 |
| Brave | 151.1.93.136 | isolated page launch/read-only probe | user plist readable; policy payload not installed by B0 | `ManagedBookmarks` | `ExtensionSettings`, `ExtensionInstallForcelist` | documented local mechanism; policy rendering needs B3 |
| Firefox | 155.0.1 | isolated `about:policies` launch/read-only probe | app-bundle distribution policy documented | `ManagedBookmarks` | `ExtensionSettings` | supported distribution path; cask restore required |
| Vivaldi | 8.2.4133.47 | isolated `vivaldi://policy` probe | no verified official enterprise contract | best-effort audit/export | best-effort audit/export | unsupported-unverified; evidence gate remains open |

Chrome, Edge and Brave local plist support is documented by vendors, but no policy was
installed during B0. Mandatory policy must remain distinct from recommended defaults.
Firefox distribution policy is supported by Mozilla documentation and can be restored
after a cask update; MDM/configuration-profile behavior was not assumed. Vivaldi policy
support was not inferred from Chromium and is not verified.

## Sanitized inventory

| Browser | Profile label | Bookmark count | Enabled-state count | System-component count | User-extension candidates | Snapshot hash |
|---|---|---:|---:|---:|---:|---|
| Chrome | default | 97 | 0 | 0 | 0 | sanitized-baseline |
| Edge | default | 532 | 0 | 0 | 0 | sanitized-baseline |
| Brave | default | 0 | 0 | 0 | 0 | sanitized-baseline |
| Firefox | default-release | 16 | 0 | 0 | 0 | sanitized-baseline |
| Vivaldi | default | 31 | 0 | 0 | 0 | sanitized-baseline |

Counts only. No title, URL, account, extension ID, or profile-state material is present.

## Duplicate experiment

B0/B1 uses fake records only; concrete fake URLs live in capability fixtures, never in
this research note. Compare normalized browser, folder, title and URL fingerprints in
isolated profiles. Measure whether managed-folder restore
creates an acceptable duplicate beside ordinary bookmarks. No real bookmark is captured
until B1 schema/validator gates pass. If duplicate UX is unacceptable, stop for user
choice; custom extension/native-host work is outside baseline.

## Decision

Proceed with separate Chrome, Edge, Brave and Firefox policy adapters using only evidence
above. Keep Vivaldi best-effort audit/export plus one-time interactive Sync login path;
do not claim managed policy until a later installed-build test proves it live.
