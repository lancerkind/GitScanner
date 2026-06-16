import subprocess
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from gitscanner.count_spring_controllers import (
    build_parser,
    build_clone_url,
    build_gitlab_headers,
    build_gitlab_token,
    build_github_headers,
    build_summary_for_scan_run,
    collect_karate_feature_files,
    count_controllers_in_directory,
    create_scan_run,
    extract_controller_services,
    extract_datasource_urls_from_yaml_content,
    extract_karate_paths,
    format_summary_lines,
    insert_karate_data_for_repo,
    initialize_database,
    insert_controllers,
    insert_repo,
    get_repo_info,
    parse_cli_args,
    process_repositories,
    read_repos_from_file,
)


class DummyResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}

    def json(self):
        return self._payload


def test_parse_cli_args_parses_repos_file():
    args = parse_cli_args(["https://api.github.com", "github_repos.txt"])
    assert args.API_BASE_URL == "https://api.github.com"
    assert args.repos_file == "github_repos.txt"
    assert args.provider == "github"


def test_parse_cli_args_parses_provider_option():
    args = parse_cli_args(["https://gitlab.com/api/v4", "github_repos.txt", "--provider", "gitlab"])
    assert args.provider == "gitlab"


def test_parse_cli_args_no_args_prints_usage_and_exits(capsys):
    with pytest.raises(SystemExit) as exc_info:
        parse_cli_args([])

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert captured.out == build_parser().format_help()
    assert "--provider" in captured.out
    assert "GITHUB_TOKEN" in captured.out
    assert "GITLAB_TOKEN" in captured.out


def test_read_repos_from_file_skips_comments_and_empty_lines(tmp_path):
    repos_file = tmp_path / "github_repos.txt"
    repos_file.write_text("\n# comment\norg/repo-a\n\norg/repo-b\n", encoding="utf-8")

    repos = read_repos_from_file(repos_file)
    assert repos == ["org/repo-a", "org/repo-b"]


def test_read_repos_from_file_not_found_raises_runtime_error():
    with pytest.raises(RuntimeError, match="not found"):
        read_repos_from_file("missing-repos-file.txt")


def test_build_github_headers_with_and_without_token(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    assert build_github_headers() == {"Accept": "application/vnd.github.v3+json"}
    assert build_github_headers("abc123")["Authorization"] == "token abc123"


def test_build_gitlab_token_and_headers(monkeypatch):
    monkeypatch.delenv("GITLAB_TOKEN", raising=False)
    assert build_gitlab_token() is None
    assert build_gitlab_headers() == {"Accept": "application/json"}
    assert build_gitlab_headers("xyz") == {"Accept": "application/json", "PRIVATE-TOKEN": "xyz"}


def test_build_clone_url_for_github_public_and_custom_api_urls():
    assert (
        build_clone_url("org/repo", api_base_url="https://api.github.com", token="tkn")
        == "https://tkn@github.com/org/repo.git"
    )
    assert (
        build_clone_url("org/repo", api_base_url="https://api.github.com", token=None)
        == "https://github.com/org/repo.git"
    )
    assert (
        build_clone_url("org/repo", api_base_url="https://git.company.com/api/v3", token="tkn")
        == "https://tkn@git.company.com/org/repo.git"
    )
    assert (
        build_clone_url("org/repo", api_base_url="https://git.company.com/api/v3", token=None)
        == "https://git.company.com/org/repo.git"
    )


def test_build_clone_url_for_gitlab_public_and_custom_api_urls():
    assert (
        build_clone_url(
            "group/sub/repo",
            api_base_url="https://gitlab.com/api/v4",
            provider="gitlab",
            token="gl-token",
        )
        == "https://oauth2:gl-token@gitlab.com/group/sub/repo.git"
    )
    assert (
        build_clone_url(
            "group/sub/repo",
            api_base_url="https://gitlab.com/api/v4",
            provider="gitlab",
            token=None,
        )
        == "https://gitlab.com/group/sub/repo.git"
    )
    assert (
        build_clone_url(
            "group/sub/repo",
            api_base_url="https://gitlab.company.com/api/v4",
            provider="gitlab",
            token="gl-token",
        )
        == "https://oauth2:gl-token@gitlab.company.com/group/sub/repo.git"
    )
    assert (
        build_clone_url(
            "group/sub/repo",
            api_base_url="https://gitlab.company.com/api/v4",
            provider="gitlab",
            token=None,
        )
        == "https://gitlab.company.com/group/sub/repo.git"
    )


def test_get_repo_info_returns_payload_on_200():
    def fake_get(url, headers=None):
        return DummyResponse(status_code=200, payload={"name": "repo"})

    payload = get_repo_info("org/repo", headers={}, get=fake_get)
    assert payload == {"name": "repo"}


def test_get_repo_info_returns_none_on_non_200():
    def fake_get(url, headers=None):
        return DummyResponse(status_code=404)

    assert get_repo_info("org/repo", headers={}, get=fake_get) is None


def test_count_controllers_in_directory_counts_controller_types(tmp_path):
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "A.java").write_text("@RestController class A {}", encoding="utf-8")
    (src_dir / "B.java").write_text("@Controller class B {}", encoding="utf-8")
    (src_dir / "C.java").write_text("class C {}", encoding="utf-8")

    controllers = count_controllers_in_directory(tmp_path)
    assert len(controllers) == 2
    assert sorted(item["type"] for item in controllers) == ["Controller", "RestController"]
    assert all("endpoints" in item for item in controllers)


