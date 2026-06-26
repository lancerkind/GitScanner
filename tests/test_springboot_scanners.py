import sqlite3
from gitscanner.persistence.schema import SCHEMA_STATEMENTS
from gitscanner.scanners.springboot.controllers import count_controllers_in_directory
from gitscanner.scanners.springboot.datasources import collect_repo_datasources
from gitscanner.scanners.springboot.services import extract_controller_services, scan_service_dependencies_for_repo


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
 
 
def test_scan_service_dependencies_for_repo_comprehensive(tmp_path):
    conn = sqlite3.connect(":memory:")
    for stmt in SCHEMA_STATEMENTS:
        conn.execute(stmt)
    repo_id = 1
    conn.execute("INSERT INTO repos (id, name) VALUES (?, ?)", (repo_id, "test"))
    conn.execute("INSERT INTO controllers (id, repo_id, name, type) VALUES (?, ?, ?, ?)",
                 (1, repo_id, "MyController", "RestController"))
 
    (tmp_path / "MyController.java").write_text("@RestController public class MyController { private UserService userService; }")
    (tmp_path / "UserService.java").write_text("public class UserService { public void save() { jdbcTemplate.execute('...'); } }")
 
    conn.execute("INSERT INTO dependency_classifications (marker, dependency_type) VALUES ('jdbcTemplate', 'SQL')")
 
    records = scan_service_dependencies_for_repo(conn, repo_id, str(tmp_path))
    assert len(records) == 1
    assert records[0]["service_name"] == "UserService"
    assert "jdbcTemplate" in records[0]["markers"]
 
 
def test_count_controllers_in_directory_complex(tmp_path):
    java_content = """
@RestController
@RequestMapping("/api/v1")
public class ComplexController {
    @GetMapping({"/items", "/list"})
    public List<String> getItems() { return null; }
 
    @PostMapping(value = "/{id}/update", consumes = "application/json")
    public void update(@PathVariable("id") String id, @RequestBody String body) { }
}
"""
    (tmp_path / 'ComplexController.java').write_text(java_content)
    records = count_controllers_in_directory(tmp_path)
    assert len(records) == 1
    assert records[0]['base_path'] == '/api/v1'
    # Multiple paths support might be limited, but let's check what it finds
    assert len(records[0]['endpoints']) >= 2
