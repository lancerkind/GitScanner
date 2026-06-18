import sqlite3

from gitscanner.core.models import ScanContext, ScanResult
from gitscanner.scanners.karate.features import (
    KarateFeatureScanner,
    collect_karate_feature_files,
    extract_karate_paths,
)


def test_collect_karate_feature_files_scans_only_src_test_java(tmp_path):
    feature_file = tmp_path / 'src' / 'test' / 'java' / 'features' / 'orders.feature'
    feature_file.parent.mkdir(parents=True)
    feature_file.write_text('Feature: orders', encoding='utf-8')

    files = collect_karate_feature_files(tmp_path)

    assert files == [feature_file]


def test_extract_karate_paths_extracts_non_url_paths():
    content = """
    Given path '/orders', id
    And path '/users'
    And url 'https://example.com/absolute'
    """

    assert extract_karate_paths(content) == ["/orders'", '/users']


def test_karate_feature_scanner_returns_scan_result(tmp_path):
    db = sqlite3.connect(':memory:')
    db.execute('CREATE TABLE controllers (id INTEGER PRIMARY KEY, repo_id INTEGER, name TEXT)')
    db.execute("INSERT INTO controllers(id, repo_id, name) VALUES (1, 10, 'OrdersController')")

    feature_file = tmp_path / 'src' / 'test' / 'java' / 'orderscontroller.feature'
    feature_file.parent.mkdir(parents=True)
    feature_file.write_text("Given path '/orders'", encoding='utf-8')

    scanner = KarateFeatureScanner(db)
    context = ScanContext(repo_id=10, repo_name='repo', repo_root=tmp_path)

    result = scanner.scan(context)

    assert isinstance(result, ScanResult)
    assert result.capability == 'karate.features'
