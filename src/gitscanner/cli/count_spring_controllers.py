"""CLI orchestration for the controller scanner command."""

from gitscanner import count_spring_controllers as legacy


build_parser = legacy.build_parser
parse_cli_args = legacy.parse_cli_args
read_repos_from_file = legacy.read_repos_from_file
main = legacy.main
