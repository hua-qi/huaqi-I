from abc import ABC, abstractmethod
from typing import Callable


class SchedulerAdapter(ABC):

    @abstractmethod
    def start(self) -> None:
        pass

    @abstractmethod
    def stop(self) -> None:
        pass

    @abstractmethod
    def add_interval_job(self, func: Callable, seconds: int, job_id: str) -> None:
        pass

    @abstractmethod
    def add_cron_job(self, func: Callable, cron_expr: str, job_id: str) -> None:
        pass

    @abstractmethod
    def remove_job(self, job_id: str) -> None:
        pass
