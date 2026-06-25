DROP TABLE IF EXISTS service_dependency_markers;
DROP TABLE IF EXISTS controller_services;
DROP TABLE IF EXISTS controllers;
DROP TABLE IF EXISTS repos;
DROP TABLE IF EXISTS scan_runs;

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

INSERT INTO scan_runs(id, scanned_at, notes) VALUES
    (1, '2026-01-01 08:00:00', 'older run'),
    (2, '2026-01-02 08:00:00', 'latest run');

INSERT INTO repos(id, scan_run_id, name, url) VALUES
    (101, 1, 'old-repo', 'https://example.test/old.git'),
    (201, 2, 'repo-a', 'https://example.test/repo-a.git'),
    (202, 2, 'repo-b', 'https://example.test/repo-b.git'),
    (203, 2, 'repo-c', 'https://example.test/repo-c.git');

INSERT INTO controllers(id, repo_id, name, base_path, type) VALUES
    (1001, 101, 'OldController', '/old', 'RestController'),
    (2001, 201, 'ControllerA', '/a', 'RestController'),
    (2002, 202, 'ControllerB', '/b', 'RestController'),
    (2003, 203, 'ControllerC', '/c', 'RestController');

INSERT INTO controller_services(id, controller_id, service_name, found) VALUES
    (3001, 1001, 'UnknownService', 0),
    (3002, 2001, 'UnknownService', 0),
    (3003, 2002, 'ServiceB', 1),
    (3004, 2003, 'ServiceC', 1);

INSERT INTO service_dependency_markers(controller_service_id, marker) VALUES
    (3001, 'NoDependency'),
    (3002, 'NoDependency'),
    (3003, 'NoDependency'),
    (3004, 'JdbcTemplate');
