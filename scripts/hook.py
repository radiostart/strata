#!/usr/bin/env python3
"""Launch a strata hook: ``hook.py <name>``. Called by ``hooks/run.sh``."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from strata.hook import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(sys.argv))
