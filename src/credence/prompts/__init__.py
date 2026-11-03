"""Versioned system prompts. Each version is a file; the version string goes on every extraction."""

from importlib import resources

_FILES = resources.files(__name__)


def available() -> list[str]:
    return sorted(p.name.removesuffix(".md") for p in _FILES.iterdir() if p.name.endswith(".md"))


def load(version: str) -> str:
    """The system prompt text for `version`, e.g. "v1"."""
    path = _FILES / f"{version}.md"
    if not path.is_file():
        raise ValueError(f"unknown prompt version {version!r}; have {', '.join(available())}")
    return path.read_text(encoding="utf-8").strip()
