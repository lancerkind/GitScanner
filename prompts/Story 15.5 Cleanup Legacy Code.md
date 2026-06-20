# 15.5 Cleanup Legacy Code

Refactor the legacy `count_spring_controllers.py` module out of the application.

Several modules currently import functions from `gitscanner.count_spring_controllers` and re-export or delegate to them. 
Move those functions into the modules that are presently referencing them, preserving the current behavior and public 
API of those modules.

The goal is that the application no longer depends on `count_spring_controllers.py`.

# Implementation Notes

Use the existing imports and compatibility wrappers as breadcrumbs for where each function belongs.

For example:
- CLI-related behavior should live in the CLI orchestration module that currently references it.
- Database schema and persistence behavior should live in the persistence/schema/store modules that currently reference it.
- Summary/reporting behavior should live in the reporting module that currently references it.
- Scanner/parsing behavior should live with the scanner modules that currently use or conceptually own it.
- Repository/clone behavior should live in the core git/repository layer as appropriate.

Preserve existing behavior unless a test clearly indicates otherwise.

After the migration, there should be no imports of `gitscanner.count_spring_controllers`.

# Acceptance Criteria

- All unit tests pass.
- The application runs without errors from the configured script entry point.
- `count_spring_controllers.py` is removed.
- `pyproject.toml` scripts section is updated so the application launches through the new module location.
- No production code imports `gitscanner.count_spring_controllers`.
- Existing public functions exposed by the newer modules continue to work where tests or application code depend on them.
- Searching the codebase for `count_spring_controllers` returns no production imports.
- Any tests that still import legacy symbols should be updated to import from the new module locations.

 