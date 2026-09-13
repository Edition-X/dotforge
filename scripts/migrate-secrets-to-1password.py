#!/usr/bin/env python3
"""Move this repository's vault-encrypted secrets into 1Password.

One-off migration, run once by hand from the repo root with the venv active:

    venv/bin/python scripts/migrate-secrets-to-1password.py --dry-run
    venv/bin/python scripts/migrate-secrets-to-1password.py

What it creates in the 1Password vault (default: `dotforge`):

    ansible-vault           Password        password    the Ansible Vault password
    linear-api-key          API Credential  credential  vault.yml linear_api_key
    todoist-api-key         API Credential  credential  vault.yml todoist_api_key
    grafana-service-account API Credential  credential  vault.yml grafana_service_account_token
                                            url         vault.yml grafana_url
    mcp-gateway-sunrise     API Credential  credential  vault.yml mcp_gateway_sunrise_token

Those are exactly the secret references the playbook reads back
(`op://dotforge/<item>/<field>`), so the names are a contract, not a taste.

The two SSH private keys (host_files/localhost/id_ed25519, id_rsa) are not
created through the CLI: every CLI path (JSON template, field assignment,
OpenSSH or PKCS#8 text) stores an SSH Key item that 1Password cannot read back
(`"private_key" isn't a field`), and the SSH agent would not serve it. They are
decrypted into a mode-0700 directory instead, for the app's own importer
(New Item > SSH Key > Add Private Key > Import a Key File); trash that
directory afterwards.

Safety: secret values travel from ansible-vault plaintext to `op item create`
over stdin as a JSON template and are never printed or put on a command line.
An item that already exists is left alone, so the script is safe to re-run.
`vault_vault_pass` (the vault password stored inside the vault it protects) is
dead and deliberately not migrated.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
VAULT_YML = REPO / "host_vars" / "localhost" / "vault.yml"
SSH_KEYS = ("id_ed25519", "id_rsa")

# vault.yml key -> (item title, note shown on the item)
CREDENTIALS = {
    "linear_api_key": ("linear-api-key", "Linear personal API key"),
    "todoist_api_key": ("todoist-api-key", "Todoist API token"),
    "grafana_service_account_token": ("grafana-service-account", "Grafana service account token"),
    "mcp_gateway_sunrise_token": ("mcp-gateway-sunrise", "Bearer token for the local sunrise MCP gateway"),
}


ACCOUNT = "my.1password.com"


def op(*args: str, stdin: str | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    # stdin is the JSON template or nothing at all: with the app integration
    # off, `op` offers to add an account and waits on an inherited terminal.
    # The account is always explicit: the CLI sees two, and everything the
    # playbook reads back names the same one.
    return subprocess.run(
        ["op", "--account", ACCOUNT, *args],
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
    # `op whoami` reports "not signed in" under the app integration even when
    # every other command works; the account listing is the reliable probe.
    accounts = op("account", "list", "--format", "json", check=False)
    if accounts.returncode != 0 or not accounts.stdout.strip():
        sys.exit(
            "op has no account. In 1Password: Settings > Developer > "
            "'Integrate with 1Password CLI', then run `op vault list` once."
        )


def vault_password() -> bytes:
    result = subprocess.run([str(REPO / "scripts" / "vault-pass")], capture_output=True, check=True)
    return result.stdout.strip(b"\r\n")


def decrypt(path: Path, password: bytes) -> str:
    from ansible.parsing.vault import VaultLib, VaultSecret

    lib = VaultLib([("default", VaultSecret(password))])
    return lib.decrypt(path.read_bytes()).decode("utf-8")


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
    # title, which would read as "absent" and create a third. A vault that does
    # not exist yet (a dry run before the first real run) holds nothing.
    result = op("item", "list", "--vault", vault, "--format", "json", check=False)
    if result.returncode != 0:
        return False
    listing = json.loads(result.stdout or "[]")
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


def stage_ssh_key(export_dir: Path, name: str, private_key: str, dry_run: bool) -> None:
    """Write one decrypted key, mode 0600 in a 0700 directory, for the app importer."""
    target = export_dir / name
    if dry_run:
        print(f"ssh key {name}: would write {target}")
        return
    export_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(export_dir, 0o700)
    with open(os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w", encoding="utf-8") as stream:
        stream.write(private_key)
    print(f"ssh key {name}: written to {target}")


def main() -> int:
    global ACCOUNT
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--vault", default="dotforge", help="1Password vault to create items in")
    parser.add_argument("--account", default=ACCOUNT, help="1Password account (sign-in address) that holds the vault")
    parser.add_argument("--dry-run", action="store_true", help="report what would be created, create nothing")
    parser.add_argument("--skip-ssh", action="store_true", help="leave the SSH keys out")
    parser.add_argument(
        "--ssh-export-dir",
        type=Path,
        default=Path.home() / ".local" / "state" / "dotforge" / "ssh-import",
        help="where the decrypted SSH keys are staged for the 1Password app importer",
    )
    args = parser.parse_args()
    ACCOUNT = args.account

    preflight()
    password = vault_password()
    ensure_vault(args.vault, args.dry_run)

    create_item(args.vault, password_item(password), args.dry_run)

    secrets = yaml.safe_load(decrypt(VAULT_YML, password))
    grafana_url = secrets.get("grafana_url")
    for key, (title, note) in CREDENTIALS.items():
        if key not in secrets:
            print(f"item {title}: {key} not in vault.yml, skipped")
            continue
        url = grafana_url if key == "grafana_service_account_token" else None
        create_item(args.vault, credential_item(title, note, str(secrets[key]), url), args.dry_run)

    if not args.skip_ssh:
        staged = []
        for name in SSH_KEYS:
            path = REPO / "host_files" / "localhost" / name
            if not path.is_file():
                print(f"ssh key {name}: {path.relative_to(REPO)} missing, skipped")
                continue
            stage_ssh_key(args.ssh_export_dir, name, decrypt(path, password), args.dry_run)
            staged.append(name)
        if staged and not args.dry_run:
            print(
                f"\nImport each of {', '.join(staged)} in the 1Password app: open the {args.vault} vault,"
                " New Item > SSH Key, title it exactly as the file is named, Add Private Key >"
                f" Import a Key File, pick it from {args.ssh_export_dir}, Save."
                f"\nThen: trash {args.ssh_export_dir}"
            )

    print("done" if not args.dry_run else "dry run complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
