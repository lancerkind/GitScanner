# Story 4.6 Refactor to Sql Lite

By default, create/use a SQLite database file named `gitscanner.db` in the current working directory.

# Schema
CREATE TABLE scan_runs (
    scan_id     INTEGER PRIMARY KEY,
    id          INTEGER PRIMARY KEY,
    scanned_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes       TEXT NULL
);

CREATE TABLE repos (
    id          INTEGER PRIMARY KEY,
    scan_run_id INTEGER REFERENCES scan_runs(id),
    name        TEXT,      -- "coding_examples/spring-boot-app"
    url         TEXT
);

CREATE TABLE controllers (
    id          INTEGER PRIMARY KEY,
    repo_id     INTEGER REFERENCES repos(id),
    name        TEXT,      -- Java file stem, e.g., "CatController" from "CatController.java"
    base_path   TEXT       -- May be NULL unless it can be trivially detected
    type        TEXT       -- Should be either "RestController" or "Controller"
);

## Requirements

- Each execution of `count_spring_controllers` creates exactly one row in `scan_runs`.
- All repositories scanned during that execution are associated with that scan run through `repos.scan_run_id`.
- After a scan completes, summary totals and per-repository breakdowns must be generated from SQLite data, not from in-memory counters.
- The CLI report should use only the current scan run created by that command invocation.
- If a Java file contains both `@RestController` and `@Controller`, store one controller row with type `RestController`.
- The human-readable stdout format produced by `count_spring_controllers` should remain unchanged, except that the 
values are derived from SQLite after persistence.
- Existing tests should continue to pass.
- Adding extra stdout lines for database setup or persistence is allowed.
- On startup, the application should create the SQLite database and required tables if they do not already exist.
- Use Python's standard library `sqlite3` module. Do not add external dependencies.
Use `CREATE TABLE IF NOT EXISTS` for this story.
- Do not add additional dependencies or migration frameworks.
Additional indexes are optional but not required for this story.
- Use a transaction per repository so successfully scanned repositories are persisted even if a later repository fails.
- Add DB tests for:
  - creating the SQLite schema
  - inserting a scan run
  - inserting repos associated with a scan run
  - inserting controller rows associated with repos
  - generating summary totals from SQLite
  - ensuring existing report output remains unchanged
- DB Tests should use temporary SQLite database files or in-memory SQLite databases.
- Remove existing model/dataclass objects if they are not useful or add unnecessary complexity.