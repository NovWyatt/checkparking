"""Single source of truth for the application release version.

Build scripts generate :mod:`check_vehicle_ocr._build_meta` immediately before
freezing the application.  The generated module is deliberately ignored by
Git: source runs report a development build, while distributable artifacts
embed their exact build date, commit and GitHub repository.
"""

from __future__ import annotations

VERSION = "1.10.0"
DEFAULT_GITHUB_REPOSITORY = "NovWyatt/checkparking"

try:
    from ._build_meta import BUILD_DATE, COMMIT_SHA, GITHUB_REPOSITORY
except ImportError:
    BUILD_DATE = "development"
    COMMIT_SHA = "local"
    GITHUB_REPOSITORY = DEFAULT_GITHUB_REPOSITORY

if not GITHUB_REPOSITORY:
    GITHUB_REPOSITORY = DEFAULT_GITHUB_REPOSITORY

__version__ = VERSION


def display_build() -> str:
    """Compact, non-secret build identifier suitable for the UI."""
    if BUILD_DATE == "development":
        return "Development build"
    return f"{BUILD_DATE} • {COMMIT_SHA[:12]}"
