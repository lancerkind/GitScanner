"""Repository/provider helpers extracted from legacy scanner module."""

from gitscanner import count_spring_controllers as legacy


build_provider_token = legacy.build_provider_token
build_token = legacy.build_token
build_github_headers = legacy.build_github_headers
build_gitlab_headers = legacy.build_gitlab_headers
derive_clone_host = legacy.derive_clone_host
build_clone_url = legacy.build_clone_url
get_repo_info = legacy.get_repo_info
clone_and_count = legacy.clone_and_count
