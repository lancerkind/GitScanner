import sqlite3

from gitscanner.core.models import ScanContext, ScanResult
from gitscanner.persistence.sqlite_store import SqliteStore
from gitscanner.persistence.schema import SCHEMA_STATEMENTS
import gitscanner.persistence.sqlite_store as sqlite_store


def test_save_scan_result_dispatches_controller_records(monkeypatch):
    captured = {}

    def fake_insert_controllers(conn, repo_id, records):
        captured['payload'] = (repo_id, records)

    monkeypatch.setattr(sqlite_store, 'insert_controllers', fake_insert_controllers)

    store = SqliteStore(conn=object())
    context = ScanContext(repo_id=7, repo_name='repo', repo_root='unused')
    result = ScanResult(capability='springboot.controllers', records=[{'name': 'A'}])

    store.save_scan_result(context, result)

    assert captured['payload'] == (7, [{'name': 'A'}])


def test_save_scan_result_dispatches_datasource_records(monkeypatch):
    captured = {}

    def fake_insert_repo_datasources(conn, repo_id, records):
        captured['payload'] = (repo_id, records)

    monkeypatch.setattr(sqlite_store, 'insert_repo_datasources', fake_insert_repo_datasources)

    store = SqliteStore(conn=object())
    context = ScanContext(repo_id=9, repo_name='repo', repo_root='unused')
    result = ScanResult(capability='springboot.datasources', records=[{'url': 'jdbc:h2:mem:test'}])

    store.save_scan_result(context, result)

    assert captured['payload'][0] == 9
    assert captured['payload'][1][0]['url'].startswith('jdbc:')


def test_insert_service_dependency_markers_persists_no_dependency_when_markers_empty():
    conn = sqlite3.connect(':memory:')
    for statement in SCHEMA_STATEMENTS:
        conn.execute(statement)

    controller_service_id = sqlite_store.insert_controller_service(conn, controller_id=1, service_name='ServiceA', found=True)

    sqlite_store.insert_service_dependency_markers(conn, controller_service_id, [])

    rows = conn.execute(
        'SELECT marker FROM service_dependency_markers WHERE controller_service_id = ?',
        (controller_service_id,),
    ).fetchall()
    assert rows == [('NoDependency',)]


def test_insert_service_dependency_markers_keeps_existing_markers_without_no_dependency():
    conn = sqlite3.connect(':memory:')
    for statement in SCHEMA_STATEMENTS:
        conn.execute(statement)

    controller_service_id = sqlite_store.insert_controller_service(conn, controller_id=1, service_name='ServiceA', found=True)

    sqlite_store.insert_service_dependency_markers(conn, controller_service_id, ['JdbcTemplate'])

    rows = conn.execute(
        'SELECT marker FROM service_dependency_markers WHERE controller_service_id = ?',
        (controller_service_id,),
    ).fetchall()
    assert rows == [('JdbcTemplate',)]


def test_save_scan_result_persists_unknown_service_and_no_dependency_marker():
    conn = sqlite3.connect(':memory:')
    for statement in SCHEMA_STATEMENTS:
        conn.execute(statement)

    store = SqliteStore(conn=conn)
    context = ScanContext(repo_id=1, repo_name='repo', repo_root='unused')
    result = ScanResult(
        capability='springboot.service_dependencies',
        records=[
            {'controller_id': 10, 'service_name': 'UnknownService', 'found': False, 'markers': []},
        ],
    )

    store.save_scan_result(context, result)
 
    service_row = conn.execute('SELECT service_name, found FROM controller_services').fetchone()
    marker_row = conn.execute('SELECT marker FROM service_dependency_markers').fetchone()
    assert service_row == ('UnknownService', 0)
    assert marker_row == ('NoDependency',)
 
 
def test_insert_controllers_with_endpoints_and_params():
    conn = sqlite3.connect(":memory:")
    for stmt in SCHEMA_STATEMENTS:
        conn.execute(stmt)
    repo_id = 1
    conn.execute("INSERT INTO repos (id, name) VALUES (?, ?)", (repo_id, "test"))
 
    controllers = [{
        "name": "C1",
        "type": "RestController",
        "base_path": "/api",
        "endpoints": [{
            "http_method": "GET",
            "path": "/hello",
            "parameters": [{"name": "p1", "java_type": "String", "source": "query", "required": True}]
        }]
    }]
 
    sqlite_store.insert_controllers(conn, repo_id, controllers)
 
    count = conn.execute("SELECT COUNT(*) FROM endpoints").fetchone()[0]
    assert count == 1
    param_count = conn.execute("SELECT COUNT(*) FROM parameters").fetchone()[0]
    assert param_count == 1
 
 
def test_sqlite_store_initialize_database():
    conn = sqlite3.connect(":memory:")
    sqlite_store.initialize_database(conn)
    # Check if a table exists
    row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='repos'").fetchone()
    assert row is not None
 
 
def test_sqlite_store_create_scan_run():
    conn = sqlite3.connect(":memory:")
    for stmt in SCHEMA_STATEMENTS:
        conn.execute(stmt)
    run_id = sqlite_store.create_scan_run(conn, "test run")
    assert run_id is not None
    row = conn.execute("SELECT notes FROM scan_runs WHERE id = ?", (run_id,)).fetchone()
    assert row[0] == "test run"
 
 
def test_insert_repo_karate_data_cleanup():
    conn = sqlite3.connect(":memory:")
    for stmt in SCHEMA_STATEMENTS:
        conn.execute(stmt)
    repo_id = 1
    conn.execute("INSERT INTO repos (id, name) VALUES (?, ?)", (repo_id, "test"))
 
    fid = sqlite_store.insert_karate_feature_file(conn, repo_id, 1, "p", "n")
    sqlite_store.insert_karate_paths(conn, fid, ["/a"])
 
    sqlite_store.delete_repo_karate_data(conn, repo_id)
    count = conn.execute("SELECT COUNT(*) FROM karate_feature_files").fetchone()[0]
    assert count == 0
    pcount = conn.execute("SELECT COUNT(*) FROM karate_paths").fetchone()[0]
    assert pcount == 0

