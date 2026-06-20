import re
from collections import defaultdict
from pathlib import Path

from gitscanner.core.models import ScanResult
from gitscanner.scanners.springboot.parsing import split_top_level_commas
from gitscanner.scanners.springboot.parameters import extract_endpoint_parameters


HTTP_METHOD_BY_ANNOTATION = {
    "Get": "GET",
    "Post": "POST",
    "Put": "PUT",
    "Delete": "DELETE",
    "Patch": "PATCH",
}
MAPPING_ANNOTATION_PATTERN = re.compile(
    r"@(?P<name>Get|Post|Put|Delete|Patch|Request)Mapping(?:\s*\((?P<args>.*?)\))?",
    re.DOTALL,
)
PATH_NAMED_PATTERN = re.compile(r"\b(?:value|path)\s*=\s*\"([^\"]*)\"")
PATH_ARRAY_PATTERN = re.compile(r"\b(?:value|path)\s*=\s*\{(?P<items>[^}]*)\}", re.DOTALL)
STRING_LITERAL_PATTERN = re.compile(r'"([^\"]*)"')
REQUEST_METHOD_PATTERN = re.compile(r"RequestMethod\.([A-Z]+)")
STATIC_REQUEST_METHOD_PATTERN = re.compile(r"\bmethod\s*=\s*([A-Z]+)")


def count_controllers_in_directory(directory):
    """Collect Spring controller files found within a directory."""
    controllers = []

    for java_file in Path(directory).rglob("*.java"):
        try:
            with open(java_file, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

                if "@RestController" in content:
                    base_path, endpoints = extract_controller_mappings(content)
                    controllers.append(
                        {
                            "name": java_file.stem,
                            "base_path": base_path,
                            "type": "RestController",
                            "endpoints": endpoints,
                        }
                    )
                elif "@Controller" in content:
                    base_path, endpoints = extract_controller_mappings(content)
                    controllers.append(
                        {
                            "name": java_file.stem,
                            "base_path": base_path,
                            "type": "Controller",
                            "endpoints": endpoints,
                        }
                    )
        except Exception:
            continue

    return controllers


def extract_controller_mappings(content):
    class_index = content.find("class ")
    class_level_request_mapping = None
    matches = list(MAPPING_ANNOTATION_PATTERN.finditer(content))
    if class_index >= 0:
        request_mappings_before_class = [
            match
            for match in matches
            if match.group("name") == "Request" and match.end() <= class_index
        ]
        if request_mappings_before_class:
            class_level_request_mapping = request_mappings_before_class[-1]

    base_path = None
    if class_level_request_mapping:
        paths = extract_paths_from_annotation_args(class_level_request_mapping.group("args"))
        if paths:
            non_null_paths = [path for path in paths if path is not None]
            if len(non_null_paths) > 1:
                base_path = non_null_paths
            elif non_null_paths:
                base_path = non_null_paths[0]

    endpoints = []
    for match in matches:
        if match.group("args") is None:
            next_index = match.end()
            while next_index < len(content) and content[next_index].isspace():
                next_index += 1
            if next_index < len(content) and content[next_index] == "(":
                continue
        if class_level_request_mapping and match.span() == class_level_request_mapping.span():
            continue
        mapping_endpoints = build_endpoints_from_annotation(match.group("name"), match.group("args"))
        parameters = extract_endpoint_parameters(content, match.end())
        for endpoint in mapping_endpoints:
            endpoint["parameters"] = list(parameters)
        endpoints.extend(mapping_endpoints)

    endpoints_by_method = defaultdict(list)
    for endpoint in endpoints:
        endpoints_by_method[endpoint["http_method"]].append(endpoint)

    filtered_endpoints = []
    for endpoint in endpoints:
        if endpoint["path"] is not None:
            filtered_endpoints.append(endpoint)
            continue
        method_endpoints = endpoints_by_method[endpoint["http_method"]]
        has_path_specific_variant = any(item["path"] is not None for item in method_endpoints)
        if not has_path_specific_variant:
            filtered_endpoints.append(endpoint)

    return base_path, filtered_endpoints


def extract_paths_from_annotation_args(annotation_args):
    if annotation_args is None:
        return [None]

    array_match = PATH_ARRAY_PATTERN.search(annotation_args)
    if array_match:
        return [path for path in STRING_LITERAL_PATTERN.findall(array_match.group("items"))]

    paths = PATH_NAMED_PATTERN.findall(annotation_args)
    if paths:
        return paths

    stripped_args = annotation_args.strip()
    unnamed_paths = []
    if stripped_args.startswith("{"):
        unnamed_paths = STRING_LITERAL_PATTERN.findall(stripped_args)
    if stripped_args.startswith('"'):
        unnamed_paths = STRING_LITERAL_PATTERN.findall(stripped_args)
    if unnamed_paths:
        return unnamed_paths
    return [None]


def build_endpoints_from_annotation(mapping_name, annotation_args):
    paths = extract_paths_from_annotation_args(annotation_args)
    if mapping_name == "Request":
        request_methods = []
        if annotation_args:
            request_methods = REQUEST_METHOD_PATTERN.findall(annotation_args)
            if not request_methods:
                request_methods = STATIC_REQUEST_METHOD_PATTERN.findall(annotation_args)
        if not request_methods:
            request_methods = ["GET"]
    else:
        request_methods = [HTTP_METHOD_BY_ANNOTATION[mapping_name]]

    return [
        {"http_method": http_method, "path": path}
        for http_method in request_methods
        for path in paths
    ]


class SpringControllerScanner:
    capability = "springboot.controllers"

    def scan(self, context):
        return ScanResult(capability=self.capability, records=count_controllers_in_directory(str(context.repo_root)))
