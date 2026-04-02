from typing import Optional


class HuaqiError(Exception):
    def __init__(self, message: str, context: Optional[dict] = None):
        super().__init__(message)
        self.context = context or {}


class StorageError(HuaqiError):
    pass


class SignalNotFoundError(StorageError):
    pass


class SignalDuplicateError(StorageError):
    pass


class VectorError(HuaqiError):
    pass


class VectorUpsertError(VectorError):
    pass


class TelosError(HuaqiError):
    pass


class DimensionNotFoundError(TelosError):
    pass


class DimensionParseError(TelosError):
    pass


class DistillationError(HuaqiError):
    pass


class AnalysisError(DistillationError):
    pass


class UpdateGenerationError(DistillationError):
    pass


class SchedulerError(HuaqiError):
    pass


class InterfaceError(HuaqiError):
    pass


class AgentError(HuaqiError):
    pass


class IntentParseError(AgentError):
    pass


class UserError(HuaqiError):
    pass


class UserNotFoundError(UserError):
    pass
