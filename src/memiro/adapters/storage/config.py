from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True, kw_only=True)
class MediaConfig:
    """Where the local storage keeps the files the edge serves as media."""

    root: Path
