import gitscanner.count_spring_controllers as facade
from gitscanner import count_spring_controllers as package_facade


def test_compat_exports_are_available():
    assert facade.parse_cli_args is package_facade.parse_cli_args
    assert facade.process_repositories is package_facade.process_repositories
    assert callable(facade.main)
