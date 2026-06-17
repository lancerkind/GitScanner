from typing import Protocol

from gitscanner.core.models import ScanContext, ScanResult


class RepoScanner(Protocol):
    capability: str

    def scan(self, context: ScanContext) -> ScanResult:
        ...