def test_count_controllers_in_directory_prefers_rest_controller_if_both_annotations(tmp_path):
    (tmp_path / "Both.java").write_text("@RestController @Controller class Both {}", encoding="utf-8")
    controllers = count_controllers_in_directory(tmp_path)
    assert controllers == [{"name": "Both", "base_path": None, "type": "RestController", "endpoints": []}]


def test_count_controllers_in_directory_extracts_base_path_and_endpoints(tmp_path):
    (tmp_path / "CatController.java").write_text(
        """
        @RestController
        @RequestMapping(path = "/api/cats")
        class CatController {
            @GetMapping("/{id}")
            Cat getById(
                @PathVariable Long id,
                @RequestParam(value="status", required=false, defaultValue="active") String status,
                @RequestHeader("Authorization") String authorization,
                @RequestBody OrderRequest body,
                HttpServletRequest request
            ) {}

            @RequestMapping(value = "/x", method = RequestMethod.POST)
            void postX() {}

            @RequestMapping("/any")
            void any() {}
        }
        """,
        encoding="utf-8",
    )

    controllers = count_controllers_in_directory(tmp_path)
    assert len(controllers) == 1
    controller = controllers[0]
    assert controller["base_path"] == "/api/cats"
    assert controller["type"] == "RestController"
    assert controller["endpoints"] == [
        {
            "http_method": "GET",
            "path": "/{id}",
            "parameters": [
                {"name": "id", "java_type": "Long", "source": "PATH", "required": True},
                {"name": "status", "java_type": "String", "source": "QUERY", "required": False},
                {
                    "name": "Authorization",
                    "java_type": "String",
                    "source": "HEADER",
                    "required": False,
                },
                {"name": "body", "java_type": "OrderRequest", "source": "BODY", "required": True},
            ],
        },
        {"http_method": "POST", "path": "/x", "parameters": []},
        {"http_method": "ANY", "path": "/any", "parameters": []},
    ]


def test_count_controllers_in_directory_supports_multiple_request_methods(tmp_path):
    (tmp_path / "MultiController.java").write_text(
        """
        @Controller
        class MultiController {
            @RequestMapping(path = "/m", method = {RequestMethod.GET, RequestMethod.DELETE})
            String method(@RequestParam("status") String status) { return "ok"; }
        }
        """,
        encoding="utf-8",
    )

    controllers = count_controllers_in_directory(tmp_path)
    assert controllers[0]["endpoints"] == [
        {
            "http_method": "GET",
            "path": "/m",
            "parameters": [
                {"name": "status", "java_type": "String", "source": "QUERY", "required": False}
            ],
        },
        {
            "http_method": "DELETE",
            "path": "/m",
            "parameters": [
                {"name": "status", "java_type": "String", "source": "QUERY", "required": False}
            ],
        },
    ]


