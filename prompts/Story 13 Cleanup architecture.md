## Refactoring implementation instructions for agentic AI

Refactor `count_spring_controllers` from a single mixed-responsibility module into a small package architecture that separates CLI, repository orchestration, scanning capabilities, Spring Boot scanning, Karate scanning, persistence, and lightweight summary reporting.

The primary goal is to apply SOLID principles:

- **Single Responsibility:** each module/class should have one reason to change.
- **Open/Closed:** new scanners should be pluggable without editing orchestration logic heavily.
- **Dependency Inversion:** orchestration should depend on scanner/repository abstractions, not concrete Spring/Karate implementation details.
- **Interface Segregation:** scanners expose a small common API.
- **Liskov Substitution:** all scanners can be run through the same scanner pipeline contract.

Do **not** change user-facing CLI behavior unless explicitly required for compatibility. Preserve current test behavior by either updating tests to new modules or keeping backward-compatible import wrappers in `gitscanner.count_spring_controllers`.

---

## Desired package structure

Create or migrate toward this structure:

```plain text
gitscanner/
  __init__.py

  cli/
    __init__.py
    count_spring_controllers.py

  core/
    __init__.py
    models.py
    scanner.py
    scan_runner.py
    repository.py
    git.py

  persistence/
    __init__.py
    sqlite_store.py
    schema.py

  reporting/
    __init__.py
    summary.py

  scanners/
    __init__.py

    springboot/
      __init__.py
      controllers.py
      mappings.py
      parameters.py
      datasources.py
      services.py
      persistence.py

    karate/
      __init__.py
      features.py
      persistence.py
```


Keep `gitscanner/count_spring_controllers.py` as a compatibility facade initially. It should import and re-export the old public functions so existing tests and console entry points continue to work while the refactor lands safely.

---

## Target responsibilities

### 1. CLI package: `gitscanner.cli.count_spring_controllers`

Move CLI-only concerns here:

- argument parser creation
- CLI argument parsing
- reading repo file
- token lookup
- printing progress
- converting exceptions to process exit codes
- calling the scan runner
- printing summary output

Functions that belong here:

- `build_parser`
- `parse_cli_args`
- `read_repos_from_file`
- `main`

Keep CLI intentionally thin. It should not know how to scan Spring controllers, Karate files, datasources, or services.

Suggested CLI flow:

```python
def main(argv=None):
    args = parse_cli_args(sys.argv[1:] if argv is None else argv)
    repos = read_repos_from_file(args.repos_file)
    scanner_registry = default_scanners()
    runner = ScanRunner(...)
    scan_run_id, summary = runner.run(repos)
    print_summary(summary)
```


---

### 2. Core scanner API: `gitscanner.core.scanner`

Introduce a minimal scanner plugin API.

Suggested contract:

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Sequence, Any


@dataclass(frozen=True)
class ScanContext:
    repo_id: int
    repo_name: str
    repo_root: Path


@dataclass(frozen=True)
class ScanResult:
    capability: str
    records: Sequence[Any]


class RepoScanner(Protocol):
    capability: str

    def scan(self, context: ScanContext) -> ScanResult:
        ...
```


Use this API to plug in current and future capabilities.

Initial scanner capabilities:

- `springboot.controllers`
- `springboot.datasources`
- `springboot.service_dependencies`
- `karate.features`

The scan runner should accept a list of scanners:

```python
runner = ScanRunner(
    repository_client=...,
    store=...,
    scanners=[
        SpringControllerScanner(),
        KarateFeatureScanner(),
        SpringDatasourceScanner(),
        SpringServiceDependencyScanner(),
    ],
)
```


Adding a scanner later should mean:

1. Create a new scanner class.
2. Register it in `default_scanners()`.
3. Add persistence if needed.
4. Add tests.

The orchestration code should not need to know scanning internals.

---

### 3. Core scan orchestration: `gitscanner.core.scan_runner`

Move repository processing here.

Responsibilities:

- create database schema through store
- create scan run
- clone each repo
- insert repo row
- run all configured scanners
- persist scanner results
- cleanup cloned repo
- build final summary

This is the replacement for `process_repositories`.

Important: the runner should coordinate, not parse Java, parse Karate, parse YAML, or format output.

Suggested shape:

```python
class ScanRunner:
    def __init__(self, repository_client, store, scanners, reporter):
        ...

    def run(self, repos):
        scan_run_id = self.store.create_scan_run()
        for repo_name in repos:
            with self.repository_client.checkout(repo_name) as checkout:
                repo_id = self.store.insert_repo(scan_run_id, repo_name, checkout.clone_url)
                context = ScanContext(repo_id=repo_id, repo_name=repo_name, repo_root=checkout.path)

                for scanner in self.scanners:
                    result = scanner.scan(context)
                    self.store.save_scan_result(context, result)

        return scan_run_id, self.reporter.build_summary(scan_run_id)
