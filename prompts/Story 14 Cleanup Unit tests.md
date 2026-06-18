# Story 14 Refactor Unit Tests to Target Refactored Architecture

## Refactoring implementation instructions for agentic AI

The previous architecture cleanup introduced package boundaries and compatibility facades, but the unit tests still primarily import and exercise `gitscanner.count_spring_controllers`. That means the tests can pass while the refactored modules are only thin wrappers around the legacy facade, leaving the new architecture insufficiently verified.

Refactor the unit tests so they directly test the refactored code in its intended modules:

- CLI behavior through `gitscanner.cli.count_spring_controllers`
- Git/provider behavior through `gitscanner.core.git`
- repository checkout abstraction through `gitscanner.core.repository`
- scan orchestration through `gitscanner.core.scan_runner`
- scanner contracts through `gitscanner.core.scanner` and `gitscanner.core.models`
- Spring Boot parsing/scanning through `gitscanner.scanners.springboot.*`
- Karate scanning through `gitscanner.scanners.karate.*`
- persistence through `gitscanner.persistence.*`
- summary reporting through `gitscanner.reporting.summary`

The compatibility facade `gitscanner.count_spring_controllers` should still have a small dedicated test file, but only to verify backwards-compatible exports and legacy entry points. It should no longer be the main unit test target.

---

## Goal

Move the unit test suite from facade-based coverage to architecture-based coverage.

The refactored test suite should make it obvious when:

1. a scanner module is not implemented and only delegates to legacy code,
2. orchestration bypasses the scanner pipeline,
3. persistence is still mixed with scanning,
4. CLI code contains parsing/scanning/database responsibilities,
5. Karate or Spring Boot modules depend on the compatibility facade,
6. compatibility imports work but new modules do not.

---

## Desired test file structure

Refactor the current broad test file into focused modules:

```
tests/
  __init__.py

  test_compat_count_spring_controllers.py

  test_cli_count_spring_controllers.py

  test_core_git.py
  test_core_repository.py
  test_core_scan_runner.py
  test_core_scanner_contract.py

  test_persistence_sqlite_store.py
  test_persistence_schema.py

  test_reporting_summary.py

  test_springboot_controllers.py
  test_springboot_mappings.py
  test_springboot_parameters.py
  test_springboot_datasources.py
  test_springboot_services.py
  test_springboot_scanners.py

  test_karate_features.py
  test_karate_scanners.py
  test_karate_persistence.py
```


It is acceptable to create fewer files if some modules do not exist yet, but tests should still be organized by architectural responsibility rather than by the old monolithic facade.

---

## Import rules for the refactored tests

### Primary rule

Tests must import the code under test from the module that owns the responsibility.

For example:

```python
from gitscanner.scanners.springboot.controllers import count_controllers_in_directory
from gitscanner.scanners.springboot.datasources import collect_repo_datasources
from gitscanner.scanners.karate.features import collect_karate_feature_files
from gitscanner.persistence.sqlite_store import SqliteStore
from gitscanner.core.scan_runner import ScanRunner
```


### Do not use the facade except in compatibility tests

Only `tests/test_compat_count_spring_controllers.py` should import from:

```python
from gitscanner import count_spring_controllers
from gitscanner.count_spring_controllers import ...
```


All other test modules should avoid importing from `gitscanner.count_spring_controllers`.

### Add a guard test

Add a test that fails if non-compat tests import the facade.

Suggested approach:

```python
from pathlib import Path


def test_non_compat_tests_do_not_import_legacy_facade():
    tests_dir = Path(__file__).parent
    offenders = []

    for test_file in tests_dir.glob("test_*.py"):
        if test_file.name == "test_compat_count_spring_controllers.py":
            continue

        content = test_file.read_text(encoding="utf-8")
        forbidden_imports = [
            "from gitscanner.count_spring_controllers import",
            "from gitscanner import count_spring_controllers",
            "import gitscanner.count_spring_controllers",
        ]

        if any(pattern in content for pattern in forbidden_imports):
            offenders.append(test_file.name)

    assert offenders == []
```


Place this in a small test file such as:

```
tests/test_architecture_imports.py
```


---

## Test migration map

Move existing tests according to the responsibility they verify.

### CLI tests

Move to:

```
tests/test_cli_count_spring_controllers.py
```


Import from:

```python
from gitscanner.cli.count_spring_controllers import (
    build_parser,
    parse_cli_args,
    read_repos_from_file,
    main,
)
```


Tests to move or adapt:

- CLI argument parsing
- provider option parsing
- no-args usage output
- required provider validation
- repo file reading
- missing repo file errors
- `main` success behavior
- `main` runtime-error behavior

The CLI tests should mock orchestration at the CLI boundary. They should not validate Java parsing, Karate scanning, or database insert details.

Acceptance criteria for CLI tests:

1. CLI tests import only the CLI module and supporting standard library/test utilities.
2. CLI tests verify that `main` calls the runner/process boundary with parsed arguments.
3. CLI tests do not import scanner modules unless testing scanner registration behavior explicitly.
4. CLI tests do not directly assert database schema or scanner output.

---

### Git/provider tests

Move to:

```
tests/test_core_git.py
```


Import from:

```python
from gitscanner.core.git import (
    build_clone_url,
    build_gitlab_headers,
    build_github_headers,
    build_token,
    get_repo_info,
    clone_and_count,
)
```


Tests to move or adapt:

- GitHub headers with explicit token
- GitHub headers with environment token
- GitLab headers with explicit token
- GitLab headers with environment token
- GitHub clone URL generation
- GitLab clone URL generation
- custom host clone URL generation
- successful repo API payload
- non-200 repo API response
- clone timeout wrapping
- clone failure wrapping

Acceptance criteria:

1. Provider/auth tests do not import CLI or scanner modules.
2. `clone_and_count` tests verify checkout/clone behavior only.
3. If `clone_and_count` remains as a compatibility name, also test the preferred repository abstraction separately.

---

### Repository client tests

Create:

```
tests/test_core_repository.py
```


Import from:

```python
from pathlib import Path

from gitscanner.core.repository import RepositoryClient, RepositoryCheckout
```


Add tests that verify:

1. `RepositoryClient.checkout()` calls the injected clone function with:
   - `repo_name`
   - `api_base_url`
   - `provider`
   - `token`

2. `checkout()` returns a `RepositoryCheckout`.

3. `checkout.path` is a `Path`.

4. `checkout.clone_url` is populated from the clone result.

Example behavior:

```python
def test_repository_client_checkout_wraps_clone_result(tmp_path):
    def fake_clone(repo_name, api_base_url, provider="github", token=None):
        assert repo_name == "org/repo"
        assert api_base_url == "https://gitlab.example.com/api/v4"
        assert provider == "gitlab"
        assert token == "secret"
        return {
            "path": str(tmp_path / "repo"),
            "clone_url": "https://gitlab.example.com/org/repo.git",
        }

    client = RepositoryClient(clone_and_count_func=fake_clone)

    checkout = client.checkout(
        "org/repo",
        api_base_url="https://gitlab.example.com/api/v4",
        provider="gitlab",
        token="secret",
    )

    assert isinstance(checkout, RepositoryCheckout)
    assert checkout.path == tmp_path / "repo"
    assert checkout.clone_url == "https://gitlab.example.com/org/repo.git"
```


---

### Scan runner tests

Create:

```
tests/test_core_scan_runner.py
```


Import from:

```python
from pathlib import Path

from gitscanner.core.models import ScanContext, ScanResult
from gitscanner.core.scan_runner import ScanRunner
```


Test scan orchestration directly with fakes.

Do not use sqlite or real scanners in these tests.

Use fake classes:

```python
class FakeRepositoryClient:
    def __init__(self, root):
        self.root = root
        self.calls = []

    def checkout(self, repo_name, api_base_url, provider, token):
        self.calls.append((repo_name, api_base_url, provider, token))
        return type(
            "Checkout",
            (),
            {
                "path": self.root / repo_name.replace("/", "_"),
                "clone_url": f"https://example.com/{repo_name}.git",
            },
        )()


class FakeStore:
    def __init__(self):
        self.initialized = False
        self.scan_runs = []
        self.repos = []
        self.saved_results = []

    def initialize_database(self):
        self.initialized = True

    def create_scan_run(self):
        self.scan_runs.append("created")
        return 123

    def insert_repo(self, scan_run_id, repo_name, url):
        repo_id = len(self.repos) + 1
        self.repos.append((repo_id, scan_run_id, repo_name, url))
        return repo_id

    def save_scan_result(self, context, result):
        self.saved_results.append((context, result))


class FakeScanner:
    capability = "fake.capability"

    def __init__(self):
        self.contexts = []

    def scan(self, context):
        self.contexts.append(context)
        return ScanResult(self.capability, [{"repo": context.repo_name}])


class FakeReporter:
    def build_summary(self, scan_run_id):
        return {"scan_run_id": scan_run_id}
```


