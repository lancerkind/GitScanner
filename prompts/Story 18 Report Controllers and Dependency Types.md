# User Story: Controllers and Dependency Types SQL Report

## Title

Generate a Controllers and Dependency Types Report from the Latest Repo Scan

## User Story

As an architect or application analyst,  
I want a SQL report that lists each controller and its classified dependency types from the latest repository scan,  
So that I can understand which repositories and controllers depend on Kafka, APIs, Oracle, CloudSQL, and other dependency categories.

## Background

The scanner stores repository scan results in SQLite tables.

Relevant schema tables include:

- `scan_runs`
- `repos`
- `controllers`
- `controller_services`
- `service_dependency_markers`
- `dependency_classifications`

Dependency markers are stored in `service_dependency_markers.marker`.

Human-readable dependency categories are stored in `dependency_classifications.dependency_type`, keyed by `dependency_classifications.marker`.

Examples of default classifications include:

| marker | dependency_type |
|---|---|
| `kafka` | `Kafka` |
| `RestTemplate` | `API` |
| `WebClient` | `API` |
| `FeignClient` | `API` |
| `jdbc:oracle:` | `Oracle` |
| `jdbc:postgresql:` | `CloudSQL` |
| `cloudsql` | `CloudSQL` |
| `jdbc:mysql:` | `CloudSQL` |

## Scope

Create a new SQL report file:

```plain text
sql_reports/controllers_report.sql
```


The report should return controller dependency information for the **latest scan run only**.

## Report Output

The report should return the following columns:

| column | description |
|---|---|
| `repo` | Repository name from `repos.name` |
| `controller` | Controller name from `controllers.name` |
| `dependency` | Classified dependency type from `dependency_classifications.dependency_type` |

Example output:

| repo | controller | dependency |
|---|---|---|
| repository/here | controllerA | Kafka |
| repository/here | controllerA | API |
| repository/here | controllerB | Oracle |
| repository/another | controllerX | CloudSQL |

## Functional Requirements

### FR1: Use Latest Scan Only

The report must include data only from repositories associated with the latest scan run.

The latest scan run should be determined from `scan_runs.scanned_at`.

If multiple scan runs have the same latest `scanned_at`, the implementation should behave deterministically by using the highest `scan_runs.id` among those rows.

### FR2: Join Controllers to Dependency Markers

The report should traverse the schema as follows:

```plain text
scan_runs
  -> repos
  -> controllers
  -> controller_services
  -> service_dependency_markers
  -> dependency_classifications
```


### FR3: Classify Dependency Markers

The report should map each dependency marker to a dependency type using:

```sql
service_dependency_markers.marker = dependency_classifications.marker
```


The output should use `dependency_classifications.dependency_type`, not the raw marker.

### FR4: Multiple Dependencies Produce Multiple Rows

If a controller has more than one dependency marker that maps to dependency classifications, the report must return one row per dependency type.

Example:

| repo | controller | dependency |
|---|---|---|
| repository/here | controllerA | Kafka |
| repository/here | controllerA | API |

### FR5: Avoid Duplicate Rows

If multiple services or markers under the same controller resolve to the same dependency type, the report should return the dependency only once per repository/controller/dependency combination.

For example, if `controllerA` has both `RestTemplate` and `WebClient`, both classify as `API`, so the report should return only:

| repo | controller | dependency |
|---|---|---|
| repository/here | controllerA | API |

### FR6: Exclude Unclassified Markers

Markers that do not exist in `dependency_classifications` should not appear in the report.

### FR7: Exclude Scanner Difficulty Findings

The report should not include `NoDependency` or `UnknownService` unless they are explicitly classified in `dependency_classifications`.

In the current schema/default classification setup, they should not appear.

### FR8: Ordering

Results should be ordered by:

1. repository name
2. controller name
3. dependency type

## Acceptance Criteria

### AC1: SQL Report File Exists

A file exists at:

```plain text
sql_reports/controllers_report.sql
```


