# SpringBoot Controller Counter

This project helps you:

1. List repositories from GitHub or GitLab.
2. Count Spring controller files (`@RestController` and `@Controller`).

Use `uv run` so commands execute through the project entry points defined in `pyproject.toml`.

## Using `list_repos`

`list_repos` fetches repositories for an organization/group/user namespace and prints one repo per line.

### Show help

```bash
uv run list_repos
```

### GitHub examples

```bash
# List all accessible repos for an org/user
uv run list_repos https://api.github.com anthropics

# Filter by repo name substring (case-insensitive)
uv run list_repos https://api.github.com anthropics --filter spring
```

### GitLab examples

```bash
# List all accessible repos for a GitLab namespace
uv run list_repos https://gitlab.com/api/v4 gnome --provider gitlab

# Filter by repo name substring (case-insensitive)
uv run list_repos https://gitlab.com/api/v4 gnome --provider gitlab --filter spring
```

## Using `count_spring_controllers`

`count_spring_controllers` reads a text file with one `owner/repo` (or `group/subgroup/repo`) per line,
clones each repo, and prints a summary.

### Show help

```bash
uv run count_spring_controllers
```

### GitHub examples

```bash
uv run count_spring_controllers https://api.github.com github_repos.txt

# GitHub Enterprise-style API URL
uv run count_spring_controllers https://git.company.com/api/v3 github_repos.txt
```

### GitLab examples

```bash
uv run count_spring_controllers https://gitlab.com/api/v4 gitlab_repos.txt --provider gitlab

# Self-hosted GitLab API URL
uv run count_spring_controllers https://gitlab.company.com/api/v4 enterprise_repos.txt --provider gitlab
```

## Authentication

- GitHub: set `GITHUB_TOKEN` for private repos/higher limits.
- GitLab: set `GITLAB_TOKEN` for private repos/higher limits.

Examples:

```bash
export GITHUB_TOKEN="your_github_token"
export GITLAB_TOKEN="your_gitlab_token"
```

For GitHub tokens, create one at: https://github.com/settings/tokens

## Repository list file format

Each line should be a repo path:

```text
# Comments are allowed
mycompany/user-service
mycompany/payment-service

# GitLab subgroup example
gitlab-org/platform/team-a/service-x
```

## What it counts

- **@RestController** - REST API controllers
- **@Controller** - Traditional MVC controllers
- Avoids double-counting files with both annotations

## Output Example

```
Loaded 15 repositories from github_repos.txt

Searching 15 repositories for SpringBoot controllers...

[1/15] Searching mycompany/user-service...
  ✓ Found 8 controllers (@RestController: 6, @Controller: 2)
[2/15] Searching mycompany/payment-service...
  ✓ Found 12 controllers (@RestController: 12, @Controller: 0)
[3/15] Searching mycompany/order-service...
  - No controllers found
...

======================================================================
SUMMARY
======================================================================

Repositories with controllers: 12/15

Total @RestController: 134
Total @Controller: 23
Total Controllers: 157

----------------------------------------------------------------------
Breakdown by repository:
----------------------------------------------------------------------
mycompany/order-service                            34 controllers
mycompany/payment-service                          12 controllers
mycompany/user-service                              8 controllers
...
```

## SQLite schema and reporting

Scanner results are stored in a local SQLite database (`gitscanner.db`).

### Schema overview

- `controllers` stores controller classes discovered in each repository.
- `endpoints` stores endpoint details (for example HTTP method and path) linked to each controller.
- `parameters` stores endpoint parameter details (name, Java type, source, and required/optional) linked to each endpoint.
- `karate_feature_files` stores discovered Karate `.feature` files per repository, optionally linked to a controller when one can be inferred from the path.
- `karate_paths` stores distinct API paths extracted from each Karate feature file and linked to `karate_feature_files`.

This schema is designed so the scanner focuses on collecting structured data, while reporting can evolve independently.

