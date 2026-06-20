import re
from pathlib import Path

from gitscanner.core.models import ScanResult


KARATE_PATH_PATTERN = re.compile(r"/\S+")


def find_controller_id_for_feature_file(file_path, controller_id_by_name):
    for segment in Path(file_path).parts:
        controller_id = controller_id_by_name.get(segment)
        if controller_id is not None:
            return controller_id
    return None


def extract_karate_paths(content):
    seen_paths = []
    seen_set = set()
    for match in KARATE_PATH_PATTERN.finditer(content):
        candidate = match.group(0)
        start_index = match.start()
        if start_index >= 1 and content[start_index - 1] == ":":
            continue
        if candidate.endswith("'") or candidate.endswith('"'):
            candidate = candidate[:-1]
        if candidate.endswith(","):
            candidate = candidate[:-1]
        if not candidate or candidate in seen_set:
            continue
        seen_set.add(candidate)
        seen_paths.append(candidate)
    return seen_paths


def collect_karate_feature_files(directory):
    test_root = Path(directory) / "src" / "test" / "java"
    if not test_root.exists() or not test_root.is_dir():
        return []
    return sorted(test_root.rglob("*.feature"))


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
