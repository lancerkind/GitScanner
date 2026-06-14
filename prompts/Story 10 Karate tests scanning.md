# Scan and Store Karate Test Files

## Context
This scanner collects and stores data only. It produces a brief console summary to confirm what was scanned.
All detailed reporting is handled by a separate program that queries the database directly. Do not implement verbose
or detailed reporting in the scanner.

This is a major new feature for the scanner. Consider if this story should be implemented in a seperate module since this implementation
is a seperate vertical for the scanner. Also consider refactoring the existing `count_spring_controllers.py` module to use this new feature
and other possible new scanning verticals.  Currently the verticles are: SpringBoot.  Karate will be the second one.

This extends the existing Spring Boot scanner (`count_spring_controllers.py`) which already scans GitLab and Github
repositories and stores controllers, endpoints, and parameters in `scanner.db`. We are adding a Karate test file scan so
that future stories can determine controller and endpoint test coverage, and track coverage growth over time.

---

## User Story
As an API initiative analyst, I want the scanner to discover and store Karate feature files and the paths they reference,
so that I can later determine which controllers and endpoints have test coverage and track how that coverage grows month
over month.

---

## Background and Conventions

### Karate Test Location
All Spring Boot repos store Karate tests under:
```
/src/test/java/
```
This path is fixed — no variation across repos.

### Controller-to-Directory Mapping
Each controller maps to a directory with the **exact same name** as the controller class (including the `Controller` suffix):

```
CatController.java  →  /src/test/java/.../CatController/
```
The `...` may be any intermediate package directories. The scanner should find the `CatController` directory anywhere beneath `/src/test/java/`.

### Feature Files
Karate tests are `.feature` files. All `.feature` files found within a controller's directory are considered candidate tests for that controller.

### Path Matching Convention
A feature file covers an endpoint if it contains the endpoint's path template or base path. Matching rules:

- Endpoint `GET /cats/{id}` → match if feature file contains `/cats/{id}` or `/cats/`
- Endpoint `POST /cats` → match if feature file contains `/cats`
- Match is **case-sensitive**
- Match is **substring-based** — the path just needs to appear somewhere in the file text
- The base URL (from `karate-config.js`) is **not** in the feature files and should be **ignored** — only the path portion is matched
- `karate-config.js` itself is **not scanned**

---

## Database Changes

Add the following two tables to the existing schema initialization:

```sql
CREATE TABLE IF NOT EXISTS karate_feature_files (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id         INTEGER NOT NULL REFERENCES repos(id),
    controller_id   INTEGER REFERENCES controllers(id),
    file_path       TEXT NOT NULL,
    file_name       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS karate_paths (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    feature_file_id INTEGER NOT NULL REFERENCES karate_feature_files(id),
    path            TEXT NOT NULL
);
```

### Notes on Schema Design

- `controller_id` on `karate_feature_files` is **nullable** — a feature file found under `/src/test/java/` but not inside a recognized controller directory is still stored, with `controller_id` set to `NULL`
- `karate_paths` stores each distinct path found in a feature file as a separate row — one feature file may reference multiple paths
- `file_path` stores the full path relative to the repo root (e.g. `src/test/java/com/example/CatController/get_cat.feature`)
- `file_name` stores just the filename (e.g. `get_cat.feature`)

---

## Scanning Logic

### Step 1 — Find All Feature Files
For each repo, recursively scan all files under `/src/test/java/`. Collect every file with a `.feature` extension.

### Step 2 — Associate Feature File to Controller
For each feature file found, check whether any segment of its path matches a known controller name for that repo (from the `controllers` table). For example:

```
src/test/java/com/example/CatController/get_cat.feature
```
The path segment `CatController` matches the controller named `CatController` → set `controller_id` accordingly.

If no path segment matches a known controller name, store the file with `controller_id = NULL`.

### Step 3 — Extract Paths from Feature File Content
For each feature file, scan its text content for path-like strings. A path-like string is defined as:

- Starts with `/`
- Followed by at least one non-whitespace character
- May contain path template variables in `{curly braces}`
- May contain Karate expression syntax (e.g. `#(variable)`) — store as-is, do not attempt to resolve

Extract each distinct path found and insert one row per path into `karate_paths`.

**Examples of paths to extract:**
```
/cats
/cats/{id}
/cats/#(catId)
/orders/{orderId}/items
```

**Do not extract:**
- The base URL (e.g. `https://api.example.com`) — only extract the path portion starting from `/`
- Duplicate paths within the same feature file — store each distinct path once per file

### Step 4 — Insert into Database
For each feature file:
1. Insert a row into `karate_feature_files`
2. For each extracted path, insert a row into `karate_paths` referencing the feature file

---

## Re-scan Behavior
On re-scan of a repo, delete and re-insert all `karate_feature_files` and `karate_paths` rows associated with that repo's `repo_id`, consistent with how controllers and endpoints are handled today.

---

## Report Changes

### Default Report (no flags)
Extend the existing per-repo summary line to include Karate file counts:

```text
----------------------------------------------------------------------
Breakdown by repository:
----------------------------------------------------------------------
coding_examples/spring-boot-app                      1 controllers  8 endpoints  5 feature files
gitlab-ci-examples1/gitlab-runner-spring-boot-demo   1 controllers  1 endpoints  0 feature files
```

---

## Edge Cases the Scanner Must Handle

1. **No `/src/test/java/` directory** — repo has no test directory at all; store nothing, do not error, report `0 feature files`
2. **Feature file not under any controller directory** — store with `controller_id = NULL`; do not include in verbose controller output
3. **Controller directory exists but contains no `.feature` files** — report `(none)` in verbose output
4. **Feature file references no extractable paths** — insert the `karate_feature_files` row but no `karate_paths` rows
5. **Same path appears multiple times in one feature file** — store it only once per file
6. **Feature file belongs to a directory matching a controller in a different repo** — association is always scoped to the current `repo_id`

---

## Acceptance Criteria

- [ ] `karate_feature_files` and `karate_paths` tables are created on startup if they do not exist
- [ ] All `.feature` files under `/src/test/java/` are discovered for each repo
- [ ] Feature files are correctly associated to controllers by directory name match
- [ ] Feature files with no matching controller are stored with `controller_id = NULL`
- [ ] Paths starting with `/` are extracted from feature file content and stored in `karate_paths`
- [ ] Duplicate paths within the same feature file are stored only once
- [ ] Re-scan cleanly replaces existing Karate data for a repo
- [ ] Default report shows feature file count per repo
- [ ] Query the database directly to determine if a feature file is associated with a controller
- [ ] Repos with no `/src/test/java/` directory report `0 feature files` without error
