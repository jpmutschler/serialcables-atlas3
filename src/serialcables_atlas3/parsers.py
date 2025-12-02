"""Response parsers for Atlas3 CLI output."""

import re
from typing import Dict, List, Optional

from .exceptions import ParseError
from .models import (
    AllErrorCounters,
    BistResult,
    ClockStatus,
    ErrorCounters,
    FanInfo,
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
    SpreadMode,
    SpreadStatus,
    ThermalInfo,
    VersionInfo,
    VoltageInfo,
)

# Regex pattern to strip ANSI escape codes from terminal output
ANSI_ESCAPE_PATTERN = re.compile(r"\x1b\[[0-9;]*m")


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text."""
    return ANSI_ESCAPE_PATTERN.sub("", text)


def parse_version(response: str) -> VersionInfo:
    """Parse the 'ver' command response."""
    try:
        # Extract company
        company_match = re.search(r"Company\s*:\s*(.+)", response)
        company = company_match.group(1).strip() if company_match else "Unknown"

        # Extract model
        model_match = re.search(r"Model\s*:\s*(.+)", response)
        model = model_match.group(1).strip() if model_match else "Unknown"

        # Extract serial number
        serial_match = re.search(r"Serial No\.\s*:\s*(.+)", response)
        serial = serial_match.group(1).strip() if serial_match else None
        if serial == "":
            serial = None

        # Extract MCU version
        mcu_version_match = re.search(r"MCU Info.*?Version\s*:\s*([\d.]+)", response, re.DOTALL)
        mcu_version = mcu_version_match.group(1).strip() if mcu_version_match else "Unknown"

        # Extract MCU build time
        build_match = re.search(r"Build Time\s*:\s*(.+)", response)
        build_time = build_match.group(1).strip() if build_match else "Unknown"

        # Extract SBR version
        sbr_match = re.search(r"SBR Info.*?Version\s*:\s*([A-Fa-f0-9]+)", response, re.DOTALL)
        sbr_version = sbr_match.group(1).strip() if sbr_match else "Unknown"

        return VersionInfo(
            company=company,
            model=model,
            serial_number=serial,
            mcu_version=mcu_version,
            mcu_build_time=build_time,
            sbr_version=sbr_version,
        )
    except Exception as e:
        raise ParseError(response, f"Failed to parse version info: {e}")


def parse_lsd(response: str) -> HostCardInfo:
    """Parse the 'lsd' command response."""
    try:
        # Parse temperature
        temp_match = re.search(r"Switch Temperature\s*:\s*(\d+)", response)
        temp = float(temp_match.group(1)) if temp_match else 0.0
        thermal = ThermalInfo(switch_temperature_celsius=temp)

        # Parse fan speed
        fan_match = re.search(r"Switch Fan\s*:\s*(\d+)\s*RPM", response)
        fan_rpm = int(fan_match.group(1)) if fan_match else 0
        fan = FanInfo(switch_fan_rpm=fan_rpm)

        # Parse voltages
        v15_match = re.search(r"1\.5V\s+Voltage\s*:\s*([\d.]+)\s*V", response)
        vdd_match = re.search(r"VDD\s+Voltage\s*:\s*([\d.]+)\s*V", response)
        vdda_match = re.search(r"VDDA\s+Voltage\s*:\s*([\d.]+)\s*V", response)
        vdda12_match = re.search(r"VDDA12\s+Voltage\s*:\s*([\d.]+)\s*V", response)

        voltages = VoltageInfo(
            voltage_1v5=float(v15_match.group(1)) if v15_match else 0.0,
            voltage_vdd=float(vdd_match.group(1)) if vdd_match else 0.0,
            voltage_vdda=float(vdda_match.group(1)) if vdda_match else 0.0,
            voltage_vdda12=float(vdda12_match.group(1)) if vdda12_match else 0.0,
        )

        # Parse power consumption
        pv_match = re.search(r"Power Voltage\s*:\s*([\d.]+)\s*V", response)
        lc_match = re.search(r"Load Current\s*:\s*([\d.]+)\s*A", response)
        lp_match = re.search(r"Load Power\s*:\s*([\d.]+)\s*W", response)

        power = PowerInfo(
            power_voltage=float(pv_match.group(1)) if pv_match else 0.0,
            load_current=float(lc_match.group(1)) if lc_match else 0.0,
            load_power=float(lp_match.group(1)) if lp_match else 0.0,
        )

        return HostCardInfo(thermal=thermal, fan=fan, voltages=voltages, power=power)
    except Exception as e:
        raise ParseError(response, f"Failed to parse lsd response: {e}")


def _parse_port_line(line: str, port_type: PortType) -> Optional[PortInfo]:
    """Parse a single port line from showport output."""
    # Strip ANSI color codes from the line
    line = _strip_ansi(line)

    # Pattern for port lines like:
    # Stn7 | Con00 | Port 112 | Speed: Gen4 | Width: 4 | Max: Gen6 x4 | Status: Degraded
    # Stn2 | USP00 | Port 032 | Speed: Gen4 | Width: 4 | Max: Gen6 x16 | Status: Degraded
    pattern = r"Stn(\d+)\s*\|\s*(\w+)\s*\|\s*Port\s*(\d+)\s*\|\s*Speed:\s*(\w+)\s*\|\s*Width:\s*(\d+)\s*\|\s*Max:\s*(\w+)\s*x(\d+)\s*\|\s*Status:\s*(\w+)"

    match = re.search(pattern, line, re.IGNORECASE)
    if not match:
        return None

    station = int(match.group(1))
    connector = match.group(2)
    port_number = int(match.group(3))
    speed_str = match.group(4)
    width = int(match.group(5))
    max_speed_str = match.group(6)
    max_width = int(match.group(7))
    status_str = match.group(8)

    # Parse negotiated speed (Gen1 with width 0 means no link)
    try:
        neg_speed = LinkSpeed.from_string(speed_str) if width > 0 else None
    except ValueError:
        neg_speed = None

    try:
        max_speed = LinkSpeed.from_string(max_speed_str)
    except ValueError:
        max_speed = LinkSpeed.GEN6

    try:
        status = LinkStatus.from_string(status_str)
    except ValueError:
        status = LinkStatus.IDLE

    return PortInfo(
        station=station,
        connector=connector,
        port_number=port_number,
        negotiated_speed=neg_speed,
        negotiated_width=width,
        max_speed=max_speed,
        max_width=max_width,
        status=status,
        port_type=port_type,
    )


def parse_showport(response: str) -> PortStatus:
    """Parse the 'showport' command response."""
    try:
        # Extract chip version
        chip_match = re.search(r"Atlas3 chip ver:\s*(\w+)", response)
        chip_version = chip_match.group(1) if chip_match else "Unknown"

        upstream_ports: List[PortInfo] = []
        ext_mcio_ports: List[PortInfo] = []
        int_mcio_ports: List[PortInfo] = []
        straddle_ports: List[PortInfo] = []

        lines = response.split("\n")
        current_section = None

        for line in lines:
            line = line.strip()

            # Detect section headers
            if "Upstream Ports" in line:
                current_section = "upstream"
            elif "EXT MCIO Ports" in line:
                current_section = "ext_mcio"
            elif "INT MCIO Ports" in line:
                current_section = "int_mcio"
            elif "Straddle Ports" in line:
                current_section = "straddle"
            elif line.startswith("Stn"):
                # Parse port line based on current section
                if current_section == "upstream":
                    port = _parse_port_line(line, PortType.USP)
                    if port:
                        upstream_ports.append(port)
                elif current_section == "ext_mcio":
                    port = _parse_port_line(line, PortType.MCIO_EXT)
                    if port:
                        ext_mcio_ports.append(port)
                elif current_section == "int_mcio":
                    port = _parse_port_line(line, PortType.MCIO_INT)
                    if port:
                        int_mcio_ports.append(port)
                elif current_section == "straddle":
                    port = _parse_port_line(line, PortType.STRADDLE)
                    if port:
                        straddle_ports.append(port)

        return PortStatus(
            chip_version=chip_version,
            upstream_ports=upstream_ports,
            ext_mcio_ports=ext_mcio_ports,
            int_mcio_ports=int_mcio_ports,
            straddle_ports=straddle_ports,
        )
    except Exception as e:
        raise ParseError(response, f"Failed to parse showport response: {e}")


def parse_bist(response: str) -> BistResult:
    """Parse the 'bist' command response."""
    try:
        devices: List[I2CDevice] = []

        # Pattern: CH0    INA231    0x80    OK
        pattern = r"(CH\d+)\s+(\w+)\s+(0x[0-9A-Fa-f]+)\s+(\w+)"

        for match in re.finditer(pattern, response):
            channel = match.group(1)
            device_name = match.group(2)
            address = int(match.group(3), 16)
            status = match.group(4)

            devices.append(
                I2CDevice(
                    channel=channel,
                    device_name=device_name,
                    address=address,
                    status=status,
                )
            )

        return BistResult(devices=devices)
    except Exception as e:
        raise ParseError(response, f"Failed to parse bist response: {e}")


def parse_counters(response: str) -> AllErrorCounters:
    """Parse the 'counters' command response."""
    try:
        counters: List[ErrorCounters] = []

        # Pattern for counter lines
        # Port#    PortRx      BadTLP      BadDLLP     RecDiag     LinkDown    FlitError
        # 32       00000000    00000000    00000000    00000000    00000000    00000000
        pattern = r"^(\d+)\s+([0-9A-Fa-f]+)\s+([0-9A-Fa-f]+)\s+([0-9A-Fa-f]+)\s+([0-9A-Fa-f]+)\s+([0-9A-Fa-f]+)\s+([0-9A-Fa-f]+)"

        for line in response.split("\n"):
            match = re.match(pattern, line.strip())
            if match:
                counters.append(
                    ErrorCounters(
                        port_number=int(match.group(1)),
                        port_rx=int(match.group(2), 16),
                        bad_tlp=int(match.group(3), 16),
                        bad_dllp=int(match.group(4), 16),
                        rec_diag=int(match.group(5), 16),
                        link_down=int(match.group(6), 16),
                        flit_error=int(match.group(7), 16),
                    )
                )

        return AllErrorCounters(counters=counters)
    except Exception as e:
        raise ParseError(response, f"Failed to parse counters response: {e}")


def parse_showmode(response: str) -> OperationMode:
    """Parse the 'showmode' command response."""
    try:
        match = re.search(r"PCIe switch mode\s*(\d+)", response)
        if match:
            mode = int(match.group(1))
            return OperationMode(mode)
        raise ParseError(response, "Could not find mode in response")
    except ValueError as e:
        raise ParseError(response, f"Invalid mode value: {e}")


def parse_spread(response: str) -> SpreadStatus:
    """Parse the 'spread' command (status check) response."""
    try:
        if "OFF" in response.upper() or "off" in response.lower():
            return SpreadStatus(enabled=False, mode=SpreadMode.OFF)
        elif "2500PPM" in response:
            return SpreadStatus(enabled=True, mode=SpreadMode.DOWN_2500PPM)
        elif "5000PPM" in response:
            return SpreadStatus(enabled=True, mode=SpreadMode.DOWN_5000PPM)
        else:
            # Default to off if unclear
            return SpreadStatus(enabled=False, mode=None)
    except Exception as e:
        raise ParseError(response, f"Failed to parse spread response: {e}")


def parse_clk(response: str) -> ClockStatus:
    """Parse the 'clk' command response."""
    try:
        straddle = "Straddle" in response and "enable" in response.lower()
        ext_mcio = "EXT MCIO" in response and "enable" in response.lower()
        int_mcio = "INT MCIO" in response and "enable" in response.lower()

        # More careful parsing
        lines = response.split("\n")
        for line in lines:
            if "Straddle" in line:
                straddle = "enable" in line.lower() and "disable" not in line.lower()
            if "EXT MCIO" in line:
                ext_mcio = "enable" in line.lower() and "disable" not in line.lower()
            if "INT MCIO" in line:
                int_mcio = "enable" in line.lower() and "disable" not in line.lower()

        return ClockStatus(
            straddle_enabled=straddle,
            ext_mcio_enabled=ext_mcio,
            int_mcio_enabled=int_mcio,
        )
    except Exception as e:
        raise ParseError(response, f"Failed to parse clk response: {e}")


def parse_flit(response: str) -> FlitStatus:
    """Parse the 'flit' command response."""
    try:
        # Parse lines like "Station2 flit disable mode : off:" or "Station2 flit disable mode : on:"
        # The format has : value : with the value between two colons
        station2 = False
        station5 = False
        station7 = False
        station8 = False

        for line in response.split("\n"):
            line_lower = line.lower()
            # Check for pattern like "station2" ... ": on" or ": off"
            if "station2" in line_lower:
                # Look for ": on" pattern (with potential trailing colon)
                station2 = ": on" in line_lower
            elif "station5" in line_lower:
                station5 = ": on" in line_lower
            elif "station7" in line_lower:
                station7 = ": on" in line_lower
            elif "station8" in line_lower:
                station8 = ": on" in line_lower

        return FlitStatus(
            station2=station2,
            station5=station5,
            station7=station7,
            station8=station8,
        )
    except Exception as e:
        raise ParseError(response, f"Failed to parse flit response: {e}")


def parse_register_dump(response: str) -> RegisterDump:
    """Parse the 'dr' command response."""
    try:
        values: Dict[int, int] = {}
        start_address = 0

        # Pattern: 60800000:c0401000 00100000 060400a0 00010000
        pattern = r"([0-9A-Fa-f]+):([0-9A-Fa-f ]+)"

        first = True
        for match in re.finditer(pattern, response):
            addr = int(match.group(1), 16)
            if first:
                start_address = addr
                first = False

            value_strs = match.group(2).strip().split()
            for i, val in enumerate(value_strs):
                values[addr + (i * 4)] = int(val, 16)

        return RegisterDump(start_address=start_address, values=values)
    except Exception as e:
        raise ParseError(response, f"Failed to parse register dump: {e}")


def parse_flash_dump(response: str) -> FlashDump:
    """Parse the 'df' command response."""
    try:
        values: Dict[int, int] = {}
        start_address = 0

        # Pattern: 00000400:3ba240c0 b4000000 e00e0104 8afb000a
        pattern = r"([0-9A-Fa-f]+):([0-9A-Fa-f ]+)"

        first = True
        for match in re.finditer(pattern, response):
            addr = int(match.group(1), 16)
            if first:
                start_address = addr
                first = False

            value_strs = match.group(2).strip().split()
            for i, val in enumerate(value_strs):
                values[addr + (i * 4)] = int(val, 16)

        return FlashDump(start_address=start_address, values=values)
    except Exception as e:
        raise ParseError(response, f"Failed to parse flash dump: {e}")


def parse_iicwr(response: str, address: int, connector: int, channel: str) -> I2CReadResult:
    """Parse the 'iicwr' command response."""
    try:
        data: List[int] = []

        # Pattern: Data [0] = 6
        pattern = r"Data\s*\[(\d+)\]\s*=\s*([0-9A-Fa-f]+)"

        for match in re.finditer(pattern, response):
            # idx = int(match.group(1))
            value = int(match.group(2), 16)
            data.append(value)

        return I2CReadResult(
            address=address,
            connector=connector,
            channel=channel,
            data=data,
        )
    except Exception as e:
        raise ParseError(response, f"Failed to parse iicwr response: {e}")


def parse_iicw(
    response: str, address: int, connector: int, channel: str, write_data: List[int]
) -> I2CWriteResult:
    """Parse the 'iicw' command response."""
    try:
        # Verify success from response
        if "Write Data" in response or "success" in response.lower():
            return I2CWriteResult(
                address=address,
                connector=connector,
                channel=channel,
                data=write_data,
            )
        raise ParseError(response, "I2C write did not succeed")
    except Exception as e:
        raise ParseError(response, f"Failed to parse iicw response: {e}")


def parse_success(response: str, success_phrases: Optional[List[str]] = None) -> bool:
    """Check if a command response indicates success."""
    if success_phrases is None:
        success_phrases = ["success", "ok", "done"]

    response_lower = response.lower()
    return any(phrase in response_lower for phrase in success_phrases)
