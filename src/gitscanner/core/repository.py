"""Repository checkout abstractions."""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from gitscanner.core import git

@dataclass(frozen=True)
class RepositoryCheckout:
    path: Path
    clone_url: str
    cleanup_path: Optional[Path] = None


class RepositoryClient:
    def __init__(self, clone_and_count_func: Callable = git.clone_and_count):
        self._clone_and_count = clone_and_count_func

    def checkout(self, repo_name, api_base_url="https://api.github.com", provider="github", token=None):
        result = self._clone_and_count(
            repo_name,
            api_base_url=api_base_url,
            provider=provider,
            token=token,
        )
        if "path" not in result:
            raise RuntimeError(
                f"Repository checkout for {repo_name} did not return a repository path. "
                "Expected clone_and_count() to return a dictionary containing a 'path' key."
            )

        cleanup_path = result.get("cleanup_path")

        return RepositoryCheckout(
            path=Path(result["path"]),
            clone_url=result.get("clone_url") or "",
            cleanup_path=Path(cleanup_path) if cleanup_path else None,
        )
