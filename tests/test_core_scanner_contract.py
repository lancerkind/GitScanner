from pathlib import Path

from gitscanner.core.models import ScanContext, ScanResult
from gitscanner.scanners.springboot.controllers import SpringControllerScanner
from gitscanner.scanners.springboot.datasources import SpringDatasourceScanner


def test_spring_controller_scanner_returns_scan_result_with_capability(tmp_path):
    scanner = SpringControllerScanner()
    context = ScanContext(repo_id=1, repo_name='repo', repo_root=tmp_path)

    result = scanner.scan(context)

    assert isinstance(result, ScanResult)
    assert result.capability == 'springboot.controllers'


def test_spring_datasource_scanner_returns_scan_result_with_capability(tmp_path):
    scanner = SpringDatasourceScanner()
    context = ScanContext(repo_id=1, repo_name='repo', repo_root=tmp_path)

    result = scanner.scan(context)

    assert isinstance(result, ScanResult)
    assert result.capability == 'springboot.datasources'