Test expectations:

1. database initialization happens once,
2. scan run is created once,
3. every repo is checked out,
4. every scanner receives a `ScanContext`,
5. `store.save_scan_result()` receives each scanner result,
6. reporter builds summary from the returned scan run ID,
7. `run()` returns `(scan_run_id, summary)`.

Also add a test with multiple scanners to prove the runner is scanner-agnostic.

Acceptance criteria:

1. `ScanRunner` tests do not depend on Spring Boot, Karate, sqlite, CLI, or the facade.
2. Scanner order is preserved.
3. `ScanContext` contains the inserted repo ID, repo name, and checkout path.
4. Adding a new fake scanner does not require changing runner logic.

---

### Scanner contract tests

Create:

```
tests/test_core_scanner_contract.py
```


Import from:

```python
from pathlib import Path

from gitscanner.core.models import ScanContext, ScanResult
```


Verify basic model behavior:

- `ScanContext` stores repo ID/name/root.
- `ScanResult` stores capability and records.
- scanner classes return `ScanResult`, not raw lists, where applicable.

If concrete scanner classes exist, use parameterized tests:

```python
import pytest

from gitscanner.scanners.springboot.controllers import SpringControllerScanner
from gitscanner.scanners.springboot.datasources import SpringDatasourceScanner
from gitscanner.scanners.karate.features import KarateFeatureScanner


@pytest.mark.parametrize(
    "scanner,capability",
    [
        (SpringControllerScanner(), "springboot.controllers"),
        (SpringDatasourceScanner(), "springboot.datasources"),
        (KarateFeatureScanner(), "karate.features"),
    ],
)
def test_scanner_returns_scan_result(scanner, capability, tmp_path):
    context = ScanContext(repo_id=1, repo_name="org/repo", repo_root=tmp_path)

    result = scanner.scan(context)

    assert isinstance(result, ScanResult)
    assert result.capability == capability
    assert isinstance(result.records, list)
```


Only include concrete scanner classes that currently exist.

---

## Spring Boot test modules

### Controller scanning tests

Move controller discovery and endpoint extraction tests to:

```
tests/test_springboot_controllers.py
```


Import from:

```python
from gitscanner.scanners.springboot.controllers import (
    count_controllers_in_directory,
    scan_spring_controllers,
)
```


Tests to move or adapt:

- counts `@RestController` and `@Controller`
- prefers `@RestController` when both annotations are present
- extracts base path and endpoints
- handles multiple request mappings
- extracts annotations without arguments
- supports `path = ...`
- supports static import request methods
- supports multiple paths per mapping
- supports multiple request methods
- ignores unreadable files

Add a direct scanner-class test if `SpringControllerScanner` exists:

```python
from gitscanner.core.models import ScanContext
from gitscanner.scanners.springboot.controllers import SpringControllerScanner


def test_spring_controller_scanner_returns_controller_scan_result(tmp_path):
    (tmp_path / "CatController.java").write_text(
        "@RestController class CatController {}",
        encoding="utf-8",
    )

    scanner = SpringControllerScanner()
    result = scanner.scan(ScanContext(repo_id=1, repo_name="org/repo", repo_root=tmp_path))

    assert result.capability == "springboot.controllers"
    assert result.records == [
        {
            "name": "CatController",
            "base_path": None,
            "type": "RestController",
            "endpoints": [],
        }
    ]
```


---

### Mapping parsing tests

Create:

```
tests/test_springboot_mappings.py
```


Import mapping-specific functions from:

```python
from gitscanner.scanners.springboot.mappings import (
    extract_controller_mappings,
    extract_paths_from_annotation_args,
    build_endpoints_from_annotation,
)
```


Move mapping-specific expectations out of controller tests where possible.

Cover:

- `@GetMapping`
- `@PostMapping`
- `@PutMapping`
- `@DeleteMapping`
- `@PatchMapping`
- `@RequestMapping`
- no-argument mapping annotations
- `value =`
- `path =`
- array path syntax
- multiple HTTP methods
- static imported request methods
- `RequestMethod.GET` style request methods

