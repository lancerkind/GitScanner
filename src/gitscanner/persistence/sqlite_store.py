import sqlite3

from gitscanner import count_spring_controllers as legacy


class SqliteStore:
    def __init__(self, conn):
        self.conn = conn

    def initialize_database(self):
        legacy.initialize_database(self.conn)

    def create_scan_run(self, notes=None):
        return legacy.create_scan_run(self.conn, notes)

    def insert_repo(self, scan_run_id, repo_name, url=None):
        return legacy.insert_repo(self.conn, scan_run_id, repo_name, url)

    def save_scan_result(self, context, result):
        capability = result.capability
        if capability == "springboot.controllers":
            legacy.insert_controllers(self.conn, context.repo_id, result.records)
            return
        if capability == "karate.features":
            legacy.delete_repo_karate_data(self.conn, context.repo_id)
            for feature in result.records:
                feature_file_id = legacy.insert_karate_feature_file(
                    self.conn,
                    context.repo_id,
                    feature["controller_id"],
                    feature["file_path"],
                    feature["file_name"],
                )
                legacy.insert_karate_paths(self.conn, feature_file_id, feature.get("paths") or [])
            return
        if capability == "springboot.datasources":
            legacy.insert_repo_datasources(self.conn, context.repo_id, result.records)
            return
        if capability == "springboot.service_dependencies":
            for row in result.records:
                controller_service_id = legacy.insert_controller_service(
                    self.conn,
                    row["controller_id"],
                    row["service_name"],
                    row["found"],
                )
                legacy.insert_service_dependency_markers(
                    self.conn,
                    controller_service_id,
                    row.get("markers") or [],
                )

    def build_summary(self, scan_run_id):
        return legacy.build_summary_for_scan_run(self.conn, scan_run_id)


def connect(db_path):
    return sqlite3.connect(db_path)


initialize_database = legacy.initialize_database
create_scan_run = legacy.create_scan_run
insert_repo = legacy.insert_repo
insert_controllers = legacy.insert_controllers
insert_endpoints = legacy.insert_endpoints
insert_parameters = legacy.insert_parameters
delete_repo_karate_data = legacy.delete_repo_karate_data
insert_karate_feature_file = legacy.insert_karate_feature_file
insert_karate_paths = legacy.insert_karate_paths
insert_repo_datasources = legacy.insert_repo_datasources
insert_controller_service = legacy.insert_controller_service
insert_service_dependency_markers = legacy.insert_service_dependency_markers
build_summary_for_scan_run = legacy.build_summary_for_scan_run
