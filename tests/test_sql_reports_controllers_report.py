import sqlite3
from pathlib import Path

def _execute_sql_file(conn, relative_path):
    project_root = Path(__file__).resolve().parents[1]
    sql = (project_root / relative_path).read_text(encoding='utf-8')
    conn.executescript(sql)

def test_controllers_report_returns_latest_run_classified_dependencies_only():
    conn = sqlite3.connect(':memory:')
    _execute_sql_file(conn, 'sql_reports/test_controllers_report_fixture.sql')
    
    report_sql_path = Path(__file__).resolve().parents[1] / 'sql_reports/controllers_report.sql'
    report_sql = report_sql_path.read_text(encoding='utf-8')

    rows = conn.execute(report_sql).fetchall()

    expected = [
        ('repository/another', 'controllerX', 'CloudSQL'),
        ('repository/here', 'controllerA', 'API'),
        ('repository/here', 'controllerA', 'Kafka'),
        ('repository/here', 'controllerB', 'Oracle'),
    ]
    
    # Sort actual and expected to be sure, although the SQL should handle ordering
    assert rows == expected