### Karate reporting schema notes

- Karate reporting is based on the relationship `repositories -> karate_feature_files -> karate_paths`.
- This allows reports such as:
  - feature-file coverage by repository/controller
  - extracted API path inventory from Karate scenarios
  - comparison between scanned Spring endpoints and Karate-referenced paths

### Reporting approach

- Detailed, polished reporting will be built in a separate reporting tool that reads from the SQLite database.
- You can also build your own custom reports directly from `gitscanner.db` using standard SQLite queries.

## Running reports

After scanning repositories, you can query `gitscanner.db` directly to generate reports.
1. Run the scanner to populate data
```bash
uv run count_spring_controllers https://api.github.com github_repos.txt
```
2. Execute a report SQL file
Use SQLite's `-init` option to run the bundled report query (`reporting/archetype_report.sql`):
```bash
sqlite3 gitscanner.db -init sql reports/archetype_report.sql
```

## Build your own quick report

Example: top repositories by number of controllers discovered.

```bash
sqlite3 gitscanner.db "SELECT repo_name, COUNT(*) AS controller_count FROM controllers GROUP BY repo_name ORDER BY controller_count DESC LIMIT 20;"
```

## Testing reporting

Use `reporting/test_archetype_fixture.sql` to validate archetype reporting logic against known, synthetic data before running the report on production scan data.

- The script creates a fresh test schema and seeds lookup/reference data.
- It inserts one fixture repository per archetype scenario (for example: `MIXED`, `KAFKA`, `SPANNER`, `ORACLE`, `POSTGRES`, `OTHER_SQL`, `UPSTREAM_REST_API`, `NO_DEPENDENCIES_DETECTED`, `UNCLASSIFIED`).
- It includes the archetype report query at the end so the result set is returned immediately.

Run it against a test database:

```bash
sqlite3 sql reports/test.db -init sql reports/test_archetype_fixture.sql
```

Then visually verify that each fixture repo maps to the expected archetype (including the `repo-h2-only` case, which should remain `NO_DEPENDENCIES_DETECTED`).

## Managing Your Repository List

**Add comments for organization:**
```
# User Services
mycompany/user-service
mycompany/auth-service

# Payment Services  
mycompany/payment-service
```

**Temporarily exclude a repo:**
```
# mycompany/legacy-service  # Comment out to skip
mycompany/new-service
```

**Scan repos from multiple organizations:**
```
mycompany/service-a
othercompany/service-b
personal-account/project-c
```

## Troubleshooting

**Rate limit errors:**
- The script automatically waits when rate limited
- For many repos, Option 2 (cloning) may be faster

**Authentication errors:**
- Verify your token has correct permissions
- For private repos, ensure `repo` scope is enabled

**No results found:**
- Check that repos contain Java/SpringBoot code
- Verify annotation format (some projects use fully qualified names)

**invalid peer certificate: UnknownIssuer**
**Failed to download `pytest==9.0.3`**
  ```bash
  ├─▶ Request failed after 3 retries
  ├─▶ Failed to fetch: `https://files.pythonhosted.org/packages/d4/24/a372aaf5c9b7208e7112038812994107bc65a84cd00e0354a88c2c77a617/pytest-9.0.3-py3-none-any.whl`
  ├─▶ error sending request for url (https://files.pythonhosted.org/packages/d4/24/a372aaf5c9b7208e7112038812994107bc65a84cd00e0354a88c2c77a617/pytest-9.0.3-py3-none-any.whl)
  ├─▶ client error (Connect)
  ╰─▶ invalid peer certificate: UnknownIssuer
  ```
- Run `export UV_NATIVE_TLS=true` and then your `uv sync` etc. will work.  This tells UV that
it should use the Certificate Authorities in your MacOS keychain.  This is probably coming up due to corporate firewall.
- If the above doesn't solve the problem, you may also need to install an SSL provider for python: `brew install openssl`