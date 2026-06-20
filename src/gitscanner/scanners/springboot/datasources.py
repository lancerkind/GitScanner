import re
from pathlib import Path

from gitscanner.core.models import ScanResult


INLINE_YAML_PATTERN = re.compile(r"^\s*([A-Za-z0-9_.-]+)\s*:\s*(.+?)\s*$")


def collect_application_yml_files(directory):
    resources_root = Path(directory) / "src" / "main" / "resources"
    if not resources_root.exists() or not resources_root.is_dir():
        return []
    return sorted([
        *resources_root.rglob("application*.yml"),
        *resources_root.rglob("application*.yaml"),
    ])


def strip_yaml_inline_comment(value):
    quote_char = None
    for index, char in enumerate(value):
        if char in {'"', "'"}:
            if quote_char is None:
                quote_char = char
            elif quote_char == char:
                quote_char = None
        if char == "#" and quote_char is None:
            return value[:index].rstrip()
    return value.rstrip()


def normalize_yaml_value(value):
    value = strip_yaml_inline_comment(value.strip())
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def extract_datasource_urls_from_yaml_content(content):
    stack = []
    urls = []
    flat_urls = []

    for raw_line in content.splitlines():
        line_without_comment = strip_yaml_inline_comment(raw_line).rstrip()
        stripped = line_without_comment.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue

        indent = len(line_without_comment) - len(line_without_comment.lstrip(" "))
        while stack and indent <= stack[-1][0]:
            stack.pop()

        key, _, raw_value = stripped.partition(":")
        key = key.strip()
        value = raw_value.strip()

        if not value:
            stack.append((indent, key))
            continue

        full_path = ".".join([item[1] for item in stack] + [key])
        normalized_value = normalize_yaml_value(value)
        if full_path in {"spring.datasource.url", "env.spring.datasource.url"} and normalized_value:
            urls.append(normalized_value)

        inline_match = INLINE_YAML_PATTERN.match(line_without_comment)
        if inline_match and inline_match.group(1) == "env.spring.datasource.url":
            inline_value = normalize_yaml_value(inline_match.group(2))
            if inline_value:
                flat_urls.append(inline_value)

    merged_urls = []
    seen = set()
    for url in [*urls, *flat_urls]:
        if url in seen:
            continue
        seen.add(url)
        merged_urls.append(url)
    return merged_urls


def collect_repo_datasources(repo_root):
    datasource_rows = []
    for file_path in collect_application_yml_files(repo_root):
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        urls = extract_datasource_urls_from_yaml_content(content)
        relative_name = str(file_path.relative_to(repo_root)).replace("\\", "/")
        datasource_rows.extend([{"source_file": relative_name, "url": url} for url in urls])
    return datasource_rows


class SpringDatasourceScanner:
    capability = "springboot.datasources"

    def scan(self, context):
        return ScanResult(capability=self.capability, records=collect_repo_datasources(str(context.repo_root)))