```


For Python 3.9 compatibility, use normal classes or `Protocol` from `typing` if supported. Avoid newer syntax like `list[str]` if the project style needs Python 3.9 compatibility; prefer `List[str]` from `typing`.

---

### 4. Git/repository concerns: `gitscanner.core.git` and `gitscanner.core.repository`

Separate clone/auth/provider logic from scanning.

Move these functions:

- `build_provider_token`
- `build_token`
- `derive_clone_host`
- `build_clone_url`
- `build_github_headers`
- `build_gitlab_headers`
- `get_repo_info`
- `clone_and_count` logic, renamed to something like `GitRepositoryClient.checkout`

Suggested model:

```python
@dataclass
class RepoCheckout:
    repo_name: str
    clone_url: str
    path: Path
    cleanup_path: Optional[Path] = None
```


Create a context manager for cleanup:

```python
class GitRepositoryClient:
    def checkout(self, repo_name):
        ...
```


The Git client should **only** clone and cleanup. It should not count controllers or run scanners.

---

### 5. Spring Boot package: `gitscanner.scanners.springboot`

Move all Spring Boot-specific logic into this package.

#### `controllers.py`

Responsible for finding controller files and returning controller records.

Move/adapt:

- `count_controllers_in_directory`
- controller file discovery
- `@RestController` vs `@Controller` detection

Rename preferred public API:

```python
def scan_spring_controllers(repo_root):
    ...
```


Keep a compatibility alias:

```python
count_controllers_in_directory = scan_spring_controllers
```


#### `mappings.py`

Responsible for Spring mapping annotation parsing.

Move:

- `extract_controller_mappings`
- `extract_paths_from_annotation_args`
- `build_endpoints_from_annotation`
- mapping regex constants

#### `parameters.py`

Responsible for endpoint parameter parsing.

Move:

- `extract_endpoint_parameters`
- `build_parameter_from_definition`
- `extract_parameter_name`
- `extract_parameter_required`
- `split_top_level_commas`
- `find_matching_closing_parenthesis`

#### `datasources.py`

Responsible for application YAML scanning.

Move:

- `collect_application_yml_files`
- `strip_yaml_inline_comment`
- `normalize_yaml_value`
- `extract_datasource_urls_from_yaml_content`
- `collect_repo_datasources`

#### `services.py`

Responsible for controller service extraction and dependency marker scanning.

Move:

- `extract_controller_services`
- `extract_service_names_from_signature`
- `find_java_file_by_name`
- `find_markers_in_service_content`
- service dependency scanning logic

Avoid direct printing from scanner logic. Return warnings or structured results instead. CLI/reporting can decide whether to print them.

#### `persistence.py`

Responsible for persisting Spring Boot-specific records:

- controllers
- base paths
- endpoints
- parameters
- datasources
- controller services
- service dependency markers

Move:

- `insert_controllers`
- `insert_endpoints`
- `insert_parameters`
- `insert_repo_datasources`
- `insert_controller_service`
- `insert_service_dependency_markers`

---

### 6. Karate subpackage: `gitscanner.scanners.karate`

Karate scanning must be in a subpackage under `gitscanner`, not mixed with Spring Boot or CLI code.

#### `features.py`

Responsible only for Karate feature scanning/parsing.

Move:

- `collect_karate_feature_files`
- `extract_karate_paths`
- `find_controller_id_for_feature_file`, unless this becomes persistence/store logic
- high-level scanner class `KarateFeatureScanner`

The scanner should return feature file records like:

```python
{
    "file_path": "src/test/java/...",
    "file_name": "cat.feature",
    "controller_name_hint": "CatController",
    "paths": ["/cats", "/cats/{id}"],
}
```


Prefer avoiding direct database lookup inside scanner. The scanner should not need a sqlite connection.

Controller matching can happen in persistence/store code or in a small domain service that receives controller names.

#### `persistence.py`

Responsible for persisting Karate data:

- `insert_karate_feature_file`
- `insert_karate_paths`
- `insert_karate_data_for_repo`, or preferably split this so the scanner scans and persistence stores

Avoid a function that both scans files and writes to DB. That violates SRP.

---

### 7. Persistence package: `gitscanner.persistence`

Separate database schema and store operations from scanning.

#### `schema.py`

Move:

- `SCHEMA_STATEMENTS`
- `get_default_classifications`

#### `sqlite_store.py`

Move:

- `initialize_database`
- `seed_dependency_classifications`
- `create_scan_run`
- `insert_repo`
- capability-specific save methods
- helper query methods required by reporting

Suggested store API:

```python
class SQLiteScanStore:
    def initialize(self): ...
    def create_scan_run(self, notes=None): ...
    def insert_repo(self, scan_run_id, repo_name, url=None): ...
    def save_scan_result(self, context, result): ...
    def build_summary(self, scan_run_id): ...
