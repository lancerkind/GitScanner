#!/usr/bin/env python3
"""
Count SpringBoot Controllers by cloning repos from a file list.
Useful for private repos or when code search API is limited.
"""

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import requests

from gitscanner.models import Controller, RepoResult, ScanSummary


def build_provider_token(provider, token=None):
    if token is not None:
        return token
    if provider == "gitlab":
        return os.environ.get("GITLAB_TOKEN")
    return os.environ.get("GITHUB_TOKEN")

def build_parser():
    parser = argparse.ArgumentParser(
        description="Count Spring controller files by cloning repositories from a list.",
        usage="python count_spring_controllers.py <repos_file>",
        epilog="Environment variables: GITHUB_TOKEN (github), GITLAB_TOKEN (gitlab).",
    )
    parser.add_argument(
        "repos_file",
        help="Text file containing one repository per line in owner/repo format",
    )
    parser.add_argument(
        "--provider",
        choices=("github", "gitlab"),
        default="github",
        help="Repository provider for clone/auth behavior (default: github)",
    )
    return parser


def parse_cli_args(argv):
    parser = build_parser()
    if not argv:
        print(parser.format_help(), end="")
        raise SystemExit(1)
    return parser.parse_args(argv)


def build_github_token(token=None):
    return build_provider_token("github", token=token)


def build_gitlab_token(token=None):
    return build_provider_token("gitlab", token=token)


def build_github_headers(token=None):
    token = build_github_token(token)
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"
    return headers


def build_gitlab_headers(token=None):
    token = build_gitlab_token(token)
    headers = {"Accept": "application/json"}
    if token:
        headers["PRIVATE-TOKEN"] = token
    return headers


def read_repos_from_file(file_path):
    """Read repository names from a file (one per line)."""
    repos = []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                # Skip empty lines and comments
                if line and not line.startswith("#"):
                    repos.append(line)

        return repos
    except FileNotFoundError:
        raise RuntimeError(f"Error: File '{file_path}' not found")
    except Exception as exc:
        raise RuntimeError(f"Error reading file: {exc}") from exc


def get_repo_info(repo_full_name, headers=None, get=requests.get):
    """Get repository information from GitHub API."""
    url = f"https://api.github.com/repos/{repo_full_name}"
    response = get(url, headers=headers if headers is not None else {})

    if response.status_code == 200:
        return response.json()

    return None


def count_controllers_in_directory(directory):
    """Count controller annotations in Java files within a directory."""
    rest_controllers = 0
    controllers = 0

    for java_file in Path(directory).rglob("*.java"):
        try:
            with open(java_file, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

                # Count @RestController
                if "@RestController" in content:
                    rest_controllers += 1
                # Count @Controller (but not if file has @RestController)
                elif "@Controller" in content:
                    controllers += 1
        except Exception:
            continue

    return rest_controllers, controllers


def build_clone_url(repo_full_name, provider="github", token=None):
    if provider == "gitlab":
        token = build_gitlab_token(token)
        if token:
            return f"https://oauth2:{token}@gitlab.com/{repo_full_name}.git"
        return f"https://gitlab.com/{repo_full_name}.git"

    token = build_github_token(token)
    if token:
        return f"https://{token}@github.com/{repo_full_name}.git"
    return f"https://github.com/{repo_full_name}.git"


def clone_and_count(repo_full_name, provider="github", token=None, run=subprocess.run):
    """Clone a repo temporarily and count controllers."""
    clone_url = build_clone_url(repo_full_name, provider=provider, token=token)

    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            # Clone with minimal depth
            result = run(
                ["git", "clone", "--depth", "1", clone_url, tmpdir],
                capture_output=True,
                text=True,
                timeout=300,
            )

            if result.returncode != 0:
                raise RuntimeError(f"Clone failed: {result.stderr.strip()}")

            # Count controllers
            rest_count, controller_count = count_controllers_in_directory(tmpdir)
            return rest_count, controller_count

        except subprocess.TimeoutExpired:
            raise RuntimeError("Clone timeout")
        except Exception as exc:
            raise RuntimeError(f"Error: {exc}") from exc


def process_repositories(repos, provider="github", token=None, clone_and_count_func=clone_and_count):
    total_rest_controllers = 0
    total_controllers = 0
    repo_results = []

    for repo_name in repos:
        rest_count, controller_count = clone_and_count_func(repo_name, provider=provider, token=token)
        total = rest_count + controller_count

        if total > 0:
            repo_results.append(
                RepoResult(
                    repo_name=repo_name,
                    controllers=[
                        Controller(
                            rest_controllers=rest_count,
                            controllers=controller_count,
                        )
                    ],
                    total_at_rest_controllers=rest_count,
                    total_at_controllers=controller_count,
                    total_rest_controllers=total,
                )
            )

        total_rest_controllers += rest_count
        total_controllers += controller_count

    return ScanSummary(
        total_rest_controllers=total_rest_controllers,
        total_controllers=total_controllers,
        repo_results=repo_results,
    )


def format_summary_lines(stats, total_repos):
    lines = [
        "\n" + "=" * 70,
        "SUMMARY",
        "=" * 70,
        f"\nRepositories with controllers: {len(stats.repo_results)}/{total_repos}",
        f"\nTotal @RestController files: {stats.total_rest_controllers}",
        f"Total @Controller files: {stats.total_controllers}",
        f"Total Controller files: {stats.total_controller_files}",
    ]

    if stats.repo_results:
        lines.extend([
            "\n" + "-" * 70,
            "Breakdown by repository:",
            "-" * 70,
        ])
        for result in sorted(stats.repo_results, key=lambda x: x.total_rest_controllers, reverse=True):
            lines.append(f"{result.repo_name:50} {result.total_rest_controllers:3} controllers")

    return lines


def main():
    try:
        args = parse_cli_args(sys.argv[1:])
        repos = read_repos_from_file(args.repos_file)

        if not repos:
            raise RuntimeError("No repositories found in file")

        print(f"Loaded {len(repos)} repositories from {args.repos_file}")
        print(f"\nCloning and searching {len(repos)} repositories...\n")

        if args.provider == "gitlab":
            token = build_gitlab_token()
        else:
            token = build_github_token()

        stats = process_repositories(repos, provider=args.provider, token=token)
        for line in format_summary_lines(stats, len(repos)):
            print(line)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()