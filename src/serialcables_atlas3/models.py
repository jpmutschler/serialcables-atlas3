"""Data models for Atlas3 Host Adapter Card responses."""

from dataclasses import dataclass
from enum import Enum
import json
from typing import Any, Dict, List, Optional


class LinkSpeed(Enum):
    """PCIe link speed generations."""

    GEN1 = "Gen1"  # 2.5 GT/s
    GEN2 = "Gen2"  # 5.0 GT/s
    GEN3 = "Gen3"  # 8.0 GT/s
    GEN4 = "Gen4"  # 16.0 GT/s
    GEN5 = "Gen5"  # 32.0 GT/s
    GEN6 = "Gen6"  # 64.0 GT/s

    @classmethod
    def from_string(cls, value: str) -> "LinkSpeed":
        """Parse link speed from string."""
        value = value.strip().lower()
        for speed in cls:
            if speed.value.lower() == value:
                return speed
        raise ValueError(f"Unknown link speed: {value}")


class LinkStatus(Enum):
    """Port link status."""

    ACTIVE = "Active"  # Desired and negotiated link speed matched
    DEGRADED = "Degraded"  # Desired and negotiated speed/width don't match
    IDLE = "Idle"  # No physical link detected

    @classmethod
    def from_string(cls, value: str) -> "LinkStatus":
        """Parse link status from string."""
        value = value.strip().lower()
        for status in cls:
            if status.value.lower() == value:
                return status
        raise ValueError(f"Unknown link status: {value}")


class PortType(Enum):
    """Port type classification."""

    USP = "USP"  # Upstream Port
    DSP = "DSP"  # Downstream Port
    MCIO_EXT = "EXT_MCIO"
    MCIO_INT = "INT_MCIO"
    STRADDLE = "Straddle"
    GOLDEN_FINGER = "Golden_Finger"


class SpreadMode(Enum):
    """PCIe clock spread modes."""

    OFF = "off"  # No spread (CFC - Common Frequency Clock)
    DOWN_2500PPM = "1"  # -0.25% spread (SSC)
    DOWN_5000PPM = "2"  # -0.5% spread (SSC)


class OperationMode(Enum):
    """Host card operation modes."""

    MODE_1 = 1  # Common clock, precoding Enable
    MODE_2 = 2  # Common clock, precoding Disable
    MODE_3 = 3  # SRNS, precoding Enable
    MODE_4 = 4  # SRNS, precoding Disable


class SdbTarget(Enum):
    """SDB UART port target."""

    USB = "usb"  # Route to USB connector CN6
    MCU = "mcu"  # Route to MCU


class FirmwareType(Enum):
    """Firmware types for update."""

    MINI = "mini"  # Atlas3 unmanaged mini SBR
    MAIN = "main"  # Atlas3 unmanaged main SBR
    FW = "fw"  # Atlas3 managed FW
    MCU = "mcu"  # On-board MCU FW


@dataclass
class VersionInfo:
    """Version and product information."""

    company: str
    model: str
    serial_number: Optional[str]
    mcu_version: str
    mcu_build_time: str
    sbr_version: str


@dataclass
class ThermalInfo:
    """Temperature sensor information."""

    switch_temperature_celsius: float


@dataclass
class FanInfo:
    """Fan speed information."""

    switch_fan_rpm: int


@dataclass
class VoltageInfo:
    """Voltage sensor readings."""

    voltage_1v5: float
    voltage_vdd: float
    voltage_vdda: float
    voltage_vdda12: float


@dataclass
class PowerInfo:
    """Power consumption information."""

    power_voltage: float
    load_current: float
    load_power: float


@dataclass
class HostCardInfo:
    """Complete host card information from lsd command."""

    thermal: ThermalInfo
    fan: FanInfo
    voltages: VoltageInfo
    power: PowerInfo


@dataclass
class PortInfo:
    """Information about a single port."""

    station: int
    connector: Optional[str]
    port_number: int
    negotiated_speed: Optional[LinkSpeed]
    negotiated_width: int
    max_speed: LinkSpeed
    max_width: int
    status: LinkStatus
    port_type: PortType

    @property
    def station_name(self) -> str:
        """Get station as string (e.g., 'Stn2', 'Stn7')."""
        return f"Stn{self.station}"

    @property
    def speed(self) -> Optional[str]:
        """Get negotiated speed as string (e.g., 'Gen4', 'Gen5')."""
        return self.negotiated_speed.value if self.negotiated_speed else None

    @property
    def width(self) -> int:
        """Get negotiated width (alias for negotiated_width)."""
        return self.negotiated_width

    @property
    def max_speed_str(self) -> str:
        """Get max speed as combined string (e.g., 'Gen6 x16', 'Gen6 x4')."""
        return f"{self.max_speed.value} x{self.max_width}"

    @property
    def status_str(self) -> str:
        """Get status as string (e.g., 'Degraded', 'Idle', 'Active')."""
        return self.status.value

    @property
    def is_linked(self) -> bool:
        """Check if port has an active link (Width > 0)."""
        return self.negotiated_width > 0

    @property
    def is_degraded(self) -> bool:
        """Check if port is operating in degraded mode."""
        return self.status == LinkStatus.DEGRADED


