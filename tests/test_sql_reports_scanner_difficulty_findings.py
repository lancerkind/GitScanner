import sqlite3
from pathlib import Path


def _execute_sql_file(conn, relative_path):
    project_root = Path(__file__).resolve().parents[1]
    sql = (project_root / relative_path).read_text(encoding='utf-8')
    conn.executescript(sql)


def test_scanner_difficulty_report_returns_latest_run_findings_only():
    conn = sqlite3.connect(':memory:')
    _execute_sql_file(conn, 'sql_reports/test_scanner_difficulty_findings_fixture.sql')
    report_sql = (Path(__file__).resolve().parents[1] / 'sql_reports/scanner_findings_report.sql').read_text(
        encoding='utf-8'
    )

    rows = conn.execute(report_sql).fetchall()

    assert rows == [
        ('2026-01-02', 'repo-a', 'ControllerA', 'UnknownService', 'NoDependency'),
        ('2026-01-02', 'repo-b', 'ControllerB', 'ServiceB', 'NoDependency'),
    ]