"""Summary/sql reports compatibility exports."""

def build_summary_for_scan_run(conn, scan_run_id):
    total_repos_scanned = conn.execute(
        "SELECT COUNT(*) FROM repos WHERE scan_run_id = ?",
        (scan_run_id,),
    ).fetchone()[0]
    repos_with_controllers = conn.execute(
        """
        SELECT COUNT(DISTINCT r.id)
        FROM repos r
        JOIN controllers c ON c.repo_id = r.id
        WHERE r.scan_run_id = ?
        """,
        (scan_run_id,),
    ).fetchone()[0]
    total_rest_controllers = conn.execute(
        """
        SELECT COUNT(*)
        FROM controllers c
        JOIN repos r ON r.id = c.repo_id
        WHERE r.scan_run_id = ? AND c.type = 'RestController'
        """,
        (scan_run_id,),
    ).fetchone()[0]
    total_controllers = conn.execute(
        """
        SELECT COUNT(*)
        FROM controllers c
        JOIN repos r ON r.id = c.repo_id
        WHERE r.scan_run_id = ? AND c.type = 'Controller'
        """,
        (scan_run_id,),
    ).fetchone()[0]
    total_endpoints = conn.execute(
        """
        SELECT COUNT(*)
        FROM endpoints e
        JOIN controllers c ON c.id = e.controller_id
        JOIN repos r ON r.id = c.repo_id
        WHERE r.scan_run_id = ?
        """,
        (scan_run_id,),
    ).fetchone()[0]
    total_feature_files = conn.execute(
        """
        SELECT COUNT(*)
        FROM karate_feature_files k
        JOIN repos r ON r.id = k.repo_id
        WHERE r.scan_run_id = ?
        """,
        (scan_run_id,),
    ).fetchone()[0]
    total_datasources = conn.execute(
        """
        SELECT COUNT(*)
        FROM repo_datasources d
        JOIN repos r ON r.id = d.repo_id
        WHERE r.scan_run_id = ?
        """,
        (scan_run_id,),
    ).fetchone()[0]
    total_services_scanned = conn.execute(
        """
        SELECT COUNT(*)
        FROM controller_services cs
        JOIN controllers c ON c.id = cs.controller_id
        JOIN repos r ON r.id = c.repo_id
        WHERE r.scan_run_id = ?
        """,
        (scan_run_id,),
    ).fetchone()[0]
    total_services_not_found = conn.execute(
        """
        SELECT COUNT(*)
        FROM controller_services cs
        JOIN controllers c ON c.id = cs.controller_id
        JOIN repos r ON r.id = c.repo_id
        WHERE r.scan_run_id = ? AND cs.found = 0
        """,
        (scan_run_id,),
    ).fetchone()[0]
    total_dependency_markers = conn.execute(
        """
        SELECT COUNT(*)
        FROM service_dependency_markers sdm
        JOIN controller_services cs ON cs.id = sdm.controller_service_id
        JOIN controllers c ON c.id = cs.controller_id
        JOIN repos r ON r.id = c.repo_id
        WHERE r.scan_run_id = ?
        """,
        (scan_run_id,),
    ).fetchone()[0]
    breakdown_rows = conn.execute(
        """
        SELECT
            r.name,
            SUM(CASE WHEN c.type = 'RestController' THEN 1 ELSE 0 END) AS rest_count,
            SUM(CASE WHEN c.type = 'Controller' THEN 1 ELSE 0 END) AS controller_count,
            COUNT(c.id) AS total_count,
            COUNT(DISTINCT k.id) AS feature_file_count
        FROM repos r
        LEFT JOIN controllers c ON c.repo_id = r.id
        LEFT JOIN karate_feature_files k ON k.repo_id = r.id
        WHERE r.scan_run_id = ?
        GROUP BY r.id, r.name
        ORDER BY total_count DESC, r.name ASC
        """,
        (scan_run_id,),
    ).fetchall()

    return {
        "total_repos_scanned": total_repos_scanned,
        "repos_with_controllers": repos_with_controllers,
        "total_rest_controllers": total_rest_controllers,
        "total_controllers": total_controllers,
        "total_controller_files": total_rest_controllers + total_controllers,
        "total_endpoints": total_endpoints,
        "total_feature_files": total_feature_files,
        "total_datasources": total_datasources,
        "total_services_scanned": total_services_scanned,
        "total_services_not_found": total_services_not_found,
        "total_dependency_markers": total_dependency_markers,
        "repo_results": [
            {
                "repo_name": row[0],
                "total_at_rest_controllers": row[1],
                "total_at_controllers": row[2],
                "total_rest_controllers": row[3],
                "total_feature_files": row[4],
            }
            for row in breakdown_rows
        ],
    }


def format_summary_lines(stats):
    lines = [
        "\n" + "=" * 70,
        "SUMMARY",
        "=" * 70,
        f"\nRepositories with controllers: {stats['repos_with_controllers']}/{stats['total_repos_scanned']}",
        f"\nTotal @RestController files: {stats['total_rest_controllers']}",
        f"Total @Controller files: {stats['total_controllers']}",
        f"Total Controller files: {stats['total_controller_files']}",
        f"Total endpoints: {stats['total_endpoints']}",
        f"Total feature files: {stats['total_feature_files']}",
        f"Total datasources: {stats['total_datasources']}",
        f"Total services scanned: {stats['total_services_scanned']}",
        f"Total services not found: {stats['total_services_not_found']}",
        f"Total dependency markers: {stats['total_dependency_markers']}",
    ]

    if stats["repo_results"]:
        lines.extend([
            "\n" + "-" * 70,
            "Breakdown by repository:",
            "-" * 70,
        ])
        for result in stats["repo_results"]:
            lines.append(
                f"{result['repo_name']:50} {result['total_rest_controllers']:3} controllers"
                f" {result['total_feature_files']:3} feature files"
            )

    return lines


class SummaryReporter:
    def __init__(self, conn):
        self.conn = conn

    def build_summary(self, scan_run_id):
        return build_summary_for_scan_run(self.conn, scan_run_id)