```


It is acceptable for `save_scan_result` to dispatch based on `result.capability`.

Example:

```python
def save_scan_result(self, context, result):
    if result.capability == "springboot.controllers":
        self.insert_controllers(context.repo_id, result.records)
    elif result.capability == "karate.features":
        self.insert_karate_features(context.repo_id, result.records)
    ...
```


If that dispatch grows, move to capability-specific persisters later.

---

### 8. Reporting package: `gitscanner.reporting.summary`

Move lightweight summary reporting out of scanning and persistence.

Move:

- `build_summary_for_scan_run`, or wrap store queries behind reporter
- `format_summary_lines`
- `print_repo_dependency_summary`
- `print_service_not_found_warnings`, or replace with structured warnings

Recommended split:

- `SummaryReporter.build_summary(scan_run_id)` returns a dictionary or dataclass.
- `format_summary_lines(summary)` formats text.
- CLI prints the formatted lines.

Do not let scanners print summary output.

---

## Compatibility requirements

To reduce risk, keep `gitscanner.count_spring_controllers` as a facade that re-exports existing public API names used by tests and callers.

Example:

```python
from gitscanner.cli.count_spring_controllers import (
    build_parser,
    parse_cli_args,
    read_repos_from_file,
    main,
)

from gitscanner.core.git import (
    build_clone_url,
    build_github_headers,
    build_gitlab_headers,
    build_token,
    get_repo_info,
    clone_and_count,
)

