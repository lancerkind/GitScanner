#!/usr/bin/env python3
"""CLI orchestration for scanning Spring controller data."""

# suppress OpenSSL warnings
import warnings
from urllib.parse import quote
warnings.filterwarnings(
    "ignore",
    message="urllib3 v2 only supports OpenSSL 1.1.1+.*",
)

import argparse
import os
import sqlite3
import sys
from pathlib import Path

from gitscanner.core.git import (
    build_clone_url,
    build_github_headers,
    build_gitlab_headers,
    build_provider_token,
    build_token,
    clone_and_count,
    derive_clone_host,
    get_repo_info,
)
from gitscanner.core.models import ScanResult
from gitscanner.core.repository import RepositoryClient
from gitscanner.core.scan_runner import ScanRunner
from gitscanner.persistence.sqlite_store import SqliteStore, connect
from gitscanner.reporting.summary import format_summary_lines
from gitscanner.scanners.karate.features import KarateFeatureScanner
from gitscanner.scanners.springboot.controllers import count_controllers_in_directory
from gitscanner.scanners.springboot.datasources import collect_repo_datasources
from gitscanner.scanners.springboot.services import SpringServiceDependencyScanner


DB_FILE_NAME = "gitscanner.db"


class SpringControllerScannerCompat:
    capability = "springboot.controllers"

    def scan(self, context):
        return ScanResult(capability=self.capability, records=count_controllers_in_directory(str(context.repo_root)))


class SpringDatasourceScannerCompat:
    capability = "springboot.datasources"

    def scan(self, context):
        return ScanResult(capability=self.capability, records=collect_repo_datasources(str(context.repo_root)))


def build_parser():
    parser = argparse.ArgumentParser(description="Scan repositories for Spring controller data")
    parser.add_argument("provider", nargs="?", default="github", choices=["github", "gitlab"])
    parser.add_argument("api_base_url", nargs="?", default="https://api.github.com")
    parser.add_argument("repos_file", nargs="?", default="github_repos.txt")
    parser.add_argument("--token", dest="token", default=None)
    parser.add_argument("--db-path", dest="db_path", default=None)
    return parser


def parse_cli_args(argv):
    parser = build_parser()
    if not argv:
        print(parser.format_help(), end="")
        raise SystemExit(1)
    return parser.parse_args(argv)


def read_repos_from_file(file_path):
    path = Path(file_path)
    with path.open("r", encoding="utf-8") as file_handle:
        return [
            line.strip()
            for line in file_handle
            if line.strip() and not line.lstrip().startswith("#")
        ]


def get_default_db_path():
    return str(Path.cwd() / DB_FILE_NAME)


def process_repositories(
    repos,
    api_base_url="https://api.github.com",
    provider="github",
    token=None,
    db_path=None,
    clone_and_count_func=clone_and_count,
    sqlite_connect=sqlite3.connect,
):
    database_path = db_path or get_default_db_path()
    conn = sqlite_connect(database_path)
    try:
        store = SqliteStore(conn)
        runner = ScanRunner(
            repository_client=RepositoryClient(clone_and_count_func=clone_and_count_func),
            store=store,
            scanners=[
                SpringControllerScannerCompat(),
                KarateFeatureScanner(conn),
                SpringDatasourceScannerCompat(),
                SpringServiceDependencyScanner(conn),
            ],
            reporter=store,
            api_base_url=api_base_url,
            provider=provider,
            token=token,
        )
        return runner.run(repos)
    finally:
        conn.close()


def main():
    args = parse_cli_args(sys.argv[1:])
    token = build_provider_token(args.provider, token=args.token) or os.environ.get(
        "GITHUB_TOKEN" if args.provider == "github" else "GITLAB_TOKEN"
    )
    repos = read_repos_from_file(args.repos_file)
    _, stats = process_repositories(
        repos,
        api_base_url=args.api_base_url,
        provider=args.provider,
        token=token,
        db_path=args.db_path,
        sqlite_connect=connect,
    )
    for line in format_summary_lines(stats):
        print(line)


if __name__ == "__main__":
    main()