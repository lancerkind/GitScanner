from gitscanner.core.models import ScanContext, ScanResult
from gitscanner.persistence.sqlite_store import SqliteStore
import gitscanner.persistence.sqlite_store as sqlite_store


def test_save_scan_result_dispatches_controller_records(monkeypatch):
    captured = {}

    def fake_insert_controllers(conn, repo_id, records):
        captured['payload'] = (repo_id, records)

    monkeypatch.setattr(sqlite_store.legacy, 'insert_controllers', fake_insert_controllers)

    store = SqliteStore(conn=object())
    context = ScanContext(repo_id=7, repo_name='repo', repo_root='unused')
    result = ScanResult(capability='springboot.controllers', records=[{'name': 'A'}])

    store.save_scan_result(context, result)

    assert captured['payload'] == (7, [{'name': 'A'}])


def test_save_scan_result_dispatches_datasource_records(monkeypatch):
    captured = {}

    def fake_insert_repo_datasources(conn, repo_id, records):
        captured['payload'] = (repo_id, records)

    monkeypatch.setattr(sqlite_store.legacy, 'insert_repo_datasources', fake_insert_repo_datasources)

    store = SqliteStore(conn=object())
    context = ScanContext(repo_id=9, repo_name='repo', repo_root='unused')
    result = ScanResult(capability='springboot.datasources', records=[{'url': 'jdbc:h2:mem:test'}])

    store.save_scan_result(context, result)

    assert captured['payload'][0] == 9
    assert captured['payload'][1][0]['url'].startswith('jdbc:')