Keep controller file discovery tests separate from annotation parsing tests.

---

### Parameter parsing tests

Create:

```
tests/test_springboot_parameters.py
```


Import from:

```python
from gitscanner.scanners.springboot.parameters import (
    extract_endpoint_parameters,
    split_top_level_commas,
    find_matching_closing_parenthesis,
)
```


Cover:

- `@PathVariable`
- `@RequestParam`
- `@RequestHeader`
- `@CookieValue`
- `@RequestBody`
- generic Java types such as `List<String>`
- required flags
- default values
- ignored framework parameters such as `Model` and `HttpServletRequest`
- splitting comma-separated method parameters while preserving nested annotation arguments

Acceptance criteria:

1. Parameter parsing tests do not need temporary Java files unless testing integration with controller scanning.
2. Pure parsing behavior is tested as pure function behavior.

---

### Datasource scanning tests

Move datasource tests to:

```
tests/test_springboot_datasources.py
```


Import from:

```python
from gitscanner.scanners.springboot.datasources import (
    collect_application_yml_files,
    collect_repo_datasources,
    extract_datasource_urls_from_yaml_content,
    normalize_yaml_value,
    strip_yaml_inline_comment,
)
```


Tests to move or adapt:

- nested `spring.datasource.url`
- nested `env.spring.datasource.url`
- flat `env.spring.datasource.url`
- `.yml` and `.yaml`
- `application.yml`
- `application.yaml`
- `application-*.yml`
- `application-*.yaml`
- ignore files outside expected resource locations if that is required behavior
- inline comment stripping
- quote normalization

Add scanner-class test if `SpringDatasourceScanner` exists:

```python
from gitscanner.core.models import ScanContext
from gitscanner.scanners.springboot.datasources import SpringDatasourceScanner


def test_spring_datasource_scanner_returns_datasource_scan_result(tmp_path):
    app = tmp_path / "src" / "main" / "resources" / "application.yml"
    app.parent.mkdir(parents=True)
    app.write_text(
        "spring:\n  datasource:\n    url: jdbc:h2:mem:test\n",
        encoding="utf-8",
    )

    result = SpringDatasourceScanner().scan(
        ScanContext(repo_id=1, repo_name="org/repo", repo_root=tmp_path)
    )

    assert result.capability == "springboot.datasources"
    assert result.records == [
        {
            "source_file": "src/main/resources/application.yml",
            "url": "jdbc:h2:mem:test",
        }
    ]
```


---

### Service dependency tests

Move service extraction tests to:

```
tests/test_springboot_services.py
```


Import from:

```python
from gitscanner.scanners.springboot.services import (
    extract_controller_services,
    extract_service_names_from_signature,
    find_java_file_by_name,
    find_markers_in_service_content,
)
```


Tests to move or adapt:

- `@Autowired private final` field
- package-private autowired field
- `@Autowired(required = false)`
- private final field without autowired
- deduplication
- marker detection for dependency technologies
- service file lookup by class name

Add scanner-class test if `SpringServiceDependencyScanner` exists.

Acceptance criteria:

1. Service parsing is tested without database access.
2. Scanner test returns structured records.
3. Persistence of service records is tested separately in sqlite tests.

---

### Spring scanner integration tests

Create:

```
tests/test_springboot_scanners.py
```


This file should test Spring scanner classes as plugins, not low-level parsing.

Import from concrete scanner modules:

```python
from gitscanner.core.models import ScanContext
from gitscanner.scanners.springboot.controllers import SpringControllerScanner
from gitscanner.scanners.springboot.datasources import SpringDatasourceScanner
from gitscanner.scanners.springboot.services import SpringServiceDependencyScanner
```


Test each scanner returns:

- a `ScanResult`
- the correct `capability`
- records in the expected shape

Do not use sqlite here.

---

## Karate test modules

### Karate feature parsing tests

Move Karate file/path tests to:

```
tests/test_karate_features.py
```


Import from:

```python
from gitscanner.scanners.karate.features import (
    collect_karate_feature_files,
    extract_karate_paths,
)
```


Tests to move or adapt:

- scans only `src/test/java`
- ignores `src/test/resources` if that is current behavior
- extracts distinct `path` values
- ignores full URLs
- preserves Karate expression paths like `#(catId)`
- handles repeated paths

