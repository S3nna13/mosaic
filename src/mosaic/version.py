"""Package version information."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class VersionInfo:
    """Immutable version metadata."""

    major: int
    minor: int
    patch: int
    release: str = "alpha"  # alpha, beta, rc, final
    build_date: str = None
    git_commit: str = None

    def __str__(self) -> str:
        base = f"{self.major}.{self.minor}.{self.patch}"
        if self.release != "final":
            base += f"-{self.release}"
        return base

    def prettify(self) -> str:
        return f"MOSAIC {self} ({self.build_date or 'unknown'})"


# Semantic Versioning 2.0.0
VERSION = VersionInfo(
    major=0,
    minor=3,
    patch=0,
    release="alpha",
    build_date=datetime.utcnow().strftime("%Y-%m-%d"),
)

GIT_COMMIT = ""


def get_version() -> str:
    """Return the human-readable version string."""
    return str(VERSION)


def get_version_info() -> VersionInfo:
    """Return the full version info object."""
    return VERSION