### AC2: Report Returns Latest Scan Only

Given an older scan run and a newer scan run,  
When `sql_reports/controllers_report.sql` is executed,  
Then rows from the older scan run are excluded.

### AC3: Report Returns One Row Per Controller Dependency Type

Given a controller with multiple dependency markers that classify to different dependency types,  
When the report is executed,  
Then the report returns one row per dependency type.

Example:

| repo | controller | dependency |
|---|---|---|
| repository/here | controllerA | Kafka |
| repository/here | controllerA | API |

### AC4: Report Deduplicates Same Dependency Type

Given a controller with multiple markers that classify to the same dependency type,  
When the report is executed,  
Then the report returns only one row for that dependency type.

Example markers:

| marker | dependency_type |
|---|---|
| `RestTemplate` | `API` |
| `WebClient` | `API` |

Expected report row:

| repo | controller | dependency |
|---|---|---|
| repository/here | controllerA | API |

### AC5: Report Excludes Unclassified Markers

Given a dependency marker that has no matching row in `dependency_classifications`,  
When the report is executed,  
Then that marker does not appear in the report.

### AC6: Report Is Sorted

Given multiple repositories, controllers, and dependency types,  
When the report is executed,  
Then rows are ordered by repository name, controller name, and dependency type.

## Suggested Test Coverage

Add a test file such as:

```plain text
tests/test_sql_reports_controllers_report.py
```


Add a SQL fixture such as:

```plain text
sql_reports/test_controllers_report_fixture.sql
```


The test should:

1. Create the relevant tables.
2. Insert at least two `scan_runs`.
3. Insert repositories for both old and latest scan runs.
4. Insert controllers for both old and latest repos.
5. Insert controller services.
6. Insert dependency markers.
7. Insert dependency classifications.
8. Execute `sql_reports/controllers_report.sql`.
9. Assert exact returned rows.

## Example Test Scenario

Fixture data should include:

### Older Scan

Should be excluded entirely.

| repo | controller | marker |
|---|---|---|
| old/repo | OldController | KafkaTemplate |

### Latest Scan

Should be included.

| repo | controller | markers |
|---|---|---|
| repository/here | controllerA | `kafka`, `RestTemplate`, `WebClient` |
| repository/here | controllerB | `jdbc:oracle:` |
| repository/another | controllerX | `jdbc:postgresql:` |
| repository/ignored | controllerY | `SomeUnclassifiedMarker` |

Expected report rows:

| repo | controller | dependency |
|---|---|---|
| repository/another | controllerX | CloudSQL |
| repository/here | controllerA | API |
| repository/here | controllerA | Kafka |
| repository/here | controllerB | Oracle |

Notes:

- `RestTemplate` and `WebClient` both classify as `API`, so only one `API` row should appear for `controllerA`.
- `SomeUnclassifiedMarker` should be excluded.
- The older scan row should be excluded.

## Implementation Notes

The report can likely be implemented as a single SQL query using:

- a common table expression to identify the latest scan run
- joins across the schema tables
- `DISTINCT` to deduplicate controller/dependency combinations
- an inner join to `dependency_classifications` to exclude unclassified markers

The report should be executable directly with SQLite, for example:

```python
import sqlite3
from pathlib import Path

conn = sqlite3.connect("gitscanner.db")
sql = Path("sql_reports/controllers_report.sql").read_text(encoding="utf-8")
rows = conn.execute(sql).fetchall()
```


## Definition of Done

- [ ] `sql_reports/controllers_report.sql` exists.
- [ ] Report returns columns: `repo`, `controller`, `dependency`.
- [ ] Report uses only the latest scan run.
- [ ] Report returns one row per repository/controller/dependency type.
- [ ] Report deduplicates repeated dependency types for the same controller.
- [ ] Report excludes unclassified dependency markers.
- [ ] Report output is ordered by repository, controller, and dependency.
- [ ] Unit tests cover latest-scan filtering, multiple dependencies, deduplication, and unclassified marker exclusion.