@dataclass
class PortStatus:
    """Complete port status from showport command."""

    chip_version: str
    upstream_ports: List[PortInfo]
    ext_mcio_ports: List[PortInfo]
    int_mcio_ports: List[PortInfo]
    straddle_ports: List[PortInfo]


@dataclass
class I2CDevice:
    """I2C device information from bist command."""

    channel: str
    device_name: str
    address: int
    status: str

    @property
    def is_ok(self) -> bool:
        """Check if device is responding correctly."""
        return self.status.upper() == "OK"


@dataclass
class BistResult:
    """Built-in self-test results."""

    devices: List[I2CDevice]

    @property
    def all_passed(self) -> bool:
        """Check if all devices passed."""
        return all(dev.is_ok for dev in self.devices)


@dataclass
class ErrorCounters:
    """Error counters for a single port."""

    port_number: int
    port_rx: int
    bad_tlp: int
    bad_dllp: int
    rec_diag: int
    link_down: int
    flit_error: int

    @property
    def has_errors(self) -> bool:
        """Check if any errors have occurred."""
        return any(
            [
                self.port_rx,
                self.bad_tlp,
                self.bad_dllp,
                self.rec_diag,
                self.link_down,
                self.flit_error,
            ]
        )

    @property
    def total_errors(self) -> int:
        """Sum of all error counters for this port."""
        return (
            self.port_rx
            + self.bad_tlp
            + self.bad_dllp
            + self.rec_diag
            + self.link_down
            + self.flit_error
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "port_number": self.port_number,
            "port_rx": self.port_rx,
            "bad_tlp": self.bad_tlp,
            "bad_dllp": self.bad_dllp,
            "rec_diag": self.rec_diag,
            "link_down": self.link_down,
            "flit_error": self.flit_error,
            "has_errors": self.has_errors,
            "total_errors": self.total_errors,
        }

    def to_json(self, indent: Optional[int] = None) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)


@dataclass
class AllErrorCounters:
    """Error counters for all ports."""

    counters: List[ErrorCounters]

    @property
    def total_errors(self) -> int:
        """Sum of all error counters."""
        return sum(c.total_errors for c in self.counters)

    @property
    def ports_with_errors(self) -> List[ErrorCounters]:
        """Get list of ports that have errors."""
        return [c for c in self.counters if c.has_errors]

    def get_port(self, port_number: int) -> Optional[ErrorCounters]:
        """Get error counters for a specific port number."""
        for counter in self.counters:
            if counter.port_number == port_number:
                return counter
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "counters": [c.to_dict() for c in self.counters],
            "total_errors": self.total_errors,
            "port_count": len(self.counters),
        }

    def to_json(self, indent: Optional[int] = None) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    def to_dataframe(self) -> Any:
        """
        Convert to pandas DataFrame for data analysis.

        Returns:
            pandas.DataFrame with port error data

        Raises:
            ImportError: If pandas is not installed

        Example:
            >>> counters = card.get_error_counters()
            >>> df = counters.to_dataframe()
            >>> df[df['has_errors'] == True]  # Filter ports with errors
        """
        try:
            import pandas as pd  # type: ignore[import-untyped]
        except ImportError:
            raise ImportError(
                "pandas is required for to_dataframe(). Install with: pip install pandas"
            )

        return pd.DataFrame([c.to_dict() for c in self.counters])


@dataclass
class ClockStatus:
    """PCIe clock output status."""

    straddle_enabled: bool
    ext_mcio_enabled: bool
    int_mcio_enabled: bool


@dataclass
class SpreadStatus:
    """PCIe clock spread status."""

    enabled: bool
    mode: Optional[SpreadMode] = None


@dataclass
class FlitStatus:
    """Flit mode status for all stations."""

    station2: bool  # True = disabled, False = enabled
    station5: bool
    station7: bool
    station8: bool


@dataclass
class RegisterDump:
    """Register dump result."""

    start_address: int
    values: Dict[int, int]  # address -> value mapping


@dataclass
class FlashDump:
    """Flash memory dump result."""

    start_address: int
    values: Dict[int, int]  # address -> value mapping


@dataclass
class I2CReadResult:
    """I2C read operation result."""

    address: int
    connector: int
    channel: str
    data: List[int]


@dataclass
class I2CWriteResult:
    """I2C write operation result."""

    address: int
    connector: int
    channel: str
    data: List[int]
