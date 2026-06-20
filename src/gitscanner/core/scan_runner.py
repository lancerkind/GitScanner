from typing import Iterable, List, Optional
import shutil

from gitscanner.core.models import ScanContext
from gitscanner.core.scanner import RepoScanner


class ScanRunner:
    def __init__(
        self,
        repository_client,
        store,
        scanners: Iterable[RepoScanner],
        reporter,
        api_base_url: str = "https://api.github.com",
        provider: str = "github",
        token: Optional[str] = None,
    ):
        self.repository_client = repository_client
        self.store = store
        self.scanners: List[RepoScanner] = list(scanners)
        self.reporter = reporter
        self.api_base_url = api_base_url
        self.provider = provider
        self.token = token

    def run(self, repos):
        self.store.initialize_database()
        scan_run_id = self.store.create_scan_run()
        for repo_name in repos:
            checkout = self.repository_client.checkout(
                repo_name,
                api_base_url=self.api_base_url,
                provider=self.provider,
                token=self.token,
            )
            try:
                repo_id = self.store.insert_repo(scan_run_id, repo_name, checkout.clone_url)
                context = ScanContext(repo_id=repo_id, repo_name=repo_name, repo_root=checkout.path)
                for scanner in self.scanners:
                    self.store.save_scan_result(context, scanner.scan(context))
            finally:
                if getattr(checkout, "cleanup_path", None):
                    shutil.rmtree(checkout.cleanup_path, ignore_errors=True)
        return scan_run_id, self.reporter.build_summary(scan_run_id)
