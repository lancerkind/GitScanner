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
        *resources_root.rglob("bootstrap*.yml"),
        *resources_root.rglob("bootstrap*.yaml"),
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


def extract_datasource_info_from_yaml_content(content):
    stack = []
    urls = []
    flat_urls = []
    kafka_brokers = []
    kafka_bindings = []

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

        full_path = ".".join([item[1] for item in stack] + [key])
        normalized_value = normalize_yaml_value(value)

        if not value:
            stack.append((indent, key))
            # Check for spring.cloud.stream.bindings or spring.cloud.stream.kafka
            continue

        if full_path in {"spring.datasource.url", "env.spring.datasource.url"} and normalized_value:
            urls.append(normalized_value)
        elif full_path == "spring.cloud.stream.kafka.binder.brokers" and normalized_value:
            kafka_brokers.append(normalized_value)
        
        # Check if it's a binding key: spring.cloud.stream.bindings.<binding-key>
        if len(stack) >= 4:
            parent_path = ".".join([item[1] for item in stack[:4]])
            if parent_path == "spring.cloud.stream.bindings":
                binding_key = stack[4][1] if len(stack) > 4 else key
                # We only need to process the binding key once.
                # In YAML, it can be:
                # bindings:
                #   my-in-0:
                #     destination: ...
                # Or just a value (less likely for bindings).
                # If we are here, and the parent is bindings, then the current key or one of its ancestors is the binding name.
                pass

        inline_match = INLINE_YAML_PATTERN.match(line_without_comment)
        if inline_match and inline_match.group(1) == "env.spring.datasource.url":
            inline_value = normalize_yaml_value(inline_match.group(2))
            if inline_value:
                flat_urls.append(inline_value)

    # Re-scan for bindings specifically because the stack-based approach above is a bit messy for nested bindings
    stack = []
    has_stream_config = False
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
        stack.append((indent, key))
        full_path = ".".join([item[1] for item in stack])
        
        if full_path in {"spring.cloud.stream.kafka", "spring.cloud.stream.bindings"}:
            has_stream_config = True

        if full_path.startswith("spring.cloud.stream.bindings."):
            parts = full_path.split(".")
            if len(parts) == 5: # spring.cloud.stream.bindings.<binding_key>
                binding_key = parts[4]
                binding_name, direction = parse_binding_key(binding_key)
                if binding_name and direction:
                    if not any(b["binding_name"] == binding_name and b["direction"] == direction for b in kafka_bindings):
                        kafka_bindings.append({"binding_name": binding_name, "direction": direction})

    merged_urls = []
    seen = set()
    for url in [*urls, *flat_urls]:
        if url in seen:
            continue
        seen.add(url)
        merged_urls.append(url)
    
    return {
        "urls": merged_urls,
        "kafka_brokers": kafka_brokers,
        "kafka_bindings": kafka_bindings,
        "has_stream_config": has_stream_config
    }


def parse_binding_key(key):
    match = re.match(r"^(.*)-(in|out)-\d+$", key)
    if match:
        name = match.group(1)
        direction = "input" if match.group(2) == "in" else "output"
        return name, direction
    return None, None


def collect_repo_datasources(repo_root):
    datasource_rows = []
    for file_path in collect_application_yml_files(repo_root):
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        
        info = extract_datasource_info_from_yaml_content(content)
        relative_name = str(file_path.relative_to(repo_root)).replace("\\", "/")
        
        # SQL URLs
        datasource_rows.extend([{"source_file": relative_name, "url": url} for url in info["urls"]])
        
        # Kafka Broker URL (AC1)
        if info["has_stream_config"]:
            broker_url = info["kafka_brokers"][0] if info["kafka_brokers"] else "kafka://stream-binder"
            datasource_rows.append({"source_file": relative_name, "url": broker_url})
            
    return datasource_rows


def collect_repo_kafka_bindings(repo_root):
    binding_rows = []
    for file_path in collect_application_yml_files(repo_root):
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        
        info = extract_datasource_info_from_yaml_content(content)
        binding_rows.extend(info["kafka_bindings"])
    
    # Remove duplicates across files if any (though unlikely to have same binding in different files for same repo, but possible)
    unique_bindings = []
    seen = set()
    for b in binding_rows:
        key = (b["binding_name"], b["direction"])
        if key not in seen:
            seen.add(key)
            unique_bindings.append(b)
            
    return unique_bindings


class SpringKafkaBindingScanner:
    capability = "springboot.kafka_bindings"

    def scan(self, context):
        return ScanResult(capability=self.capability, records=collect_repo_kafka_bindings(str(context.repo_root)))


class SpringDatasourceScanner:
    capability = "springboot.datasources"

    def scan(self, context):
        return ScanResult(capability=self.capability, records=collect_repo_datasources(str(context.repo_root)))
