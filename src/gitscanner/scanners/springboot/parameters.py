import re

from gitscanner.scanners.springboot.parsing import find_matching_closing_parenthesis, split_top_level_commas


SUPPORTED_PARAMETER_SOURCE_BY_ANNOTATION = {
    "PathVariable": "PATH",
    "RequestParam": "QUERY",
    "RequestHeader": "HEADER",
    "RequestBody": "BODY",
    "CookieValue": "COOKIE",
}
SUPPORTED_PARAMETER_ANNOTATION_PATTERN = re.compile(
    r"@(?P<name>PathVariable|RequestParam|RequestHeader|RequestBody|CookieValue)\s*(?:\((?P<args>.*?)\))?",
    re.DOTALL,
)
REQUIRED_ATTRIBUTE_PATTERN = re.compile(r"\brequired\s*=\s*(true|false)")
NAME_ATTRIBUTE_PATTERN = re.compile(r"\b(?:value|name)\s*=\s*\"([^\"]+)\"")


def extract_parameter_name(annotation_args, java_parameter_name):
    if not annotation_args:
        return java_parameter_name
    explicit_name = NAME_ATTRIBUTE_PATTERN.search(annotation_args)
    if explicit_name:
        return explicit_name.group(1)
    literal_values = re.findall(r'"([^\"]+)"', annotation_args)
    if literal_values:
        return literal_values[0]
    return java_parameter_name


def extract_parameter_required(source, annotation_args):
    if source == "BODY":
        return True
    if not annotation_args:
        return True
    match = REQUIRED_ATTRIBUTE_PATTERN.search(annotation_args)
    if match:
        return match.group(1).lower() == "true"
    return True


def build_parameter_from_definition(parameter_definition):
    match = SUPPORTED_PARAMETER_ANNOTATION_PATTERN.search(parameter_definition)
    if not match:
        return None

    annotation_name = match.group("name")
    source = SUPPORTED_PARAMETER_SOURCE_BY_ANNOTATION[annotation_name]
    annotation_args = match.group("args")
    after_annotation = parameter_definition[match.end():].strip()
    parts = [part for part in re.split(r"\s+", after_annotation) if part]
    if len(parts) < 2:
        return None
    java_type = parts[-2]
    parameter_name = parts[-1]

    return {
        "name": extract_parameter_name(annotation_args, parameter_name),
        "java_type": java_type,
        "source": source,
        "required": extract_parameter_required(source, annotation_args),
    }


def extract_endpoint_parameters(content, mapping_end_index):
    signature_start = content.find("(", mapping_end_index)
    if signature_start == -1:
        return []
    signature_end = find_matching_closing_parenthesis(content, signature_start)
    if signature_end == -1:
        return []
    signature_body = content[signature_start + 1:signature_end]
    parameters = []
    for parameter_definition in split_top_level_commas(signature_body):
        parameter = build_parameter_from_definition(parameter_definition)
        if parameter is not None:
            parameters.append(parameter)
    return parameters
