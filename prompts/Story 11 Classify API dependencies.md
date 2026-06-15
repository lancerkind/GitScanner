# Scan and Store Service Dependencies for Spring Boot Controllers

## Context
This extends the existing Spring Boot scanner (`count_spring_controllers.py`) which already scans GitLab repositories 
and stores controllers, endpoints, parameters, and Karate feature files in `scanner.db`. We are adding a dependency 
scan that traces which external systems (Oracle, CloudSQL, Spanner, Kafka, API) each controller depends on by following
one hop through its injected Services.

---

## User Story
As an API initiative analyst, I want the scanner to discover and store the upstream dependencies of each Spring Boot 
controller's Services, so that I can understand which external systems each API depends on and track how that 
changes over time.

---

## Design Principles
- The scanner collects and stores data only. No verbose or detailed reporting is produced. A brief console summary 
confirms what was scanned.
- All detailed reporting is handled by a separate program that queries the database directly.
- Each scan run is a complete, independent snapshot. Nothing from a previous scan is deleted or overwritten. 
Historical data accumulates across runs to support month-over-month trending.
- Raw dependency markers are stored as found in source code. Classification of those markers into dependency types is 
handled by a separate mapping table (`dependency_classifications`), so classifications can be updated without re-scanning.
- `dependency_classifications` is a shared lookup table. It exists outside the scan run model — there is only ever one 
copy, shared across all scan runs. It is pre-seeded at startup and can be extended manually via DB tools.

---

## Background and Conventions

### Dependency Chain
The scanner traces one hop from Controller to Service:
```
Controller  →  injected or instantiated Service(s)  →  dependency markers
```
It does not follow Services that inject other Services (no two-hop traversal).

### Service Injection and Instantiation Styles
All four Spring Boot styles must be handled:

```java
// Style 1 — Field injection
@Autowired
private CatService catService;

// Style 2 — Constructor injection
public CatController(CatService catService) { ... }

// Style 3 — Setter injection
@Autowired
public void setCatService(CatService catService) { ... }

// Style 4 — Direct instantiation
private CatService catService = new CatService();
```

### Dependency Markers in Services
The scanner looks for these specific classes and annotations in Service files:

| Marker | Dependency Type |
|---|---|
| `JdbcTemplate` | SQL Database (refined by datasource URL) |
| `JpaRepository` | SQL Database (refined by datasource URL) |
| `CrudRepository` | SQL Database (refined by datasource URL) |
| `SpannerTemplate` | Spanner |
| `SpannerRepository` | Spanner |
| `KafkaTemplate` | Kafka |
| `KafkaListener` | Kafka |
| `RestTemplate` | API |
| `WebClient` | API |
| `FeignClient` | API |

### Datasource Classification
The datasource type is determined from the URL value found in `application*.yml` files:

| URL Pattern | Classification      |
|---|---------------------|
| `jdbc:oracle:` | Oracle              |
| `jdbc:postgresql:` | CloudSQL            |
| `cloudsql` | CloudSQL            |
| `jdbc:mysql:` | CloudSQL            |
| `jdbc:h2:` | H2 (in-memory/test) |
| `jdbc:sqlserver:` | MS SQL Server       |

---

## Classification Pre-Seed Function

All marker-to-type and URL-to-type mappings must live in a single dedicated function, called at startup. This function is the only place classifications are defined — it must be easy to extend as new markers are discovered across repos.

```python
def get_default_classifications():
    """
    Returns all known dependency marker classifications.
    Add new entries here as new markers are discovered.
    Each entry is (marker, dependency_type).
    """
    return [
        # SQL - resolved further by datasource URL
        ("JdbcTemplate",        "SQL Database"),
        ("JpaRepository",       "SQL Database"),
        ("CrudRepository",      "SQL Database"),
        # Spanner
        ("SpannerTemplate",     "Spanner"),
        ("SpannerRepository",   "Spanner"),
        # Kafka
        ("KafkaTemplate",       "Kafka"),
        ("KafkaListener",       "Kafka"),
        # API
        ("RestTemplate",        "API"),
        ("WebClient",           "API"),
        ("FeignClient",         "API"),
        # Datasource URL patterns
        ("jdbc:oracle:",        "Oracle"),
        ("jdbc:postgresql:",    "CloudSQL"),
        ("cloudsql",            "CloudSQL"),
        ("jdbc:mysql:",         "CloudSQL"),
        ("jdbc:h2:",            "H2"),
        ("jdbc:sqlserver:",     "SQL Server"),
    ]
```

### Startup Behavior
On every startup, the scanner calls this function and inserts any classifications not already present in `dependency_classifications` using `INSERT OR IGNORE`. It does **not** overwrite or delete existing rows — this preserves any manual corrections made via DB tools.

---

## Database Changes

Add the following four tables:

