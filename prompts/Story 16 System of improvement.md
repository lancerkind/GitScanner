# System of improvement
When the scanner cannot find services or dependencies, collect that status in the database so I can investigate if there
is a problem. 
We'll use the existing tables.  These situations are merely tracked and won't cause the scanner to stop. 

# Situations of scanning difficulty
- For each discovered controller, if the scanner stores zero associated controller service records for that controller, 
record a finding with type `UnknownService` in `controller_services` table so I can 
identify the repository, controller, and service that need investigation.  (This looks like it's already implemented.)
- Add a `NoDependency` to the `service_dependency_markers` table. For each discovered controller-service association, 
if the scanner stores zero dependency marker records for that service association, record a finding with type
`NoDependency` so that I can later use the persisted data to go back to the repository and controller and service 
to investigate if there is a problem.

# Reporting of 

Add a SQL report:

`sql_reports/scanner_findings_report.sql`

The report should return a table using the latest scan run, listing the following for repositories and controllers
associated with a service name of `UnknownService` or associated with a `service_dependency_markers` of `NoDependency`:
Example:
| scan date | repository name | controller name | service name | service dependency marker |
|-----------|-----------------|-----------------|--------------|---------------------------|
|2026-01-01 | repo1           | controller1     | UnknownService | NoDependency              |
|2026-01-01 | repo2           | controller2     | ServiceA       | NoDependency              |  


Results should be ordered by repository name, controller name, and service name.

# Acceptance tests
- add unit tests for both situtations: UnknownService, NoDependency.
- repo with controller and no services
- repo with controller, service, and no dependency markers
- repo with controller, service, and dependency markers
- scanner should continue and complete normally
- A report exists at `sql_reports/scanner_findings_report.sql`.
- Tests or fixtures cover both finding types and a no-finding success case.

