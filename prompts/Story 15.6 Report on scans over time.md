# Report scans over time
As the data changes over time, it is important to track the delta between each time period. 
This will allow us to see how the enterprise code base is evolving over time.  Namely the following trends:
- growth/reduction of feature files
- growth/reduction of endpoints
- growth/reduction of controllers

# Schema usage
The report should read from the existing SQLite schema:
- `scan_runs` provides the scan date via `scanned_at`.
- `repos` belongs to a scan run via `scan_run_id`.
- `controllers` belongs to a repo via `repo_id`.
- `endpoints` belongs to a controller via `controller_id`.
- `karate_feature_files` belongs to a repo via `repo_id`.

For each repository in each scan run:
- `controllers` is `COUNT(DISTINCT controllers.id)`.
- `endpoints` is `COUNT(DISTINCT endpoints.id)`.
- `feature_files` is `COUNT(DISTINCT karate_feature_files.id)`.
- Repositories with no controllers, endpoints, or feature files should still appear with zero counts.


# Specification
- this will be implemented as a sql script `./reporting/trends_over_time.sql` directory.
- Order by repository name alphabetically ascending, then scan date descending.
- Repositories should be grouped across scan runs by `repos.name`.
- Dates should be rendered as `YYYY-MM-DD`.
- The SQL must be compatible with SQLite.
Example:

|repository | date       | controllers | endpoints | feature files |
| --- |------------| --- | --- | --- |
| my/repository | 2026/6/20  | 5 | 25 | 10 |
| my/repository | 2026/6/10  | 4 | 20 | 4 |
| my/repository | 2026/01/5  | 3 | 15 | 0 |
| another/repository | 2026/6/10  | 5 | 25 | 10 |
| another/repository | 2026/5/20  | 4 | 20 | 4 |
| another/repository | 2025/12/01 | 3 | 15 | 0 |

# Acceptance Criteria
- A new SQL report exists at `reporting/delta_over_time_report.sql`.
- The report returns one row per repository per scan run.
- The report includes repository name, scan date, controller count, endpoint count, and Karate feature file count.
- Counts are zero when related records are missing.
- Results are ordered by repository name ascending, then scan date descending.
- The SQL is SQLite-compatible.
- Run the `reporting/delta_over_time_report.sql` script and ensure it produces the expected output and no sql errors.

## Create or update a SQL fixture under `reporting/` that inserts at least:
- two repositories
- three scan runs for one repository
- two scan runs for another repository
- changes in controller count
- changes in endpoint count
- changes in Karate feature file count
- one repository/run with zero related records
- run fixture against test.db and then test the `reporting/delta_over_time_report.sql` script 
