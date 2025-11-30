#!/usr/bin/env python3
"""
Example script demonstrating the Serial Cables Atlas3 Python API.

This script shows various ways to interact with the Atlas3 Host Adapter Card.
"""

from serialcables_atlas3 import Atlas3, SpreadMode, OperationMode


def main():
    # Replace with your actual serial port
    PORT = "/dev/ttyUSB0"  # Linux
    # PORT = "COM3"  # Windows
    
    # Method 1: Using context manager (recommended)
    with Atlas3(PORT) as card:
        # Get and display version information
        print("=" * 60)
        print("Atlas3 Host Adapter Card Information")
        print("=" * 60)
        
        version = card.get_version()
        print(f"\nProduct Info:")
        print(f"  Company: {version.company}")
        print(f"  Model: {version.model}")
        print(f"  Serial: {version.serial_number or 'N/A'}")
        print(f"  MCU Version: {version.mcu_version}")
        print(f"  SBR Version: {version.sbr_version}")
        
        # Get host card status
        status = card.get_host_card_info()
        print(f"\nHost Card Status:")
        print(f"  Temperature: {status.thermal.switch_temperature_celsius}°C")
        print(f"  Fan Speed: {status.fan.switch_fan_rpm} RPM")
        print(f"  Power: {status.power.load_power:.2f}W @ {status.power.power_voltage:.2f}V")
        print(f"  Current: {status.power.load_current:.2f}A")
        
        print(f"\nVoltage Rails:")
        print(f"  1.5V: {status.voltages.voltage_1v5:.3f}V")
        print(f"  VDD: {status.voltages.voltage_vdd:.3f}V")
        print(f"  VDDA: {status.voltages.voltage_vdda:.3f}V")
        print(f"  VDDA12: {status.voltages.voltage_vdda12:.3f}V")
        
        # Get port status
        ports = card.get_port_status()
        print(f"\nPort Status (Chip: {ports.chip_version}):")
        
        print("\n  Upstream Ports:")
        for port in ports.upstream_ports:
            speed = port.negotiated_speed.value if port.negotiated_speed else "N/A"
            print(f"    Port {port.port_number}: {speed} x{port.negotiated_width} [{port.status.value}]")
        
        print("\n  External MCIO Ports:")
        for port in ports.ext_mcio_ports:
            if port.is_linked:
                speed = port.negotiated_speed.value
                print(f"    Port {port.port_number}: {speed} x{port.negotiated_width} [{port.status.value}]")
            else:
                print(f"    Port {port.port_number}: [Idle]")
        
        print("\n  Internal MCIO Ports:")
        for port in ports.int_mcio_ports:
            if port.is_linked:
                speed = port.negotiated_speed.value
                print(f"    Port {port.port_number}: {speed} x{port.negotiated_width} [{port.status.value}]")
            else:
                print(f"    Port {port.port_number}: [Idle]")
        
        print("\n  Straddle Ports:")
        for port in ports.straddle_ports:
            if port.is_linked:
                speed = port.negotiated_speed.value
                print(f"    Port {port.port_number}: {speed} x{port.negotiated_width} [{port.status.value}]")
            else:
                print(f"    Port {port.port_number}: [Idle]")
        
        # Run BIST
        print("\nBuilt-In Self Test:")
        bist = card.run_bist()
        for device in bist.devices:
            status_str = "✓" if device.is_ok else "✗"
            print(f"  {status_str} {device.device_name} @ {device.channel} (0x{device.address:02X})")
        print(f"\n  Overall: {'PASS' if bist.all_passed else 'FAIL'}")
        
        # Check error counters
        counters = card.get_error_counters()
        if counters.total_errors > 0:
            print(f"\n⚠️  Warning: {counters.total_errors} total errors detected!")
            for c in counters.counters:
                if c.has_errors:
                    print(f"    Port {c.port_number}: "
                          f"TLP={c.bad_tlp}, DLLP={c.bad_dllp}, Flit={c.flit_error}")
        else:
            print("\n  No errors detected")
        
        # Get configuration
        mode = card.get_mode()
        print(f"\nConfiguration:")
        print(f"  Operation Mode: {mode.value}")
        
        spread = card.get_spread_status()
        print(f"  Clock Spread: {'Enabled' if spread.enabled else 'Disabled'}")
        
        clk = card.get_clock_status()
        print(f"  Clock Output:")
        print(f"    Straddle: {'Enabled' if clk.straddle_enabled else 'Disabled'}")
        print(f"    EXT MCIO: {'Enabled' if clk.ext_mcio_enabled else 'Disabled'}")
        print(f"    INT MCIO: {'Enabled' if clk.int_mcio_enabled else 'Disabled'}")
        
        flit = card.get_flit_status()
        print(f"  Flit Mode Disabled:")
        print(f"    Station 2: {'Yes' if flit.station2 else 'No'}")
        print(f"    Station 5: {'Yes' if flit.station5 else 'No'}")
        print(f"    Station 7: {'Yes' if flit.station7 else 'No'}")
        print(f"    Station 8: {'Yes' if flit.station8 else 'No'}")


def example_configuration():
    """Example showing how to configure the card."""
    PORT = "/dev/ttyUSB0"
    
    with Atlas3(PORT) as card:
        # Set operation mode (requires reset to take effect)
        # Mode 1: Common clock, precoding enabled
        card.set_mode(OperationMode.MODE_1)
        
        # Configure clock spread
        # Options: SpreadMode.OFF, SpreadMode.DOWN_2500PPM, SpreadMode.DOWN_5000PPM
        card.set_spread(SpreadMode.OFF)
        
        # Enable clock output to connectors
        card.set_clock_output(True)
        
        # Enable flit mode on all stations (required for Gen6)
        card.set_flit_mode("all", disable=False)
        
        # Reset a specific connector
        card.reset_connector(0)  # Reset CON0
        
        print("Configuration complete!")


def example_register_access():
    """Example showing low-level register access."""
    PORT = "/dev/ttyUSB0"
    
    with Atlas3(PORT) as card:
        # Read registers from Port 32 (golden finger)
        dump = card.read_port_registers(32)
        print("Port 32 registers:")
        for addr, value in sorted(dump.values.items())[:10]:
            print(f"  0x{addr:08X}: 0x{value:08X}")
        
        # Read flash memory
        flash = card.read_flash(0x400, count=4)
        print("\nFlash @ 0x400:")
        for addr, value in sorted(flash.values.items()):
            print(f"  0x{addr:08X}: 0x{value:08X}")


def example_i2c_access():
    """Example showing I2C device access."""
    PORT = "/dev/ttyUSB0"
    
    with Atlas3(PORT) as card:
        # Read 8 bytes from I2C device at address 0xD4 on CON2, channel A
        result = card.i2c_read(
            address=0xD4,
            connector=2,
            channel="a",
            read_bytes=8,
            register=0
        )
        print(f"I2C read from 0xD4: {[hex(b) for b in result.data]}")
        
        # Write to I2C device
        # card.i2c_write(address=0xD4, connector=2, channel="a", data=[0xFF])


if __name__ == "__main__":
    # Run the main example
    main()
    
    # Uncomment to run other examples:
    # example_configuration()
    # example_register_access()
    # example_i2c_access()
