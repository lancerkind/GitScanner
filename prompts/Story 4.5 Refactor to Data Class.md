# Story 4.5 Refactor to Data Class

Refactor the scanning flow so scanning is decoupled from reporting.

Scanning should collect structured data into data classes. Reporting should consume those data classes and handle display/output formatting.

Introduce a `RepoResult` data class:
# RepoResult
Add RepoResult to the same module as the existing scan result models, or create a new models.py if no such module exists.

Here is the model. Adjust as you see fit.
```python
@dataclass
class RepoResult:
    repo_name: str
    controllers: list[Controller] = field(default_factory=list)
    total_at_rest_controllers: int = 0
    total_at_controllers: int = 0
    total_rest_controllers: int = 0
```

## Requirements

- Repository scanning should return a `RepoResult`.
- Multi-repository scanning, if present, should return `list[RepoResult]`.
- The scanner should populate:
  - `repo_name`
  - `controllers`
  - `total_at_rest_controllers`
  - `total_at_controllers`
  - `total_rest_controllers`
- Reporting/printing should consume `RepoResult` list of objects instead of relying on scanner-side output.
- Existing command-line output should remain unchanged unless the current tests require otherwise.
- Existing tests should continue to pass.
- Add or update tests to verify that scanning returns populated `RepoResult` instances.
