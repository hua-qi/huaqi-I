from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date


@dataclass
class DateRange:
    start: date
    end: date


class DataProvider(ABC):
    name: str
    priority: int = 50
    supported_reports: list

    @abstractmethod
    def get_context(self, report_type: str, date_range: "DateRange") -> "str | None":
        pass


_registry: list = []


def register(provider: DataProvider) -> None:
    _registry.append(provider)


def get_providers(report_type: str) -> list:
    return sorted(
        [p for p in _registry if report_type in p.supported_reports or "*" in p.supported_reports],
        key=lambda p: p.priority,
    )
