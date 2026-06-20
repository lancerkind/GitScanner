"""Database schema compatibility exports."""

SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS scan_runs (
        id          INTEGER PRIMARY KEY,
        scanned_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        notes       TEXT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS repos (
        id          INTEGER PRIMARY KEY,
        scan_run_id INTEGER REFERENCES scan_runs(id),
        name        TEXT,
        url         TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS controllers (
        id          INTEGER PRIMARY KEY,
        repo_id     INTEGER REFERENCES repos(id),
        name        TEXT,
        base_path   TEXT,
        type        TEXT CHECK(type IN ('RestController', 'Controller'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS controller_base_paths (
        id             INTEGER PRIMARY KEY,
        controller_id  INTEGER NOT NULL REFERENCES controllers(id),
        path           TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS endpoints (
        id             INTEGER PRIMARY KEY,
        controller_id  INTEGER REFERENCES controllers(id),
        http_method    TEXT,
        path           TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS parameters (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        endpoint_id   INTEGER NOT NULL REFERENCES endpoints(id),
        name          TEXT NOT NULL,
        java_type     TEXT NOT NULL,
        source        TEXT NOT NULL,
        required      BOOLEAN NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS karate_feature_files (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        repo_id        INTEGER NOT NULL REFERENCES repos(id),
        controller_id  INTEGER REFERENCES controllers(id),
        file_path      TEXT NOT NULL,
        file_name      TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS karate_paths (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        feature_file_id  INTEGER NOT NULL REFERENCES karate_feature_files(id),
        path             TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS repo_datasources (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        repo_id         INTEGER NOT NULL REFERENCES repos(id),
        source_file     TEXT NOT NULL,
        url             TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS controller_services (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        controller_id   INTEGER NOT NULL REFERENCES controllers(id),
        service_name    TEXT NOT NULL,
        found           BOOLEAN NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS service_dependency_markers (
        id                    INTEGER PRIMARY KEY AUTOINCREMENT,
        controller_service_id INTEGER NOT NULL REFERENCES controller_services(id),
        marker                TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS dependency_classifications (
        marker          TEXT PRIMARY KEY,
        dependency_type TEXT NOT NULL
    )
    """,
)


def get_default_classifications():
    return [
        ("JdbcTemplate", "SQL Database"),
        ("JpaRepository", "SQL Database"),
        ("CrudRepository", "SQL Database"),
        ("SpannerTemplate", "Spanner"),
        ("SpannerRepository", "Spanner"),
        ("KafkaTemplate", "Kafka"),
        ("KafkaListener", "Kafka"),
        ("RestTemplate", "API"),
        ("WebClient", "API"),
        ("FeignClient", "API"),
        ("jdbc:oracle:", "Oracle"),
        ("jdbc:postgresql:", "CloudSQL"),
        ("cloudsql", "CloudSQL"),
        ("jdbc:mysql:", "CloudSQL"),
        ("jdbc:h2:", "H2"),
        ("jdbc:sqlserver:", "SQL Server"),
    ]


def seed_dependency_classifications(conn):
    conn.executemany(
        """
        INSERT OR IGNORE INTO dependency_classifications(marker, dependency_type)
        VALUES (?, ?)
        """,
        get_default_classifications(),
    )
