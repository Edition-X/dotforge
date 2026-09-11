#!/usr/bin/env python3
"""Fail when a tool is pinned to different versions in different files.

requirements.txt and .pre-commit-config.yaml both pin ansible-lint, yamllint
and ruff. They used to drift: the venv carried ruff 0.16.7 while the hook ran
0.14.7, so `ruff check .` and the pre-commit hook could disagree about the same
file. requirements.txt asked for agreement in a comment — "Keep in step with
the ansible-lint rev pinned in .pre-commit-config.yaml" — which is a wish, not
a check.

The ansible-lint hook also carries its own copy of ansible-core, in
`additional_dependencies`, resolved inside pre-commit's isolated hook
environment rather than the project venv. A floor there (`>=2.15.0`) let that
environment drift to a newer ansible-core than requirements.txt pins, so
ansible-lint parsed against one Ansible version while `make check` ran
another. Checked the same way as the other shared tools, against an exact `==`
pin rather than a `rev:`.

Reports every mismatch rather than stopping at the first, so one run tells you
everything to fix.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# pre-commit repository URL fragment -> the distribution name in requirements.
SHARED_TOOLS = {
    "ansible-community/ansible-lint": "ansible-lint",
    "adrienverge/yamllint": "yamllint",
    "astral-sh/ruff-pre-commit": "ruff",
    "gitleaks/gitleaks": None,  # not a Python dependency; version lives only here
}


def requirement_pins() -> dict[str, str]:
    pins: dict[str, str] = {}
    for line in (REPO / "requirements.txt").read_text(encoding="utf-8").splitlines():
        match = re.match(r"^([A-Za-z0-9._-]+)==([^\s#]+)", line.strip())
        if match:
            pins[match.group(1).lower()] = match.group(2)
    return pins


def hook_revisions() -> dict[str, str]:
    revisions: dict[str, str] = {}
    repository: str | None = None
    for line in (REPO / ".pre-commit-config.yaml").read_text(encoding="utf-8").splitlines():
        repo = re.search(r"^\s*-\s*repo:\s*https://github\.com/(\S+)", line)
        if repo:
            repository = repo.group(1)
            continue
        rev = re.search(r"^\s*rev:\s*v?([^\s#]+)", line)
        if rev and repository:
            revisions[repository] = rev.group(1)
            repository = None
    return revisions


def additional_dependency_pin(distribution: str) -> str | None:
    """Read an exact `name==version` entry out of any hook's `additional_dependencies`.

    Unlike `rev:`, this resolves inside pre-commit's own hook environment, not
    the project venv — so a dependency named here needs its own agreement
    check against requirements.txt rather than being covered by hook_revisions.
    """
    pattern = re.compile(rf"^\s*-\s*{re.escape(distribution)}==([^\s#]+)")
    for line in (REPO / ".pre-commit-config.yaml").read_text(encoding="utf-8").splitlines():
        match = pattern.match(line)
        if match:
            return match.group(1)
    return None


# additional_dependencies distribution name -> the distribution name in
# requirements.txt. Currently the same, but kept separate from SHARED_TOOLS
# because it is matched by an `==` entry inside a hook, not a `rev:`.
ADDITIONAL_DEPENDENCY_TOOLS = {
    "ansible-core": "ansible-core",
}


def main() -> int:
    pins = requirement_pins()
    revisions = hook_revisions()
    failures: list[str] = []
    checked = 0

    for repository, distribution in SHARED_TOOLS.items():
        if distribution is None:
            continue
        hook_version = revisions.get(repository)
        pinned = pins.get(distribution)
        if hook_version is None:
            failures.append(f"{repository} has no pinned rev in .pre-commit-config.yaml")
            continue
        if pinned is None:
            failures.append(f"{distribution} is not pinned with == in requirements.txt")
            continue
        checked += 1
        if hook_version != pinned:
            failures.append(
                f"{distribution}: requirements.txt pins {pinned}, "
                f"pre-commit hook pins {hook_version}"
            )

    for dependency_name, distribution in ADDITIONAL_DEPENDENCY_TOOLS.items():
        dependency_version = additional_dependency_pin(dependency_name)
        pinned = pins.get(distribution)
        if dependency_version is None:
            failures.append(f"{dependency_name} has no exact `==` additional_dependencies pin")
            continue
        if pinned is None:
            failures.append(f"{distribution} is not pinned with == in requirements.txt")
            continue
        checked += 1
        if dependency_version != pinned:
            failures.append(
                f"{distribution}: requirements.txt pins {pinned}, "
                f"pre-commit additional_dependencies pins {dependency_version}"
            )

    unpinned = [
        line.strip()
        for line in (REPO / "requirements.txt").read_text(encoding="utf-8").splitlines()
        if line.strip()
        and not line.lstrip().startswith("#")
        and "==" not in line
    ]
    failures.extend(f"{entry} is not pinned to an exact version" for entry in unpinned)

    for failure in failures:
        print(f"❌ {failure}")
    if failures:
        return 1
    print(f"✅ tool pins: shared={checked} requirements-exact={len(pins)} agreed=true")
    return 0


if __name__ == "__main__":
    sys.exit(main())
