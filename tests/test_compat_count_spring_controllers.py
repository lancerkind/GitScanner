from gitscanner.cli import count_spring_controllers as facade
from gitscanner.core import git


def test_compat_exports_are_available():
    assert facade.build_github_headers() == git.build_github_headers()
    assert facade.process_repositories is not None
    assert callable(facade.main)
