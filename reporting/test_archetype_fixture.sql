DROP TABLE IF EXISTS parameters;
DROP TABLE IF EXISTS endpoints;
DROP TABLE IF EXISTS controller_base_paths;
DROP TABLE IF EXISTS service_dependency_markers;
DROP TABLE IF EXISTS controller_services;
DROP TABLE IF EXISTS karate_paths;
DROP TABLE IF EXISTS karate_feature_files;
DROP TABLE IF EXISTS repo_datasources;
DROP TABLE IF EXISTS controllers;
DROP TABLE IF EXISTS repos;
DROP TABLE IF EXISTS scan_runs;
DROP TABLE IF EXISTS dependency_classifications;

CREATE TABLE IF NOT EXISTS scan_runs (
    id          INTEGER PRIMARY KEY,
    scanned_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes       TEXT NULL
);

CREATE TABLE IF NOT EXISTS repos (
    id          INTEGER PRIMARY KEY,
    scan_run_id INTEGER REFERENCES scan_runs(id),
    name        TEXT,
    url         TEXT
);

CREATE TABLE IF NOT EXISTS controllers (
    id          INTEGER PRIMARY KEY,
    repo_id     INTEGER REFERENCES repos(id),
    name        TEXT,
    base_path   TEXT,
    type        TEXT CHECK(type IN ('RestController', 'Controller'))
);

CREATE TABLE IF NOT EXISTS controller_base_paths (
    id             INTEGER PRIMARY KEY,
    controller_id  INTEGER NOT NULL REFERENCES controllers(id),
    path           TEXT
);

CREATE TABLE IF NOT EXISTS endpoints (
    id             INTEGER PRIMARY KEY,
    controller_id  INTEGER REFERENCES controllers(id),
    http_method    TEXT,
    path           TEXT
);

