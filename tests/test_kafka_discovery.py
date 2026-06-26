import sqlite3
import re
from pathlib import Path
from gitscanner.scanners.springboot.datasources import collect_repo_datasources, collect_repo_kafka_bindings
from gitscanner.scanners.springboot.services import SpringCloudStreamScanner
from gitscanner.core.models import ScanContext
from gitscanner.persistence.schema import SCHEMA_STATEMENTS, get_default_classifications
from gitscanner.persistence.sqlite_store import SqliteStore

def test_collect_repo_datasources_finds_kafka_broker_in_yaml(tmp_path):
    config = tmp_path / 'src' / 'main' / 'resources'
    config.mkdir(parents=True)
    yaml_content = """
spring:
  cloud:
    stream:
      kafka:
        binder:
          brokers: localhost:9092
"""
    (config / 'application.yml').write_text(yaml_content, encoding='utf-8')

    result = collect_repo_datasources(tmp_path)

    # Should find Kafka broker
    assert any(r['url'] == 'localhost:9092' for r in result)

def test_collect_repo_datasources_defaults_kafka_broker_if_missing_but_stream_present(tmp_path):
    config = tmp_path / 'src' / 'main' / 'resources'
    config.mkdir(parents=True)
    yaml_content = """
spring:
  cloud:
    stream:
      bindings:
        input-in-0:
          destination: my-topic
"""
    (config / 'application.yml').write_text(yaml_content, encoding='utf-8')

    result = collect_repo_datasources(tmp_path)

    assert any(r['url'] == 'kafka://stream-binder' for r in result)

def test_collect_repo_kafka_bindings_extracts_bindings(tmp_path):
    config = tmp_path / 'src' / 'main' / 'resources'
    config.mkdir(parents=True)
    yaml_content = """
spring:
  cloud:
    stream:
      bindings:
        subscriptionInput-in-0:
          destination: topic1
        orderOutput-out-0:
          destination: topic2
"""
    (config / 'application.yml').write_text(yaml_content, encoding='utf-8')

    result = collect_repo_kafka_bindings(tmp_path)

    assert len(result) == 2
    assert any(r['binding_name'] == 'subscriptionInput' and r['direction'] == 'input' for r in result)
    assert any(r['binding_name'] == 'orderOutput' and r['direction'] == 'output' for r in result)

def test_spring_cloud_stream_scanner_matches_beans_and_marks_services(tmp_path):
    # Setup database
    conn = sqlite3.connect(":memory:")
    for stmt in SCHEMA_STATEMENTS:
        conn.execute(stmt)
    store = SqliteStore(conn)
    
    repo_id = 1
    # Mock data in DB
    conn.execute("INSERT INTO repos (id, name) VALUES (?, ?)", (repo_id, "test-repo"))
    conn.execute("INSERT INTO repo_kafka_bindings (repo_id, binding_name, direction) VALUES (?, ?, ?)", 
                 (repo_id, "subscriptionInput", "input"))
    
    # We need a controller and a service for AC4
    controller_id = 1
    conn.execute("INSERT INTO controllers (id, repo_id, name, type) VALUES (?, ?, ?, ?)", 
                 (controller_id, repo_id, "MyController", "RestController"))
    conn.execute("INSERT INTO controller_services (id, controller_id, service_name, found) VALUES (?, ?, ?, ?)",
                 (1, controller_id, "CopsBundledEventsService", 1))

    # Setup files
    java_file = tmp_path / 'KafkaConfig.java'
    java_content = """
@Configuration
public class KafkaConfig {
    @Bean
    public Consumer<SubscriptionEvent> subscriptionInput(CopsBundledEventsService listener) {
        return listener::handle;
    }
}
"""
    java_file.write_text(java_content, encoding='utf-8')

    # Run scanner
    scanner = SpringCloudStreamScanner(conn)
    context = ScanContext(repo_id=repo_id, repo_name="test-repo", repo_root=tmp_path)
    result = scanner.scan(context)
    store.save_scan_result(context, result)

    # Check AC3: bean_name updated
    row = conn.execute("SELECT bean_name FROM repo_kafka_bindings WHERE binding_name = 'subscriptionInput'").fetchone()
    assert row[0] == 'subscriptionInput'

    # Check AC4: service marker added
    marker = conn.execute("SELECT marker FROM service_dependency_markers WHERE controller_service_id = 1").fetchone()
    assert marker[0] == 'kafka'

def test_no_duplicate_rows_on_rescan(tmp_path):
    # Setup database
    conn = sqlite3.connect(":memory:")
    for stmt in SCHEMA_STATEMENTS:
        conn.execute(stmt)
    
    repo_id = 1
    conn.execute("INSERT INTO repos (id, name) VALUES (?, ?)", (repo_id, "test-repo"))
    
    from gitscanner.persistence.sqlite_store import insert_repo_datasources, insert_repo_kafka_bindings
    
    # Test repo_datasources duplicates
    rows = [{"source_file": "app.yml", "url": "kafka://host"}]
    insert_repo_datasources(conn, repo_id, rows)
    insert_repo_datasources(conn, repo_id, rows)
    
    count = conn.execute("SELECT COUNT(*) FROM repo_datasources").fetchone()[0]
    assert count == 1

    # Test repo_kafka_bindings duplicates
    binding_rows = [{"binding_name": "b1", "direction": "input"}]
    insert_repo_kafka_bindings(conn, repo_id, binding_rows)
    insert_repo_kafka_bindings(conn, repo_id, binding_rows)
    
    count = conn.execute("SELECT COUNT(*) FROM repo_kafka_bindings").fetchone()[0]
    assert count == 1

