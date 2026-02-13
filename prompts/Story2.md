# Repo_List
Generate a Python module with a `main()` CLI that lists repositories (public + private) for a GitHub organization and prints
them to stdout in `owner/repo` format (one per line). This output is intended to be redirected into `repos.txt` for
`count_spring_controllers.py`.

# Inputs
## Environment Variables
- `GITHUB_TOKEN` (required for private repos; recommended always to avoid rate limits)

### CLI Arguments
CLI will use positional arguments and an optional `--filter` argument.
1. `API_BASE_URL`: Base GitHub REST API URL
   - example for GitHub.com: `api.github.com`
   - example for GitHub Enterprise: `github.<company>.com/api/v3`
2. `ORG`: Organization name (login), e.g. `mycompany`

Optional:
- `--filter <substring>`: only include repos whose repository *name* contains this substring (case-insensitive).

### Output
- Print to stdout
- fetch all repos for the org
- one repository per line
- format `owner/repo`
- example: 
```text
organization-name/repo-name1
organization-name/repo-name2
...
```

# Dependencies
Use whatever is available in the python environment. 
- `requests`

# Acceptance Criteria

- If no CLI args are provided, print a helpful usage message (include required args and mention `GITHUB_TOKEN`) and exit non-zero.
- When required args are provided, print the repository list to stdout, one `org/repo` per line.
- Must fetch **all** repositories for the org (handle API pagination; do not stop at the first page).
- Include public and private repositories that the token can access.
- Filtering:
  - If `--filter` is provided, include only repos whose short name matches the substring (case-insensitive).
- Error handling:
  - For HTTP 401/403: write a clear error message to stderr that mentions `GITHUB_TOKEN` and that it is missing/invalid/insufficient permissions; exit non-zero.
  - For other non-2xx errors: write an error message to stderr with HTTP status; exit non-zero.

# Testing
please test against the following github organizations:
| Input                                                            | Expect        |
| ---------------------------------------------------------------- | ----------    |
| api.github.com lancerkind                                        | > 40 repos    |
| api.github.com HAWS-Product-Team                                 | >= 2 repos    | 
| api.github.com HAWS-Product-Team --filter "Application"          | >= 1 repo     |
