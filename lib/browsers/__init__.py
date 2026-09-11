"""Browser catalog management: capture, policy, publishing and their checks.

These modules used to be hyphenated scripts under `scripts/`, which cannot be
imported, so six of them carried a private copy of an `importlib` loader to
reach each other. That loader also gave the same file two module identities —
`browser-snapshot.py` was loaded as both `browser_snapshot` and
`browser_snapshot_cleanup`, so one process held two copies with separate state.

They are a package now. `scripts/` keeps a thin entry point per command so
every existing invocation — Makefile targets, the browsers role, the launchd
job, CI — still works unchanged, and the entry point adds this directory to
`sys.path` relative to itself. That relative resolution matters: the publishing
automation deliberately runs the *isolated clone's* copy of the code, and an
installed package would have silently resolved back to the main checkout.
"""

from __future__ import annotations

from pathlib import Path

# The repository this package was loaded from, which is not necessarily the
# one the user is sitting in.
REPO = Path(__file__).resolve().parent.parent.parent

# One list, consumed by every module here. The Ansible side reads the same
# names from the role's browsers_catalog_names.
BROWSERS = ("chrome", "edge", "brave", "firefox", "vivaldi")

CATALOG_ROOT = REPO / "host_files" / "localhost" / "browsers"
STATE_ROOT = Path.home() / ".local" / "state" / "macbook-pro"
POLICY_STATE = STATE_ROOT / "browser-policy"

# Profile directories relative to ~/Library/Application Support.
CHROMIUM_PROFILES = {
    "chrome": "Google/Chrome/Default",
    "edge": "Microsoft Edge/Default",
    "brave": "BraveSoftware/Brave-Browser/Default",
    "vivaldi": "Vivaldi/Default",
}
