# SpringBoot Controller Counter

This project helps you:

1. List repositories from GitHub or GitLab.
2. Clone each repository and count Spring controller files (`@RestController` and `@Controller`).

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
uv run count_spring_controllers github_repos.txt
```

### GitLab examples

```bash
uv run count_spring_controllers gitlab_repos.txt --provider gitlab
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
- I think you only have to do `export UV_NATIVE_TLS=true` and then your `uv sync` etc. will work.  This tells UV that
it should use the Certificate Authorities in your MacOS keychain.  This is probably coming up due to corporate firewall.
- If the above doesn't solve the problem, you may also need to install an SSL provider for python: `brew install openssl`