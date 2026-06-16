import argparse
import os
import sys

# suppress OpenSSL warnings
import warnings
from urllib.parse import quote
warnings.filterwarnings(
    "ignore",
    message="urllib3 v2 only supports OpenSSL 1.1.1+.*",
)

from urllib.parse import quote
from requests.exceptions import ConnectionError, Timeout

import requests


def _raise_connectivity_error(api_base_url):
    raise RuntimeError(
        f"Error: Could not connect to API_BASE_URL: {api_base_url}\n"
        "Please verify that the API URL is correct and reachable."
    )


def _raise_timeout_error(api_base_url):
    raise RuntimeError(
        f"Error: Request to {api_base_url} timed out.\n"
        "Please check your network connection and try again."
    )


def _raise_auth_required_error(token_env_var):
    raise RuntimeError(
        "Error: Authentication is required to access this resource.\n"
        f"Please set {token_env_var} and try again."
    )


def _raise_auth_failed_error(token_env_var):
    raise RuntimeError(
        "Error: Authentication failed. The configured token may be invalid, expired, or missing required permissions.\n"
        f"Please verify {token_env_var} and try again."
    )


def _raise_namespace_not_found_error(org):
    raise RuntimeError(
        f"Error: Organization or namespace not found: {org}\n"
        "Please check the spelling or verify that you have access to it."
    )


def _raise_unexpected_response_error(provider_name, status_code, org):
    raise RuntimeError(
        f"Error: {provider_name} API returned HTTP {status_code} while listing repositories for {org}.\n"
        "Please try again later."
    )


def _raise_invalid_api_endpoint_response_error(provider_name, api_base_url):
    raise RuntimeError(
        f"Error: API_BASE_URL does not appear to be a valid {provider_name} API endpoint: {api_base_url}\n"
        f"The server returned HTTP 200, but the response did not look like a {provider_name} API response.\n"
        "Please verify that the API URL is correct."
    )


def _safe_parse_json(response, provider_name, org):
    try:
        return response.json()
    except ValueError as exc:
        raise RuntimeError(
            f"Error: {provider_name} API returned an unexpected response format while listing repositories for {org}."
        ) from exc


def _response_text(response):
    text = getattr(response, "text", None)
    if text is not None:
        return text

    payload = getattr(response, "_payload", None)
    if isinstance(payload, str):
        return payload

    return ""


def _content_type(response):
    headers = getattr(response, "headers", {}) or {}
    return headers.get("Content-Type", "").lower()


def _is_json_content_type(content_type):
    return "application/json" in content_type or content_type.endswith("+json")


def _looks_like_wrong_api_response(data, text_lower):
    if isinstance(data, dict):
        status = data.get("status")
        message = data.get("message")
        error = data.get("error")
        code = data.get("code")

        if status == "ok" and data.get("data") is None:
            return True

        generic_messages = {"welcome", "route not found", "not found", "page not found"}
        if isinstance(message, str) and message.strip().lower() in generic_messages:
            return True

        if isinstance(error, str) and "not found" in error.lower():
            return True

        if isinstance(code, int) and code >= 400:
            return True

    if "<html" in text_lower:
        return True

    return any(keyword in text_lower for keyword in ["not found", "route not found", "page not found", "<meta http-equiv=\"refresh\"", "window.location"])


def _validate_first_success_response(response, provider_name, api_base_url):
    content_type = _content_type(response)
    body_text = _response_text(response)
    body_text_lower = body_text.lower()

    if content_type and not _is_json_content_type(content_type):
        _raise_invalid_api_endpoint_response_error(provider_name, api_base_url)

    if "<html" in body_text_lower:
        _raise_invalid_api_endpoint_response_error(provider_name, api_base_url)

    try:
        data = response.json()
    except ValueError as exc:
        if content_type and _is_json_content_type(content_type):
            raise RuntimeError(
                f"Error: {provider_name} API returned an unexpected response format while listing repositories."
            ) from exc
        _raise_invalid_api_endpoint_response_error(provider_name, api_base_url)
        raise

    if _looks_like_wrong_api_response(data, body_text_lower):
        _raise_invalid_api_endpoint_response_error(provider_name, api_base_url)

    return data


