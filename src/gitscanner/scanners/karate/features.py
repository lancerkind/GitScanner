from gitscanner import count_spring_controllers as legacy
from gitscanner.core.models import ScanResult


collect_karate_feature_files = legacy.collect_karate_feature_files
extract_karate_paths = legacy.extract_karate_paths
find_controller_id_for_feature_file = legacy.find_controller_id_for_feature_file


class KarateFeatureScanner:
    capability = "karate.features"

    def __init__(self, conn):
        self.conn = conn

    def scan(self, context):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT id, name
            FROM controllers
            WHERE repo_id = ?
            """,
            (context.repo_id,),
        )
        controller_id_by_name = {name: controller_id for controller_id, name in cursor.fetchall()}
        records = []
        for feature_path in collect_karate_feature_files(str(context.repo_root)):
            relative_path = feature_path.relative_to(context.repo_root)
            file_path = str(relative_path)
            controller_id = find_controller_id_for_feature_file(file_path, controller_id_by_name)
            if controller_id is None:
                continue
            try:
                content = feature_path.read_text(encoding="utf-8")
            except OSError:
                continue
            records.append(
                {
                    "controller_id": controller_id,
                    "file_path": file_path,
                    "file_name": feature_path.name,
                    "paths": extract_karate_paths(content),
                }
            )
        return ScanResult(capability=self.capability, records=records)
