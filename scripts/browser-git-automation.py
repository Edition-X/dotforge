#!/usr/bin/env python3
"""CLI entry point. The implementation lives in lib/browsers/automation.py.

The path is resolved relative to this file so that a copy of the repository
runs its own code rather than whichever copy happens to be installed.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

from browsers import automation  # noqa: E402

if __name__ == "__main__":
    sys.exit(automation.main())