def test_count_controllers_in_directory_extracts_annotation_variants_and_generic_types(tmp_path):
    (tmp_path / "OrderController.java").write_text(
        """
        @RestController
        class OrderController {
            @PutMapping("/orders/{id}")
            void update(
                @PathVariable("id") Long orderId,
                @RequestParam(name="page", required=true) Integer page,
                @RequestHeader(value="X-Trace") String trace,
                @CookieValue("sid") String sessionId,
                @RequestBody List<String> values,
                Model model
            ) {}
        }
        """,
        encoding="utf-8",
    )

    controllers = count_controllers_in_directory(tmp_path)
    assert controllers[0]["endpoints"][0]["parameters"] == [
        {"name": "id", "java_type": "Long", "source": "PATH", "required": True},
        {"name": "page", "java_type": "Integer", "source": "QUERY", "required": True},
        {"name": "X-Trace", "java_type": "String", "source": "HEADER", "required": False},
        {"name": "sid", "java_type": "String", "source": "COOKIE", "required": False},
        {"name": "values", "java_type": "List<String>", "source": "BODY", "required": True},
    ]


def test_count_controllers_in_directory_ignores_unreadable_file(monkeypatch, tmp_path):
    broken_file = tmp_path / "Broken.java"
    broken_file.write_text("@Controller class Broken {}", encoding="utf-8")

    import builtins

    original_open = builtins.open

    def fake_open(file, *args, **kwargs):
        if Path(file) == broken_file:
            raise OSError("cannot read")
        return original_open(file, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", fake_open)
    controllers = count_controllers_in_directory(tmp_path)
    assert controllers == []


def test_process_repositories_aggregates_totals_and_filters_zero_repos():
    def fake_clone_and_count(repo_name, api_base_url, provider="github", token=None):
        assert api_base_url == "https://gitlab.company.com/api/v4"
        assert provider == "gitlab"
        return {
            "org/a": [
                {"name": "A1", "base_path": None, "type": "RestController"},
                {"name": "A2", "base_path": None, "type": "RestController", "endpoints": [{"http_method": "GET", "path": "/a2"}]},
                {"name": "A3", "base_path": None, "type": "Controller", "endpoints": []},
            ],
            "org/b": [],
            "org/c": [
                {"name": "C1", "base_path": None, "type": "Controller", "endpoints": [{"http_method": "POST", "path": "/c1"}]},
                {"name": "C2", "base_path": None, "type": "Controller", "endpoints": []},
                {"name": "C3", "base_path": None, "type": "Controller", "endpoints": []},
            ],
        }[repo_name]

    _, stats = process_repositories(
        ["org/a", "org/b", "org/c"],
        api_base_url="https://gitlab.company.com/api/v4",
        provider="gitlab",
        token="abc",
        db_path=":memory:",
        clone_and_count_func=fake_clone_and_count,
    )

    assert stats["total_rest_controllers"] == 2
    assert stats["total_controllers"] == 4
    assert stats["total_controller_files"] == 6
    assert [item["repo_name"] for item in stats["repo_results"]] == ["org/a", "org/c", "org/b"]
    assert stats["repo_results"][0]["total_at_rest_controllers"] == 2
    assert stats["repo_results"][0]["total_at_controllers"] == 1
    assert stats["repo_results"][0]["total_rest_controllers"] == 3
    assert stats["total_endpoints"] == 2
    assert stats["total_feature_files"] == 0


def test_format_summary_lines_includes_sorted_breakdown():
    stats = {
        "repos_with_controllers": 2,
        "total_repos_scanned": 3,
        "total_rest_controllers": 2,
        "total_controllers": 3,
        "total_controller_files": 5,
        "total_endpoints": 7,
        "total_feature_files": 4,
        "total_datasources": 2,
        "total_services_scanned": 5,
        "total_services_not_found": 1,
        "total_dependency_markers": 6,
        "repo_results": [
            {
                "repo_name": "org/two",
                "total_at_rest_controllers": 1,
                "total_at_controllers": 3,
                "total_rest_controllers": 4,
                "total_feature_files": 3,
            },
            {
                "repo_name": "org/one",
                "total_at_rest_controllers": 1,
                "total_at_controllers": 0,
                "total_rest_controllers": 1,
                "total_feature_files": 1,
            },
        ],
    }

    lines = format_summary_lines(stats)
    assert any("Repositories with controllers: 2/3" in line for line in lines)
    assert any("Total feature files: 4" in line for line in lines)
    assert any("Total datasources: 2" in line for line in lines)
    assert any("Total dependency markers: 6" in line for line in lines)
    joined = "\n".join(lines)
    assert joined.index("org/two") < joined.index("org/one")
    assert "4 controllers   3 feature files" in joined


def test_initialize_database_creates_schema(tmp_path):
    db_path = tmp_path / "scan.db"
    with sqlite3.connect(db_path) as conn:
        initialize_database(conn)
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('scan_runs','repos','controllers','parameters')"
            )
        }
    assert tables == {"scan_runs", "repos", "controllers", "parameters"}
    with sqlite3.connect(db_path) as conn:
        endpoint_tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('endpoints','karate_feature_files','karate_paths')"
            )
        }
    assert endpoint_tables == {"endpoints", "karate_feature_files", "karate_paths"}
    with sqlite3.connect(db_path) as conn:
        dependency_tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('repo_datasources','controller_services','service_dependency_markers','dependency_classifications')"
            )
        }
    assert dependency_tables == {
        "repo_datasources",
        "controller_services",
        "service_dependency_markers",
        "dependency_classifications",
    }


