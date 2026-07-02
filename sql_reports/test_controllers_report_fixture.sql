-- Create schema
CREATE TABLE scan_runs (
    id          INTEGER PRIMARY KEY,
    scanned_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes       TEXT NULL
);

CREATE TABLE repos (
    id          INTEGER PRIMARY KEY,
    scan_run_id INTEGER REFERENCES scan_runs(id),
    name        TEXT,
    url         TEXT
);

CREATE TABLE controllers (
    id          INTEGER PRIMARY KEY,
    repo_id     INTEGER REFERENCES repos(id),
    name        TEXT,
    base_path   TEXT,
    type        TEXT CHECK(type IN ('RestController', 'Controller'))
);

CREATE TABLE controller_services (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    controller_id   INTEGER NOT NULL REFERENCES controllers(id),
    service_name    TEXT NOT NULL,
    found           BOOLEAN NOT NULL
);

CREATE TABLE service_dependency_markers (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    controller_service_id INTEGER NOT NULL REFERENCES controller_services(id),
    marker                TEXT NOT NULL
);

CREATE TABLE dependency_classifications (
    marker          TEXT PRIMARY KEY,
    dependency_type TEXT NOT NULL
);

-- Insert Classifications
INSERT INTO dependency_classifications (marker, dependency_type) VALUES ('kafka', 'Kafka');
INSERT INTO dependency_classifications (marker, dependency_type) VALUES ('KafkaTemplate', 'Kafka');
INSERT INTO dependency_classifications (marker, dependency_type) VALUES ('RestTemplate', 'API');
INSERT INTO dependency_classifications (marker, dependency_type) VALUES ('WebClient', 'API');
INSERT INTO dependency_classifications (marker, dependency_type) VALUES ('jdbc:oracle:', 'Oracle');
INSERT INTO dependency_classifications (marker, dependency_type) VALUES ('jdbc:postgresql:', 'CloudSQL');

-- Older Scan
INSERT INTO scan_runs (id, scanned_at) VALUES (1, '2026-01-01 10:00:00');
INSERT INTO repos (id, scan_run_id, name) VALUES (1, 1, 'old/repo');
INSERT INTO controllers (id, repo_id, name) VALUES (1, 1, 'OldController');
INSERT INTO controller_services (id, controller_id, service_name, found) VALUES (1, 1, 'OldService', 1);
INSERT INTO service_dependency_markers (controller_service_id, marker) VALUES (1, 'KafkaTemplate');

-- Latest Scan
INSERT INTO scan_runs (id, scanned_at) VALUES (2, '2026-01-02 10:00:00');

-- repository/here
INSERT INTO repos (id, scan_run_id, name) VALUES (2, 2, 'repository/here');
INSERT INTO controllers (id, repo_id, name) VALUES (2, 2, 'controllerA');
INSERT INTO controller_services (id, controller_id, service_name, found) VALUES (2, 2, 'ServiceA1', 1);
INSERT INTO service_dependency_markers (controller_service_id, marker) VALUES (2, 'kafka');
INSERT INTO service_dependency_markers (controller_service_id, marker) VALUES (2, 'RestTemplate');
INSERT INTO controller_services (id, controller_id, service_name, found) VALUES (3, 2, 'ServiceA2', 1);
INSERT INTO service_dependency_markers (controller_service_id, marker) VALUES (3, 'WebClient');

INSERT INTO controllers (id, repo_id, name) VALUES (3, 2, 'controllerB');
INSERT INTO controller_services (id, controller_id, service_name, found) VALUES (4, 3, 'ServiceB', 1);
INSERT INTO service_dependency_markers (controller_service_id, marker) VALUES (4, 'jdbc:oracle:');

-- repository/another
INSERT INTO repos (id, scan_run_id, name) VALUES (3, 2, 'repository/another');
INSERT INTO controllers (id, repo_id, name) VALUES (4, 3, 'controllerX');
INSERT INTO controller_services (id, controller_id, service_name, found) VALUES (5, 4, 'ServiceX', 1);
INSERT INTO service_dependency_markers (controller_service_id, marker) VALUES (5, 'jdbc:postgresql:');

-- repository/ignored
INSERT INTO repos (id, scan_run_id, name) VALUES (4, 2, 'repository/ignored');
INSERT INTO controllers (id, repo_id, name) VALUES (5, 4, 'controllerY');
INSERT INTO controller_services (id, controller_id, service_name, found) VALUES (6, 5, 'ServiceY', 1);
INSERT INTO service_dependency_markers (controller_service_id, marker) VALUES (6, 'SomeUnclassifiedMarker');
