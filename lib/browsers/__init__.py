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

CATALOG_ROOT = REPO / "host_files" / "localhost" / "browsers"
MANIFEST_PATH = CATALOG_ROOT / "manifest.yml"
STATE_ROOT = Path.home() / ".local" / "state" / "dotforge"
POLICY_STATE = STATE_ROOT / "browser-policy"

APPLICATION_SUPPORT = Path.home() / "Library" / "Application Support"


def _load_manifest() -> list[dict[str, object]]:
    """Read the fleet description that Ansible reads from the same file."""
    import yaml  # local: keeps the package importable for callers without it

    document = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or document.get("version") != 1:
        raise RuntimeError("browser manifest version is unsupported")
    entries = document.get("browsers")
    if not isinstance(entries, list) or not entries:
        raise RuntimeError("browser manifest lists no browsers")
    return entries


MANIFEST = _load_manifest()

# Catalog names, in manifest order.
BROWSERS = tuple(str(entry["catalog"]) for entry in MANIFEST)

# Chromium profile directories relative to ~/Library/Application Support.
CHROMIUM_PROFILES = {
    str(entry["catalog"]): str(entry["profile"])
    for entry in MANIFEST
    if entry["engine"] == "chromium"
}


def manifest_for(catalog: str) -> dict[str, object]:
    for entry in MANIFEST:
        if entry["catalog"] == catalog:
            return entry
    raise KeyError(f"no manifest entry for browser {catalog}")


def managed(engine: str | None = None) -> list[dict[str, object]]:
    """Browsers with a proven policy contract, optionally filtered by engine."""
    return [
        entry
        for entry in MANIFEST
        if entry["policy"]["support"] == "managed_preference"
        and (engine is None or entry["engine"] == engine)
    ]