def build_parser():
    parser = argparse.ArgumentParser(
        description="List repositories for a GitHub organization/user or GitLab namespace.",
        usage="python repo_scanning.py <API_BASE_URL> <ORG> [--filter <substring>]",
        epilog="Environment variables: GITSCANNER_TOKEN.",
    )
    parser.add_argument(
        "API_BASE_URL",
        help="Base REST **API** URL (e.g., https://api.github.com or http://gitlab.com/api/v4)",
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
    return os.environ.get("GITSCANNER_TOKEN")


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
    validated_first_success = False

    try:
        response = get(url, headers=headers, params=params)
        if response.status_code == 404:
            url = f"{base_url}/users/{org}/repos"
            response = get(url, headers=headers, params=params)

        while True:
            if response.status_code == 401:
                _raise_auth_required_error("GITSCANNER_TOKEN")

            if response.status_code == 403:
                _raise_auth_failed_error("GITSCANNER_TOKEN")

            if response.status_code == 404:
                _raise_namespace_not_found_error(org)

            if not response.ok:
                _raise_unexpected_response_error("GitHub", response.status_code, org)

            if not validated_first_success:
                page_repos = _validate_first_success_response(response, "GitHub", base_url)
                validated_first_success = True
            else:
                page_repos = _safe_parse_json(response, "GitHub", org)
            if not page_repos:
                break

            repos.extend(page_repos)

            if "next" in response.links:
                params["page"] += 1
                response = get(url, headers=headers, params=params)
            else:
                break

    except Timeout:
        _raise_timeout_error(base_url)
    except ConnectionError:
        _raise_connectivity_error(base_url)
    except requests.exceptions.RequestException:
        _raise_connectivity_error(base_url)

    return repos


def _fetch_gitlab_group_projects(base_url, org, headers, get):
    encoded_org = quote(org, safe="")
    repos = []
    params = {"per_page": 100, "page": 1, "include_subgroups": True}
    url = f"{base_url}/groups/{encoded_org}/projects"
    response = get(url, headers=headers, params=params)
    validated_first_success = False

    while True:
        if response.status_code == 401:
            _raise_auth_required_error("GITSCANNER_TOKEN")

        if response.status_code == 403:
            _raise_auth_failed_error("GITSCANNER_TOKEN")

        if response.status_code == 404:
            return None

        if not response.ok:
            _raise_unexpected_response_error("GitLab", response.status_code, org)

        if not validated_first_success:
            page_repos = _validate_first_success_response(response, "GitLab", base_url)
            validated_first_success = True
        else:
            page_repos = _safe_parse_json(response, "GitLab", org)
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
    validated_first_success = False

    if users_response.status_code == 401:
        _raise_auth_required_error("GITSCANNER_TOKEN")

    if users_response.status_code == 403:
        _raise_auth_failed_error("GITSCANNER_TOKEN")

    if not users_response.ok:
        _raise_unexpected_response_error("GitLab", users_response.status_code, org)

    if not validated_first_success:
        users = _validate_first_success_response(users_response, "GitLab", base_url)
        validated_first_success = True
    else:
        users = _safe_parse_json(users_response, "GitLab", org)
    if users:
        user_id = users[0]["id"]
        repos = []
        params = {"per_page": 100, "page": 1}
        url = f"{base_url}/users/{user_id}/projects"
        response = get(url, headers=headers, params=params)
        while True:
            if response.status_code == 401:
                _raise_auth_required_error("GITSCANNER_TOKEN")

            if response.status_code == 403:
                _raise_auth_failed_error("GITSCANNER_TOKEN")

            if not response.ok:
                _raise_unexpected_response_error("GitLab", response.status_code, org)

            if not validated_first_success:
                page_repos = _validate_first_success_response(response, "GitLab", base_url)
                validated_first_success = True
            else:
                page_repos = _safe_parse_json(response, "GitLab", org)
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
        if response.status_code == 401:
            _raise_auth_required_error("GITSCANNER_TOKEN")

        if response.status_code == 403:
            _raise_auth_failed_error("GITSCANNER_TOKEN")

        if response.status_code == 404:
            _raise_namespace_not_found_error(org)

        if not response.ok:
            _raise_unexpected_response_error("GitLab", response.status_code, org)

        if not validated_first_success:
            page_repos = _validate_first_success_response(response, "GitLab", base_url)
            validated_first_success = True
        else:
            page_repos = _safe_parse_json(response, "GitLab", org)
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
    except Timeout:
        _raise_timeout_error(base_url)
    except ConnectionError:
        _raise_connectivity_error(base_url)
    except requests.exceptions.RequestException:
        _raise_connectivity_error(base_url)

    return []


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
