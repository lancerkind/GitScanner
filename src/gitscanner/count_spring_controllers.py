#!/usr/bin/env python3
"""
Count SpringBoot Controllers by cloning repos from a file list.
Useful for private repos or when code search API is limited.
"""

import argparse
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

# suppress OpenSSL warnings
import warnings
from urllib.parse import quote
warnings.filterwarnings(
    "ignore",
    message="urllib3 v2 only supports OpenSSL 1.1.1+.*",
)

import requests


DB_FILE_NAME = "gitscanner.db"
HTTP_METHOD_BY_ANNOTATION = {
    "Get": "GET",
    "Post": "POST",
    "Put": "PUT",
    "Delete": "DELETE",
    "Patch": "PATCH",
}
MAPPING_ANNOTATION_PATTERN = re.compile(
    r"@(?P<name>Get|Post|Put|Delete|Patch|Request)Mapping\s*\((?P<args>.*?)\)",
    re.DOTALL,
)
PATH_NAMED_PATTERN = re.compile(r"\b(?:value|path)\s*=\s*\"([^\"]*)\"")
PATH_ARRAY_PATTERN = re.compile(r"\b(?:value|path)\s*=\s*\{(?P<items>[^}]*)\}", re.DOTALL)
STRING_LITERAL_PATTERN = re.compile(r'"([^\"]*)"')
REQUEST_METHOD_PATTERN = re.compile(r"RequestMethod\.([A-Z]+)")

SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS scan_runs (
        id          INTEGER PRIMARY KEY,
        scanned_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        notes       TEXT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS repos (
        id          INTEGER PRIMARY KEY,
        scan_run_id INTEGER REFERENCES scan_runs(id),
        name        TEXT,
        url         TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS controllers (
        id          INTEGER PRIMARY KEY,
        repo_id     INTEGER REFERENCES repos(id),
        name        TEXT,
        base_path   TEXT,
        type        TEXT CHECK(type IN ('RestController', 'Controller'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS endpoints (
        id             INTEGER PRIMARY KEY,
        controller_id  INTEGER REFERENCES controllers(id),
        http_method    TEXT,
        path           TEXT
    )
    """,
)


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


def get_default_db_path():
    return str(Path.cwd() / DB_FILE_NAME)


def initialize_database(conn):
    for statement in SCHEMA_STATEMENTS:
        conn.execute(statement)
    conn.commit()


def create_scan_run(conn, notes=None):
    cursor = conn.execute("INSERT INTO scan_runs(notes) VALUES (?)", (notes,))
    conn.commit()
    return cursor.lastrowid


def insert_repo(conn, scan_run_id, repo_name, url=None):
    cursor = conn.execute(
        "INSERT INTO repos(scan_run_id, name, url) VALUES (?, ?, ?)",
        (scan_run_id, repo_name, url),
    )
    return cursor.lastrowid


def insert_controllers(conn, repo_id, controllers):
    for item in controllers:
        cursor = conn.execute(
            "INSERT INTO controllers(repo_id, name, base_path, type) VALUES (?, ?, ?, ?)",
            (repo_id, item["name"], item["base_path"], item["type"]),
        )
        insert_endpoints(conn, cursor.lastrowid, item.get("endpoints", []))


def insert_endpoints(conn, controller_id, endpoints):
    if not endpoints:
        return
    conn.executemany(
        "INSERT INTO endpoints(controller_id, http_method, path) VALUES (?, ?, ?)",
        [(controller_id, item["http_method"], item["path"]) for item in endpoints],
    )


def build_summary_for_scan_run(conn, scan_run_id):
    total_repos_scanned = conn.execute(
        "SELECT COUNT(*) FROM repos WHERE scan_run_id = ?",
        (scan_run_id,),
    ).fetchone()[0]
    repos_with_controllers = conn.execute(
        """
        SELECT COUNT(DISTINCT r.id)
        FROM repos r
        JOIN controllers c ON c.repo_id = r.id
        WHERE r.scan_run_id = ?
        """,
        (scan_run_id,),
    ).fetchone()[0]
    total_rest_controllers = conn.execute(
        """
        SELECT COUNT(*)
        FROM controllers c
        JOIN repos r ON r.id = c.repo_id
        WHERE r.scan_run_id = ? AND c.type = 'RestController'
        """,
        (scan_run_id,),
    ).fetchone()[0]
    total_controllers = conn.execute(
        """
        SELECT COUNT(*)
        FROM controllers c
        JOIN repos r ON r.id = c.repo_id
        WHERE r.scan_run_id = ? AND c.type = 'Controller'
        """,
        (scan_run_id,),
    ).fetchone()[0]
    total_endpoints = conn.execute(
        """
        SELECT COUNT(*)
        FROM endpoints e
        JOIN controllers c ON c.id = e.controller_id
        JOIN repos r ON r.id = c.repo_id
        WHERE r.scan_run_id = ?
        """,
        (scan_run_id,),
    ).fetchone()[0]
    breakdown_rows = conn.execute(
        """
        SELECT
            r.name,
            SUM(CASE WHEN c.type = 'RestController' THEN 1 ELSE 0 END) AS rest_count,
            SUM(CASE WHEN c.type = 'Controller' THEN 1 ELSE 0 END) AS controller_count,
            COUNT(*) AS total_count
        FROM repos r
        JOIN controllers c ON c.repo_id = r.id
        WHERE r.scan_run_id = ?
        GROUP BY r.id, r.name
        ORDER BY total_count DESC, r.name ASC
        """,
        (scan_run_id,),
    ).fetchall()

    return {
        "total_repos_scanned": total_repos_scanned,
        "repos_with_controllers": repos_with_controllers,
        "total_rest_controllers": total_rest_controllers,
        "total_controllers": total_controllers,
        "total_controller_files": total_rest_controllers + total_controllers,
        "total_endpoints": total_endpoints,
        "repo_results": [
            {
                "repo_name": row[0],
                "total_at_rest_controllers": row[1],
                "total_at_controllers": row[2],
                "total_rest_controllers": row[3],
            }
            for row in breakdown_rows
        ],
    }


def count_controllers_in_directory(directory):
    """Collect Spring controller files found within a directory."""
    controllers = []

    for java_file in Path(directory).rglob("*.java"):
        try:
            with open(java_file, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

                if "@RestController" in content:
                    base_path, endpoints = extract_controller_mappings(content)
                    controllers.append(
                        {
                            "name": java_file.stem,
                            "base_path": base_path,
                            "type": "RestController",
                            "endpoints": endpoints,
                        }
                    )
                elif "@Controller" in content:
                    base_path, endpoints = extract_controller_mappings(content)
                    controllers.append(
                        {
                            "name": java_file.stem,
                            "base_path": base_path,
                            "type": "Controller",
                            "endpoints": endpoints,
                        }
                    )
        except Exception:
            continue

    return controllers


def extract_controller_mappings(content):
    class_index = content.find("class ")
    class_level_request_mapping = None
    matches = list(MAPPING_ANNOTATION_PATTERN.finditer(content))
    if class_index >= 0:
        request_mappings_before_class = [
            match
            for match in matches
            if match.group("name") == "Request" and match.end() <= class_index
        ]
        if request_mappings_before_class:
            class_level_request_mapping = request_mappings_before_class[-1]

    base_path = None
    if class_level_request_mapping:
        paths = extract_paths_from_annotation_args(class_level_request_mapping.group("args"))
        if paths:
            base_path = paths[0]

    endpoints = []
    for match in matches:
        if class_level_request_mapping and match.span() == class_level_request_mapping.span():
            continue
        endpoints.extend(build_endpoints_from_annotation(match.group("name"), match.group("args")))

    return base_path, endpoints


def extract_paths_from_annotation_args(annotation_args):
    array_match = PATH_ARRAY_PATTERN.search(annotation_args)
    if array_match:
        return [path for path in STRING_LITERAL_PATTERN.findall(array_match.group("items"))]

    paths = PATH_NAMED_PATTERN.findall(annotation_args)
    if paths:
        return paths

    stripped_args = annotation_args.strip()
    unnamed_paths = []
    if stripped_args.startswith('"'):
        unnamed_paths = STRING_LITERAL_PATTERN.findall(stripped_args)
    if unnamed_paths:
        return unnamed_paths

    return [None]


def build_endpoints_from_annotation(mapping_name, annotation_args):
    paths = extract_paths_from_annotation_args(annotation_args)
    if mapping_name == "Request":
        methods = REQUEST_METHOD_PATTERN.findall(annotation_args) or ["ANY"]
        return [
            {"http_method": method, "path": path}
            for path in paths
            for method in methods
        ]

    return [
        {"http_method": HTTP_METHOD_BY_ANNOTATION[mapping_name], "path": path}
        for path in paths
    ]


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
    """Clone a repo temporarily and collect controllers."""
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

            return count_controllers_in_directory(tmpdir)

        except subprocess.TimeoutExpired:
            raise RuntimeError("Clone timeout")
        except Exception as exc:
            raise RuntimeError(f"Error: {exc}") from exc


def process_repositories(
    repos,
    provider="github",
    token=None,
    db_path=None,
    clone_and_count_func=clone_and_count,
    sqlite_connect=sqlite3.connect,
):
    db_path = db_path or get_default_db_path()
    with sqlite_connect(db_path) as conn:
        initialize_database(conn)
        scan_run_id = create_scan_run(conn)

        for repo_name in repos:
            controllers = clone_and_count_func(repo_name, provider=provider, token=token)
            with conn:
                repo_id = insert_repo(conn, scan_run_id, repo_name, url=build_clone_url(repo_name, provider, token))
                if controllers:
                    insert_controllers(conn, repo_id, controllers)

        return scan_run_id, build_summary_for_scan_run(conn, scan_run_id)


def format_summary_lines(stats):
    lines = [
        "\n" + "=" * 70,
        "SUMMARY",
        "=" * 70,
        f"\nRepositories with controllers: {stats['repos_with_controllers']}/{stats['total_repos_scanned']}",
        f"\nTotal @RestController files: {stats['total_rest_controllers']}",
        f"Total @Controller files: {stats['total_controllers']}",
        f"Total Controller files: {stats['total_controller_files']}",
        f"Total endpoints: {stats['total_endpoints']}",
    ]

    if stats["repo_results"]:
        lines.extend([
            "\n" + "-" * 70,
            "Breakdown by repository:",
            "-" * 70,
        ])
        for result in stats["repo_results"]:
            lines.append(f"{result['repo_name']:50} {result['total_rest_controllers']:3} controllers")

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

        _, stats = process_repositories(repos, provider=args.provider, token=token)
        for line in format_summary_lines(stats):
            print(line)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()