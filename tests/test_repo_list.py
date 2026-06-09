import pytest
import requests
from types import SimpleNamespace

from gitscanner.repo_list import (
    build_parser,
    build_gitlab_headers,
    build_github_headers,
    fetch_gitlab_repos,
    fetch_github_repos,
    fetch_repos,
    format_repo_names,
    parse_cli_args,
)


class DummyResponse:
    def __init__(self, status_code=200, ok=True, payload=None, links=None):
        self.status_code = status_code
        self.ok = ok
        self._payload = payload if payload is not None else []
        self.links = links if links is not None else {}

    def json(self):
        return self._payload


def test_parse_cli_args_parses_filter_option():
    args = parse_cli_args(["https://api.github.com", "anthropics", "--filter", "spring"])
    assert args.API_BASE_URL == "https://api.github.com"
    assert args.ORG == "anthropics"
    assert args.filter_substring == "spring"
    assert args.provider == "github"


def test_parse_cli_args_parses_provider_option():
    args = parse_cli_args(["https://gitlab.com/api/v4", "group/name", "--provider", "gitlab"])
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


def test_build_github_headers_uses_explicit_token():
    headers = build_github_headers(token="abc123")
    assert headers == {"Authorization": "token abc123"}


def test_build_github_headers_empty_without_token(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    headers = build_github_headers()
    assert headers == {}


def test_build_gitlab_headers_with_and_without_token(monkeypatch):
    monkeypatch.delenv("GITLAB_TOKEN", raising=False)
    assert build_gitlab_headers() == {}
    assert build_gitlab_headers("gl-token") == {"PRIVATE-TOKEN": "gl-token"}


def test_fetch_github_repos_falls_back_to_users_endpoint_and_paginates():
    calls = []

    def fake_get(url, headers=None, params=None):
        calls.append((url, params["page"]))
        if len(calls) == 1:
            return DummyResponse(status_code=404, ok=False)
        if len(calls) == 2:
            return DummyResponse(
                status_code=200,
                ok=True,
                payload=[{"name": "repo1", "full_name": "org/repo1"}],
                links={"next": {"url": "next"}},
            )
        return DummyResponse(
            status_code=200,
            ok=True,
            payload=[{"name": "repo2", "full_name": "org/repo2"}],
            links={},
        )

    repos = fetch_github_repos("https://api.github.com/", "anthropics", headers={}, get=fake_get)

    assert [repo["full_name"] for repo in repos] == ["org/repo1", "org/repo2"]
    assert calls[0][0].endswith("/orgs/anthropics/repos")
    assert calls[1][0].endswith("/users/anthropics/repos")
    assert calls[2] == ("https://api.github.com/users/anthropics/repos", 2)


@pytest.mark.parametrize("status_code", [401, 403])
def test_fetch_github_repos_auth_and_rate_limit_errors(status_code):
    def fake_get(url, headers=None, params=None):
        return DummyResponse(status_code=status_code, ok=False)

    with pytest.raises(RuntimeError, match="Authentication failed or rate limit exceeded"):
        fetch_github_repos("https://api.github.com", "anthropics", get=fake_get)


def test_fetch_github_repos_generic_http_error():
    def fake_get(url, headers=None, params=None):
        return DummyResponse(status_code=500, ok=False)

    with pytest.raises(RuntimeError, match="Received HTTP 500"):
        fetch_github_repos("https://api.github.com", "anthropics", get=fake_get)


def test_fetch_github_repos_wraps_request_exception():
    def fake_get(url, headers=None, params=None):
        raise requests.exceptions.Timeout("network timeout")

    with pytest.raises(RuntimeError, match="network timeout"):
        fetch_github_repos("https://api.github.com", "anthropics", get=fake_get)


def test_fetch_gitlab_repos_group_path_paginates_and_encodes_namespace():
    calls = []

    def fake_get(url, headers=None, params=None):
        calls.append((url, params["page"]))
        assert headers == {"PRIVATE-TOKEN": "abc"}
        if len(calls) == 1:
            return DummyResponse(
                status_code=200,
                ok=True,
                payload=[{"name": "spring-api", "full_name": "group/sub/spring-api"}],
                links={"next": {"url": "next"}},
            )
        return DummyResponse(status_code=200, ok=True, payload=[], links={})

    repos = fetch_gitlab_repos(
        "https://gitlab.com/api/v4",
        "group/sub",
        headers={"PRIVATE-TOKEN": "abc"},
        get=fake_get,
    )

    assert repos == [{"name": "spring-api", "full_name": "group/sub/spring-api"}]
    assert calls[0][0].endswith("/groups/group%2Fsub/projects")


def test_fetch_gitlab_repos_falls_back_to_user_projects():
    calls = []

    def fake_get(url, headers=None, params=None):
        calls.append(url)
        if url.endswith("/groups/user-name/projects"):
            return DummyResponse(status_code=404, ok=False)
        if url.endswith("/users"):
            return DummyResponse(status_code=200, ok=True, payload=[{"id": 42}])
        if url.endswith("/users/42/projects"):
            return DummyResponse(
                status_code=200,
                ok=True,
                payload=[{"name": "repo", "full_name": "user-name/repo"}],
                links={},
            )
        raise AssertionError(f"Unexpected URL: {url}")

    repos = fetch_gitlab_repos("https://gitlab.com/api/v4", "user-name", headers={}, get=fake_get)
    assert [repo["full_name"] for repo in repos] == ["user-name/repo"]


def test_fetch_gitlab_repos_group_http_error_raises_runtime_error():
    def fake_get(url, headers=None, params=None):
        return DummyResponse(status_code=500, ok=False)

    with pytest.raises(RuntimeError, match="Received HTTP 500"):
        fetch_gitlab_repos("https://gitlab.com/api/v4", "group", get=fake_get)


def test_fetch_gitlab_repos_user_lookup_http_error_raises_runtime_error():
    def fake_get(url, headers=None, params=None):
        if url.endswith("/groups/user-name/projects"):
            return DummyResponse(status_code=404, ok=False)
        return DummyResponse(status_code=500, ok=False)

    with pytest.raises(RuntimeError, match="Received HTTP 500"):
        fetch_gitlab_repos("https://gitlab.com/api/v4", "user-name", get=fake_get)


def test_fetch_gitlab_repos_user_projects_non_ok_raises_runtime_error():
    def fake_get(url, headers=None, params=None):
        if url.endswith("/groups/user-name/projects"):
            return DummyResponse(status_code=404, ok=False)
        if url.endswith("/users"):
            return DummyResponse(status_code=200, ok=True, payload=[{"id": 42}])
        if url.endswith("/users/42/projects"):
            return DummyResponse(status_code=503, ok=False)
        raise AssertionError("unexpected url")

    with pytest.raises(RuntimeError, match="Received HTTP 503"):
        fetch_gitlab_repos("https://gitlab.com/api/v4", "user-name", get=fake_get)


def test_fetch_gitlab_repos_fallback_user_auth_and_404_errors():
    def fake_get_auth(url, headers=None, params=None):
        if url.endswith("/groups/user-name/projects"):
            return DummyResponse(status_code=404, ok=False)
        if url.endswith("/users"):
            return DummyResponse(status_code=200, ok=True, payload=[])
        return DummyResponse(status_code=401, ok=False)

    with pytest.raises(RuntimeError, match="GITLAB_TOKEN"):
        fetch_gitlab_repos("https://gitlab.com/api/v4", "user-name", get=fake_get_auth)

    def fake_get_404(url, headers=None, params=None):
        if url.endswith("/groups/user-name/projects"):
            return DummyResponse(status_code=404, ok=False)
        if url.endswith("/users"):
            return DummyResponse(status_code=200, ok=True, payload=[])
        return DummyResponse(status_code=404, ok=False)

    with pytest.raises(RuntimeError, match="Received HTTP 404"):
        fetch_gitlab_repos("https://gitlab.com/api/v4", "user-name", get=fake_get_404)


def test_fetch_gitlab_repos_wraps_request_exception():
    def fake_get(url, headers=None, params=None):
        raise requests.exceptions.Timeout("gitlab timeout")

    with pytest.raises(RuntimeError, match="gitlab timeout"):
        fetch_gitlab_repos("https://gitlab.com/api/v4", "group", get=fake_get)


@pytest.mark.parametrize("status_code", [401, 403])
def test_fetch_gitlab_repos_auth_error_mentions_gitlab_token(status_code):
    def fake_get(url, headers=None, params=None):
        return DummyResponse(status_code=status_code, ok=False)

    with pytest.raises(RuntimeError, match="GITLAB_TOKEN"):
        fetch_gitlab_repos("https://gitlab.com/api/v4", "group", get=fake_get)


def test_fetch_repos_routes_by_provider(monkeypatch):
    calls = []

    monkeypatch.setattr(
        "gitscanner.repo_list.fetch_github_repos",
        lambda api_base_url, org, headers=None, get=None: calls.append(("github", headers)) or [],
    )
    monkeypatch.setattr(
        "gitscanner.repo_list.fetch_gitlab_repos",
        lambda api_base_url, org, headers=None, get=None: calls.append(("gitlab", headers)) or [],
    )

    fetch_repos("https://api.github.com", "anthropics", provider="github")
    fetch_repos("https://gitlab.com/api/v4", "group", provider="gitlab")

    assert calls[0][0] == "github"
    assert calls[1][0] == "gitlab"


def test_main_success_prints_formatted_lines(monkeypatch, capsys):
    from gitscanner import repo_list as module

    monkeypatch.setattr(
        module,
        "parse_cli_args",
        lambda argv: SimpleNamespace(
            API_BASE_URL="https://gitlab.com/api/v4",
            ORG="group/sub",
            provider="gitlab",
            filter_substring="spring",
        ),
    )
    monkeypatch.setattr(
        module,
        "fetch_repos",
        lambda api_base_url, org, provider, get=requests.get: [
            {"name": "spring-api", "full_name": "group/sub/spring-api"},
            {"name": "other", "full_name": "group/sub/other"},
        ],
    )

    module.main()
    out = capsys.readouterr().out.strip().splitlines()
    assert out == ["group/sub/spring-api"]


def test_main_runtime_error_prints_to_stderr_and_exits(monkeypatch, capsys):
    from gitscanner import repo_list as module

    monkeypatch.setattr(module, "parse_cli_args", lambda argv: (_ for _ in ()).throw(RuntimeError("boom")))

    with pytest.raises(SystemExit) as exc_info:
        module.main()

    assert exc_info.value.code == 1
    assert "boom" in capsys.readouterr().err


def test_format_repo_names_without_filter():
    repos = [
        {"name": "AlphaRepo", "full_name": "org/AlphaRepo"},
        {"name": "BetaRepo", "full_name": "org/BetaRepo"},
    ]
    assert format_repo_names(repos) == ["org/AlphaRepo", "org/BetaRepo"]


def test_format_repo_names_with_case_insensitive_filter():
    repos = [
        {"name": "spring-data", "full_name": "org/spring-data"},
        {"name": "kotlin-utils", "full_name": "org/kotlin-utils"},
    ]
    assert format_repo_names(repos, "SPRING") == ["org/spring-data"]


def test_format_repo_names_uses_gitlab_path_with_namespace_when_full_name_missing():
    repos = [
        {"name": "spring-app", "path_with_namespace": "group/sub/spring-app"},
        {"name": "tooling", "path_with_namespace": "group/sub/tooling"},
    ]

    assert format_repo_names(repos) == ["group/sub/spring-app", "group/sub/tooling"]
    assert format_repo_names(repos, "SPRING") == ["group/sub/spring-app"]
