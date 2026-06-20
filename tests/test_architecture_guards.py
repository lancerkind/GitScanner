from pathlib import Path


def test_tests_do_not_import_legacy_facade():
    tests_dir = Path(__file__).parent
    forbidden = []

    needle_module = '.'.join(['gitscanner', 'count_spring_controllers'])
    needle_package = 'from gitscanner import ' + 'count_spring_controllers'

    for path in tests_dir.glob('test_*.py'):
        if path.name == 'test_architecture_guards.py':
            continue
        text = path.read_text(encoding='utf-8')
        if needle_module in text or needle_package in text:
            forbidden.append(path.name)

    assert forbidden == []


def test_scanner_modules_do_not_import_cli_or_compat_facade():
    modules = [
        Path('src/gitscanner/core/scanner.py'),
        Path('src/gitscanner/core/scan_runner.py'),
        Path('src/gitscanner/core/repository.py'),
    ]

    for module in modules:
        text = module.read_text(encoding='utf-8')
        assert 'gitscanner.cli' not in text
        assert 'gitscanner.count_spring_controllers' not in text