def test_extract_datasource_urls_supports_all_required_structures():
    content = """
spring:
  datasource:
    url: jdbc:oracle:thin:@//hostname:1521/mydb
env:
  spring:
    datasource:
      url: jdbc:postgresql://localhost:5432/db
env.spring.datasource.url: jdbc:h2:mem:testdb
"""

    urls = extract_datasource_urls_from_yaml_content(content)
    assert urls == [
        "jdbc:oracle:thin:@//hostname:1521/mydb",
        "jdbc:postgresql://localhost:5432/db",
        "jdbc:h2:mem:testdb",
    ]


def test_extract_controller_services_supports_all_required_styles():
    content = """
@RestController
class CatController {
    @Autowired
    private CatService catService;

    public CatController(DogService dogService) {}

    @Autowired
    public void setBirdService(BirdService birdService) {}

    private FishService fishService = new FishService();
}
"""

    assert extract_controller_services(content) == ["BirdService", "CatService", "DogService", "FishService"]


def test_db_insert_scan_repo_controller_and_summary(tmp_path):
    db_path = tmp_path / "scan.db"
    with sqlite3.connect(db_path) as conn:
        initialize_database(conn)
        scan_run_id = create_scan_run(conn)
        repo_id = insert_repo(conn, scan_run_id, "org/repo", "https://example/repo.git")
        insert_controllers(
            conn,
            repo_id,
            [
                {
                    "name": "A",
                    "base_path": "/api",
                    "type": "RestController",
                    "endpoints": [
                        {
                            "http_method": "GET",
                            "path": "/a",
                            "parameters": [
                                {"name": "id", "java_type": "Long", "source": "PATH", "required": True}
                            ],
                        },
                        {"http_method": "POST", "path": "/a"},
                    ],
                },
                {"name": "B", "base_path": None, "type": "Controller", "endpoints": []},
            ],
        )
        conn.commit()
        summary = build_summary_for_scan_run(conn, scan_run_id)

    assert summary["total_repos_scanned"] == 1
    assert summary["repos_with_controllers"] == 1
    assert summary["total_rest_controllers"] == 1
    assert summary["total_controllers"] == 1
    assert summary["total_controller_files"] == 2
    assert summary["total_endpoints"] == 2
    assert summary["total_feature_files"] == 0
    assert summary["repo_results"][0]["repo_name"] == "org/repo"
    with sqlite3.connect(db_path) as conn:
        parameters = conn.execute("SELECT name, java_type, source, required FROM parameters").fetchall()
    assert parameters == [("id", "Long", "PATH", 1)]


