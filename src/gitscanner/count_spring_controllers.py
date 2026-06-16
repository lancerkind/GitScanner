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
from collections import defaultdict

# suppress OpenSSL warnings
import warnings
from urllib.parse import quote
from urllib.parse import urlsplit
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
SUPPORTED_PARAMETER_SOURCE_BY_ANNOTATION = {
    "PathVariable": "PATH",
    "RequestParam": "QUERY",
    "RequestHeader": "HEADER",
    "RequestBody": "BODY",
    "CookieValue": "COOKIE",
}
SUPPORTED_PARAMETER_ANNOTATION_PATTERN = re.compile(
    r"@(?P<name>PathVariable|RequestParam|RequestHeader|RequestBody|CookieValue)\s*(?:\((?P<args>.*?)\))?",
    re.DOTALL,
)
REQUIRED_ATTRIBUTE_PATTERN = re.compile(r"\brequired\s*=\s*(true|false)")
NAME_ATTRIBUTE_PATTERN = re.compile(r"\b(?:value|name)\s*=\s*\"([^\"]+)\"")
KARATE_PATH_PATTERN = re.compile(r"/\S+")
JAVA_SERVICE_TYPE_PATTERN = re.compile(r"\b([A-Z][A-Za-z0-9_]*Service)\b")
INLINE_YAML_PATTERN = re.compile(r"^\s*([A-Za-z0-9_.-]+)\s*:\s*(.+?)\s*$")

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
    """
    CREATE TABLE IF NOT EXISTS parameters (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        endpoint_id   INTEGER NOT NULL REFERENCES endpoints(id),
        name          TEXT NOT NULL,
        java_type     TEXT NOT NULL,
        source        TEXT NOT NULL,
        required      BOOLEAN NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS karate_feature_files (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        repo_id         INTEGER NOT NULL REFERENCES repos(id),
        controller_id   INTEGER REFERENCES controllers(id),
        file_path       TEXT NOT NULL,
        file_name       TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS karate_paths (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        feature_file_id INTEGER NOT NULL REFERENCES karate_feature_files(id),
        path            TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS repo_datasources (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        repo_id         INTEGER NOT NULL REFERENCES repos(id),
        source_file     TEXT NOT NULL,
        url             TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS controller_services (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        controller_id   INTEGER NOT NULL REFERENCES controllers(id),
        service_name    TEXT NOT NULL,
        found           BOOLEAN NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS service_dependency_markers (
        id                    INTEGER PRIMARY KEY AUTOINCREMENT,
        controller_service_id INTEGER NOT NULL REFERENCES controller_services(id),
        marker                TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS dependency_classifications (
        marker          TEXT PRIMARY KEY,
        dependency_type TEXT NOT NULL
    )
    """,
)


def get_default_classifications():
    return [
        ("JdbcTemplate", "SQL Database"),
        ("JpaRepository", "SQL Database"),
        ("CrudRepository", "SQL Database"),
        ("SpannerTemplate", "Spanner"),
        ("SpannerRepository", "Spanner"),
        ("KafkaTemplate", "Kafka"),
        ("KafkaListener", "Kafka"),
        ("RestTemplate", "API"),
        ("WebClient", "API"),
        ("FeignClient", "API"),
        ("jdbc:oracle:", "Oracle"),
        ("jdbc:postgresql:", "CloudSQL"),
        ("cloudsql", "CloudSQL"),
        ("jdbc:mysql:", "CloudSQL"),
        ("jdbc:h2:", "H2"),
        ("jdbc:sqlserver:", "SQL Server"),
    ]


def seed_dependency_classifications(conn):
    conn.executemany(
        """
        INSERT OR IGNORE INTO dependency_classifications(marker, dependency_type)
        VALUES (?, ?)
        """,
        get_default_classifications(),
    )


def build_provider_token(provider, token=None):
    if token is not None:
        return token
    return os.environ.get("GITSCANNER_TOKEN")

