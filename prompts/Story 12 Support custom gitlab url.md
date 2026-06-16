# Story 12: Support custom GitLab base URL in count_spring_controllers

`count_spring_controllers` currently builds clone URLs using hardcoded public provider hosts such as `github.com` and `gitlab.com`.

Enterprises often use self-hosted version control systems, so the scanner must allow the user to pass the provider API base URL, similar to `repo_list.py`.

## Requirements

- Change the CLI to accept:

  ```bash
  uv run count_spring_controllers <API_BASE_URL> <repos_file> --provider [gitlab | github]
  ```

- Examples:

  ```bash
  uv run count_spring_controllers https://api.github.com github_repos.txt
  uv run count_spring_controllers https://gitlab.com/api/v4 gitlab_repos.txt --provider gitlab
  uv run count_spring_controllers https://gitlab.company.com/api/v4 enterprise_repos.txt --provider gitlab
  ```

- For GitLab, derive the clone host from the API base URL:
  - `https://gitlab.com/api/v4` -> `https://gitlab.com/<group>/<repo>.git`
  - `https://gitlab.company.com/api/v4` -> `https://gitlab.company.com/<group>/<repo>.git`

- Preserve token behavior:
  - GitHub uses `GITHUB_TOKEN`
  - GitLab uses `GITLAB_TOKEN`
  - For GitLab token cloning, use:
    ```text
    https://oauth2:<token>@<gitlab-host>/<group>/<repo>.git
    ```

- Keep `--provider` with existing choices:
  - `github`
  - `gitlab`

- Update README examples.

## Acceptance Criteria

- `count_spring_controllers` no longer hardcodes `gitlab.com` when provider is GitLab and a custom API base URL is supplied.
- `count_spring_controllers` no longer hardcodes `github.com` when provider is github (or default) and a custom API base URL is supplied.
- Existing GitHub and GitLab.com examples still work when given their public API base URLs.
- Tests cover clone URL generation for:
  - GitHub public API URL
  - GitLab public API URL
  - custom GitLab API URL
  - custom GitLab API URL with token
  - custom Github API URL
  - custom Github API URL with token
- Tests cover CLI parsing for `<API_BASE_URL> <repos_file>`.

# Requirements:
- use the same parameter style as repo_list.py:
`uv run count_spring_controllers <API_BASE_URL> <repos_file>` followed by optional arguements.
