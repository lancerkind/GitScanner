from gitscanner.reporting.summary import SummaryReporter, format_summary_lines


def test_summary_reporter_delegates_build_summary(monkeypatch):
    called = {}

    def fake_build_summary_for_scan_run(conn, scan_run_id):
        called['args'] = (conn, scan_run_id)
        return {'scan_run_id': scan_run_id}

    monkeypatch.setattr('gitscanner.reporting.summary.build_summary_for_scan_run', fake_build_summary_for_scan_run)

    reporter = SummaryReporter(conn='db-conn')
    summary = reporter.build_summary(123)

    assert called['args'] == ('db-conn', 123)
    assert summary['scan_run_id'] == 123


def test_format_summary_lines_returns_lines():
    stats = {
        'repos_with_controllers': 0,
        'total_repos_scanned': 0,
        'total_rest_controllers': 0,
        'total_controllers': 0,
        'total_controller_files': 0,
        'total_endpoints': 0,
        'total_feature_files': 0,
        'total_datasources': 0,
        'total_services_scanned': 0,
        'total_services_not_found': 0,
        'total_dependency_markers': 0,
        'repo_breakdown': [],
        'repo_results': [],
    }
    lines = format_summary_lines(stats)
    assert isinstance(lines, list)