def build_parser():
    parser = argparse.ArgumentParser(
        description="Count Spring controller files by cloning repositories from a list.",
        usage="count_spring_controllers <provider> <API_BASE_URL> <repos_file>",
        epilog="Environment variables: GITSCANNER_TOKEN. Scanning results are stored in a sqlite database in the pwd called '{DB_FILE_NAME}'.",

    )
    parser.add_argument(
        "provider",
        choices=("github", "gitlab"),
        help="Repository provider for clone/auth behavior (choices: github, gitlab)",
    )
    parser.add_argument(
        "API_BASE_URL",
        help="Base REST API URL (e.g., https://api.github.com or https://gitlab.com/api/v4)",
    )
    parser.add_argument(
        "repos_file",
        help="Text file containing one repository per line in owner/repo format",
    )
    return parser


def parse_cli_args(argv):
    parser = build_parser()
    if not argv:
        print(parser.format_help(), end="")
        raise SystemExit(1)
    return parser.parse_args(argv)


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
    seed_dependency_classifications(conn)
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
    for item in endpoints:
        cursor = conn.execute(
            "INSERT INTO endpoints(controller_id, http_method, path) VALUES (?, ?, ?)",
            (controller_id, item["http_method"], item["path"]),
        )
        insert_parameters(conn, cursor.lastrowid, item.get("parameters", []))


