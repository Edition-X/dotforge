#!/usr/bin/env python3
"""Refuse commits that put a plaintext secret into the repository.

Two checks, both structural rather than textual:

1. Paths that are meaningless unless vault-encrypted really are encrypted.
2. No YAML mapping key whose name means "credential" carries a literal value.

The second replaces four hand-rolled regexes that required the value to be
quoted, covered three key names, and only examined YAML through `grep`. They
reported a clean tree for a file holding `password: hunter2`, a quoted
AWS-shaped `api_key` and `vault_pass: swordfish`, and then printed a green
tick. Entropy scanners do not catch those either — `hunter2` is a dictionary
word and the canonical `AKIA...EXAMPLE` key is in gitleaks' own stopword
allowlist — so gitleaks runs alongside this for provider-shaped and
high-entropy secrets, and this owns the structural rule.

The rule this encodes is the repository's actual convention: every secret lives
in `host_vars/<host>/vault.yml` and is referenced indirectly, so a
credential-shaped key should never hold a literal. A value containing `{{` is a
reference and passes; anything else under such a key is a finding.

Values are never printed — only the file, the key path and the key name.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

import yaml

VAULT_MARKER = "$ANSIBLE_VAULT"

# Paths that are meaningless unless encrypted.
MUST_ENCRYPT = (
    re.compile(r"^host_files/[^/]+/id_rsa$"),
    re.compile(r"^host_files/[^/]+/id_ed25519$"),
    re.compile(r"^host_files/[^/]+/vault_pass\.txt$"),
    re.compile(r"^host_vars/[^/]+/vault\.yml$"),
    # Personal bookmark URLs. The repository is public; these are not.
    re.compile(r"^host_files/[^/]+/browsers/[^/]+/bookmarks\.yml$"),
    # Work skills that name an employer's customers, sites and hosts.
    re.compile(r"^host_files/[^/]+/ai/skills/(?:sunrise-cells|sunrise-devcontainer-rollout)/SKILL\.md$"),
    # The SSH client config names an employer's fleet domain and host patterns.
    # ansible.builtin.template decrypts a vault-encrypted template on the way.
    re.compile(r"^roles/ssh/templates/config\.j2$"),
)

# Key names that mean "this is a credential".
CREDENTIAL_KEY = re.compile(
    r"(?:^|[_.-])(?:pass|passwd|password|secret|secrets|token|apikey|credential|credentials"
    r"|privatekey|bearer|auth)(?:$|[_.-])"
    r"|api[_.-]?key",
    re.IGNORECASE,
)

# Key names that merely *locate* or *describe* a credential rather than being
# one: a path, a URL, a file name, an owning user, a boolean toggle.
LOCATION_KEY = re.compile(
    r"(?:_file|_path|_dir|_url|_uri|_name|_user|_users|_id|_enabled|_disabled|_scope|_mode"
    r"|_command|_args|_env)$",
    re.IGNORECASE,
)

# Vendored third-party trees, matching the lint exclusions.
SKIP_PREFIXES = (
    "collections/",
    "node_modules/",
    "venv/",
    "host_files/localhost/nvim/autoload/plugged/",
    "host_files/localhost/nvim/pack/github/start/copilot.vim/",
    "host_files/localhost/ai/skills/",
)


def staged_paths() -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--cached", "-z", "--name-only", "--diff-filter=ACMR"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [path for path in result.stdout.split("\0") if path]


def tracked_paths() -> list[str]:
    result = subprocess.run(["git", "ls-files", "-z"], capture_output=True, text=True, check=True)
    return [path for path in result.stdout.split("\0") if path]


def read_blob(path: str, staged: bool) -> str | None:
    """Read the staged blob, so staging clean then dirtying cannot slip past."""
    if staged:
        result = subprocess.run(["git", "show", f":{path}"], capture_output=True, text=True)
        return result.stdout if result.returncode == 0 else None
    try:
        return Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def is_encrypted(content: str) -> bool:
    return content.startswith(VAULT_MARKER)


def literal_findings(document: object, trail: tuple[str, ...] = ()) -> list[str]:
    """Report credential-shaped keys whose value is a literal, not a reference."""
    findings: list[str] = []
    if isinstance(document, dict):
        for key, value in document.items():
            name = str(key)
            path = (*trail, name)
            if isinstance(value, (dict, list)):
                findings.extend(literal_findings(value, path))
                continue
            if not CREDENTIAL_KEY.search(name) or LOCATION_KEY.search(name):
                continue
            if value is None or isinstance(value, bool):
                continue
            text = str(value)
            # A reference to a vault variable or any other computed value is the
            # convention this repository follows.
            if "{{" in text or not text.strip():
                continue
            findings.append(".".join(path))
    elif isinstance(document, list):
        for index, value in enumerate(document):
            findings.extend(literal_findings(value, (*trail, str(index))))
    return findings


def check(paths: list[str], staged: bool) -> int:
    encrypted_checked = 0
    yaml_checked = 0
    failures = 0

    for path in paths:
        # Must-encrypt wins over the vendored-tree skip: an encrypted skill
        # lives under a skipped prefix, and skipping it would silently accept
        # the plaintext version too.
        if not any(pattern.match(path) for pattern in MUST_ENCRYPT) and path.startswith(SKIP_PREFIXES):
            continue

        for pattern in MUST_ENCRYPT:
            if pattern.match(path):
                encrypted_checked += 1
                content = read_blob(path, staged)
                if content is None:
                    print(f"❌ {path} could not be read.")
                    failures += 1
                elif not is_encrypted(content):
                    print(f"❌ {path} must be vault-encrypted but is not.")
                    print(f"   ansible-vault encrypt {path}")
                    failures += 1
                break
        else:
            if not path.endswith((".yml", ".yaml")):
                continue
            content = read_blob(path, staged)
            if content is None or is_encrypted(content):
                continue
            try:
                documents = list(yaml.safe_load_all(content))
            except yaml.YAMLError:
                # Malformed YAML is check-yaml's problem, not this hook's.
                continue
            yaml_checked += 1
            for document in documents:
                for key_path in literal_findings(document):
                    print(f"❌ {path}: `{key_path}` holds a literal value under a credential-shaped key.")
                    print("   Move it into host_vars/<host>/vault.yml and reference it as {{ vault_… }}.")
                    failures += 1

    if failures:
        return 1
    print(
        f"✅ secrets: must-encrypt paths={encrypted_checked} yaml-inspected={yaml_checked} "
        "literal-credentials=0"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="scan every tracked file, not just staged")
    parser.add_argument("paths", nargs="*", help="explicit paths (pre-commit passes these)")
    arguments = parser.parse_args()
    if arguments.all:
        return check(tracked_paths(), staged=False)
    if arguments.paths:
        return check(list(arguments.paths), staged=False)
    return check(staged_paths(), staged=True)


if __name__ == "__main__":
    sys.exit(main())
