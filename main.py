#!/usr/bin/env python3
"""
Count SpringBoot Controllers by cloning repos from a file list.
Useful for private repos or when code search API is limited.
"""

import os
import subprocess
import tempfile
import shutil
import sys
from pathlib import Path
import requests

# Configuration
GITHUB_TOKEN = "your_github_token_here"
HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}


def read_repos_from_file(file_path):
    """Read repository names from a file (one per line)."""
    repos = []

    try:
        with open(file_path, 'r') as f:
            for line in f:
                line = line.strip()
                # Skip empty lines and comments
                if line and not line.startswith('#'):
                    repos.append(line)

        print(f"Loaded {len(repos)} repositories from {file_path}")
        return repos
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading file: {e}")
        sys.exit(1)


def get_repo_info(repo_full_name):
    """Get repository information from GitHub API."""
    url = f"https://api.github.com/repos/{repo_full_name}"
    response = requests.get(url, headers=HEADERS)

    if response.status_code == 200:
        return response.json()
    else:
        print(f"  Warning: Could not fetch info for {repo_full_name}: {response.status_code}")
        return None


def count_controllers_in_directory(directory):
    """Count controller annotations in Java files within a directory."""
    rest_controllers = 0
    controllers = 0

    for java_file in Path(directory).rglob("*.java"):
        try:
            with open(java_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

                # Count @RestController
                if '@RestController' in content:
                    rest_controllers += 1
                # Count @Controller (but not if file has @RestController)
                elif '@Controller' in content:
                    controllers += 1
        except Exception as e:
            print(f"  Warning: Could not read {java_file}: {e}")

    return rest_controllers, controllers


def clone_and_count(repo_full_name):
    """Clone a repo temporarily and count controllers."""
    # Construct clone URL with authentication
    clone_url = f'https://{GITHUB_TOKEN}@github.com/{repo_full_name}.git'

    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            # Clone with minimal depth
            result = subprocess.run(
                ['git', 'clone', '--depth', '1', clone_url, tmpdir],
                capture_output=True,
                text=True,
                timeout=300
            )

            if result.returncode != 0:
                print(f"  ✗ Clone failed: {result.stderr}")
                return 0, 0

            # Count controllers
            rest_count, controller_count = count_controllers_in_directory(tmpdir)
            return rest_count, controller_count

        except subprocess.TimeoutExpired:
            print(f"  ✗ Clone timeout")
            return 0, 0
        except Exception as e:
            print(f"  ✗ Error: {e}")
            return 0, 0


def main():
    if len(sys.argv) < 2:
        print("Usage: python count_spring_controllers_clone.py <repos_file>")
        print("\nExample:")
        print("  python count_spring_controllers_clone.py repos.txt")
        print("\nrepos_file should contain one repository per line in format:")
        print("  owner/repo-name")
        print("  # Comments are allowed")
        sys.exit(1)

    repos_file = sys.argv[1]
    repos = read_repos_from_file(repos_file)

    if not repos:
        print("No repositories found in file")
        sys.exit(1)

    print(f"\nCloning and searching {len(repos)} repositories...\n")

    total_rest_controllers = 0
    total_controllers = 0
    repo_results = []

    for i, repo_name in enumerate(repos, 1):
        print(f"[{i}/{len(repos)}] Processing {repo_name}...")

        rest_count, controller_count = clone_and_count(repo_name)
        total = rest_count + controller_count

        if total > 0:
            repo_results.append({
                'repo': repo_name,
                'rest_controllers': rest_count,
                'controllers': controller_count,
                'total': total
            })
            print(f"  ✓ Found {total} controller files")

        total_rest_controllers += rest_count
        total_controllers += controller_count

    # Print summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"\nRepositories with controllers: {len(repo_results)}/{len(repos)}")
    print(f"\nTotal @RestController files: {total_rest_controllers}")
    print(f"Total @Controller files: {total_controllers}")
    print(f"Total Controller files: {total_rest_controllers + total_controllers}")

    if repo_results:
        print("\n" + "-" * 70)
        print("Breakdown by repository:")
        print("-" * 70)
        for result in sorted(repo_results, key=lambda x: x['total'], reverse=True):
            print(f"{result['repo']:50} {result['total']:3} controllers")


if __name__ == "__main__":
    main()