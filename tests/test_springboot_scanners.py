from gitscanner.scanners.springboot.controllers import count_controllers_in_directory
from gitscanner.scanners.springboot.datasources import collect_repo_datasources
from gitscanner.scanners.springboot.services import extract_controller_services


def test_count_controllers_in_directory_counts_controller_types(tmp_path):
    java_file = tmp_path / 'SampleController.java'
    java_file.write_text(
        'import org.springframework.web.bind.annotation.RestController;\n@RestController\npublic class SampleController {}',
        encoding='utf-8',
    )

    records = count_controllers_in_directory(tmp_path)

    assert len(records) == 1
    assert records[0]['type'] == 'RestController'


def test_collect_repo_datasources_finds_yaml_datasource(tmp_path):
    config = tmp_path / 'src' / 'main' / 'resources'
    config.mkdir(parents=True)
    (config / 'application.yaml').write_text('spring:\n  datasource:\n    url: jdbc:h2:mem:testdb', encoding='utf-8')

    result = collect_repo_datasources(tmp_path)

    assert len(result) == 1
    assert result[0]['url'] == 'jdbc:h2:mem:testdb'


def test_extract_controller_services_supports_private_final_field_without_autowired():
    java_content = 'private final UserService userService;'
    assert extract_controller_services(java_content) == ['UserService']
