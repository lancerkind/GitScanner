-- test trends over time report

DROP TABLE IF EXISTS endpoints;
DROP TABLE IF EXISTS karate_feature_files;
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

CREATE TABLE IF NOT EXISTS endpoints (
    id             INTEGER PRIMARY KEY,
    controller_id  INTEGER REFERENCES controllers(id),
    http_method    TEXT,
    path           TEXT
);

CREATE TABLE IF NOT EXISTS karate_feature_files (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id        INTEGER NOT NULL REFERENCES repos(id),
    controller_id  INTEGER REFERENCES controllers(id),
    file_path      TEXT NOT NULL,
    file_name      TEXT NOT NULL
);

INSERT INTO scan_runs(id, scanned_at, notes) VALUES
    (1, '2026-01-05 09:00:00', 'alpha oldest run'),
    (2, '2026-06-10 09:00:00', 'alpha middle run'),
    (3, '2026-06-20 09:00:00', 'alpha newest run'),
    (4, '2025-12-01 09:00:00', 'beta oldest run'),
    (5, '2026-06-10 09:00:00', 'beta newest run');

INSERT INTO repos(id, scan_run_id, name, url) VALUES
    (11, 1, 'alpha/repository', 'https://example.test/alpha.git'),
    (12, 2, 'alpha/repository', 'https://example.test/alpha.git'),
    (13, 3, 'alpha/repository', 'https://example.test/alpha.git'),
    (21, 4, 'beta/repository', 'https://example.test/beta.git'),
    (22, 5, 'beta/repository', 'https://example.test/beta.git');

INSERT INTO controllers(id, repo_id, name, base_path, type) VALUES
    (101, 11, 'AlphaControllerV1', '/alpha', 'RestController'),
    (102, 12, 'AlphaControllerV2A', '/alpha', 'RestController'),
    (103, 12, 'AlphaControllerV2B', '/alpha/admin', 'RestController'),
    (104, 13, 'AlphaControllerV3A', '/alpha', 'RestController'),
    (105, 13, 'AlphaControllerV3B', '/alpha/admin', 'RestController'),
    (106, 13, 'AlphaControllerV3C', '/alpha/internal', 'RestController'),
    (201, 22, 'BetaControllerV2', '/beta', 'RestController');

INSERT INTO endpoints(id, controller_id, http_method, path) VALUES
    (1001, 101, 'GET', '/alpha/health'),
    (1002, 101, 'GET', '/alpha/version'),
    (1003, 102, 'GET', '/alpha/health'),
    (1004, 102, 'GET', '/alpha/version'),
    (1005, 103, 'POST', '/alpha/admin/reindex'),
    (1006, 104, 'GET', '/alpha/health'),
    (1007, 104, 'GET', '/alpha/version'),
    (1008, 105, 'POST', '/alpha/admin/reindex'),
    (1009, 106, 'GET', '/alpha/internal/metrics'),
    (1010, 106, 'POST', '/alpha/internal/cache/refresh'),
    (2001, 201, 'GET', '/beta/health'),
    (2002, 201, 'GET', '/beta/version'),
    (2003, 201, 'POST', '/beta/jobs/run'),
    (2004, 201, 'DELETE', '/beta/cache');

INSERT INTO karate_feature_files(repo_id, file_path, file_name) VALUES
    (12, 'src/test/resources/features/alpha', 'health.feature'),
    (13, 'src/test/resources/features/alpha', 'health.feature'),
    (13, 'src/test/resources/features/alpha', 'admin.feature'),
    (22, 'src/test/resources/features/beta', 'health.feature'),
    (22, 'src/test/resources/features/beta', 'jobs.feature'),
    (22, 'src/test/resources/features/beta', 'cache.feature');