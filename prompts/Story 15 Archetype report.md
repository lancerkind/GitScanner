# User Story: Repo Archetype Classification — SQLite Query & Test Fixture

## Summary
As an API Testing initiative lead, I want a SQLite query that classifies each repo from the most recent scan into a 
testing archetype, and a fixture script that populates a test database with known data so I can verify the query 
produces correct results before running it against production data.

---

## Background

All data lives in `scanner.db`, queried directly via IntelliJ's Database tool. There is no Python reporting script. 
The archetype query is a standalone `.sql` file. Results are read on-screen or exported to CSV via IntelliJ.

A repo's archetype is determined by its dependency types, derived from two sources in the database:
1. `service_dependency_markers` → classified via `dependency_classifications`
2. `repo_datasources` → classified via URL pattern matching in `dependency_classifications`

Both sources are combined and deduplicated per repo before archetype assignment.

---

## Deliverables

Two files, located in a new `reporting/` directory:

| File | Purpose |
|---|---|
| `reporting/archetype_report.sql` | The report query — run against `scanner.db` |
| `reporting/test_archetype_fixture.sql` | Fixture script — populates `test.db` with known data and runs the report query inline to verify results |

---

## Archetypes

Evaluated in priority order. A repo is assigned the **first matching archetype**.

| Priority | Archetype                  | Rule                                                              |
|----------|----------------------------|-------------------------------------------------------------------|
| 1        | `MIXED`                    | 3 or more distinct non-H2 dependency types                        |
| 2        | `KAFKA`                    | Has Kafka dependency                                              |
| 3        | `ORACLE`                   | Has an Oracle SQL-type dependency                                 |
| 4        | `SPANNER`                  | Has Spanner SQL-type dependency                                   |
| 5        | `POSTGRES`                 | Has a PostgreSQL SQL-type dependency                              |
| 6        | `OTHER_SQL`                | Has any other SQL-type dependency                                 |
| 7        | `UPSTREAM_REST_API`        | Has dependency on REST APIs                                       |
| 8        | `NO_DEPENDENCIES_DETECTED` | No dependency markers or datasource URLs resolved to a known type |
| 9        | `UNCLASSIFIED`             | Has services but none could be resolved or classified             |

**SQL-type dependencies:** `SQL Database`, `Oracle`, `CloudSQL`, `SQL Server`, `PostgreSQL`, `Spanner`. H2 is excluded.

---

## Report Query (`archetype_report.sql`)

The query must:

1. Identify the latest `scan_run_id` (highest `id` in `scan_runs`)
2. For each repo in that run, collect all resolved dependency types from both sources
3. Exclude `H2` from archetype consideration
4. Apply the priority CASE statement to assign exactly one archetype per repo
5. Return one row per repo with these columns:

| Column | Description |
|---|---|
| `repo_name` | From `repos.name` |
| `archetype` | Assigned archetype string |
| `dependency_types` | Comma-separated list of resolved types for that repo (including H2 if present, for transparency) |
| `controller_count` | Number of controllers in that repo |
| `endpoint_count` | Number of endpoints across all controllers in that repo |

6. Order results by `archetype ASC`, then `repo_name ASC`

### Suggested Query Structure

Use CTEs for readability:

```sql
WITH
  latest_run AS (...),          -- isolates the max scan_run_id
  repo_marker_types AS (...),   -- dependency types from service_dependency_markers
  repo_datasource_types AS (...),-- dependency types from repo_datasources URL patterns
  repo_all_types AS (...),      -- union of both sources, deduplicated per repo
  repo_type_flags AS (...),     -- boolean flags per repo: has_kafka, has_api, etc.
  repo_counts AS (...)          -- controller_count and endpoint_count per repo
SELECT ...
FROM repos
JOIN latest_run ...
LEFT JOIN repo_type_flags ...
LEFT JOIN repo_counts ...
```

The CASE statement lives in the final SELECT, reading from `repo_type_flags`.

---

## Fixture Script (`test_archetype_fixture.sql`)

### Purpose
Populate a fresh SQLite database (`test.db`) with synthetic data, run the archetype query against it, 
and return results that can be manually verified against the expected archetype column.  There should be an example
for each archetype.

### Structure

The fixture script must:
1. Create all required tables (same schema as `scanner.db`)
2. Seed `dependency_classifications` with the standard lookup values
3. Insert one `scan_runs` row
4. Insert one synthetic repo per archetype case (see table below)
5. Insert supporting rows (controllers, endpoints, services, markers, datasources) to trigger the correct archetype for each repo
6. End with the full archetype query (identical to `archetype_report.sql`) so results are returned immediately on execution

### Fixture Repos — One Per Archetype

| Repo Name            | Expected Archetype         | How to Trigger                                                                     |
|----------------------|----------------------------|------------------------------------------------------------------------------------|
| `repo-mixed`         | `MIXED`                    | Markers for `JdbcTemplate`, `KafkaTemplate`, and `RestTemplate` (3 distinct types) |
| `repo-kafka`         | `KAFKA`                    | Marker for `KafkaTemplate` only                                                    |
| `repo-api`           | `UPSTREAM_REST_API`        | Marker for `RestTemplate` only                                                     |
| `repo-spanner`       | `SPANNER`                  | Marker for `SpannerTemplate` only                                                  |
| `repo-oracle`        | `ORACLE`                   | Marker for `OracleTemplate` only                                                   |
| `repo-postgres`      | `POSTGRES`                 | Marker for `PostgresTemplate` only                                                 |
| `repo-other-sql`     | `OTHER_SQL`                | Marker for `OtherSqlTemplate` only                                                 |
| `repo-h2-only`       | `NO_DEPENDENCIES_DETECTED` | Datasource URL `jdbc:h2:mem:testdb` only — H2 must not qualify as SQL              |
| `repo-no-deps`       | `NO_DEPENDENCIES_DETECTED` | Controller and endpoint present, no services or datasources                        |
| `repo-unclassified`  | `UNCLASSIFIED`             | Controller, endpoint present, services present but no datasources or dependencies  |

### Verification
After running the fixture script in IntelliJ, the result set must show each repo in the `repo_name` column alongside 
its expected archetype in the `archetype` column. No automated assertion mechanism is required — visual inspection 
against the expected table above is sufficient.

---

## Acceptance Criteria

- [ ] `archetype_report.sql` runs without error against `scanner.db` in IntelliJ
- [ ] Every repo in the latest scan appears in the results exactly once
- [ ] `test_archetype_fixture.sql` runs without error against a fresh `test.db` in IntelliJ
- [ ] Fixture results show all repos, each assigned the expected archetype
- [ ] `repo-h2-only` is classified as `NO_DEPENDENCIES_DETECTED`, not `OTHER_SQL` or `UPSTREAM_REST_API`
- [ ] `repo-mixed` is classified as `MIXED_COMPLEX` despite having Kafka (priority 1 wins)
- [ ] `repo-oracle-datasource` is classified as `ORACLE` using only datasource URL classification
- [ ] The `dependency_types` column in results includes H2 where present (for transparency), even though H2 is excluded from archetype logic
- [ ] Both files are plain `.sql` with no external dependencies