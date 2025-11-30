"""Custom exceptions for the Serial Cables Atlas3 library."""

from typing import Optional


class Atlas3Error(Exception):
    """Base exception for all Atlas3-related errors."""

    pass


class ConnectionError(Atlas3Error):
    """Raised when connection to the Atlas3 device fails."""

    def __init__(self, port: str, message: Optional[str] = None):
        self.port = port
        self.message = message or f"Failed to connect to Atlas3 on port {port}"
        super().__init__(self.message)


class CommandError(Atlas3Error):
    """Raised when a CLI command fails or returns an error."""

    def __init__(self, command: str, message: Optional[str] = None):
        self.command = command
        self.message = message or f"Command '{command}' failed"
        super().__init__(self.message)


class TimeoutError(Atlas3Error):
    """Raised when a command times out waiting for response."""

    def __init__(self, command: str, timeout: float):
        self.command = command
        self.timeout = timeout
        self.message = f"Command '{command}' timed out after {timeout}s"
        super().__init__(self.message)


class InvalidParameterError(Atlas3Error):
    """Raised when an invalid parameter is passed to a command."""

    def __init__(self, parameter: str, value: str, valid_values: Optional[str] = None):
        self.parameter = parameter
        self.value = value
        self.valid_values = valid_values
        msg = f"Invalid value '{value}' for parameter '{parameter}'"
        if valid_values:
            msg += f". Valid values: {valid_values}"
        super().__init__(msg)


class FirmwareUpdateError(Atlas3Error):
    """Raised when a firmware update operation fails."""

    def __init__(self, firmware_type: str, message: Optional[str] = None):
        self.firmware_type = firmware_type
        self.message = message or f"Failed to update {firmware_type} firmware"
        super().__init__(self.message)


class ParseError(Atlas3Error):
    """Raised when response parsing fails."""

    def __init__(self, response: str, message: Optional[str] = None):
        self.response = response
        self.message = message or f"Failed to parse response: {response[:100]}..."
        super().__init__(self.message)
