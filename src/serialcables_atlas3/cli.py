#!/usr/bin/env python3
"""Command-line interface for Atlas3 Host Adapter Card."""

import argparse
import json
import sys
from typing import Any, Dict, List, Optional

from . import Atlas3, __version__
from .exceptions import Atlas3Error
from .models import PortInfo


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        prog="atlas3-cli",
        description="Serial Cables Atlas3 PCIe Gen6 Host Adapter Card CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  atlas3-cli -p /dev/ttyUSB0 version
  atlas3-cli -p COM3 status
  atlas3-cli -p /dev/ttyUSB0 ports
  atlas3-cli -p /dev/ttyUSB0 bist
  atlas3-cli -p /dev/ttyUSB0 spread off
  atlas3-cli -p /dev/ttyUSB0 reset 0
        """,
    )

    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "-p",
        "--port",
        required=True,
        help="Serial port (e.g., /dev/ttyUSB0 or COM3)",
    )
    parser.add_argument(
        "-b",
        "--baudrate",
        type=int,
        default=115200,
        help="Serial baudrate (default: 115200)",
    )
    parser.add_argument(
        "-t",
        "--timeout",
        type=float,
        default=5.0,
        help="Command timeout in seconds (default: 5.0)",
    )
    parser.add_argument(
        "-j",
        "--json",
        action="store_true",
        help="Output in JSON format",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Find devices
    subparsers.add_parser("find", help="Find available Atlas3 devices")

    # Version info
    subparsers.add_parser("version", help="Show version and product information")

    # Status (lsd)
    subparsers.add_parser("status", help="Show host card status (temperature, voltages, power)")

    # System info
    subparsers.add_parser("sysinfo", help="Show complete system information")

    # Port status
    subparsers.add_parser("ports", help="Show port link status")

    # Error counters
    counters_parser = subparsers.add_parser("counters", help="Show or clear error counters")
    counters_parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear all error counters",
    )

    # BIST
    subparsers.add_parser("bist", help="Run built-in self-test")

    # Mode
    mode_parser = subparsers.add_parser("mode", help="Get or set operation mode")
    mode_parser.add_argument(
        "value",
        nargs="?",
        type=int,
        choices=[1, 2, 3, 4],
        help="Mode to set (1-4)",
    )

    # Spread
    spread_parser = subparsers.add_parser("spread", help="Get or set clock spread")
    spread_parser.add_argument(
        "value",
        nargs="?",
        choices=["1", "2", "off"],
        help="Spread mode: 1 (2500PPM), 2 (5000PPM), or off",
    )

    # Clock
    clk_parser = subparsers.add_parser("clock", help="Get or set clock output")
    clk_parser.add_argument(
        "value",
        nargs="?",
        choices=["enable", "disable", "en", "dis"],
        help="Enable or disable clock output",
    )

    # Flit
    flit_parser = subparsers.add_parser("flit", help="Get or set flit mode")
    flit_parser.add_argument(
        "station",
        nargs="?",
        help="Station (2, 5, 7, 8, or all)",
    )
    flit_parser.add_argument(
        "state",
        nargs="?",
        choices=["on", "off"],
        help="Flit disable mode: on (disable) or off (enable)",
    )

    # SDB
    sdb_parser = subparsers.add_parser("sdb", help="Get or set SDB UART routing")
    sdb_parser.add_argument(
        "target",
        nargs="?",
        choices=["usb", "mcu"],
        help="SDB target: usb or mcu",
    )

    # Reset connector
    reset_parser = subparsers.add_parser("reset", help="Send PERST# to connector")
    reset_parser.add_argument(
        "connector",
        help="Connector (0-4 or all)",
    )

    # MCU reset
    subparsers.add_parser("mcu-reset", help="Reset the on-board MCU")

    # Register read
    reg_parser = subparsers.add_parser("reg-read", help="Read switch registers")
    reg_parser.add_argument(
        "address",
        help="Register address (hex)",
    )
    reg_parser.add_argument(
        "-c",
        "--count",
        type=int,
        default=16,
        help="Number of values to read",
    )

    # Register write
    regw_parser = subparsers.add_parser("reg-write", help="Write switch register")
    regw_parser.add_argument(
        "address",
        help="Register address (hex)",
    )
    regw_parser.add_argument(
        "data",
        help="Data to write (hex)",
    )

    # Port register read
    portreg_parser = subparsers.add_parser("port-reg", help="Read port registers")
    portreg_parser.add_argument(
        "port",
        type=int,
        help="Port number (0-143)",
    )

    # Flash read
    flash_parser = subparsers.add_parser("flash-read", help="Read flash memory")
    flash_parser.add_argument(
        "address",
        help="Flash address (hex)",
    )
    flash_parser.add_argument(
        "-c",
        "--count",
        type=int,
        default=16,
        help="Number of values to read",
    )

    # I2C read
    i2cr_parser = subparsers.add_parser("i2c-read", help="Read from I2C device")
    i2cr_parser.add_argument("address", help="Device address (hex)")
    i2cr_parser.add_argument("connector", type=int, help="Connector (0-4)")
    i2cr_parser.add_argument("channel", choices=["a", "b"], help="Channel (a or b)")
    i2cr_parser.add_argument("bytes", type=int, help="Bytes to read (1-128)")
    i2cr_parser.add_argument("-r", "--register", default="0", help="Register offset (hex)")

    # I2C write
    i2cw_parser = subparsers.add_parser("i2c-write", help="Write to I2C device")
    i2cw_parser.add_argument("address", help="Device address (hex)")
    i2cw_parser.add_argument("connector", type=int, help="Connector (0-4)")
    i2cw_parser.add_argument("channel", choices=["a", "b"], help="Channel (a or b)")
    i2cw_parser.add_argument("data", nargs="+", help="Data bytes (hex)")

    return parser


def format_output(data: Dict[str, Any], as_json: bool) -> str:
    """Format output data."""
    if as_json:
        return json.dumps(data, indent=2, default=str)

    lines = []
    for key, value in data.items():
        if isinstance(value, dict):
            lines.append(f"{key}:")
            for k, v in value.items():
                lines.append(f"  {k}: {v}")
        elif isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                if isinstance(item, dict):
                    lines.append("  -")
                    for k, v in item.items():
                        lines.append(f"    {k}: {v}")
                else:
                    lines.append(f"  - {item}")
        else:
            lines.append(f"{key}: {value}")
    return "\n".join(lines)


def cmd_find(args: argparse.Namespace) -> int:
    """Handle find command."""
    devices = Atlas3.find_devices()
    if args.json:
        print(json.dumps({"devices": devices}))
    else:
        if devices:
            print("Found potential Atlas3 devices:")
            for dev in devices:
                print(f"  {dev}")
        else:
            print("No devices found")
    return 0


def cmd_version(card: Atlas3, args: argparse.Namespace) -> int:
    """Handle version command."""
    info = card.get_version()
    data = {
        "company": info.company,
        "model": info.model,
        "serial_number": info.serial_number,
        "mcu_version": info.mcu_version,
        "mcu_build_time": info.mcu_build_time,
        "sbr_version": info.sbr_version,
    }
    print(format_output(data, args.json))
    return 0


def cmd_status(card: Atlas3, args: argparse.Namespace) -> int:
    """Handle status command."""
    info = card.get_host_card_info()
    data = {
        "thermal": {
            "switch_temperature_celsius": info.thermal.switch_temperature_celsius,
        },
        "fan": {
            "switch_fan_rpm": info.fan.switch_fan_rpm,
        },
        "voltages": {
            "1.5V": f"{info.voltages.voltage_1v5}V",
            "VDD": f"{info.voltages.voltage_vdd}V",
            "VDDA": f"{info.voltages.voltage_vdda}V",
            "VDDA12": f"{info.voltages.voltage_vdda12}V",
        },
        "power": {
            "voltage": f"{info.power.power_voltage}V",
            "current": f"{info.power.load_current}A",
            "power": f"{info.power.load_power}W",
        },
    }
    print(format_output(data, args.json))
    return 0


def cmd_ports(card: Atlas3, args: argparse.Namespace) -> int:
    """Handle ports command."""
    status = card.get_port_status()

    def port_to_dict(port: PortInfo) -> Dict[str, Any]:
        return {
            "station": port.station,
            "port": port.port_number,
            "speed": port.negotiated_speed.value if port.negotiated_speed else "N/A",
            "width": port.negotiated_width,
            "max_speed": port.max_speed.value,
            "max_width": port.max_width,
            "status": port.status.value,
        }

    data = {
        "chip_version": status.chip_version,
        "upstream_ports": [port_to_dict(p) for p in status.upstream_ports],
        "ext_mcio_ports": [port_to_dict(p) for p in status.ext_mcio_ports],
        "int_mcio_ports": [port_to_dict(p) for p in status.int_mcio_ports],
        "straddle_ports": [port_to_dict(p) for p in status.straddle_ports],
    }
    print(format_output(data, args.json))
    return 0


def cmd_bist(card: Atlas3, args: argparse.Namespace) -> int:
    """Handle bist command."""
    result = card.run_bist()
    data = {
        "all_passed": result.all_passed,
        "devices": [
            {
                "channel": d.channel,
                "device": d.device_name,
                "address": hex(d.address),
                "status": d.status,
            }
            for d in result.devices
        ],
    }
    print(format_output(data, args.json))
    return 0 if result.all_passed else 1


def main(args: Optional[List[str]] = None) -> int:
    """Main entry point."""
    parser = create_parser()
    parsed = parser.parse_args(args)

    if not parsed.command:
        parser.print_help()
        return 1

    # Handle find command specially (doesn't need connection)
    if parsed.command == "find":
        return cmd_find(parsed)

    try:
        with Atlas3(parsed.port, parsed.baudrate, parsed.timeout) as card:
            if parsed.command == "version":
                return cmd_version(card, parsed)
            elif parsed.command == "status":
                return cmd_status(card, parsed)
            elif parsed.command == "sysinfo":
                print(card.get_system_info())
                return 0
            elif parsed.command == "ports":
                return cmd_ports(card, parsed)
            elif parsed.command == "counters":
                if parsed.clear:
                    success = card.clear_error_counters()
                    print("Counters cleared" if success else "Failed to clear counters")
                    return 0 if success else 1
                else:
                    counters = card.get_error_counters()
                    data = {
                        "total_errors": counters.total_errors,
                        "ports": [
                            {
                                "port": c.port_number,
                                "errors": c.has_errors,
                                "flit_error": c.flit_error,
                            }
                            for c in counters.counters
                        ],
                    }
                    print(format_output(data, parsed.json))
                    return 0
            elif parsed.command == "bist":
                return cmd_bist(card, parsed)
            elif parsed.command == "mode":
                if parsed.value:
                    success = card.set_mode(parsed.value)
                    print(f"Mode set to {parsed.value}" if success else "Failed")
                    print("Note: Reset controller to take effect")
                    return 0 if success else 1
                else:
                    mode = card.get_mode()
                    print(f"Current mode: {mode.value}")
                    return 0
            elif parsed.command == "spread":
                if parsed.value:
                    success = card.set_spread(parsed.value)
                    print(f"Spread set to {parsed.value}" if success else "Failed")
                    return 0 if success else 1
                else:
                    status = card.get_spread_status()
                    print(f"Spread: {'ON' if status.enabled else 'OFF'}")
                    if status.mode:
                        print(f"Mode: {status.mode.value}")
                    return 0
            elif parsed.command == "clock":
                if parsed.value:
                    enable = parsed.value in ["enable", "en"]
                    success = card.set_clock_output(enable)
                    print(
                        f"Clock output {'enabled' if enable else 'disabled'}"
                        if success
                        else "Failed"
                    )
                    return 0 if success else 1
                else:
                    clock_status = card.get_clock_status()
                    print(f"Straddle: {'enabled' if clock_status.straddle_enabled else 'disabled'}")
                    print(f"EXT MCIO: {'enabled' if clock_status.ext_mcio_enabled else 'disabled'}")
                    print(f"INT MCIO: {'enabled' if clock_status.int_mcio_enabled else 'disabled'}")
                    return 0
            elif parsed.command == "flit":
                if parsed.station and parsed.state:
                    station = parsed.station
                    if station.isdigit():
                        station = int(station)
                    disable = parsed.state == "on"
                    success = card.set_flit_mode(station, disable)
                    print("Flit mode set" if success else "Failed")
                    return 0 if success else 1
                else:
                    flit_status = card.get_flit_status()
                    print(f"Station 2 flit disable: {'on' if flit_status.station2 else 'off'}")
                    print(f"Station 5 flit disable: {'on' if flit_status.station5 else 'off'}")
                    print(f"Station 7 flit disable: {'on' if flit_status.station7 else 'off'}")
                    print(f"Station 8 flit disable: {'on' if flit_status.station8 else 'off'}")
                    return 0
            elif parsed.command == "sdb":
                if parsed.target:
                    success = card.set_sdb_target(parsed.target)
                    print(f"SDB set to {parsed.target}" if success else "Failed")
                    return 0 if success else 1
                else:
                    target = card.get_sdb_target()
                    print(f"SDB target: {target}")
                    return 0
            elif parsed.command == "reset":
                con = parsed.connector
                if con.isdigit():
                    con = int(con)
                success = card.reset_connector(con)
                print(f"Reset sent to connector {con}" if success else "Failed")
                return 0 if success else 1
            elif parsed.command == "mcu-reset":
                success = card.reset_mcu()
                print("MCU reset" if success else "Failed")
                return 0 if success else 1
            elif parsed.command == "reg-read":
                addr = int(parsed.address, 16)
                dump = card.read_register(addr, parsed.count)
                for addr, val in sorted(dump.values.items()):
                    print(f"{addr:08x}: {val:08x}")
                return 0
            elif parsed.command == "reg-write":
                addr = int(parsed.address, 16)
                reg_data = int(parsed.data, 16)
                success = card.write_register(addr, reg_data)
                print("Written" if success else "Failed")
                return 0 if success else 1
            elif parsed.command == "port-reg":
                dump = card.read_port_registers(parsed.port)
                for addr, val in sorted(dump.values.items()):
                    print(f"{addr:08x}: {val:08x}")
                return 0
            elif parsed.command == "flash-read":
                addr = int(parsed.address, 16)
                flash_dump = card.read_flash(addr, parsed.count)
                for addr, val in sorted(flash_dump.values.items()):
                    print(f"{addr:08x}: {val:08x}")
                return 0
            elif parsed.command == "i2c-read":
                addr = int(parsed.address, 16)
                reg = int(parsed.register, 16)
                read_result = card.i2c_read(
                    addr, parsed.connector, parsed.channel, parsed.bytes, reg
                )
                print(f"Data: {' '.join(f'{b:02x}' for b in read_result.data)}")
                return 0
            elif parsed.command == "i2c-write":
                addr = int(parsed.address, 16)
                write_data = [int(b, 16) for b in parsed.data]
                card.i2c_write(addr, parsed.connector, parsed.channel, write_data)
                print("Written successfully")
                return 0
            else:
                parser.print_help()
                return 1

    except Atlas3Error as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
