from __future__ import annotations

from enum import IntEnum


class ExitCode(IntEnum):
    OK = 0
    CONFIG_ERROR = 2
    AUTH_ERROR = 3
    OCI_ERROR = 4
    RUNTIME_ERROR = 5


class InventoryError(Exception):
    """Base error for inventory pipeline."""


class ConfigError(InventoryError):
    """Raised for configuration or argument issues."""


class AuthResolutionError(InventoryError):
    """Raised when authentication cannot be resolved."""


class OCIClientError(InventoryError):
    """Raised when OCI SDK operations fail in a non-retriable way."""


class ExportError(InventoryError):
    """Raised when exporting artifacts fails."""


class DiffError(InventoryError):
    """Raised when diffing inventories fails."""


def as_exit_code(exc: BaseException) -> int:
    if isinstance(exc, (ConfigError, ValueError)):
        return int(ExitCode.CONFIG_ERROR)
    if isinstance(exc, AuthResolutionError):
        return int(ExitCode.AUTH_ERROR)
    if isinstance(exc, OCIClientError):
        return int(ExitCode.OCI_ERROR)
    if isinstance(exc, (ExportError, DiffError, InventoryError)):
        return int(ExitCode.RUNTIME_ERROR)
    return 1