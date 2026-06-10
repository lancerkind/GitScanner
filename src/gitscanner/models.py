from dataclasses import dataclass, field


@dataclass
class Controller:
    rest_controllers: int = 0
    controllers: int = 0

    @property
    def total(self):
        return self.rest_controllers + self.controllers


@dataclass
class RepoResult:
    repo_name: str
    controllers: list[Controller] = field(default_factory=list)
    total_at_rest_controllers: int = 0
    total_at_controllers: int = 0
    total_rest_controllers: int = 0

    @property
    def total_controller_files(self):
        return self.total_at_rest_controllers + self.total_at_controllers


@dataclass
class ScanSummary:
    repo_results: list[RepoResult] = field(default_factory=list)
    total_rest_controllers: int = 0
    total_controllers: int = 0

    @property
    def total_controller_files(self):
        return self.total_rest_controllers + self.total_controllers
