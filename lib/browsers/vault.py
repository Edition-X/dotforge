"""Ansible Vault access for files the Python side shares with Ansible.

The bookmark catalogs hold personal URLs and are vault-encrypted in the
repository so that the repository itself can be public. Ansible reads them
natively through `include_vars`; this module gives the capture, validation and
publishing code the same view. The password comes from the file `ansible.cfg`
names, so it lives in exactly one place and is never passed around.
"""

from __future__ import annotations

import configparser
import os
from pathlib import Path

from browsers import REPO

MARKER = b"$ANSIBLE_VAULT"
DEFAULT_PASSWORD_FILE = "~/.config/macbook-pro/vault-pass"


class VaultUnavailable(RuntimeError):
    """The file is encrypted and this machine cannot decrypt it."""


def password_path() -> Path:
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(REPO / "ansible.cfg")
    raw = parser.get("defaults", "vault_password_file", fallback=DEFAULT_PASSWORD_FILE)
    return Path(os.path.expanduser(raw))


def is_encrypted(path: Path) -> bool:
    with path.open("rb") as stream:
        return stream.read(len(MARKER)) == MARKER


def _vault():  # noqa: ANN202 - ansible's VaultLib type is private to ansible
    from ansible.parsing.vault import VaultLib, VaultSecret

    secret_path = password_path()
    if not secret_path.is_file():
        raise VaultUnavailable("vault password file is missing")
    return VaultLib([("default", VaultSecret(secret_path.read_bytes().strip()))])


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