If the module exposes feature-record scanning, add tests for that function too.

---

### Karate scanner tests

Create:

```
tests/test_karate_scanners.py
```


Import from:

```python
from gitscanner.core.models import ScanContext, ScanResult
from gitscanner.scanners.karate.features import KarateFeatureScanner
```


Test scanner behavior without sqlite.

Expected scanner output shape should be independent from database IDs where possible:

```python
def test_karate_feature_scanner_returns_feature_records(tmp_path):
    feature = tmp_path / "src" / "test" / "java" / "com" / "example" / "CatController" / "cat.feature"
    feature.parent.mkdir(parents=True)
    feature.write_text(
        "Feature: cats\nScenario: get cat\nGiven path '/cats/{id}'\n",
        encoding="utf-8",
    )

    result = KarateFeatureScanner().scan(
        ScanContext(repo_id=1, repo_name="org/repo", repo_root=tmp_path)
    )

    assert isinstance(result, ScanResult)
    assert result.capability == "karate.features"
    assert result.records == [
        {
            "file_path": "src/test/java/com/example/CatController/cat.feature",
            "file_name": "cat.feature",
            "controller_name_hint": "CatController",
            "paths": ["/cats/{id}"],
        }
    ]
```


If current implementation still returns `controller_id`, update the architecture or persistence boundary so scanner output does not require a database lookup. If that cannot be changed immediately, document the temporary behavior and add a follow-up task to remove database coupling from the scanner.

---

### Karate persistence tests

Create:

```
tests/test_karate_persistence.py
```


Import from:

```python
from gitscanner.persistence.sqlite_store import (
    initialize_database,
    create_scan_run,
    insert_repo,
    insert_controllers,
)
from gitscanner.scanners.karate.persistence import (
    insert_karate_feature_file,
    insert_karate_paths,
)
```


Or, if persistence remains exposed through `SqliteStore`, test:

```python
from gitscanner.core.models import ScanContext, ScanResult
from gitscanner.persistence.sqlite_store import SqliteStore
```


Test persistence behavior separately from scanning:

1. create sqlite schema,
2. insert repo,
3. insert controller,
4. save Karate feature records,
5. verify rows in `karate_feature_files` and `karate_paths`.

Do not create real `.feature` files in persistence tests. Use in-memory records.

---

## Persistence tests

### SQLite store tests

Move database schema and insert/query tests to:

```
tests/test_persistence_sqlite_store.py
```


Import from:

```python
from gitscanner.persistence.sqlite_store import (
    SqliteStore,
    initialize_database,
    create_scan_run,
    insert_repo,
    insert_controllers,
    insert_endpoints,
    insert_parameters,
    insert_repo_datasources,
    insert_controller_service,
    insert_service_dependency_markers,
    build_summary_for_scan_run,
)
```


Tests to move or adapt:

- schema creation
- scan run insertion
- repo insertion
- controller insertion
- endpoint insertion
- parameter insertion
- datasource insertion
- Karate persistence
- service dependency persistence
- summary query data integrity

Add tests for `SqliteStore.save_scan_result()` dispatch:

```python
from gitscanner.core.models import ScanContext, ScanResult
from gitscanner.persistence.sqlite_store import SqliteStore


def test_sqlite_store_save_scan_result_dispatches_controllers():
    # arrange in-memory sqlite
    # create scan/repo
    # save ScanResult("springboot.controllers", records)
    # assert controller rows exist
```


Test all supported capabilities:

- `springboot.controllers`
- `karate.features`
- `springboot.datasources`
- `springboot.service_dependencies`

Also add a test for unknown capability behavior. Prefer explicit failure:

```python
import pytest


def test_sqlite_store_save_scan_result_rejects_unknown_capability():
    store = SqliteStore(conn)
    context = ScanContext(repo_id=1, repo_name="org/repo", repo_root=Path("."))

    with pytest.raises(ValueError, match="Unsupported scan capability"):
        store.save_scan_result(context, ScanResult("unknown.capability", []))
```


If current behavior silently ignores unknown capabilities, update implementation to raise a clear error. Silent ignore makes scanner integration failures hard to detect.

---

### Schema tests

Create:

```
tests/test_persistence_schema.py
```


Import from:

```python
from gitscanner.persistence.schema import (
    SCHEMA_STATEMENTS,
    get_default_classifications,
)
```


