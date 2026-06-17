"""Summary/reporting compatibility exports."""

from gitscanner import count_spring_controllers as legacy


build_summary_for_scan_run = legacy.build_summary_for_scan_run
format_summary_lines = legacy.format_summary_lines


class SummaryReporter:
    def __init__(self, conn):
        self.conn = conn

    def build_summary(self, scan_run_id):
        return legacy.build_summary_for_scan_run(self.conn, scan_run_id)
