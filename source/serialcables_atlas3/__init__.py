"""
Serial Cables Atlas3 PCIe Gen6 Host Adapter Card Python API.

This library provides a Python interface to communicate with the Atlas3
host adapter card via its USB-C serial interface (CN7).

Example:
    >>> from serialcables_atlas3 import Atlas3
    >>> with Atlas3("/dev/ttyUSB0") as card:
    ...     info = card.get_version()
    ...     print(f"Model: {info.model}")
    ...     status = card.get_host_card_info()
    ...     print(f"Temperature: {status.thermal.switch_temperature_celsius}°C")
    ...     ports = card.get_port_status()
    ...     for port in ports.ext_mcio_ports:
    ...         if port.is_linked:
    ...             print(f"Port {port.port_number}: {port.negotiated_speed.value} x{port.negotiated_width}")

Hardware:
    The Atlas3 Host Adapter Card features the Broadcom PEX90144 PCIe Gen6 switch
    supporting up to 144 lanes and 72 ports. Connect via USB-C connector CN7
    for CLI access.

For more information, visit: https://serialcables.com
"""

__version__ = "0.1.0"
__author__ = "Serial Cables"
__license__ = "MIT"

from .atlas3 import Atlas3
from .exceptions import (
    Atlas3Error,
    CommandError,
    ConnectionError,
    FirmwareUpdateError,
    InvalidParameterError,
    ParseError,
    TimeoutError,
)
from .models import (
    AllErrorCounters,
    BistResult,
    ClockStatus,
    ErrorCounters,
    FanInfo,
    FirmwareType,
    FlashDump,
    FlitStatus,
    HostCardInfo,
    I2CDevice,
    I2CReadResult,
    I2CWriteResult,
    LinkSpeed,
    LinkStatus,
    OperationMode,
    PortInfo,
    PortStatus,
    PortType,
    PowerInfo,
    RegisterDump,
    SdbTarget,
    SpreadMode,
    SpreadStatus,
    ThermalInfo,
    VersionInfo,
    VoltageInfo,
)

__all__ = [
    # Main class
    "Atlas3",
    # Version
    "__version__",
    # Exceptions
    "Atlas3Error",
    "CommandError",
    "ConnectionError",
    "FirmwareUpdateError",
    "InvalidParameterError",
    "ParseError",
    "TimeoutError",
    # Enums
    "FirmwareType",
    "LinkSpeed",
    "LinkStatus",
    "OperationMode",
    "PortType",
    "SdbTarget",
    "SpreadMode",
    # Data models
    "AllErrorCounters",
    "BistResult",
    "ClockStatus",
    "ErrorCounters",
    "FanInfo",
    "FlashDump",
    "FlitStatus",
    "HostCardInfo",
    "I2CDevice",
    "I2CReadResult",
    "I2CWriteResult",
    "PortInfo",
    "PortStatus",
    "PowerInfo",
    "RegisterDump",
    "SpreadStatus",
    "ThermalInfo",
    "VersionInfo",
    "VoltageInfo",
]
