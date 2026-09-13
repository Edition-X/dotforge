"""Ansible Vault access for files the Python side shares with Ansible.

The bookmark catalogs hold personal URLs and are vault-encrypted in the
repository so that the repository itself can be public. Ansible reads them
natively through `include_vars`; this module gives the capture, validation and
publishing code the same view. The password comes from the source `ansible.cfg`
names, so it lives in exactly one place and is never passed around. Like
Ansible, this runs that source when it is executable (scripts/vault-pass asks
1Password) and reads it when it is a plain file.
"""

from __future__ import annotations

import configparser
import os
import subprocess
from pathlib import Path

from browsers import REPO

MARKER = b"$ANSIBLE_VAULT"
DEFAULT_PASSWORD_FILE = "~/.config/dotforge/vault-pass"


class VaultUnavailable(RuntimeError):
    """The file is encrypted and this machine cannot decrypt it."""


def password_path() -> Path:
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(REPO / "ansible.cfg")
    raw = parser.get("defaults", "vault_password_file", fallback=DEFAULT_PASSWORD_FILE)
    path = Path(os.path.expanduser(raw))
    # Ansible resolves a relative vault_password_file against ansible.cfg's
    # directory, never the current directory.
    return path if path.is_absolute() else REPO / path


def _password() -> bytes:
    """The vault password, from the executable or file ansible.cfg names."""
    source = password_path()
    if not source.is_file():
        raise VaultUnavailable("vault password source is missing")
    if os.access(source, os.X_OK):
        # Same contract as Ansible's script vault secret: run it, take stdout.
        result = subprocess.run([str(source)], capture_output=True, check=False)
        if result.returncode != 0:
            raise VaultUnavailable("vault password script failed")
        return result.stdout.strip(b"\r\n")
    return source.read_bytes().strip()


def is_encrypted(path: Path) -> bool:
    with path.open("rb") as stream:
        return stream.read(len(MARKER)) == MARKER


def _vault():  # noqa: ANN202 - ansible's VaultLib type is private to ansible
    from ansible.parsing.vault import VaultLib, VaultSecret

    return VaultLib([("default", VaultSecret(_password()))])


def read_text(path: Path) -> str:
    """Return the plaintext of a file, decrypting it when it is vault-encrypted."""
    data = path.read_bytes()
    if not data.startswith(MARKER):
        return data.decode("utf-8")
    from ansible.errors import AnsibleError

    try:
        return _vault().decrypt(data).decode("utf-8")
    except AnsibleError as error:
        raise VaultUnavailable("vault decryption failed") from error


def encrypt_text(text: str) -> bytes:
    """Encrypt plaintext with the repository's vault password."""
    return _vault().encrypt(text.encode("utf-8"))
