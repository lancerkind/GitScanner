from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence


@dataclass(frozen=True)
class ScanContext:
    repo_id: int
    repo_name: str
    repo_root: Path


@dataclass(frozen=True)
class ScanResult:
    capability: str
    records: Sequence[Any]
