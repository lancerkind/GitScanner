from gitscanner import count_spring_controllers as legacy
from gitscanner.core.models import ScanResult


strip_yaml_inline_comment = legacy.strip_yaml_inline_comment
normalize_yaml_value = legacy.normalize_yaml_value
extract_datasource_urls_from_yaml_content = legacy.extract_datasource_urls_from_yaml_content
collect_application_yml_files = legacy.collect_application_yml_files
collect_repo_datasources = legacy.collect_repo_datasources


class SpringDatasourceScanner:
    capability = "springboot.datasources"

    def scan(self, context):
        return ScanResult(capability=self.capability, records=collect_repo_datasources(str(context.repo_root)))
