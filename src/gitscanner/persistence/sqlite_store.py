import sqlite3

from gitscanner.persistence.schema import SCHEMA_STATEMENTS, seed_dependency_classifications
from gitscanner.reporting.summary import build_summary_for_scan_run


def initialize_database(conn):
    for statement in SCHEMA_STATEMENTS:
        conn.execute(statement)
    seed_dependency_classifications(conn)
    conn.commit()


def create_scan_run(conn, notes=None):
    cursor = conn.execute("INSERT INTO scan_runs(notes) VALUES (?)", (notes,))
    conn.commit()
    return cursor.lastrowid


def insert_repo(conn, scan_run_id, repo_name, url=None):
    cursor = conn.execute(
        "INSERT INTO repos(scan_run_id, name, url) VALUES (?, ?, ?)",
        (scan_run_id, repo_name, url),
    )
    return cursor.lastrowid


def insert_controllers(conn, repo_id, controllers):
    for controller in controllers:
        cursor = conn.execute(
            "INSERT INTO controllers(repo_id, name, base_path, type) VALUES (?, ?, ?, ?)",
            (repo_id, controller["name"], controller.get("base_path"), controller["type"]),
        )
        controller_id = cursor.lastrowid
        insert_endpoints(conn, controller_id, controller.get("endpoints", []))


def insert_endpoints(conn, controller_id, endpoints):
    for endpoint in endpoints:
        cursor = conn.execute(
            "INSERT INTO endpoints(controller_id, http_method, path) VALUES (?, ?, ?)",
            (controller_id, endpoint["http_method"], endpoint["path"]),
        )
        insert_parameters(conn, cursor.lastrowid, endpoint.get("parameters", []))


def insert_parameters(conn, endpoint_id, parameters):
    for parameter in parameters:
        conn.execute(
            """
            INSERT INTO parameters(endpoint_id, name, java_type, source, required)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                endpoint_id,
                parameter["name"],
                parameter["java_type"],
                parameter["source"],
                parameter["required"],
            ),
        )


def delete_repo_karate_data(conn, repo_id):
    conn.execute(
        "DELETE FROM karate_paths WHERE feature_file_id IN (SELECT id FROM karate_feature_files WHERE repo_id = ?)",
        (repo_id,),
    )
    conn.execute(
        "DELETE FROM karate_feature_files WHERE repo_id = ?",
        (repo_id,),
    )


def insert_karate_feature_file(conn, repo_id, controller_id, file_path, file_name):
    cursor = conn.execute(
        "INSERT INTO karate_feature_files(repo_id, controller_id, file_path, file_name) VALUES (?, ?, ?, ?)",
        (repo_id, controller_id, file_path, file_name),
    )
    return cursor.lastrowid


def insert_karate_paths(conn, feature_file_id, paths):
    conn.executemany(
        "INSERT INTO karate_paths(feature_file_id, path) VALUES (?, ?)",
        [(feature_file_id, path) for path in sorted(set(paths))],
    )


def insert_repo_datasources(conn, repo_id, datasource_rows):
    conn.executemany(
        "INSERT INTO repo_datasources(repo_id, source_file, url) VALUES (?, ?, ?)",
        [(repo_id, row["source_file"], row["url"]) for row in datasource_rows],
    )


def insert_controller_service(conn, controller_id, service_name, found):
    cursor = conn.execute(
        "INSERT INTO controller_services(controller_id, service_name, found) VALUES (?, ?, ?)",
        (controller_id, service_name, found),
    )
    return cursor.lastrowid


def insert_service_dependency_markers(conn, controller_service_id, markers):
    if not markers:
        return
    conn.executemany(
        """
        INSERT INTO service_dependency_markers(controller_service_id, marker)
        VALUES (?, ?)
        """,
        [(controller_service_id, marker) for marker in sorted(markers)],
    )


class SqliteStore:
    def __init__(self, conn):
        self.conn = conn

    def initialize_database(self):
        initialize_database(self.conn)

    def create_scan_run(self, notes=None):
        return create_scan_run(self.conn, notes)

    def insert_repo(self, scan_run_id, repo_name, url=None):
        return insert_repo(self.conn, scan_run_id, repo_name, url)

    def save_scan_result(self, context, result):
        capability = result.capability
        if capability == "springboot.controllers":
            insert_controllers(self.conn, context.repo_id, result.records)
            return
        if capability == "karate.features":
            delete_repo_karate_data(self.conn, context.repo_id)
            for feature in result.records:
                feature_file_id = insert_karate_feature_file(
                    self.conn,
                    context.repo_id,
                    feature["controller_id"],
                    feature["file_path"],
                    feature["file_name"],
                )
                insert_karate_paths(self.conn, feature_file_id, feature.get("paths") or [])
            return
        if capability == "springboot.datasources":
            insert_repo_datasources(self.conn, context.repo_id, result.records)
            return
        if capability == "springboot.service_dependencies":
            for row in result.records:
                controller_service_id = insert_controller_service(
                    self.conn,
                    row["controller_id"],
                    row["service_name"],
                    row["found"],
                )
                insert_service_dependency_markers(
                    self.conn,
                    controller_service_id,
                    row.get("markers") or [],
                )

    def build_summary(self, scan_run_id):
        return build_summary_for_scan_run(self.conn, scan_run_id)


def connect(db_path):
    return sqlite3.connect(db_path)


