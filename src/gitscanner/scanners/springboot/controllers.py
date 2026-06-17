from gitscanner import count_spring_controllers as legacy
from gitscanner.core.models import ScanResult


count_controllers_in_directory = legacy.count_controllers_in_directory
extract_controller_mappings = legacy.extract_controller_mappings
extract_paths_from_annotation_args = legacy.extract_paths_from_annotation_args
build_endpoints_from_annotation = legacy.build_endpoints_from_annotation
find_matching_closing_parenthesis = legacy.find_matching_closing_parenthesis
split_top_level_commas = legacy.split_top_level_commas


class SpringControllerScanner:
    capability = "springboot.controllers"

    def scan(self, context):
        return ScanResult(capability=self.capability, records=count_controllers_in_directory(str(context.repo_root)))
