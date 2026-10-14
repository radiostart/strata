"""strata — an operating layer for repositories of layered, approved documents.

Standard library only. Requires Python 3.11+ (``tomllib``).
"""

__version__ = "0.1.0"

MANIFEST_DIR = ".strata"
MANIFEST_FILE = "strata.toml"
MANIFEST_REL = f"{MANIFEST_DIR}/{MANIFEST_FILE}"
BYPASS_ENV = "STRATA_GUARD_BYPASS"