def insert_parameters(conn, endpoint_id, parameters):
    if not parameters:
        return
    conn.executemany(
        """
        INSERT INTO parameters(endpoint_id, name, java_type, source, required)
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            (endpoint_id, item["name"], item["java_type"], item["source"], item["required"])
            for item in parameters
        ],
    )


def delete_repo_karate_data(conn, repo_id):
    conn.execute(
        """
        DELETE FROM karate_paths
        WHERE feature_file_id IN (
            SELECT id FROM karate_feature_files WHERE repo_id = ?
        )
        """,
        (repo_id,),
    )
    conn.execute("DELETE FROM karate_feature_files WHERE repo_id = ?", (repo_id,))


def insert_karate_feature_file(conn, repo_id, controller_id, file_path, file_name):
    cursor = conn.execute(
        """
        INSERT INTO karate_feature_files(repo_id, controller_id, file_path, file_name)
        VALUES (?, ?, ?, ?)
        """,
        (repo_id, controller_id, file_path, file_name),
    )
    return cursor.lastrowid


def insert_karate_paths(conn, feature_file_id, paths):
    if not paths:
        return
    conn.executemany(
        "INSERT INTO karate_paths(feature_file_id, path) VALUES (?, ?)",
        [(feature_file_id, item) for item in paths],
    )


def insert_repo_datasources(conn, repo_id, datasource_rows):
    if not datasource_rows:
        return
    conn.executemany(
        "INSERT INTO repo_datasources(repo_id, source_file, url) VALUES (?, ?, ?)",
        [(repo_id, row["source_file"], row["url"]) for row in datasource_rows],
    )


def insert_controller_service(conn, controller_id, service_name, found):
    cursor = conn.execute(
        """
        INSERT INTO controller_services(controller_id, service_name, found)
        VALUES (?, ?, ?)
        """,
        (controller_id, service_name, found),
    )
    return cursor.lastrowid


def insert_service_dependency_markers(conn, controller_service_id, markers):
    if not markers:
        return
    conn.executemany(
        """
        INSERT INTO service_dependency_markers(controller_service_id, marker)
        VALUES (?, ?)
        """,
        [(controller_service_id, marker) for marker in sorted(markers)],
    )


def find_controller_id_for_feature_file(file_path, controller_id_by_name):
    for segment in Path(file_path).parts:
        controller_id = controller_id_by_name.get(segment)
        if controller_id is not None:
            return controller_id
    return None


def extract_karate_paths(content):
    seen_paths = []
    seen_set = set()
    for match in KARATE_PATH_PATTERN.finditer(content):
        candidate = match.group(0)
        start_index = match.start()
        if start_index >= 1 and content[start_index - 1] == ":":
            continue
        if candidate.endswith("'") or candidate.endswith('"'):
            candidate = candidate[:-1]
        if candidate.endswith(","):
            candidate = candidate[:-1]
        if not candidate or candidate in seen_set:
            continue
        seen_set.add(candidate)
        seen_paths.append(candidate)
    return seen_paths


def collect_karate_feature_files(directory):
    test_root = Path(directory) / "src" / "test" / "java"
    if not test_root.exists() or not test_root.is_dir():
        return []
    return sorted(test_root.rglob("*.feature"))


def collect_application_yml_files(directory):
    resources_root = Path(directory) / "src" / "main" / "resources"
    if not resources_root.exists() or not resources_root.is_dir():
        return []
    return sorted([
        *resources_root.rglob("application*.yml"),
        *resources_root.rglob("application*.yaml"),
    ])


def strip_yaml_inline_comment(value):
    quote_char = None
    for index, char in enumerate(value):
        if char in {'"', "'"}:
            if quote_char is None:
                quote_char = char
            elif quote_char == char:
                quote_char = None
        if char == "#" and quote_char is None:
            return value[:index].rstrip()
    return value.rstrip()


def normalize_yaml_value(value):
    value = strip_yaml_inline_comment(value.strip())
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def extract_datasource_urls_from_yaml_content(content):
    stack = []
    urls = []
    flat_urls = []

    for raw_line in content.splitlines():
        line_without_comment = strip_yaml_inline_comment(raw_line).rstrip()
        stripped = line_without_comment.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue

        indent = len(line_without_comment) - len(line_without_comment.lstrip(" "))
        while stack and indent <= stack[-1][0]:
            stack.pop()

        key, _, raw_value = stripped.partition(":")
        key = key.strip()
        value = raw_value.strip()

        if not value:
            stack.append((indent, key))
            continue

        full_path = ".".join([item[1] for item in stack] + [key])
        normalized_value = normalize_yaml_value(value)
        if full_path in {"spring.datasource.url", "env.spring.datasource.url"} and normalized_value:
            urls.append(normalized_value)

        inline_match = INLINE_YAML_PATTERN.match(line_without_comment)
        if inline_match and inline_match.group(1) == "env.spring.datasource.url":
            inline_value = normalize_yaml_value(inline_match.group(2))
            if inline_value:
                flat_urls.append(inline_value)

    merged_urls = []
    seen = set()
    for url in [*urls, *flat_urls]:
        if url in seen:
            continue
        seen.add(url)
        merged_urls.append(url)
    return merged_urls


def collect_repo_datasources(repo_root):
    datasource_rows = []
    for file_path in collect_application_yml_files(repo_root):
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        urls = extract_datasource_urls_from_yaml_content(content)
        relative_name = str(file_path.relative_to(repo_root)).replace("\\", "/")
        datasource_rows.extend([{"source_file": relative_name, "url": url} for url in urls])
    return datasource_rows


def find_java_file_by_name(repo_root, file_name):
    matches = list(Path(repo_root).rglob(file_name))
    if not matches:
        return None
    return sorted(matches)[0]


def extract_service_names_from_signature(signature):
    services = set()
    params = split_top_level_commas(signature.strip())
    for param in params:
        parts = [part for part in re.split(r"\s+", param.strip()) if part]
        if len(parts) < 2:
            continue
        java_type = parts[-2]
        cleaned_type = java_type.replace("...", "")
        if cleaned_type.endswith("Service"):
            services.add(cleaned_type)
    return services


def extract_controller_services(content):
    services = set()

    field_declarations = re.findall(
        r"\b(?:private|protected|public)\s+([A-Z][A-Za-z0-9_]*Service)\s+\w+\s*(?:;|=)",
        content,
    )
    services.update(field_declarations)

    for signature in re.findall(r"\(([^)]*)\)", content, re.DOTALL):
        services.update(extract_service_names_from_signature(signature))

    direct_instantiations = re.findall(r"new\s+([A-Z][A-Za-z0-9_]*Service)\s*\(", content)
    services.update(direct_instantiations)

    return sorted(service for service in services if service.endswith("Service"))


def get_dependency_markers(conn):
    rows = conn.execute("SELECT marker FROM dependency_classifications").fetchall()
    return [row[0] for row in rows]


def find_markers_in_service_content(content, markers):
    found_markers = set()
    for marker in markers:
        if marker in content:
            found_markers.add(marker)
    return found_markers


def scan_service_dependencies_for_repo(conn, repo_id, repo_root):
    marker_candidates = get_dependency_markers(conn)
    counts = defaultdict(int)
    not_found_services = []
    controller_rows = conn.execute(
        "SELECT id, name FROM controllers WHERE repo_id = ?",
        (repo_id,),
    ).fetchall()

    for controller_id, controller_name in controller_rows:
        controller_file = find_java_file_by_name(repo_root, f"{controller_name}.java")
        if not controller_file:
            continue
        try:
            controller_content = controller_file.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        service_names = extract_controller_services(controller_content)
        for service_name in service_names:
            service_file = find_java_file_by_name(repo_root, f"{service_name}.java")
            if not service_file:
                insert_controller_service(conn, controller_id, service_name, False)
                not_found_services.append(service_name)
                counts["services_scanned"] += 1
                counts["services_not_found"] += 1
                continue

            controller_service_id = insert_controller_service(conn, controller_id, service_name, True)
            counts["services_scanned"] += 1
            try:
                service_content = service_file.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            markers = find_markers_in_service_content(service_content, marker_candidates)
            insert_service_dependency_markers(conn, controller_service_id, markers)
            counts["dependency_markers"] += len(markers)

    counts["not_found_service_names"] = sorted(set(not_found_services))
    return counts


def print_repo_dependency_summary(repo_name, datasource_rows, dependency_counts):
    datasource_files = sorted({row["source_file"] for row in datasource_rows})
    datasource_details = f" ({', '.join(datasource_files)})" if datasource_files else ""
    missing_details = ""
    if dependency_counts["not_found_service_names"]:
        missing_details = f" ({', '.join(dependency_counts['not_found_service_names'])})"

    print(repo_name)
    print(f"  Datasources found:     {len(datasource_rows)}{datasource_details}")
    print(f"  Services scanned:      {dependency_counts['services_scanned']}")
    print(f"  Services not found:    {dependency_counts['services_not_found']}{missing_details}")
    print(f"  Dependency markers:    {dependency_counts['dependency_markers']}")


def print_service_not_found_warnings(repo_name, service_names):
    for service_name in service_names:
        print(f"WARNING: {service_name}.java not found in repo {repo_name}")


def insert_karate_data_for_repo(conn, repo_id, repo_root):
    controller_rows = conn.execute(
        "SELECT id, name FROM controllers WHERE repo_id = ?",
        (repo_id,),
    ).fetchall()
    controller_id_by_name = {name: controller_id for controller_id, name in controller_rows}

    feature_files = collect_karate_feature_files(repo_root)
    inserted_count = 0
    for feature_file in feature_files:
        try:
            content = feature_file.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        relative_path = str(feature_file.relative_to(repo_root)).replace("\\", "/")
        controller_id = find_controller_id_for_feature_file(relative_path, controller_id_by_name)
        feature_file_id = insert_karate_feature_file(
            conn,
            repo_id,
            controller_id,
            relative_path,
            feature_file.name,
        )
        insert_karate_paths(conn, feature_file_id, extract_karate_paths(content))
        inserted_count += 1

    return inserted_count


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
    total_feature_files = conn.execute(
        """
        SELECT COUNT(*)
        FROM karate_feature_files k
        JOIN repos r ON r.id = k.repo_id
        WHERE r.scan_run_id = ?
        """,
        (scan_run_id,),
    ).fetchone()[0]
    total_datasources = conn.execute(
        """
        SELECT COUNT(*)
        FROM repo_datasources d
        JOIN repos r ON r.id = d.repo_id
        WHERE r.scan_run_id = ?
        """,
        (scan_run_id,),
    ).fetchone()[0]
    total_services_scanned = conn.execute(
        """
        SELECT COUNT(*)
        FROM controller_services cs
        JOIN controllers c ON c.id = cs.controller_id
        JOIN repos r ON r.id = c.repo_id
        WHERE r.scan_run_id = ?
        """,
        (scan_run_id,),
    ).fetchone()[0]
    total_services_not_found = conn.execute(
        """
        SELECT COUNT(*)
        FROM controller_services cs
        JOIN controllers c ON c.id = cs.controller_id
        JOIN repos r ON r.id = c.repo_id
        WHERE r.scan_run_id = ? AND cs.found = 0
        """,
        (scan_run_id,),
    ).fetchone()[0]
    total_dependency_markers = conn.execute(
        """
        SELECT COUNT(*)
        FROM service_dependency_markers sdm
        JOIN controller_services cs ON cs.id = sdm.controller_service_id
        JOIN controllers c ON c.id = cs.controller_id
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
            COUNT(c.id) AS total_count,
            COUNT(DISTINCT k.id) AS feature_file_count
        FROM repos r
        LEFT JOIN controllers c ON c.repo_id = r.id
        LEFT JOIN karate_feature_files k ON k.repo_id = r.id
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
        "total_feature_files": total_feature_files,
        "total_datasources": total_datasources,
        "total_services_scanned": total_services_scanned,
        "total_services_not_found": total_services_not_found,
        "total_dependency_markers": total_dependency_markers,
        "repo_results": [
            {
                "repo_name": row[0],
                "total_at_rest_controllers": row[1],
                "total_at_controllers": row[2],
                "total_rest_controllers": row[3],
                "total_feature_files": row[4],
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
        mapping_endpoints = build_endpoints_from_annotation(match.group("name"), match.group("args"))
        parameters = extract_endpoint_parameters(content, match.end())
        for endpoint in mapping_endpoints:
            endpoint["parameters"] = list(parameters)
        endpoints.extend(mapping_endpoints)

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


def find_matching_closing_parenthesis(content, opening_index):
    depth = 0
    for index in range(opening_index, len(content)):
        char = content[index]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index
    return -1


def split_top_level_commas(content):
    parts = []
    current = []
    angle_depth = 0
    paren_depth = 0
    brace_depth = 0
    bracket_depth = 0
    in_string = False

    for char in content:
        if char == '"':
            in_string = not in_string
            current.append(char)
            continue

        if not in_string:
            if char == "<":
                angle_depth += 1
            elif char == ">" and angle_depth > 0:
                angle_depth -= 1
            elif char == "(":
                paren_depth += 1
            elif char == ")" and paren_depth > 0:
                paren_depth -= 1
            elif char == "{":
                brace_depth += 1
            elif char == "}" and brace_depth > 0:
                brace_depth -= 1
            elif char == "[":
                bracket_depth += 1
            elif char == "]" and bracket_depth > 0:
                bracket_depth -= 1
            elif (
                char == ","
                and angle_depth == 0
                and paren_depth == 0
                and brace_depth == 0
                and bracket_depth == 0
            ):
                part = "".join(current).strip()
                if part:
                    parts.append(part)
                current = []
                continue

        current.append(char)

    last_part = "".join(current).strip()
    if last_part:
        parts.append(last_part)
    return parts


def extract_parameter_name(annotation_args, java_parameter_name):
    if not annotation_args:
        return java_parameter_name

    explicit_name = NAME_ATTRIBUTE_PATTERN.search(annotation_args)
    if explicit_name:
        return explicit_name.group(1)

    stripped_args = annotation_args.strip()
    if stripped_args.startswith('"'):
        unnamed_paths = STRING_LITERAL_PATTERN.findall(stripped_args)
        if unnamed_paths:
            return unnamed_paths[0]

    return java_parameter_name


def extract_parameter_required(source, annotation_args):
    if source in {"PATH", "BODY"}:
        return True

    if not annotation_args:
        return False

    required_match = REQUIRED_ATTRIBUTE_PATTERN.search(annotation_args)
    if required_match:
        return required_match.group(1) == "true"

    return False


def build_parameter_from_definition(parameter_definition):
    annotation_match = SUPPORTED_PARAMETER_ANNOTATION_PATTERN.search(parameter_definition)
    if not annotation_match:
        return None

    source = SUPPORTED_PARAMETER_SOURCE_BY_ANNOTATION[annotation_match.group("name")]
    annotation_args = annotation_match.group("args")
    stripped_definition = SUPPORTED_PARAMETER_ANNOTATION_PATTERN.sub(" ", parameter_definition)
    stripped_definition = re.sub(r"\bfinal\b", " ", stripped_definition)
    stripped_definition = re.sub(r"\s+", " ", stripped_definition).strip()
    java_parameter_match = re.search(r"(?P<java_type>.+?)\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)$", stripped_definition)
    if not java_parameter_match:
        return None

    java_type = java_parameter_match.group("java_type").strip()
    java_name = java_parameter_match.group("name")
    return {
        "name": extract_parameter_name(annotation_args, java_name),
        "java_type": java_type,
        "source": source,
        "required": extract_parameter_required(source, annotation_args),
    }


def extract_endpoint_parameters(content, mapping_end_index):
    opening_parenthesis_index = content.find("(", mapping_end_index)
    if opening_parenthesis_index < 0:
        return []

    closing_parenthesis_index = find_matching_closing_parenthesis(content, opening_parenthesis_index)
    if closing_parenthesis_index < 0:
        return []

    raw_parameters = content[opening_parenthesis_index + 1:closing_parenthesis_index]
    if not raw_parameters.strip():
        return []

    parameters = []
    for parameter_definition in split_top_level_commas(raw_parameters):
        parameter = build_parameter_from_definition(parameter_definition)
        if parameter:
            parameters.append(parameter)
    return parameters


def derive_clone_host(api_base_url, provider="github"):
    parsed = urlsplit(api_base_url)
    host = parsed.netloc
    if provider == "github" and host.startswith("api."):
        return host[4:]
    return host


def build_clone_url(repo_full_name, api_base_url, provider="github", token=None):
    host = derive_clone_host(api_base_url, provider=provider)
    token = build_token(token)
    if provider == "gitlab":
        if token:
            return f"https://oauth2:{token}@{host}/{repo_full_name}.git"
        return f"https://{host}/{repo_full_name}.git"

    if token:
        return f"https://{token}@{host}/{repo_full_name}.git"
    return f"https://{host}/{repo_full_name}.git"


def clone_and_count(repo_full_name, api_base_url, provider="github", token=None, run=subprocess.run):
    """Clone a repo temporarily and collect controllers and Karate data source path."""
    clone_url = build_clone_url(repo_full_name, api_base_url, provider=provider, token=token)

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

            return {
                "controllers": count_controllers_in_directory(tmpdir),
                "repo_path": tmpdir,
            }

        except subprocess.TimeoutExpired:
            raise RuntimeError("Clone timeout")
        except Exception as exc:
            raise RuntimeError(f"Error: {exc}") from exc


def process_repositories(
    repos,
    api_base_url="https://api.github.com",
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
            scan_result = clone_and_count_func(repo_name, api_base_url=api_base_url, provider=provider, token=token)
            if isinstance(scan_result, dict):
                controllers = scan_result.get("controllers", [])
                repo_path = scan_result.get("repo_path")
            else:
                controllers = scan_result
                repo_path = None
            with conn:
                repo_id = insert_repo(
                    conn,
                    scan_run_id,
                    repo_name,
                    url=build_clone_url(repo_name, api_base_url, provider, token),
                )
                if controllers:
                    insert_controllers(conn, repo_id, controllers)
                delete_repo_karate_data(conn, repo_id)
                datasource_rows = []
                dependency_counts = defaultdict(int)
                if repo_path:
                    insert_karate_data_for_repo(conn, repo_id, repo_path)
                    datasource_rows = collect_repo_datasources(repo_path)
                    insert_repo_datasources(conn, repo_id, datasource_rows)
                    dependency_counts = scan_service_dependencies_for_repo(conn, repo_id, repo_path)
                    print_service_not_found_warnings(repo_name, dependency_counts["not_found_service_names"])
                print_repo_dependency_summary(repo_name, datasource_rows, dependency_counts)

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
        f"Total feature files: {stats['total_feature_files']}",
        f"Total datasources: {stats['total_datasources']}",
        f"Total services scanned: {stats['total_services_scanned']}",
        f"Total services not found: {stats['total_services_not_found']}",
        f"Total dependency markers: {stats['total_dependency_markers']}",
    ]

    if stats["repo_results"]:
        lines.extend([
            "\n" + "-" * 70,
            "Breakdown by repository:",
            "-" * 70,
        ])
        for result in stats["repo_results"]:
            lines.append(
                f"{result['repo_name']:50} {result['total_rest_controllers']:3} controllers"
                f" {result['total_feature_files']:3} feature files"
            )

    return lines


def main():
    try:
        args = parse_cli_args(sys.argv[1:])
        repos = read_repos_from_file(args.repos_file)

        if not repos:
            raise RuntimeError("No repositories found in file")

        print(f"Loaded {len(repos)} repositories from {args.repos_file}")
        print(f"\nCloning and searching {len(repos)} repositories...\n")

        token = build_token()

        _, stats = process_repositories(
            repos,
            api_base_url=args.API_BASE_URL,
            provider=args.provider,
            token=token,
        )
        for line in format_summary_lines(stats):
            print(line)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()