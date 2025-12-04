# Serial Cables Atlas3 Python API

[![PyPI version](https://badge.fury.io/py/serialcables-atlas3.svg)](https://badge.fury.io/py/serialcables-atlas3)
[![Python versions](https://img.shields.io/pypi/pyversions/serialcables-atlas3.svg)](https://pypi.org/project/serialcables-atlas3/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Python library for controlling the Serial Cables Atlas3 PCIe Gen6 Host Adapter Card (PCI6-AD-x16HI-BG6-144).

## Features

- Full Python API for all CLI commands
- Type-safe with dataclasses and enums
- Context manager support for automatic connection handling
- Command-line interface included
- Comprehensive error handling
- PyPI installable

## Hardware

The Atlas3 Host Adapter Card features the **Broadcom PEX90144 PCIe Gen6 Switch** supporting:
- Up to 144 lanes and 72 ports
- Five 16-lane downstream stations
- PCIe Gen6 (64 GT/s) with FLIT mode
- Ultra low latency with FLIT & FEC
- Dynamic Port Reconfiguration (DPR)
- Hot-plug support

### Connectors

| Connector | Description | Ports |
|-----------|-------------|-------|
| CN1 | PCIe Straddle mount (x16) | Port 80 |
| CN2 | MCIO x8 (EXT upper) | Ports 120-127 |
| CN3 | MCIO x8 (EXT lower) | Ports 112-119 |
| CN4 | MCIO x8 (INT upper) | Ports 136-143 |
| CN5 | MCIO x8 (INT lower) | Ports 128-135 |
| CN6 | USB-C (SDB/SMART) | - |
| CN7 | USB-C (MCU CLI) | - |
| CN9 | 12V 2x6 Power | - |

## Installation

```bash
pip install serialcables-atlas3
```

Or install from source:

```bash
git clone https://github.com/serialcables/serialcables-atlas3.git
cd serialcables-atlas3
pip install -e .
```

## Quick Start

### Python API

```python
from serialcables_atlas3 import Atlas3

# Connect to the Atlas3 card
with Atlas3("/dev/ttyUSB0") as card:
    # Get version information
    info = card.get_version()
    print(f"Model: {info.model}")
    print(f"MCU Version: {info.mcu_version}")
    
    # Get host card status
    status = card.get_host_card_info()
    print(f"Temperature: {status.thermal.switch_temperature_celsius}°C")
    print(f"Power: {status.power.load_power}W")
    
    # Get port status
    ports = card.get_port_status()
    for port in ports.ext_mcio_ports:
        if port.is_linked:
            print(f"Port {port.port_number}: {port.speed} x{port.width}")
    
    # Run built-in self-test
    bist = card.run_bist()
    print(f"BIST: {'PASS' if bist.all_passed else 'FAIL'}")
```

### Command-Line Interface

```bash
# Show version information
atlas3-cli -p /dev/ttyUSB0 version

# Show host card status
atlas3-cli -p /dev/ttyUSB0 status

# Show port status
atlas3-cli -p /dev/ttyUSB0 ports

# Run BIST
atlas3-cli -p /dev/ttyUSB0 bist

# Set clock spread
atlas3-cli -p /dev/ttyUSB0 spread 1  # 2500PPM

# Reset a connector
atlas3-cli -p /dev/ttyUSB0 reset 0

# Output as JSON
atlas3-cli -p /dev/ttyUSB0 --json status
```

## API Reference

### Connection

```python
from serialcables_atlas3 import Atlas3

# Manual connection management
card = Atlas3("/dev/ttyUSB0", auto_connect=False)
card.connect()
# ... use the card ...
card.disconnect()

# Context manager (recommended)
with Atlas3("/dev/ttyUSB0") as card:
    # ... use the card ...
    pass  # Automatically disconnects

# Find available devices
devices = Atlas3.find_devices()
print(devices)  # ['/dev/ttyUSB0', '/dev/ttyUSB1']
```

### System Information

```python
# Get version info (ver command)
info = card.get_version()
print(info.company)       # "Serial Cables"
print(info.model)         # "PCI6-AD-x16HI-BG6-144"
print(info.mcu_version)   # "0.2.3"
print(info.sbr_version)   # "0032A022"

# Get host card info (lsd command)
status = card.get_host_card_info()
print(status.thermal.switch_temperature_celsius)  # 46.0
print(status.fan.switch_fan_rpm)                  # 6456
print(status.voltages.voltage_1v5)                # 1.499
print(status.power.load_power)                    # 126.251

# Get complete system info (sysinfo command)
sysinfo = card.get_system_info()
```

### Port Status

```python
# Get port status (showport command)
ports = card.get_port_status()
print(ports.chip_version)  # "A0"

for port in ports.ext_mcio_ports:
    print(f"Port {port.port_number}:")
    print(f"  Station: {port.station_name}")      # "Stn7", "Stn8"
    print(f"  Connector: {port.connector}")       # "Con00", "Con01"
    print(f"  Status: {port.status_str}")         # "Active", "Degraded", "Idle"
    print(f"  Linked: {port.is_linked}")          # True if width > 0
    if port.is_linked:
        print(f"  Speed: {port.speed}")           # "Gen4", "Gen5", "Gen6"
        print(f"  Width: x{port.width}")          # 4, 8, 16
    print(f"  Max: {port.max_speed_str}")         # "Gen6 x4", "Gen6 x16"

# Check for degraded links
degraded = [p for p in ports.ext_mcio_ports if p.is_degraded]

# Check for linked ports
linked = [p for p in ports.int_mcio_ports if p.is_linked]
```

### Error Counters

```python
# Get error counters (counters command)
counters = card.get_error_counters()
print(f"Total errors: {counters.total_errors}")

for c in counters.counters:
    if c.has_errors:
        print(f"Port {c.port_number}:")
        print(f"  Bad TLP: {c.bad_tlp}")
        print(f"  Bad DLLP: {c.bad_dllp}")
        print(f"  Flit Error: {c.flit_error}")

# Query specific port
port_32 = counters.get_port(32)
if port_32:
    print(f"Port 32 total errors: {port_32.total_errors}")

# Get only ports with errors
for port in counters.ports_with_errors:
    print(f"Port {port.port_number}: {port.total_errors} errors")

# Serialize to JSON
json_str = counters.to_json(indent=2)

# Convert to dictionary
data = counters.to_dict()

# Convert to pandas DataFrame (requires pandas)
df = counters.to_dataframe()
errors_df = df[df['has_errors'] == True]

# Clear error counters
card.clear_error_counters()
```

### Diagnostics

```python
# Run BIST (bist command)
result = card.run_bist()
print(f"All passed: {result.all_passed}")

for device in result.devices:
    print(f"{device.channel} {device.device_name}: {device.status}")
```

### Configuration

```python
from serialcables_atlas3 import OperationMode, SpreadMode

# Mode configuration (setmode/showmode commands)
current_mode = card.get_mode()
print(f"Current mode: {current_mode.value}")  # 1, 2, 3, or 4

card.set_mode(OperationMode.MODE_1)  # Common clock, precoding enabled
# Note: Requires controller reset to take effect

# Clock spread (spread command)
spread = card.get_spread_status()
print(f"Spread enabled: {spread.enabled}")

card.set_spread(SpreadMode.DOWN_2500PPM)  # -0.25% spread
card.set_spread("off")  # Disable spread

# Clock output (clk command)
clk = card.get_clock_status()
print(f"Straddle clock: {'enabled' if clk.straddle_enabled else 'disabled'}")

card.set_clock_output(True)   # Enable clock output
card.set_clock_output(False)  # Disable clock output

# Flit mode (flit command)
flit = card.get_flit_status()
print(f"Station 2 flit disable: {flit.station2}")

card.set_flit_mode("all", False)  # Enable flit on all stations
card.set_flit_mode(2, True)       # Disable flit on station 2

# SDB routing (sdb command)
card.set_sdb_target("usb")  # Route to USB for SwitchCLID/ARCTIC
card.set_sdb_target("mcu")  # Route to MCU for normal operation
```

### Reset Commands

```python
# Reset connector (conrst command)
card.reset_connector(0)      # Reset CON0 (EXT MCIO upper)
card.reset_connector("all")  # Reset all connectors

# Reset MCU (reset command)
card.reset_mcu()
```

### Register Access

```python
# Read registers (dr command)
dump = card.read_register(0x60800000, count=16)
for addr, value in sorted(dump.values.items()):
    print(f"0x{addr:08X}: 0x{value:08X}")

# Write register (mw command)
card.write_register(0xFFF0017C, 0xFFFFFFFF)

# Read port registers (dp command)
port_dump = card.read_port_registers(32)  # Golden finger port

# Read flash (df command)
flash = card.read_flash(0x400, count=16)
```

### I2C Access

```python
# Read from I2C device (iicwr command)
result = card.i2c_read(
    address=0xD4,
    connector=2,
    channel="a",
    read_bytes=8,
    register=0
)
print([hex(b) for b in result.data])

# Write to I2C device (iicw command)
card.i2c_write(
    address=0xD4,
    connector=2,
    channel="a",
    data=[0xFF]
)
```

## Connector and Port Mapping

| Station | Connector | Ports | Description |
|---------|-----------|-------|-------------|
| STN2 | - | 32 | Golden Finger (Upstream) |
| STN5 | CON4 | 80 | PCIe Straddle |
| STN7 | CON0 | 112-118 | EXT MCIO upper |
| STN7 | CON1 | 120-126 | EXT MCIO lower |
| STN8 | CON2 | 128-134 | INT MCIO upper |
| STN8 | CON3 | 136-142 | INT MCIO lower |

## LED Indicators

### Status LEDs

| LED | Color | Description |
|-----|-------|-------------|
| SLED1 | Red | System error |
| SLED2 | Green | Heartbeat (blinking = managed FW running) |
| SLED3 | Green | MCU status (blinking = MCU running) |

### Link Speed LEDs (Blue)

| Blink Rate | Speed |
|------------|-------|
| 0.25 Hz | Gen1 (2.5 GT/s) |
| 0.5 Hz | Gen2 (5.0 GT/s) |
| 1.0 Hz | Gen3 (8.0 GT/s) |
| 2.0 Hz | Gen4 (16.0 GT/s) |
| 4.0 Hz | Gen5 (32.0 GT/s) |
| Always on | Gen6 (64.0 GT/s) |

## Error Handling

```python
from serialcables_atlas3 import (
    Atlas3,
    Atlas3Error,
    ConnectionError,
    CommandError,
    TimeoutError,
    InvalidParameterError,
)

try:
    with Atlas3("/dev/ttyUSB0") as card:
        card.set_mode(5)  # Invalid mode
except InvalidParameterError as e:
    print(f"Invalid parameter: {e}")
except ConnectionError as e:
    print(f"Connection failed: {e}")
except TimeoutError as e:
    print(f"Command timed out: {e}")
except CommandError as e:
    print(f"Command failed: {e}")
except Atlas3Error as e:
    print(f"Atlas3 error: {e}")
```

## Development

```bash
# Clone the repository
git clone https://github.com/serialcables/serialcables-atlas3.git
cd serialcables-atlas3

# Install in development mode with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black src tests
isort src tests

# Type checking
mypy src

# Lint
ruff check src tests
```

## License

MIT License - see [LICENSE](LICENSE) for details.

## Support

- Website: https://serialcables.com
- Email: support@serialcables.com
- Address: 8811 American Way, Suite 110, Englewood, CO 80107

## Related Products

- **PCI6-AD-x16HI-BG6-144**: Gen6 x16 – 4, x8 MCIO Host Card w/ 1x16 Straddle Mount Connector (A0 144-lane Switch)8-bay E3 passive JBOF