def test_collect_karate_feature_files_scans_only_src_test_java(tmp_path):
    expected = tmp_path / "src" / "test" / "java" / "com" / "example" / "CatController" / "cat.feature"
    expected.parent.mkdir(parents=True)
    expected.write_text("Feature: cats", encoding="utf-8")
    ignored = tmp_path / "src" / "test" / "resources" / "CatController" / "ignored.feature"
    ignored.parent.mkdir(parents=True)
    ignored.write_text("Feature: ignored", encoding="utf-8")

    feature_files = collect_karate_feature_files(tmp_path)
    assert feature_files == [expected]


def test_extract_karate_paths_extracts_distinct_non_url_paths():
    content = """
    * path '/cats'
    * path '/cats/{id}'
    Given url 'https://api.example.com'
    And path '/cats/#(catId)'
    And path '/cats'
    """

    paths = extract_karate_paths(content)
    assert paths == ["/cats", "/cats/{id}", "/cats/#(catId)"]


def test_insert_karate_data_for_repo_stores_controller_mapping_and_paths(tmp_path):
    repo_root = tmp_path / "repo"
    feature_under_controller = repo_root / "src" / "test" / "java" / "com" / "example" / "CatController" / "get_cat.feature"
    feature_under_controller.parent.mkdir(parents=True)
    feature_under_controller.write_text("""
Feature: Cat tests
  Scenario: fetch cat
    Given path '/cats/{id}'
    And path '/cats/{id}'
""", encoding="utf-8")
    feature_without_controller = repo_root / "src" / "test" / "java" / "misc" / "orphan.feature"
    feature_without_controller.parent.mkdir(parents=True)
    feature_without_controller.write_text("Feature: orphan", encoding="utf-8")

    with sqlite3.connect(":memory:") as conn:
        initialize_database(conn)
        scan_run_id = create_scan_run(conn)
        repo_id = insert_repo(conn, scan_run_id, "org/repo", "https://example/repo.git")
        insert_controllers(
            conn,
            repo_id,
            [{"name": "CatController", "base_path": "/cats", "type": "RestController", "endpoints": []}],
        )
        inserted_count = insert_karate_data_for_repo(conn, repo_id, repo_root)
        conn.commit()

        assert inserted_count == 2
        rows = conn.execute(
            """
            SELECT k.file_name, c.name, p.path
            FROM karate_feature_files k
            LEFT JOIN controllers c ON c.id = k.controller_id
            LEFT JOIN karate_paths p ON p.feature_file_id = k.id
            ORDER BY k.file_name, p.path
            """
        ).fetchall()

    assert rows == [
        ("get_cat.feature", "CatController", "/cats/{id}"),
        ("orphan.feature", None, None),
    ]


def test_process_repositories_includes_karate_feature_files(tmp_path):
    def fake_clone_and_count(repo_name, api_base_url, provider="github", token=None):
        repo_root = tmp_path / repo_name.replace("/", "_")
        feature = repo_root / "src" / "test" / "java" / "com" / "example" / "CatController" / "cat.feature"
        feature.parent.mkdir(parents=True, exist_ok=True)
        feature.write_text("Given path '/cats'", encoding="utf-8")
        return {
            "controllers": [{"name": "CatController", "base_path": "/cats", "type": "RestController", "endpoints": []}],
            "repo_path": str(repo_root),
        }

    _, stats = process_repositories(
        ["org/repo"],
        db_path=":memory:",
        clone_and_count_func=fake_clone_and_count,
    )

    assert stats["total_feature_files"] == 1


