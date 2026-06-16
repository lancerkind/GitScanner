# GitScanner — Development Notes

## Build / Configuration

- Project uses a `src/` layout (`src/gitscanner`) and CLI entry points from `pyproject.toml`:
  - `list_repos = gitscanner.list_repos:main`
  - `count_spring_controllers = gitscanner.count_spring_controllers:main`
- Preferred execution path is `uv run ...` (as described in `Readme.md`). The path to uv is `/opt/homebrew/bin/uv'.
- In environments where `uv` is unavailable, run tools/tests with `PYTHONPATH=src` so imports resolve correctly.

### Setup commands

```bash
# Preferred
uv sync --dev

# If uv is not available, ensure pytest deps are installed and use PYTHONPATH=src for execution.
```

## Testing

### Run tests

```bash
# Preferred (when uv is available)
uv run pytest

# Fallback for plain python environment with src-layout imports
PYTHONPATH=src python3 -m pytest
```

### Run focused tests

```bash
PYTHONPATH=src python3 -m pytest tests/test_list_repos.py::test_format_repo_names_without_filter
```

### Adding new tests

- Place tests under `tests/` with `test_*.py` naming.
- Follow existing style in `tests/test_list_repos.py` and `tests/test_count_spring_controllers.py`:
  - Plain `pytest` functions.
  - `monkeypatch` for external calls/environment.
  - Prefer deterministic, isolated tests (no live network calls).
- For behavior involving HTTP integrations, pass fake `get` callables (current code already supports injectable `get` in fetch functions).

### Verified example (executed in this environment)

- Command run successfully:

```bash
PYTHONPATH=src python3 -m pytest tests/test_agents_demo_temp.py tests/test_list_repos.py::test_format_repo_names_without_filter
```

- Result: `2 passed`.

## Additional development/debugging notes

- API/provider switching is centralized in `src/gitscanner/list_repos.py` (`provider` argument routes GitHub vs GitLab fetch behavior).
- Authentication conventions:
  - GitHub token header uses `GITHUB_TOKEN`.
  - GitLab token header uses `GITLAB_TOKEN`.
- Error handling is intentionally user-facing (`RuntimeError` with actionable messages); preserve this style in new code/tests.
- Keep new logic testable by dependency injection (e.g., injectable HTTP function) rather than hard-coding network calls.