from gitscanner.scanners.springboot.controllers import count_controllers_in_directory
from gitscanner.scanners.springboot.mappings import extract_controller_mappings
from gitscanner.scanners.springboot.datasources import (
    collect_repo_datasources,
    extract_datasource_urls_from_yaml_content,
)
from gitscanner.scanners.springboot.services import extract_controller_services
from gitscanner.scanners.karate.features import (
    collect_karate_feature_files,
    extract_karate_paths,
)
from gitscanner.persistence.sqlite_store import (
    initialize_database,
    create_scan_run,
    insert_repo,
)
from gitscanner.reporting.summary import (
    build_summary_for_scan_run,
    format_summary_lines,
)
```


This lets the implementation move without forcing all tests to be rewritten at once.

---

## Suggested implementation sequence

### Step 1: Establish package skeleton

Create empty packages and module files:

```plain text
gitscanner/cli
gitscanner/core
gitscanner/persistence
gitscanner/reporting
gitscanner/scanners/springboot
gitscanner/scanners/karate
```


Add `__init__.py` to each package.

Run:

```shell script
uv run pytest
```


No behavior should change yet.

---

### Step 2: Move pure parsing functions first

Move low-risk pure functions:

- Spring mapping parsing
- parameter parsing
- datasource YAML parsing
- Karate path extraction
- Karate feature file discovery

Keep imports/re-exports so existing tests pass.

Run:

```shell script
uv run pytest
```


---

### Step 3: Move persistence functions

Move schema and insert/query functions into `persistence`.

Keep wrapper imports in `count_spring_controllers`.

Run:

```shell script
uv run pytest
```


---

### Step 4: Move CLI functions

Move parser, CLI parsing, repo file reading, and `main`.

Keep wrapper imports.

Run:

```shell script
uv run pytest
```


---

### Step 5: Introduce scanner API and scanner classes

Add `RepoScanner`, `ScanContext`, and `ScanResult`.

Implement scanners:

- `SpringControllerScanner`
- `KarateFeatureScanner`
- `SpringDatasourceScanner`
- `SpringServiceDependencyScanner`

At first, these can wrap existing moved functions.

Run unit tests for scanner classes directly.

---

### Step 6: Refactor `process_repositories`

Replace the current orchestration with `ScanRunner`.

Keep `process_repositories(...)` as a compatibility wrapper that instantiates the default runner.

Important compatibility behavior to preserve:

- accepts `repos`
- accepts `api_base_url`
- accepts `provider`
- accepts `token`
- accepts `db_path`
- accepts injectable `clone_and_count_func`
- accepts injectable `sqlite_connect`
- returns `(scan_run_id, stats)`

Run:

```shell script
uv run pytest
```


---

### Step 7: Separate reporting

Move summary query and formatting to `reporting.summary`.

Ensure scanners do not print.

If repo-level dependency details still need to be shown, return warnings/metadata from the scanner and let CLI or reporting print them.

Run:

```shell script
uv run pytest
```


---

### Step 8: Update tests gradually

Prefer moving tests into focused test modules:

```plain text
tests/
  test_cli_count_spring_controllers.py
  test_git.py
  test_sqlite_store.py
  test_summary.py
  test_springboot_controllers.py
  test_springboot_mappings.py
  test_springboot_datasources.py
  test_springboot_services.py
  test_karate_features.py
  test_scan_runner.py
```


Existing tests can remain until the compatibility facade is stable.

---

## Acceptance criteria

The refactor is complete when:

1. `uv run pytest` passes.
2. Existing public imports from `gitscanner.count_spring_controllers` still work.
3. CLI behavior remains compatible:
```shell script
uv run count_spring_controllers github https://api.github.com github_repos.txt
```

   and:
```shell script
python -m gitscanner.cli.count_spring_controllers github https://api.github.com github_repos.txt
```

4. Karate scanning code lives under:
```plain text
gitscanner/scanners/karate/
```

5. Spring Boot scanning code lives under:
```plain text
gitscanner/scanners/springboot/
```

6. CLI code does not parse Java, YAML, Karate, or write scanner records directly.
7. Scanning orchestration can accept a list of scanner capabilities.
8. Adding a future scanner does not require modifying Spring Boot or Karate modules.
9. Summary formatting is in `gitscanner.reporting.summary`, not in scanner modules.
10. Database schema and persistence are isolated under `gitscanner.persistence`.
11. No new external dependency is introduced unless explicitly justified. If one is needed, add it with `uv`.

---

## Notes for the implementing AI

- Use small, behavior-preserving moves first.
- After each move, run the tests.
- Avoid broad rewrites of the parsing regex logic unless tests require it.
- Preserve current dict shapes for controllers, endpoints, parameters, Karate paths, datasource rows, and summary stats.
- Prefer dataclasses for internal orchestration models, but do not force public return values to change yet.
- Keep compatibility wrappers until all call sites and tests are migrated.
- Do not make scanners responsible for CLI output.
- Do not make CLI responsible for scanner internals.
- Do not make Karate depend on Spring Boot internals except through neutral matching data such as controller names.