```sql
-- Datasource URLs found in application*.yml files
CREATE TABLE IF NOT EXISTS repo_datasources (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id         INTEGER NOT NULL REFERENCES repos(id),
    source_file     TEXT NOT NULL,   -- e.g. "application.yml", "application-local.yml"
    url             TEXT NOT NULL    -- full datasource URL value as found
);

-- Services discovered as injected into or instantiated in controllers
CREATE TABLE IF NOT EXISTS controller_services (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    controller_id   INTEGER NOT NULL REFERENCES controllers(id),
    service_name    TEXT NOT NULL,   -- e.g. "CatService"
    found           BOOLEAN NOT NULL -- false if CatService.java could not be located
);

-- Raw dependency markers found in Service source files
CREATE TABLE IF NOT EXISTS service_dependency_markers (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    controller_service_id INTEGER NOT NULL REFERENCES controller_services(id),
    marker                TEXT NOT NULL    -- e.g. "JdbcTemplate", "KafkaTemplate"
);

-- Classification mapping: marker or URL pattern → dependency type
-- Pre-seeded at startup; can be extended manually via DB tools
-- Shared across all scan runs — there is only one copy of this table
CREATE TABLE IF NOT EXISTS dependency_classifications (
    marker          TEXT PRIMARY KEY,
    dependency_type TEXT NOT NULL    -- e.g. "Oracle", "Kafka", "API"
);
```

---

## Scanning Logic

### Step 1 — Scan application*.yml for Datasources
For each repo, find all files matching `application*.yml` anywhere in the repo. For each file:

1. Parse the YAML content
2. Look for a datasource URL in any of these structures:

```yaml
# Standard Spring Boot
spring:
  datasource:
    url: jdbc:oracle:thin:@//hostname:1521/mydb

# Alternate structure
env:
  spring:
    datasource:
      url: jdbc:oracle:thin:@//hostname:1521/mydb

# Flat alternate structure
env.spring.datasource.url: jdbc:oracle:thin:@//hostname:1521/mydb
```

3. If a URL is found, insert a row into `repo_datasources` with the source filename and URL value
4. If a file contains no datasource URL, skip it silently
5. Store **all** datasource URLs found across all `application*.yml` files — do not stop at the first one found

### Step 2 — Find Services in Each Controller
For each controller already stored in the `controllers` table, scan its source file for Services using all four styles:

```java
// Style 1 — Field injection
@Autowired
private CatService catService;

// Style 2 — Constructor injection
public CatController(CatService catService) { ... }

// Style 3 — Setter injection
@Autowired
public void setCatService(CatService catService) { ... }

// Style 4 — Direct instantiation
private CatService catService = new CatService();
```

For each discovered type whose name ends in `Service`, insert a row into `controller_services`. 
Only follow types ending in `Service` — skip all others.

### Step 3 — Locate and Scan Each Service File
For each row in `controller_services`:

1. Search the repo for a `.java` file whose name matches `{service_name}.java` (e.g. `CatService.java`)
2. If **not found**: update the `controller_services` row with `found = false`; do not error; log a console warning:
```
WARNING: CatService.java not found in repo coding_examples/spring-boot-app
```
3. If **found**: set `found = true` and scan the file content for any marker present in `dependency_classifications`. 
For each marker found, insert a row into `service_dependency_markers`. 
If the same marker appears more than once in the file, store it only once per `controller_service_id`.

### Step 4 — Insert Classifications at Startup
On startup, call `get_default_classifications()` and for each entry insert into `dependency_classifications` where 
the marker does not already exist:

```sql
INSERT OR IGNORE INTO dependency_classifications (marker, dependency_type)
VALUES (?, ?);
```

---

## Console Summary
The scanner prints a brief summary after completing each repo:

```text
coding_examples/spring-boot-app
  Datasources found:     2 (application.yml, application-local.yml)
  Services scanned:      3
  Services not found:    1 (see warnings above)
  Dependency markers:    5
```

---

## Edge Cases the Scanner Must Handle

1. **No `application*.yml` files** — store nothing in `repo_datasources`; do not error
2. **`application*.yml` exists but has no datasource URL** — skip the file silently
3. **Multiple `application*.yml` files with datasource URLs** — store all of them with their source filename
4. **`application-local.yml` contains H2 URL** — store it; let reporting logic or manual review resolve 
conflicts with other datasource entries for the same repo
5. **All three YAML datasource structures** — all must be recognized; store whichever URL(s) are found
6. **Service file not found** — store the row with `found = false`; log a console warning; continue scanning
7. **Same marker appears multiple times in one Service file** — store it only once per `controller_service_id`
8. **Controller references a type not ending in `Service`** — skip it
9. **New classification added to `get_default_classifications()`** — inserted at next startup via `INSERT OR IGNORE` 
without requiring a re-scan
10. **Manual edits to `dependency_classifications`** — preserved across startups; never overwritten

---

## Acceptance Criteria

- [ ] `repo_datasources`, `controller_services`, `service_dependency_markers`, and `dependency_classifications` 
tables created on startup if they do not exist
- [ ] `get_default_classifications()` is the single source of truth for all marker and URL pattern classifications
- [ ] New classifications in `get_default_classifications()` are inserted at startup without overwriting manual edits
- [ ] All three YAML datasource structures are recognized and parsed correctly
- [ ] All `application*.yml` files are scanned; all datasource URLs stored with their source filename
- [ ] All four Service styles (field injection, constructor injection, setter injection, direct instantiation) are recognized
- [ ] Only types ending in `Service` are followed
- [ ] Service files are located by filename match anywhere in the repo
- [ ] Services not found are stored with `found = false` and a console warning is printed
- [ ] Duplicate markers within the same Service file are stored only once
- [ ] Each scan run is fully independent — no data from previous scans is modified
- [ ] Console summary is printed per repo after scanning
- [ ] Unit tests are added to ensure correctness of the implementation
- [ ] Code coverage is at least 80%