Test:

1. schema statements are present,
2. required table names are represented,
3. default dependency classifications include expected classifications,
4. schema can be initialized through sqlite without syntax errors.

This keeps schema-specific assertions out of store behavior tests.

---

## Reporting tests

Move summary formatting tests to:

```
tests/test_reporting_summary.py
```


Import from:

```python
from gitscanner.reporting.summary import (
    build_summary_for_scan_run,
    format_summary_lines,
)
```


Tests to move or adapt:

- summary line formatting
- sorted breakdown
- total feature files
- total datasources
- total service scans
- total services not found
- total dependency markers

If `build_summary_for_scan_run` remains in persistence, choose one clear ownership:

- query/database summary assembly belongs in persistence/store, or
- report model assembly belongs in reporting.

Either is acceptable, but formatting must live in reporting.

Acceptance criteria:

1. formatting tests do not use sqlite,
2. summary query tests may use sqlite if `build_summary_for_scan_run` owns database querying,
3. scanner modules are not imported by reporting tests.

---

## Compatibility facade tests

Create:

```
tests/test_compat_count_spring_controllers.py
```


This is the only test module that should import from:

```python
from gitscanner.count_spring_controllers import ...
```


Keep this file intentionally small.

Test only:

1. old public names are importable,
2. selected facade exports refer to the new implementation modules,
3. `process_repositories` compatibility wrapper still accepts the old signature,
4. legacy `main` remains callable.

Example:

```python
def test_legacy_facade_exports_cli_functions():
    from gitscanner.count_spring_controllers import build_parser, parse_cli_args
    from gitscanner.cli import count_spring_controllers as cli_module

    assert build_parser is cli_module.build_parser
    assert parse_cli_args is cli_module.parse_cli_args
```


For functions that cannot be identity-checked because wrappers are required, verify behavior instead.

Do not duplicate all scanner, parser, persistence, or reporting tests in the compatibility file.

---

## Process repository compatibility tests

If `process_repositories` remains as a compatibility wrapper, test it in the compatibility test file only.

The goal is not to retest the whole architecture through `process_repositories`; the goal is to verify legacy callers still work.

Recommended tests:

1. accepts old arguments:
   - `repos`
   - `api_base_url`
   - `provider`
   - `token`
   - `db_path`
   - `clone_and_count_func`
   - `sqlite_connect`

2. returns `(scan_run_id, stats)`.

3. includes controllers, endpoints, Karate, datasources, and service marker totals in summary.

4. internally uses the new runner/store/scanner path if practical to assert through monkeypatching.

Avoid using `process_repositories` as the primary integration test for scanner modules.

---

## Add architecture enforcement tests

Create:

```
tests/test_architecture_imports.py
```


Recommended checks:

### 1. Non-compat tests do not import facade

As described earlier.

### 2. Scanner modules do not import CLI

```python
from pathlib import Path


def test_scanner_modules_do_not_import_cli():
    root = Path(__file__).resolve().parents[1]
    scanner_files = list((root / "src" / "gitscanner" / "scanners").rglob("*.py"))

    offenders = []
    for path in scanner_files:
        content = path.read_text(encoding="utf-8")
        if "gitscanner.cli" in content:
            offenders.append(str(path.relative_to(root)))

    assert offenders == []
```


### 3. Scanner modules do not import compatibility facade

```python
def test_scanner_modules_do_not_import_legacy_facade():
    root = Path(__file__).resolve().parents[1]
    scanner_files = list((root / "src" / "gitscanner" / "scanners").rglob("*.py"))

    offenders = []
    forbidden = [
        "gitscanner.count_spring_controllers",
        "from gitscanner import count_spring_controllers",
    ]

    for path in scanner_files:
        content = path.read_text(encoding="utf-8")
        if any(pattern in content for pattern in forbidden):
            offenders.append(str(path.relative_to(root)))

    assert offenders == []
```


### 4. CLI does not import scanner internals beyond scanner registration

Depending on the final design, the CLI may call a `default_scanners()` factory. Prefer placing scanner registration in a small module rather than importing all scanner internals directly in CLI.

If a registry module exists, test:

```python
def test_cli_does_not_parse_java_yaml_or_karate_directly():
    root = Path(__file__).resolve().parents[1]
    cli_file = root / "src" / "gitscanner" / "cli" / "count_spring_controllers.py"
    content = cli_file.read_text(encoding="utf-8")

    forbidden_terms = [
        "extract_controller_mappings",
        "extract_endpoint_parameters",
        "extract_datasource_urls_from_yaml_content",
        "extract_karate_paths",
        "insert_controllers",
        "insert_karate_paths",
    ]

    offenders = [term for term in forbidden_terms if term in content]
    assert offenders == []
```


---

## Suggested implementation sequence

### Step 1: Create new empty test files

Create the target test files first.

Do not move all tests at once.

Run:

```
uv run pytest
```


---

### Step 2: Add architecture import guard

Add `tests/test_architecture_imports.py`.

At first, mark the facade-import guard as expected to fail if needed:

```python
import pytest

@pytest.mark.xfail(reason="Tests still import the compatibility facade during migration")
def test_non_compat_tests_do_not_import_legacy_facade():
    ...
```


Remove `xfail` once migration is complete.

Run:

```
uv run pytest
```


---

### Step 3: Move pure parsing tests

Move tests for:

- Spring mappings
- Spring parameters
- datasource YAML parsing
- Karate path extraction
- service name extraction

These should be the easiest to migrate because they do not need sqlite or orchestration.

Run:

```
uv run pytest
```


---

### Step 4: Move scanner file-system tests

Move tests that create temporary Java/YAML/feature files into the appropriate scanner package tests.

Run:

```
uv run pytest
```


---

### Step 5: Move persistence tests

Move sqlite schema, insert, and summary-query tests.

Keep persistence tests separate from scanner tests. Scanner tests should create records; persistence tests should store records.

Run:

```
uv run pytest
```


---

### Step 6: Add direct `ScanRunner` tests

Use fakes only.

Verify orchestration independently from the legacy `process_repositories` wrapper.

Run:

```
uv run pytest
```


---

### Step 7: Move CLI tests

Update CLI tests to import from `gitscanner.cli.count_spring_controllers`.

If the CLI module is still a thin alias to the legacy facade, this step should reveal that the refactor is incomplete. Update implementation so the CLI owns CLI behavior directly.

Run:

```
uv run pytest
```


---

### Step 8: Reduce facade tests

Move or delete duplicated tests from the legacy facade test file.

Keep only compatibility checks.

Run:

```
uv run pytest
```


---

### Step 9: Remove architecture guard `xfail`

Once no non-compat tests import the facade, remove any `xfail`.

Run:

```
uv run pytest
```


---

## Acceptance criteria

The test refactor is complete when:

1. `uv run pytest` passes.
2. Only `tests/test_compat_count_spring_controllers.py` imports `gitscanner.count_spring_controllers`.
3. Scanner tests directly import scanner modules.
4. CLI tests directly import `gitscanner.cli.count_spring_controllers`.
5. Git/provider tests directly import `gitscanner.core.git`.
6. Repository checkout tests directly import `gitscanner.core.repository`.
7. Scan orchestration tests directly import `gitscanner.core.scan_runner`.
8. Persistence tests directly import `gitscanner.persistence`.
9. Reporting tests directly import `gitscanner.reporting.summary`.
10. There is a test proving scanner modules do not import the CLI.
11. There is a test proving scanner modules do not import the compatibility facade.
12. `ScanRunner` is tested with fake repository, store, reporter, and scanner objects.
13. Scanner classes are tested to return `ScanResult` with the correct capability.
14. Persistence dispatch is tested using `ScanResult` objects.
15. The compatibility facade has only lightweight compatibility tests.
16. No new external dependency is introduced.
17. The tests make it possible to break a refactored module while facade imports still exist.

---

## Notes for the implementing AI

- Do not rewrite production behavior just to make tests easier unless the existing behavior violates the architecture.
- Prefer small moves with `uv run pytest` after each step.
- Preserve existing behavioral assertions while changing imports and test ownership.
- Keep scanner tests free of sqlite unless explicitly testing scanner-to-store integration.
- Keep persistence tests free of real source files where possible.
- Use fake objects for orchestration tests.
- Avoid broad end-to-end tests through the compatibility facade.
- The compatibility facade should prove backwards compatibility, not architectural correctness.
- If a refactored module currently delegates to the legacy facade, direct tests should expose that as a refactoring gap.
- When a test fails because the new module is still a wrapper, fix the production module rather than changing the test back to the facade.