CREATE TABLE IF NOT EXISTS parameters (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    endpoint_id   INTEGER NOT NULL REFERENCES endpoints(id),
    name          TEXT NOT NULL,
    java_type     TEXT NOT NULL,
    source        TEXT NOT NULL,
    required      BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS karate_feature_files (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id         INTEGER NOT NULL REFERENCES repos(id),
    controller_id   INTEGER REFERENCES controllers(id),
    file_path       TEXT NOT NULL,
    file_name       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS karate_paths (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    feature_file_id INTEGER NOT NULL REFERENCES karate_feature_files(id),
    path            TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS repo_datasources (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id         INTEGER NOT NULL REFERENCES repos(id),
    source_file     TEXT NOT NULL,
    url             TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS controller_services (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    controller_id   INTEGER NOT NULL REFERENCES controllers(id),
    service_name    TEXT NOT NULL,
    found           BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS service_dependency_markers (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    controller_service_id INTEGER NOT NULL REFERENCES controller_services(id),
    marker                TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dependency_classifications (
    marker          TEXT PRIMARY KEY,
    dependency_type TEXT NOT NULL
);

INSERT INTO dependency_classifications(marker, dependency_type) VALUES
    ('JdbcTemplate', 'SQL Database'),
    ('JpaRepository', 'SQL Database'),
    ('CrudRepository', 'SQL Database'),
    ('SpannerTemplate', 'Spanner'),
    ('SpannerRepository', 'Spanner'),
    ('KafkaTemplate', 'Kafka'),
    ('KafkaListener', 'Kafka'),
    ('RestTemplate', 'API'),
    ('WebClient', 'API'),
    ('FeignClient', 'API'),
    ('jdbc:oracle:', 'Oracle'),
    ('jdbc:postgresql:', 'CloudSQL'),
    ('cloudsql', 'CloudSQL'),
    ('jdbc:mysql:', 'CloudSQL'),
    ('jdbc:h2:', 'H2'),
    ('jdbc:sqlserver:', 'SQL Server'),
    ('OracleTemplate', 'Oracle'),
    ('PostgresTemplate', 'PostgreSQL'),
    ('OtherSqlTemplate', 'SQL Server');

INSERT INTO scan_runs(id, notes) VALUES (1, 'Story 15 fixture run');

INSERT INTO repos(id, scan_run_id, name, url) VALUES
    (1, 1, 'repo-mixed', 'https://example.test/repo-mixed.git'),
    (2, 1, 'repo-kafka', 'https://example.test/repo-kafka.git'),
    (3, 1, 'repo-api', 'https://example.test/repo-api.git'),
    (4, 1, 'repo-spanner', 'https://example.test/repo-spanner.git'),
    (5, 1, 'repo-oracle', 'https://example.test/repo-oracle.git'),
    (6, 1, 'repo-postgres', 'https://example.test/repo-postgres.git'),
    (7, 1, 'repo-other-sql', 'https://example.test/repo-other-sql.git'),
    (8, 1, 'repo-h2-only', 'https://example.test/repo-h2-only.git'),
    (9, 1, 'repo-no-deps', 'https://example.test/repo-no-deps.git'),
    (10, 1, 'repo-unclassified', 'https://example.test/repo-unclassified.git'),
    (11, 1, 'repo-oracle-datasource', 'https://example.test/repo-oracle-datasource.git');

INSERT INTO controllers(id, repo_id, name, base_path, type) VALUES
    (1, 1, 'MixedController', '/mixed', 'RestController'),
    (2, 2, 'KafkaController', '/kafka', 'RestController'),
    (3, 3, 'ApiController', '/api', 'RestController'),
    (4, 4, 'SpannerController', '/spanner', 'RestController'),
    (5, 5, 'OracleController', '/oracle', 'RestController'),
    (6, 6, 'PostgresController', '/postgres', 'RestController'),
    (7, 7, 'OtherSqlController', '/other-sql', 'RestController'),
    (8, 8, 'H2Controller', '/h2', 'RestController'),
    (9, 9, 'NoDepsController', '/no-deps', 'RestController'),
    (10, 10, 'UnclassifiedController', '/unclassified', 'RestController'),
    (11, 11, 'OracleDatasourceController', '/oracle-ds', 'RestController');

INSERT INTO endpoints(id, controller_id, http_method, path) VALUES
    (1, 1, 'GET', '/mixed/health'),
    (2, 2, 'GET', '/kafka/health'),
    (3, 3, 'GET', '/api/health'),
    (4, 4, 'GET', '/spanner/health'),
    (5, 5, 'GET', '/oracle/health'),
    (6, 6, 'GET', '/postgres/health'),
    (7, 7, 'GET', '/other-sql/health'),
    (8, 8, 'GET', '/h2/health'),
    (9, 9, 'GET', '/no-deps/health'),
    (10, 10, 'GET', '/unclassified/health'),
    (11, 11, 'GET', '/oracle-ds/health');

INSERT INTO controller_services(id, controller_id, service_name, found) VALUES
    (1, 1, 'MixedService', 1),
    (2, 2, 'KafkaService', 1),
    (3, 3, 'ApiService', 1),
    (4, 4, 'SpannerService', 1),
    (5, 5, 'OracleService', 1),
    (6, 6, 'PostgresService', 1),
    (7, 7, 'OtherSqlService', 1),
    (8, 10, 'UnknownService', 0);

INSERT INTO service_dependency_markers(controller_service_id, marker) VALUES
    (1, 'JdbcTemplate'),
    (1, 'KafkaTemplate'),
    (1, 'RestTemplate'),
    (2, 'KafkaTemplate'),
    (3, 'RestTemplate'),
    (4, 'SpannerTemplate'),
    (5, 'OracleTemplate'),
    (6, 'PostgresTemplate'),
    (7, 'OtherSqlTemplate');

INSERT INTO repo_datasources(repo_id, source_file, url) VALUES
    (8, 'application.yml', 'jdbc:h2:mem:testdb'),
    (11, 'application.yml', 'jdbc:oracle:thin:@localhost:1521/xe');

WITH
  latest_run AS (
    SELECT id AS scan_run_id
    FROM scan_runs
    ORDER BY id DESC
    LIMIT 1
  ),
  run_repos AS (
    SELECT r.id AS repo_id, r.name AS repo_name
    FROM repos r
    JOIN latest_run lr ON lr.scan_run_id = r.scan_run_id
  ),
  repo_marker_types AS (
    SELECT rr.repo_id, dc.dependency_type
    FROM run_repos rr
    JOIN controllers c ON c.repo_id = rr.repo_id
    JOIN controller_services cs ON cs.controller_id = c.id
    JOIN service_dependency_markers sdm ON sdm.controller_service_id = cs.id
    JOIN dependency_classifications dc ON dc.marker = sdm.marker
  ),
  repo_datasource_types AS (
    SELECT rr.repo_id, dc.dependency_type
    FROM run_repos rr
    JOIN repo_datasources rd ON rd.repo_id = rr.repo_id
    JOIN dependency_classifications dc ON lower(rd.url) LIKE '%' || lower(dc.marker) || '%'
  ),
  repo_all_types AS (
    SELECT repo_id, dependency_type FROM repo_marker_types
    UNION
    SELECT repo_id, dependency_type FROM repo_datasource_types
  ),
  repo_type_list AS (
    SELECT
      repo_id,
      group_concat(dependency_type, ', ') AS dependency_types
    FROM (
      SELECT DISTINCT repo_id, dependency_type
      FROM repo_all_types
      ORDER BY dependency_type
    )
    GROUP BY repo_id
  ),
  repo_type_flags AS (
    SELECT
      rr.repo_id,
      COALESCE(SUM(CASE WHEN rat.dependency_type IS NOT NULL THEN 1 ELSE 0 END), 0) AS resolved_type_count,
      COALESCE(SUM(CASE WHEN rat.dependency_type IS NOT NULL AND rat.dependency_type <> 'H2' THEN 1 ELSE 0 END), 0) AS resolved_non_h2_type_count,
      COUNT(DISTINCT CASE WHEN rat.dependency_type <> 'H2' THEN rat.dependency_type END) AS distinct_non_h2_type_count,
      MAX(CASE WHEN rat.dependency_type = 'Kafka' THEN 1 ELSE 0 END) AS has_kafka,
      MAX(CASE WHEN rat.dependency_type = 'Oracle' THEN 1 ELSE 0 END) AS has_oracle,
      MAX(CASE WHEN rat.dependency_type = 'Spanner' THEN 1 ELSE 0 END) AS has_spanner,
      MAX(CASE WHEN rat.dependency_type = 'PostgreSQL' THEN 1 ELSE 0 END) AS has_postgresql,
      MAX(CASE WHEN rat.dependency_type IN ('SQL Database', 'CloudSQL', 'SQL Server') THEN 1 ELSE 0 END) AS has_other_sql,
      MAX(CASE WHEN rat.dependency_type = 'API' THEN 1 ELSE 0 END) AS has_api,
      COALESCE(COUNT(DISTINCT cs.id), 0) AS service_count
    FROM run_repos rr
    LEFT JOIN repo_all_types rat ON rat.repo_id = rr.repo_id
    LEFT JOIN controllers c ON c.repo_id = rr.repo_id
    LEFT JOIN controller_services cs ON cs.controller_id = c.id
    GROUP BY rr.repo_id
  ),
  repo_counts AS (
    SELECT
      rr.repo_id,
      COUNT(DISTINCT c.id) AS controller_count,
      COUNT(e.id) AS endpoint_count
    FROM run_repos rr
    LEFT JOIN controllers c ON c.repo_id = rr.repo_id
    LEFT JOIN endpoints e ON e.controller_id = c.id
    GROUP BY rr.repo_id
  )
SELECT
  rr.repo_name,
  CASE
    WHEN rtf.distinct_non_h2_type_count >= 3 THEN 'MIXED'
    WHEN rtf.has_kafka = 1 THEN 'KAFKA'
    WHEN rtf.has_oracle = 1 THEN 'ORACLE'
    WHEN rtf.has_spanner = 1 THEN 'SPANNER'
    WHEN rtf.has_postgresql = 1 THEN 'POSTGRES'
    WHEN rtf.has_other_sql = 1 THEN 'OTHER_SQL'
    WHEN rtf.has_api = 1 THEN 'UPSTREAM_REST_API'
    WHEN rtf.resolved_non_h2_type_count = 0 AND rtf.service_count = 0 THEN 'NO_DEPENDENCIES_DETECTED'
    ELSE 'UNCLASSIFIED'
  END AS archetype,
  COALESCE(rtl.dependency_types, '') AS dependency_types,
  COALESCE(rc.controller_count, 0) AS controller_count,
  COALESCE(rc.endpoint_count, 0) AS endpoint_count
FROM run_repos rr
LEFT JOIN repo_type_flags rtf ON rtf.repo_id = rr.repo_id
LEFT JOIN repo_type_list rtl ON rtl.repo_id = rr.repo_id
LEFT JOIN repo_counts rc ON rc.repo_id = rr.repo_id
ORDER BY archetype ASC, rr.repo_name ASC;