def test_process_repositories_scans_datasources_and_service_markers(tmp_path):
    repo_root = tmp_path / "repo"
    application = repo_root / "application.yml"
    application.parent.mkdir(parents=True)
    application.write_text(
        """
spring:
  datasource:
    url: jdbc:mysql://localhost:3306/cats
""",
        encoding="utf-8",
    )
    controller = repo_root / "src" / "main" / "java" / "com" / "example" / "CatController.java"
    controller.parent.mkdir(parents=True)
    controller.write_text(
        """
@RestController
class CatController {
    private CatService catService;
}
""",
        encoding="utf-8",
    )
    service = repo_root / "src" / "main" / "java" / "com" / "example" / "CatService.java"
    service.write_text("class CatService { JdbcTemplate jdbcTemplate; KafkaTemplate kafkaTemplate; }", encoding="utf-8")

    def fake_clone_and_count(repo_name, api_base_url, provider="github", token=None):
        return {
            "controllers": [{"name": "CatController", "base_path": None, "type": "RestController"}],
            "repo_path": str(repo_root),
        }

    _, stats = process_repositories(
        ["org/repo"],
        db_path=str(tmp_path / "scan.db"),
        clone_and_count_func=fake_clone_and_count,
    )

    assert stats["total_datasources"] == 1
    assert stats["total_services_scanned"] == 1
    assert stats["total_services_not_found"] == 0
    assert stats["total_dependency_markers"] == 2
    assert stats["repo_results"][0]["total_feature_files"] == 0


def test_clone_and_count_wraps_timeout(monkeypatch):
    from gitscanner import count_spring_controllers as module

    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="git clone", timeout=300)

    with pytest.raises(RuntimeError, match="Clone timeout"):
        module.clone_and_count(
            "org/repo",
            api_base_url="https://gitlab.company.com/api/v4",
            provider="gitlab",
            token="abc",
            run=fake_run,
        )


def test_clone_and_count_wraps_failed_clone():
    from gitscanner import count_spring_controllers as module

    def fake_run(*args, **kwargs):
        return SimpleNamespace(returncode=1, stderr="fatal: auth failed")

    with pytest.raises(RuntimeError, match="Clone failed"):
        module.clone_and_count(
            "org/repo",
            api_base_url="https://gitlab.company.com/api/v4",
            provider="gitlab",
            token="abc",
            run=fake_run,
        )


def test_main_success_prints_summary(monkeypatch, capsys):
    from gitscanner import count_spring_controllers as module

    monkeypatch.setattr(
        module,
        "parse_cli_args",
        lambda argv: SimpleNamespace(
            API_BASE_URL="https://gitlab.company.com/api/v4",
            repos_file="github_repos.txt",
            provider="gitlab",
        ),
    )
    monkeypatch.setattr(module, "read_repos_from_file", lambda path: ["org/repo"])
    monkeypatch.setattr(module, "build_gitlab_token", lambda token=None: "abc")
    monkeypatch.setattr(
        module,
        "process_repositories",
        lambda repos,
               api_base_url="https://api.github.com",
               provider="github",
               token=None,
               db_path=None,
               clone_and_count_func=None,
               sqlite_connect=None: (
            1,
            {
                "total_repos_scanned": 1,
                "repos_with_controllers": 1,
                "total_rest_controllers": 1,
                "total_controllers": 0,
                "total_controller_files": 1,
                "total_endpoints": 1,
                "total_feature_files": 0,
                "total_datasources": 0,
                "total_services_scanned": 0,
                "total_services_not_found": 0,
                "total_dependency_markers": 0,
                "repo_results": [
                    {
                        "repo_name": "org/repo",
                        "total_at_rest_controllers": 1,
                        "total_at_controllers": 0,
                        "total_rest_controllers": 1,
                        "total_feature_files": 0,
                    }
                ],
            },
        ),
    )

    module.main()
    out = capsys.readouterr().out
    assert "Loaded 1 repositories" in out
    assert "SUMMARY" in out


def test_main_exits_on_runtime_error(monkeypatch, capsys):
    from gitscanner import count_spring_controllers as module

    monkeypatch.setattr(module, "parse_cli_args", lambda argv: (_ for _ in ()).throw(RuntimeError("boom")))

    with pytest.raises(SystemExit) as exc_info:
        module.main()

    assert exc_info.value.code == 1
    err = capsys.readouterr().err
    assert "boom" in err