def test_kafka_classification_exists():
    classifications = get_default_classifications()
    assert ("kafka", "Kafka") in classifications

def test_spring_cloud_stream_scanner_handles_multiple_beans_and_mixed_params(tmp_path):
    conn = sqlite3.connect(":memory:")
    for stmt in SCHEMA_STATEMENTS:
        conn.execute(stmt)
    repo_id = 1
    conn.execute("INSERT INTO repos (id, name) VALUES (?, ?)", (repo_id, "test-repo"))
    conn.execute("INSERT INTO repo_kafka_bindings (repo_id, binding_name, direction) VALUES (?, ?, ?)", 
                 (repo_id, "input1", "input"))
    conn.execute("INSERT INTO repo_kafka_bindings (repo_id, binding_name, direction) VALUES (?, ?, ?)", 
                 (repo_id, "output1", "output"))
    
    controller_id = 1
    conn.execute("INSERT INTO controllers (id, repo_id, name, type) VALUES (?, ?, ?, ?)", 
                 (controller_id, repo_id, "MyController", "RestController"))
    conn.execute("INSERT INTO controller_services (id, controller_id, service_name, found) VALUES (?, ?, ?, ?)",
                 (1, controller_id, "S1Service", 1))

    java_content = """
    @Bean
    public Consumer<String> input1(S1Service s1, OtherType other) { return s -> {}; }
    
    @Bean
    public Supplier<String> output1() { return () -> "hi"; }
    
    @Bean
    public Function<String, String> unknown(S1Service s1) { return s -> s; }
"""
    (tmp_path / 'AppConfig.java').write_text(java_content)
    
    scanner = SpringCloudStreamScanner(conn)
    context = ScanContext(repo_id=repo_id, repo_name="test-repo", repo_root=tmp_path)
    result = scanner.scan(context)
    store = SqliteStore(conn)
    store.save_scan_result(context, result)
    
    # input1 should have bean_name updated and s1 should be marked
    row = conn.execute("SELECT bean_name FROM repo_kafka_bindings WHERE binding_name = 'input1'").fetchone()
    assert row[0] == 'input1'
    
    marker = conn.execute("SELECT marker FROM service_dependency_markers WHERE controller_service_id = 1").fetchone()
    assert marker[0] == 'kafka'
    
    # output1 should have bean_name updated
    row = conn.execute("SELECT bean_name FROM repo_kafka_bindings WHERE binding_name = 'output1'").fetchone()
    assert row[0] == 'output1'

def test_extract_datasource_info_from_yaml_complex():
    from gitscanner.scanners.springboot.datasources import extract_datasource_info_from_yaml_content
    yaml = """
spring:
  cloud:
    stream:
      kafka:
        binder:
          brokers: broker1:9092,broker2:9092
      bindings:
        my-in-0:
          destination: topic-in
        my-out-0:
          destination: topic-out
  datasource:
    url: jdbc:mysql://localhost/db
"""
    info = extract_datasource_info_from_yaml_content(yaml)
    assert info["urls"] == ["jdbc:mysql://localhost/db"]
    assert info["kafka_brokers"] == ["broker1:9092,broker2:9092"]
    assert len(info["kafka_bindings"]) == 2
    assert any(b["binding_name"] == "my" and b["direction"] == "input" for b in info["kafka_bindings"])
    assert any(b["binding_name"] == "my" and b["direction"] == "output" for b in info["kafka_bindings"])

def test_spring_cloud_stream_scanner_returns_empty_if_no_bindings(tmp_path):
    conn = sqlite3.connect(":memory:")
    for stmt in SCHEMA_STATEMENTS:
        conn.execute(stmt)
    scanner = SpringCloudStreamScanner(conn)
    result = scanner.scan(ScanContext(repo_id=1, repo_name="test", repo_root=tmp_path))
    assert result.records == []

def test_collect_application_yml_files_finds_bootstrap(tmp_path):
    from gitscanner.scanners.springboot.datasources import collect_application_yml_files
    resources = tmp_path / 'src' / 'main' / 'resources'
    resources.mkdir(parents=True)
    (resources / 'bootstrap.yml').write_text("test")
    (resources / 'application.yaml').write_text("test")
    
    files = collect_application_yml_files(tmp_path)
    assert len(files) == 2
    assert any(f.name == 'bootstrap.yml' for f in files)
    assert any(f.name == 'application.yaml' for f in files)

def test_insert_repo_kafka_bindings_updates_bean_name(tmp_path):
    from gitscanner.persistence.sqlite_store import insert_repo_kafka_bindings, update_repo_kafka_binding_bean
    conn = sqlite3.connect(":memory:")
    for stmt in SCHEMA_STATEMENTS:
        conn.execute(stmt)
    repo_id = 1
    conn.execute("INSERT INTO repos (id, name) VALUES (?, ?)", (repo_id, "test"))
    
    insert_repo_kafka_bindings(conn, repo_id, [{"binding_name": "b1", "direction": "input"}])
    update_repo_kafka_binding_bean(conn, repo_id, "b1", "myBean")
    
    row = conn.execute("SELECT bean_name FROM repo_kafka_bindings WHERE binding_name = 'b1'").fetchone()
    assert row[0] == "myBean"
