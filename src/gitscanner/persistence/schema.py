"""Database schema compatibility exports."""

from gitscanner import count_spring_controllers as legacy


SCHEMA_STATEMENTS = legacy.SCHEMA_STATEMENTS
get_default_classifications = legacy.get_default_classifications
seed_dependency_classifications = legacy.seed_dependency_classifications
