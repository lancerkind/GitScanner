from gitscanner import count_spring_controllers as legacy
from gitscanner.core.models import ScanResult


find_java_file_by_name = legacy.find_java_file_by_name
extract_service_names_from_signature = legacy.extract_service_names_from_signature
extract_controller_services = legacy.extract_controller_services
get_dependency_markers = legacy.get_dependency_markers
find_markers_in_service_content = legacy.find_markers_in_service_content


class SpringServiceDependencyScanner:
    capability = "springboot.service_dependencies"

    def __init__(self, conn):
        self.conn = conn

    def scan(self, context):
        return ScanResult(
            capability=self.capability,
            records=legacy.scan_service_dependencies_for_repo(self.conn, context.repo_id, str(context.repo_root)),
        )
