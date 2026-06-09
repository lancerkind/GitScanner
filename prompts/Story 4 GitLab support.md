# Story 4 - GitLab Support

# Objective
Create GitLab support for both CLI tools so they can work with either GitHub or GitLab while preserving existing GitHub behavior and test coverage expectations.

- `repo_list.py`: list repositories for a GitLab group or user in `owner/repo` format.
- `count_spring_controllers.py`: process repository lists produced from GitLab as well as GitHub.

# Scope
Extend the implementation from Story 2 (GitHub-focused) into a provider-aware design.

- Keep existing GitHub functionality and CLI behavior backward compatible.
- Add GitLab API + clone support.
- Refactor in a way that stays unit-testable (aligned with Story 3 goals).

# Functional Requirements

## 1) Provider Selection
Both tools must support a provider selector.

- Add CLI option: `--provider <github|gitlab>`
- Default provider: `github` (to preserve current behavior)
- If provider is unknown, print parser usage/help and exit non-zero.

## 2) Authentication

### GitHub
- Continue using `GITHUB_TOKEN` as today.

### GitLab
- Add support for `GITLAB_TOKEN`.
- GitLab API requests must send token header in GitLab-compatible format (for example, `PRIVATE-TOKEN: <token>`).
- Without token, only publicly visible repositories may be returned and stricter rate limits may apply.

## 3) repo_list.py Enhancements

### Inputs
CLI positional arguments remain:
1. `API_BASE_URL`
2. `ORG` (provider-specific namespace identifier)

Optional arguments:
- `--filter <substring>` (existing behavior)
- `--provider <github|gitlab>` (new)

### GitHub Behavior
- Preserve Story 2 behavior:
  - Org endpoint with fallback to user endpoint.
  - Pagination.
  - Public + private visibility based on token permissions.

### GitLab Behavior
- Resolve namespace from `ORG` and support either:
  - a group path/name, or
  - a user namespace when applicable.
- Fetch projects via GitLab REST API from `API_BASE_URL`.
- Must handle pagination until all projects are fetched.
- Output format must still be one `owner/repo` per line.
- `--filter` applies to project short name (case-insensitive), same semantics as GitHub path.

### Error Handling
- Auth/permission failures:
  - GitHub: mention `GITHUB_TOKEN`.
  - GitLab: mention `GITLAB_TOKEN`.
- Other HTTP failures must include status code and fail non-zero.
- Network/request exceptions should produce clear stderr errors and fail non-zero.

## 4) count_spring_controllers.py Enhancements

### Inputs
- Continue to accept `repos_file`.
- Add optional `--provider <github|gitlab>` (default `github`).

### Clone URL Construction
- GitHub clone behavior remains unchanged.
- Add GitLab clone URL support based on provider.
- If token is present:
  - use `GITHUB_TOKEN` for GitHub clone auth,
  - use `GITLAB_TOKEN` for GitLab clone auth.

### Repository Processing
- Keep current controller counting rules unchanged.
- Support repository names generated from GitLab (`group/subgroup/repo` patterns included).
- Keep output summary format and sorting behavior unchanged unless explicitly required for provider disambiguation.

# Non-Functional Requirements
- Preserve executability via `python ...` and installed script entry points.
- Keep code modular (provider-specific logic separated from CLI and orchestration).
- Maintain or improve testability and readability.

# Acceptance Criteria

## CLI + Usage
- No arguments prints helpful parser-generated usage and exits non-zero.
- Usage/help must mention provider option and relevant token environment variable(s).

## repo_list.py
- GitHub path continues to work per Story 2 acceptance criteria.
- GitLab path returns all accessible repositories for target namespace, one per line in `owner/repo` format.
- Pagination is handled for GitHub and GitLab.
- `--filter` works case-insensitively for both providers.

## count_spring_controllers.py
- Can process repository list files containing GitHub or GitLab repositories.
- Clone/auth behavior is correct for selected provider.
- Controller counting and summary output remain correct.

## Error Handling
- 401/403 (or provider equivalent auth failures) produce clear token guidance and non-zero exit.
- Other non-2xx statuses produce clear HTTP error output and non-zero exit.

## Tests
- Add/update pytest unit tests for provider selection and provider-specific logic in both modules.
- Keep existing GitHub tests green.
- Add GitLab-focused tests for:
  - header/token creation,
  - API pagination,
  - filter behavior,
  - clone URL generation,
  - error handling.
- Maintain at least 80% coverage for touched modules.

# Suggested Validation Matrix

## repo_list.py
- `python src/gitscanner/repo_list.py https://api.github.com <org>`
- `python src/gitscanner/repo_list.py https://gitlab.com/api/v4 gnome --provider gitlab`
- `python src/gitscanner/repo_list.py https://gitlab.com/api/v4 gnome --provider gitlab --filter spring`

## count_spring_controllers.py
- `python src/gitscanner/count_spring_controllers.py repos.txt`
- `python src/gitscanner/count_spring_controllers.py repos_gitlab.txt --provider gitlab`

# Implementation Notes
- Prefer adding provider-specific helpers/functions rather than branching heavily in `main()`.
- Keep parser-based usage/help text as the single source of truth.
- Maintain backward compatibility for existing GitHub workflows and scripts.