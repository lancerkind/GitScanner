import argparse
import os
import sys
from urllib.parse import quote

import requests


def build_parser():
    parser = argparse.ArgumentParser(
        description="List repositories for a GitHub organization/user or GitLab namespace.",
        usage="python repo_scanning.py <API_BASE_URL> <ORG> [--filter <substring>]",
        epilog="Environment variables: GITHUB_TOKEN (github), GITLAB_TOKEN (gitlab).",
    )
    parser.add_argument(
        "API_BASE_URL",
        help="Base GitHub REST **API** URL (e.g., https://api.github.com)",
    )
    parser.add_argument("ORG", help="Organization name (login)")
    parser.add_argument(
        "--filter",
        dest="filter_substring",
        help="Only include repos whose name contains this substring (case-insensitive)",
    )
    parser.add_argument(
        "--provider",
        choices=("github", "gitlab"),
        default="github",
        help="Repository provider to query (default: github)",
    )
    return parser


def parse_cli_args(argv):
    parser = build_parser()
    if not argv:
        print(parser.format_help(), end="")
        raise SystemExit(1)
    return parser.parse_args(argv)


def build_provider_token(provider, token=None):
    if token is not None:
        return token
    if provider == "gitlab":
        return os.environ.get("GITLAB_TOKEN")
    return os.environ.get("GITHUB_TOKEN")


def build_github_headers(token=None):
    token = build_provider_token("github", token=token)

    headers = {}
    if token:
        headers["Authorization"] = f"token {token}"
    return headers


def build_gitlab_headers(token=None):
    token = build_provider_token("gitlab", token=token)
    headers = {}
    if token:
        headers["PRIVATE-TOKEN"] = token
    return headers


def fetch_github_repos(api_base_url, org, headers=None, get=requests.get):
    headers = headers if headers is not None else {}
    base_url = api_base_url.rstrip("/")
    url = f"{base_url}/orgs/{org}/repos"
    repos = []
    params = {"per_page": 100, "page": 1}

    try:
        response = get(url, headers=headers, params=params)
        if response.status_code == 404:
            url = f"{base_url}/users/{org}/repos"
            response = get(url, headers=headers, params=params)

        while True:
            if response.status_code in (401, 403):
                error_msg = "Error: Authentication failed or rate limit exceeded. "
                error_msg += "Check if GITHUB_TOKEN is missing, invalid, or has insufficient permissions."
                raise RuntimeError(error_msg)

            if not response.ok:
                raise RuntimeError(f"Error: Received HTTP {response.status_code} from {url}")

            page_repos = response.json()
            if not page_repos:
                break

            repos.extend(page_repos)

            if "next" in response.links:
                params["page"] += 1
                response = get(url, headers=headers, params=params)
            else:
                break

    except requests.exceptions.RequestException as exc:
        raise RuntimeError(f"Error: {exc}") from exc

    return repos


def _fetch_gitlab_group_projects(base_url, org, headers, get):
    encoded_org = quote(org, safe="")
    repos = []
    params = {"per_page": 100, "page": 1, "include_subgroups": True}
    url = f"{base_url}/groups/{encoded_org}/projects"
    response = get(url, headers=headers, params=params)

    while True:
        if response.status_code in (401, 403):
            error_msg = "Error: Authentication failed or access denied for GitLab. "
            error_msg += "Check if GITLAB_TOKEN is missing, invalid, or has insufficient permissions."
            raise RuntimeError(error_msg)

        if response.status_code == 404:
            return None

        if not response.ok:
            raise RuntimeError(f"Error: Received HTTP {response.status_code} from {url}")

        page_repos = response.json()
        if not page_repos:
            break

        repos.extend(page_repos)

        if "next" in response.links:
            params["page"] += 1
            response = get(url, headers=headers, params=params)
        else:
            break

    return repos


def _fetch_gitlab_user_projects(base_url, org, headers, get):
    encoded_org = quote(org, safe="")
    users_url = f"{base_url}/users"
    users_response = get(users_url, headers=headers, params={"username": org, "per_page": 1})

    if users_response.status_code in (401, 403):
        error_msg = "Error: Authentication failed or access denied for GitLab. "
        error_msg += "Check if GITLAB_TOKEN is missing, invalid, or has insufficient permissions."
        raise RuntimeError(error_msg)

    if not users_response.ok:
        raise RuntimeError(f"Error: Received HTTP {users_response.status_code} from {users_url}")

    users = users_response.json()
    if users:
        user_id = users[0]["id"]
        repos = []
        params = {"per_page": 100, "page": 1}
        url = f"{base_url}/users/{user_id}/projects"
        response = get(url, headers=headers, params=params)
        while True:
            if not response.ok:
                raise RuntimeError(f"Error: Received HTTP {response.status_code} from {url}")

            page_repos = response.json()
            if not page_repos:
                break

            repos.extend(page_repos)

            if "next" in response.links:
                params["page"] += 1
                response = get(url, headers=headers, params=params)
            else:
                break
        return repos

    fallback_url = f"{base_url}/users/{encoded_org}/projects"
    repos = []
    params = {"per_page": 100, "page": 1}
    response = get(fallback_url, headers=headers, params=params)
    while True:
        if response.status_code in (401, 403):
            error_msg = "Error: Authentication failed or access denied for GitLab. "
            error_msg += "Check if GITLAB_TOKEN is missing, invalid, or has insufficient permissions."
            raise RuntimeError(error_msg)

        if response.status_code == 404:
            raise RuntimeError(f"Error: Received HTTP 404 from {fallback_url}")

        if not response.ok:
            raise RuntimeError(f"Error: Received HTTP {response.status_code} from {fallback_url}")

        page_repos = response.json()
        if not page_repos:
            break

        repos.extend(page_repos)

        if "next" in response.links:
            params["page"] += 1
            response = get(fallback_url, headers=headers, params=params)
        else:
            break

    return repos


def fetch_gitlab_repos(api_base_url, org, headers=None, get=requests.get):
    headers = headers if headers is not None else {}
    base_url = api_base_url.rstrip("/")

    try:
        group_repos = _fetch_gitlab_group_projects(base_url, org, headers, get)
        if group_repos is not None:
            return group_repos
        return _fetch_gitlab_user_projects(base_url, org, headers, get)
    except requests.exceptions.RequestException as exc:
        raise RuntimeError(f"Error: {exc}") from exc


def fetch_repos(api_base_url, org, provider, get=requests.get):
    if provider == "gitlab":
        headers = build_gitlab_headers()
        return fetch_gitlab_repos(api_base_url, org, headers=headers, get=get)
    headers = build_github_headers()
    return fetch_github_repos(api_base_url, org, headers=headers, get=get)


def format_repo_names(repos, filter_substring=None):
    filter_sub = filter_substring.lower() if filter_substring else None
    output = []

    for repo in repos:
        repo_name = repo.get("name", "")
        full_name = repo.get("full_name") or repo.get("path_with_namespace", "")

        if filter_sub:
            if filter_sub in repo_name.lower():
                output.append(full_name)
        else:
            output.append(full_name)

    return output


def main():
    try:
        args = parse_cli_args(sys.argv[1:])
        repos = fetch_repos(args.API_BASE_URL, args.ORG, provider=args.provider)
        lines = format_repo_names(repos, args.filter_substring)
        for line in lines:
            print(line)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
