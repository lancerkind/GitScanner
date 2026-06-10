import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from gitscanner.count_spring_controllers import (
    build_parser,
    build_clone_url,
    build_gitlab_headers,
    build_gitlab_token,
    build_github_headers,
    count_controllers_in_directory,
    format_summary_lines,
    get_repo_info,
    parse_cli_args,
    process_repositories,
    read_repos_from_file,
)
from gitscanner.models import RepoResult, ScanSummary


class DummyResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}

    def json(self):
        return self._payload


def test_parse_cli_args_parses_repos_file():
    args = parse_cli_args(["github_repos.txt"])
    assert args.repos_file == "github_repos.txt"
    assert args.provider == "github"


def test_parse_cli_args_parses_provider_option():
    args = parse_cli_args(["github_repos.txt", "--provider", "gitlab"])
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


def test_build_clone_url_uses_token_when_present():
    assert build_clone_url("org/repo", token="tkn") == "https://tkn@github.com/org/repo.git"
    assert build_clone_url("org/repo", token=None) == "https://github.com/org/repo.git"


def test_build_clone_url_for_gitlab_uses_oauth2_token_when_present():
    assert (
        build_clone_url("group/sub/repo", provider="gitlab", token="gl-token")
        == "https://oauth2:gl-token@gitlab.com/group/sub/repo.git"
    )
    assert (
        build_clone_url("group/sub/repo", provider="gitlab", token=None)
        == "https://gitlab.com/group/sub/repo.git"
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

    rest_count, controller_count = count_controllers_in_directory(tmp_path)
    assert rest_count == 1
    assert controller_count == 1


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
    rest_count, controller_count = count_controllers_in_directory(tmp_path)
    assert (rest_count, controller_count) == (0, 0)


def test_process_repositories_aggregates_totals_and_filters_zero_repos():
    def fake_clone_and_count(repo_name, provider="github", token=None):
        assert provider == "gitlab"
        return {
            "org/a": (2, 1),
            "org/b": (0, 0),
            "org/c": (0, 3),
        }[repo_name]

    stats = process_repositories(
        ["org/a", "org/b", "org/c"],
        provider="gitlab",
        token="abc",
        clone_and_count_func=fake_clone_and_count,
    )

    assert isinstance(stats, ScanSummary)
    assert stats.total_rest_controllers == 2
    assert stats.total_controllers == 4
    assert stats.total_controller_files == 6
    assert all(isinstance(item, RepoResult) for item in stats.repo_results)
    assert [item.repo_name for item in stats.repo_results] == ["org/a", "org/c"]
    assert stats.repo_results[0].total_at_rest_controllers == 2
    assert stats.repo_results[0].total_at_controllers == 1
    assert stats.repo_results[0].total_rest_controllers == 3


def test_format_summary_lines_includes_sorted_breakdown():
    stats = ScanSummary(
        total_rest_controllers=2,
        total_controllers=3,
        repo_results=[
            RepoResult(
                repo_name="org/one",
                total_at_rest_controllers=1,
                total_at_controllers=0,
                total_rest_controllers=1,
            ),
            RepoResult(
                repo_name="org/two",
                total_at_rest_controllers=1,
                total_at_controllers=3,
                total_rest_controllers=4,
            ),
        ],
    )

    lines = format_summary_lines(stats, total_repos=3)
    assert any("Repositories with controllers: 2/3" in line for line in lines)
    joined = "\n".join(lines)
    assert joined.index("org/two") < joined.index("org/one")


def test_clone_and_count_wraps_timeout(monkeypatch):
    from gitscanner import count_spring_controllers as module

    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="git clone", timeout=300)

    with pytest.raises(RuntimeError, match="Clone timeout"):
        module.clone_and_count("org/repo", provider="gitlab", token="abc", run=fake_run)


def test_clone_and_count_wraps_failed_clone():
    from gitscanner import count_spring_controllers as module

    def fake_run(*args, **kwargs):
        return SimpleNamespace(returncode=1, stderr="fatal: auth failed")

    with pytest.raises(RuntimeError, match="Clone failed"):
        module.clone_and_count("org/repo", provider="gitlab", token="abc", run=fake_run)


def test_main_success_prints_summary(monkeypatch, capsys):
    from gitscanner import count_spring_controllers as module

    monkeypatch.setattr(
        module,
        "parse_cli_args",
        lambda argv: SimpleNamespace(repos_file="github_repos.txt", provider="gitlab"),
    )
    monkeypatch.setattr(module, "read_repos_from_file", lambda path: ["org/repo"])
    monkeypatch.setattr(module, "build_gitlab_token", lambda token=None: "abc")
    monkeypatch.setattr(
        module,
        "process_repositories",
        lambda repos, provider="github", token=None, clone_and_count_func=None: ScanSummary(
            total_rest_controllers=1,
            total_controllers=0,
            repo_results=[
                RepoResult(
                    repo_name="org/repo",
                    total_at_rest_controllers=1,
                    total_at_controllers=0,
                    total_rest_controllers=1,
                )
            ],
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
