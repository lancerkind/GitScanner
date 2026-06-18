from pathlib import Path

from gitscanner.core.models import ScanResult
from gitscanner.core.scan_runner import ScanRunner


class FakeRepositoryClient:
    def checkout(self, repo_name, api_base_url='https://api.github.com', provider='github', token=None):
        return type('Checkout', (), {'path': Path('/tmp/workdir'), 'clone_url': f'https://example.com/{repo_name}.git'})()


class FakeStore:
    def __init__(self):
        self.saved = []

    def initialize_database(self):
        self.initialized = True

    def create_scan_run(self):
        return 101

    def insert_repo(self, scan_run_id, repo_name, clone_url):
        return 42

    def save_scan_result(self, context, result):
        self.saved.append((context, result))


class FakeReporter:
    def build_summary(self, scan_run_id):
        return {'scan_run_id': scan_run_id, 'total_repos': 1}


class FakeScanner:
    capability = 'springboot.controllers'

    def scan(self, context):
        return ScanResult(capability=self.capability, records=[{'name': 'X'}])


def test_scan_runner_runs_pipeline_with_fake_collaborators():
    runner = ScanRunner(
        repository_client=FakeRepositoryClient(),
        store=FakeStore(),
        scanners=[FakeScanner()],
        reporter=FakeReporter(),
    )

    scan_run_id, summary = runner.run(['org/repo'])

    assert scan_run_id == 101
    assert summary['total_repos'] == 1
