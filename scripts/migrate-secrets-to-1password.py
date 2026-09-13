#!/usr/bin/env python3
"""Move this repository's vault-encrypted secrets into 1Password.

One-off migration, run once by hand from the repo root with the venv active.
Inputs are read from the working tree, or from git history once the encrypted
files have been deleted from the repository, so it can run at any point:

    venv/bin/python scripts/migrate-secrets-to-1password.py --dry-run
    venv/bin/python scripts/migrate-secrets-to-1password.py

What it creates in the 1Password vault (default: `dotforge`):

    ansible-vault           Password        password    the Ansible Vault password
    linear-api-key          API Credential  credential  vault.yml linear_api_key
    todoist-api-key         API Credential  credential  vault.yml todoist_api_key
    grafana-service-account API Credential  credential  vault.yml grafana_service_account_token
                                            url         vault.yml grafana_url
    mcp-gateway-sunrise     API Credential  credential  vault.yml mcp_gateway_sunrise_token
    id_ed25519              SSH Key         private key host_files/localhost/id_ed25519
    id_rsa                  SSH Key         private key host_files/localhost/id_rsa

Those are exactly the secret references the playbook reads back
(`op://dotforge/<item>/<field>`), so the names are a contract, not a taste.

Safety: secret values travel from ansible-vault plaintext to `op item create`
over stdin as a JSON template and are never printed, never put on a command
line, and never written to disk. An item that already exists is left alone, so
the script is safe to re-run. `vault_vault_pass` (the vault password stored
inside the vault it protects) is dead and deliberately not migrated.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
VAULT_YML = "host_vars/localhost/vault.yml"
SSH_KEYS = ("id_ed25519", "id_rsa")

# vault.yml key -> (item title, note shown on the item)
CREDENTIALS = {
    "linear_api_key": ("linear-api-key", "Linear personal API key"),
    "todoist_api_key": ("todoist-api-key", "Todoist API token"),
    "grafana_service_account_token": ("grafana-service-account", "Grafana service account token"),
    "mcp_gateway_sunrise_token": ("mcp-gateway-sunrise", "Bearer token for the local sunrise MCP gateway"),
}


def op(*args: str, stdin: str | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    # stdin is the JSON template or nothing at all: with the app integration
    # off, `op` offers to add an account and waits on an inherited terminal.
    return subprocess.run(
        ["op", *args],
        input=stdin,
        stdin=None if stdin is not None else subprocess.DEVNULL,
        capture_output=True,
        text=True,
        check=check,
    )


def preflight() -> None:
    try:
        op("--version")
    except FileNotFoundError:
        sys.exit("op not found: brew install --cask 1password-cli (make packages installs it)")
    who = op("whoami", check=False)
    if who.returncode != 0:
        sys.exit(
            "op is not signed in. In 1Password: Settings > Developer > "
            "'Integrate with 1Password CLI', then run `op vault list` once."
        )


def vault_password() -> bytes:
    result = subprocess.run([str(REPO / "scripts" / "vault-pass")], capture_output=True, check=True)
    return result.stdout.strip(b"\r\n")


def ciphertext(relative: str) -> bytes | None:
    """The vault-encrypted file, from the working tree or, once it has been
    deleted from the repository, from the last commit that still carried it."""
    path = REPO / relative
    if path.is_file():
        return path.read_bytes()
    deleted_in = subprocess.run(
        ["git", "-C", str(REPO), "rev-list", "-n", "1", "HEAD", "--", relative],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    if not deleted_in:
        return None
    shown = subprocess.run(
        ["git", "-C", str(REPO), "show", f"{deleted_in}^:{relative}"],
        capture_output=True, check=False,
    )
    return shown.stdout if shown.returncode == 0 else None


def decrypt(data: bytes, password: bytes) -> str:
    from ansible.parsing.vault import VaultLib, VaultSecret

    lib = VaultLib([("default", VaultSecret(password))])
    return lib.decrypt(data).decode("utf-8")


def ensure_vault(name: str, dry_run: bool) -> None:
    if op("vault", "get", name, check=False).returncode == 0:
        print(f"vault {name}: exists")
        return
    if dry_run:
        print(f"vault {name}: would create")
        return
    op("vault", "create", name)
    print(f"vault {name}: created")


def item_exists(vault: str, title: str) -> bool:
    # A listing, not `op item get <title>`: that errors when two items share a
    # title, which would read as "absent" and create a third.
    listing = json.loads(op("item", "list", "--vault", vault, "--format", "json").stdout or "[]")
    return any(item.get("title") == title for item in listing)


def create_item(vault: str, template: dict, dry_run: bool) -> None:
    title = template["title"]
    if item_exists(vault, title):
        print(f"item {title}: exists, skipped")
        return
    if dry_run:
        print(f"item {title}: would create ({template['category']})")
        return
    # `-` reads the JSON template from stdin, so no value touches argv.
    op("item", "create", "--vault", vault, "-", stdin=json.dumps(template))
    print(f"item {title}: created")


def password_item(password: bytes) -> dict:
    return {
        "title": "ansible-vault",
        "category": "PASSWORD",
        "fields": [
            {"id": "password", "type": "CONCEALED", "purpose": "PASSWORD", "label": "password",
             "value": password.decode("utf-8")},
            {"id": "notesPlain", "type": "STRING", "purpose": "NOTES", "label": "notesPlain",
             "value": "Ansible Vault password for Edition-X/dotforge. Read by scripts/vault-pass."},
        ],
    }


def credential_item(title: str, note: str, credential: str, url: str | None = None) -> dict:
    fields = [
        {"id": "credential", "type": "CONCEALED", "label": "credential", "value": credential},
        {"id": "notesPlain", "type": "STRING", "purpose": "NOTES", "label": "notesPlain",
         "value": f"{note}. Read by dotforge at apply time."},
    ]
    if url is not None:
        fields.append({"id": "url", "type": "URL", "label": "url", "value": url})
    return {"title": title, "category": "API_CREDENTIAL", "fields": fields}


def ssh_key_item(title: str, private_key: str) -> dict:
    return {
        "title": title,
        "category": "SSH_KEY",
        "fields": [
            {"id": "private_key", "type": "SSHKEY", "label": "private key", "value": private_key},
            {"id": "notesPlain", "type": "STRING", "purpose": "NOTES", "label": "notesPlain",
             "value": f"Imported from dotforge host_files/localhost/{title}. Served by the 1Password SSH agent."},
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--vault", default="dotforge", help="1Password vault to create items in")
    parser.add_argument("--dry-run", action="store_true", help="report what would be created, create nothing")
    parser.add_argument("--skip-ssh", action="store_true", help="leave the SSH keys out")
    args = parser.parse_args()

    preflight()
    password = vault_password()
    ensure_vault(args.vault, args.dry_run)

    create_item(args.vault, password_item(password), args.dry_run)

    vault_yml = ciphertext(VAULT_YML)
    if vault_yml is None:
        sys.exit(f"{VAULT_YML} is neither in the working tree nor in git history")
    secrets = yaml.safe_load(decrypt(vault_yml, password))
    grafana_url = secrets.get("grafana_url")
    for key, (title, note) in CREDENTIALS.items():
        if key not in secrets:
            print(f"item {title}: {key} not in vault.yml, skipped")
            continue
        url = grafana_url if key == "grafana_service_account_token" else None
        create_item(args.vault, credential_item(title, note, str(secrets[key]), url), args.dry_run)

    if not args.skip_ssh:
        for name in SSH_KEYS:
            data = ciphertext(f"host_files/localhost/{name}")
            if data is None:
                print(f"item {name}: host_files/localhost/{name} missing, skipped")
                continue
            create_item(args.vault, ssh_key_item(name, decrypt(data, password)), args.dry_run)

    print("done" if not args.dry_run else "dry run complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
