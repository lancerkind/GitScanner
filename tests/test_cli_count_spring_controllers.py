import pytest

from gitscanner.cli.count_spring_controllers import build_parser, parse_cli_args, read_repos_from_file


def test_parse_cli_args_parses_provider_and_repos_file():
    args = parse_cli_args(['github', 'https://api.github.com', 'github_repos.txt'])
    assert args.provider == 'github'
    assert args.repos_file == 'github_repos.txt'


def test_parse_cli_args_no_args_prints_usage_and_exits(capsys):
    with pytest.raises(SystemExit) as exc_info:
        parse_cli_args([])

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert captured.out == build_parser().format_help()


def test_read_repos_from_file_skips_comments_and_empty_lines(tmp_path):
    repos_file = tmp_path / 'repos.txt'
    repos_file.write_text('\n# comment\norg/repo-a\n\norg/repo-b\n', encoding='utf-8')

    assert read_repos_from_file(repos_file) == ['org/repo-a', 'org/repo-b']
