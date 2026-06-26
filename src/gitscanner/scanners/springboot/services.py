import re
from collections import defaultdict
from pathlib import Path

from gitscanner.core.models import ScanResult
from gitscanner.persistence.sqlite_store import (
    insert_controller_service,
    insert_service_dependency_markers,
    update_repo_kafka_binding_bean,
)
from gitscanner.scanners.springboot.controllers import split_top_level_commas


JAVA_IDENTIFIER_PATTERN = r"[A-Za-z_][A-Za-z0-9_]*"


def find_java_file_by_name(repo_root, file_name):
    matches = list(Path(repo_root).rglob(file_name))
    if not matches:
        return None
    return sorted(matches)[0]


def extract_service_names_from_signature(signature):
    services = set()
    params = split_top_level_commas(signature.strip())
    for param in params:
        cleaned_param = re.sub(
            r"@\w+(?:\s*\([^)]*\))?",
            " ",
            param,
            flags=re.DOTALL,
        )
        cleaned_param = re.sub(r"\bfinal\b", " ", cleaned_param)
        parts = [part for part in re.split(r"\s+", cleaned_param.strip()) if part]
        if len(parts) < 2:
            continue
        java_type = parts[-2]
        cleaned_type = java_type.replace("...", "")
        services.add(cleaned_type)
    return services


def extract_controller_services(content):
    services = set()

    field_declarations = re.findall(
        rf"""
        (?:@\w+(?:\s*\([^)]*\))?\s*)*
        (?:
            public|protected|private|static|final|volatile|transient
        |\s)+
        (?P<service>[A-Z][A-Za-z0-9_]*Service)
        \s+
        {JAVA_IDENTIFIER_PATTERN}
        \s*(?:=|;)
        """,
        content,
        flags=re.VERBOSE | re.DOTALL,
    )
    services.update(field_declarations)

    package_private_field_declarations = re.findall(
        rf"""
        (?:@\w+(?:\s*\([^)]*\))?\s*)+
        (?P<service>[A-Z][A-Za-z0-9_]*Service)
        \s+
        {JAVA_IDENTIFIER_PATTERN}
        \s*(?:=|;)
        """,
        content,
        flags=re.VERBOSE | re.DOTALL,
    )
    services.update(package_private_field_declarations)

    for signature in re.findall(r"\(([^)]*)\)", content, re.DOTALL):
        services.update(extract_service_names_from_signature(signature))

    direct_instantiations = re.findall(r"new\s+([A-Z][A-Za-z0-9_]*Service)\s*\(", content)
    services.update(direct_instantiations)

    return sorted(service for service in services if service.endswith("Service"))


def get_dependency_markers(conn):
    rows = conn.execute("SELECT marker FROM dependency_classifications").fetchall()
    return [row[0] for row in rows]


def find_markers_in_service_content(content, markers):
    found_markers = set()
    for marker in markers:
        if marker in content:
            found_markers.add(marker)
    return found_markers


def scan_service_dependencies_for_repo(conn, repo_id, repo_root):
    marker_candidates = get_dependency_markers(conn)
    records: List[Dict[str, Any]] = []
    counts = defaultdict(int)
    not_found_services = []
    controller_rows = conn.execute(
        "SELECT id, name FROM controllers WHERE repo_id = ?",
        (repo_id,),
    ).fetchall()

    for controller_id, controller_name in controller_rows:
        controller_file = find_java_file_by_name(repo_root, f"{controller_name}.java")
        if not controller_file:
            print(f"WARNING: {controller_name}.java not found while scanning services")
            continue
        try:
            controller_content = controller_file.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            print(f"WARNING: Could not read {controller_file} while scanning services")
            continue

        service_names = extract_controller_services(controller_content)
        for service_name in service_names:
            service_file = find_java_file_by_name(repo_root, f"{service_name}.java")
            if not service_file:
                records.append(
                    {
                        "controller_id": controller_id,
                        "service_name": service_name,
                        "found": False,
                        "markers": [],
                    }
                )
#                insert_controller_service(conn, controller_id, service_name, False)
#                not_found_services.append(service_name)
                counts["services_scanned"] += 1
                counts["services_not_found"] += 1
                continue

#            controller_service_id = insert_controller_service(conn, controller_id, service_name, True)
            counts["services_scanned"] += 1
            try:
                service_content = service_file.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                records.append(
                    {
                        "controller_id": controller_id,
                        "service_name": service_name,
                        "found": True,
                        "markers": [],
                    }
                )
                continue

            markers = find_markers_in_service_content(service_content, marker_candidates)
            records.append(
                {
                    "controller_id": controller_id,
                    "service_name": service_name,
                    "found": True,
                    "markers": sorted(markers),
                }
            )
#            insert_service_dependency_markers(conn, controller_service_id, markers)
            counts["dependency_markers"] += len(markers)

    counts["not_found_service_names"] = sorted(set(not_found_services))
    return records


class SpringServiceDependencyScanner:
    capability = "springboot.service_dependencies"

    def __init__(self, conn):
        self.conn = conn

    def scan(self, context):
        return ScanResult(
            capability=self.capability,
            records=scan_service_dependencies_for_repo(self.conn, context.repo_id, str(context.repo_root)),
        )


class SpringCloudStreamScanner:
    capability = "springboot.cloud_stream"

    def __init__(self, conn):
        self.conn = conn

    def scan(self, context):
        repo_id = context.repo_id
        repo_root = str(context.repo_root)

        # 1. Get bindings for this repo to know which beans to look for
        bindings = self.conn.execute(
            "SELECT binding_name FROM repo_kafka_bindings WHERE repo_id = ?",
            (repo_id,)
        ).fetchall()

        if not bindings:
            return ScanResult(capability=self.capability, records=[])

        binding_names = {b[0] for b in bindings}
        records = []

        # 2. Scan Java files for @Bean methods
        java_files = list(Path(repo_root).rglob("*.java"))

        for java_file in java_files:
            try:
                content = java_file.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            bean_methods = re.finditer(
                r"@Bean\s+(?:public|protected|private|static|final|\s)*"
                r"(Consumer|Function|Supplier)\s*<[^>]*>\s+"
                r"(?P<method_name>[A-Za-z0-9_]+)\s*\((?P<params>[^)]*)\)",
                content,
                re.DOTALL
            )

            for match in bean_methods:
                method_name = match.group("method_name")
                params_str = match.group("params")

                if method_name in binding_names:
                    records.append({
                        "binding_name": method_name,
                        "bean_name": method_name,
                        "injected_services": sorted(extract_service_names_from_signature(params_str))
                    })

        return ScanResult(capability=self.capability, records=records)
