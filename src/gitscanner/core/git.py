"""Repository/provider helpers."""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import quote
from urllib.parse import urlsplit

import requests

from gitscanner.scanners.springboot.controllers import count_controllers_in_directory


def build_provider_token(provider, token=None):
    if token is not None:
        return token
    return os.environ.get("GITSCANNER_TOKEN")


def build_token(token=None):
    return build_provider_token(None, token=token)


def build_github_headers(token=None):
    token = build_token(token)
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"
    return headers


def build_gitlab_headers(token=None):
    token = build_token(token)
    headers = {"Accept": "application/json"}
    if token:
        headers["PRIVATE-TOKEN"] = token
    return headers


def get_repo_info(repo_full_name, headers=None, get=requests.get):
    """Get repository information from GitHub API."""
    url = f"https://api.github.com/repos/{repo_full_name}"
    response = get(url, headers=headers if headers is not None else {})

    if response.status_code == 200:
        return response.json()

    return None


def derive_clone_host(api_base_url, provider="github"):
    if provider == "github":
        return "github.com"
    parsed = urlsplit(api_base_url)
    return parsed.hostname or "gitlab.com"


def build_clone_url(repo_full_name, api_base_url, provider="github", token=None):
    if provider == "github":
        token_value = build_token(token)
        if token_value:
            return f"https://{token_value}@github.com/{repo_full_name}.git"
        return f"https://github.com/{repo_full_name}.git"

    token_value = build_provider_token(provider, token=token)
    clone_host = derive_clone_host(api_base_url, provider=provider)
    if token_value:
        return f"https://oauth2:{quote(token_value, safe='')}@{clone_host}/{repo_full_name}.git"
    return f"https://{clone_host}/{repo_full_name}.git"


def clone_and_count(repo_full_name, api_base_url, provider="github", token=None, run=subprocess.run):
    """Clone repository and return checkout metadata.

    The checkout directory is intentionally not deleted here because later scanners
    need to inspect the repository contents. The caller is responsible for cleanup.
    """
    temp_dir = tempfile.mkdtemp()
    repo_name = repo_full_name.split("/")[-1]
    clone_url = build_clone_url(repo_full_name, api_base_url, provider=provider, token=token)

    result = run(
        ["git", "clone", "--depth", "1", clone_url],
        cwd=temp_dir,
        capture_output=True,
        text=True,
        timeout=300,
    )

    if result.returncode != 0:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise RuntimeError(f"Error cloning {repo_full_name}: {result.stderr.strip()}")

    repo_path = Path(temp_dir) / repo_name
    controllers = count_controllers_in_directory(str(repo_path))

    return {
        "repo": repo_full_name,
        "path": str(repo_path),
        "cleanup_path": temp_dir,
        "clone_url": clone_url,
        "controller_count": len(controllers),
        "controllers": controllers,
    }