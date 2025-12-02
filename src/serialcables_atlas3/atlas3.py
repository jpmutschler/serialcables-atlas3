"""Main Atlas3 Host Adapter Card API."""

import time
from typing import Callable, List, Optional, Union

import serial
from serial.tools import list_ports

from .exceptions import ConnectionError, InvalidParameterError, TimeoutError
from .models import (
    AllErrorCounters,
    BistResult,
    ClockStatus,
    FirmwareType,
    FlashDump,
    FlitStatus,
    HostCardInfo,
    I2CReadResult,
    I2CWriteResult,
    OperationMode,
    PortStatus,
    RegisterDump,
    SdbTarget,
    SpreadMode,
    SpreadStatus,
    VersionInfo,
)
from .parsers import (
    parse_bist,
    parse_clk,
    parse_counters,
    parse_flash_dump,
    parse_flit,
    parse_iicw,
    parse_iicwr,
    parse_lsd,
    parse_register_dump,
    parse_showmode,
    parse_showport,
    parse_spread,
    parse_success,
    parse_version,
)


class Atlas3:
    """
    Python API for Serial Cables Atlas3 PCIe Gen6 Host Adapter Card.

    This class provides a high-level interface to communicate with the Atlas3
    host adapter card via its USB-C serial interface (CN7).

    Example:
        >>> from serialcables_atlas3 import Atlas3
        >>> with Atlas3("/dev/ttyUSB0") as card:
        ...     info = card.get_version()
        ...     print(f"Model: {info.model}")
        ...     status = card.get_host_card_info()
        ...     print(f"Temperature: {status.thermal.switch_temperature_celsius}°C")

    Attributes:
        port: Serial port path (e.g., "/dev/ttyUSB0" or "COM3")
        baudrate: Serial baudrate (default: 115200)
        timeout: Command timeout in seconds (default: 5.0)
    """

    DEFAULT_BAUDRATE = 115200
    DEFAULT_TIMEOUT = 5.0
    PROMPT = "Cmd>"
    NEWLINE = "\r\n"

    def __init__(
        self,
        port: str,
        baudrate: int = DEFAULT_BAUDRATE,
        timeout: float = DEFAULT_TIMEOUT,
        auto_connect: bool = True,
    ):
        """
        Initialize Atlas3 connection.

        Args:
            port: Serial port path (e.g., "/dev/ttyUSB0" or "COM3")
            baudrate: Serial baudrate (default: 115200)
            timeout: Command timeout in seconds (default: 5.0)
            auto_connect: Automatically connect on initialization (default: True)
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self._serial: Optional[serial.Serial] = None

        if auto_connect:
            self.connect()

    def __enter__(self) -> "Atlas3":
        """Context manager entry."""
        if not self.is_connected:
            self.connect()
        return self

    def __exit__(self, exc_type: type, exc_val: Exception, exc_tb: object) -> None:
        """Context manager exit."""
        self.disconnect()

    @property
    def is_connected(self) -> bool:
        """Check if connected to the device."""
        return self._serial is not None and self._serial.is_open

    def connect(self) -> None:
        """
        Connect to the Atlas3 device.

        Raises:
            ConnectionError: If connection fails
        """
        try:
            self._serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=0.1,  # Short timeout for responsive reading
                write_timeout=self.timeout,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
            )
            # Clear any pending data
            self._serial.reset_input_buffer()
            self._serial.reset_output_buffer()
            # Send a newline to get a prompt and wait for it
            self._serial.write(b"\r\n")
            self._serial.flush()
            self._wait_for_prompt(self.timeout)
            self._serial.reset_input_buffer()
        except serial.SerialException as e:
            raise ConnectionError(self.port, str(e))

    def disconnect(self) -> None:
        """Disconnect from the Atlas3 device."""
        if self._serial and self._serial.is_open:
            self._serial.close()
        self._serial = None

    def _wait_for_prompt(self, timeout: float) -> str:
        """
        Wait for the command prompt to appear.

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            Data received up to and including the prompt

        Raises:
            TimeoutError: If prompt not received within timeout
        """
        if self._serial is None:
            raise ConnectionError(self.port, "Not connected to device")

        buffer = b""
        start_time = time.time()

        while True:
            elapsed = time.time() - start_time
            if elapsed > timeout:
                raise TimeoutError("wait_for_prompt", timeout)

            # Read available data (non-blocking due to short serial timeout)
            chunk = self._serial.read(self._serial.in_waiting or 1)
            if chunk:
                buffer += chunk
                # Check if prompt is in buffer
                if self.PROMPT.encode("utf-8") in buffer:
                    break

        return buffer.decode("utf-8", errors="replace")

    def _send_command(
        self,
        command: str,
        timeout: Optional[float] = None,
        wait_for_prompt: bool = True,
    ) -> str:
        """
        Send a command and return the response.

        Args:
            command: Command string to send
            timeout: Override default timeout
            wait_for_prompt: Wait for command prompt in response

        Returns:
            Command response string

        Raises:
            ConnectionError: If not connected
            TimeoutError: If command times out
            CommandError: If command fails
        """
        if not self.is_connected or self._serial is None:
            raise ConnectionError(self.port, "Not connected to device")

        timeout = timeout or self.timeout

        # Clear buffers
        self._serial.reset_input_buffer()

        # Send command
        cmd_bytes = (command + self.NEWLINE).encode("utf-8")
        self._serial.write(cmd_bytes)
        self._serial.flush()

        if wait_for_prompt:
            # Wait for prompt using efficient buffer-based approach
            response = self._wait_for_prompt(timeout)
        else:
            # Read for a fixed time if not waiting for prompt
            start_time = time.time()
            buffer = b""
            while time.time() - start_time < timeout:
                chunk = self._serial.read(self._serial.in_waiting or 1)
                if chunk:
                    buffer += chunk
            response = buffer.decode("utf-8", errors="replace")

        # Clean up response - split into lines and rejoin
        lines = [line.strip() for line in response.splitlines() if line.strip()]
        return "\n".join(lines)

    @staticmethod
    def find_devices() -> List[str]:
        """
        Find available Atlas3 devices.

        Returns:
            List of serial port paths that may be Atlas3 devices
        """
        ports = []
        for port in list_ports.comports():
            # Look for typical USB serial adapters
            if "USB" in port.description.upper() or "SERIAL" in port.description.upper():
                ports.append(port.device)
        return ports

    # =========================================================================
    # Version and System Information Commands
    # =========================================================================

    def get_version(self) -> VersionInfo:
        """
        Get version and product information (ver command).

        Returns:
            VersionInfo with company, model, serial, and firmware versions

        Example:
            >>> info = card.get_version()
            >>> print(f"Model: {info.model}, MCU: {info.mcu_version}")
        """
        response = self._send_command("ver")
        return parse_version(response)

    def get_host_card_info(self) -> HostCardInfo:
        """
        Get host card status including temperature, voltages, and power (lsd command).

        Returns:
            HostCardInfo with thermal, fan, voltage, and power readings

        Example:
            >>> info = card.get_host_card_info()
            >>> print(f"Temp: {info.thermal.switch_temperature_celsius}°C")
            >>> print(f"Power: {info.power.load_power}W")
        """
        response = self._send_command("lsd")
        return parse_lsd(response)

    def get_system_info(self) -> str:
        """
        Get complete system information (sysinfo command).

        This is equivalent to running ver, lsd, spread, clk, showport, and bist.

        Returns:
            Complete system information as raw string
        """
        response = self._send_command("sysinfo", timeout=30.0)
        return response

    # =========================================================================
    # Port Status Commands
    # =========================================================================

    def get_port_status(self) -> PortStatus:
        """
        Get link status for all ports (showport command).

        Returns:
            PortStatus with information about all upstream, MCIO, and straddle ports

        Example:
            >>> status = card.get_port_status()
            >>> for port in status.ext_mcio_ports:
            ...     if port.is_linked:
            ...         print(f"Port {port.port_number}: {port.negotiated_speed.value}")
        """
        response = self._send_command("showport")
        return parse_showport(response)

    def get_error_counters(self) -> AllErrorCounters:
        """
        Get error counters for all ports (counters command).

        Returns:
            AllErrorCounters with per-port error statistics

        Example:
            >>> counters = card.get_error_counters()
            >>> if counters.total_errors > 0:
            ...     print("Errors detected!")
        """
        response = self._send_command("counters")
        return parse_counters(response)

    def clear_error_counters(self) -> bool:
        """
        Clear all error counters (counters clear command).

        Returns:
            True if successful
        """
        response = self._send_command("counters clear")
        return parse_success(response, ["success", "cleared"])

    # =========================================================================
    # Diagnostics Commands
    # =========================================================================

    def run_bist(self) -> BistResult:
        """
        Run built-in self-test for on-board devices (bist command).

        Tests communication with I2C devices including current shunt, EEPROM,
        IO expander, I2C Mux, hot-swap controller, and clock buffer.

        Returns:
            BistResult with status of all tested devices

        Example:
            >>> result = card.run_bist()
            >>> if result.all_passed:
            ...     print("All devices OK")
        """
        response = self._send_command("bist")
        return parse_bist(response)

    # =========================================================================
    # Mode and Configuration Commands
    # =========================================================================

    def get_mode(self) -> OperationMode:
        """
        Get current operation mode (showmode command).

        Returns:
            OperationMode enum indicating current mode (1-4)

        Modes:
            - MODE_1: Common clock, precoding enabled
            - MODE_2: Common clock, precoding disabled
            - MODE_3: SRNS, precoding enabled
            - MODE_4: SRNS, precoding disabled
        """
        response = self._send_command("showmode")
        return parse_showmode(response)

    def set_mode(self, mode: Union[OperationMode, int]) -> bool:
        """
        Set operation mode (setmode command).

        Note: Requires controller reset to take effect.

        Args:
            mode: OperationMode enum or integer 1-4

        Returns:
            True if successful

        Raises:
            InvalidParameterError: If mode is invalid
        """
        if isinstance(mode, OperationMode):
            mode_num = mode.value
        else:
            mode_num = mode

        if mode_num not in [1, 2, 3, 4]:
            raise InvalidParameterError("mode", str(mode_num), "1, 2, 3, or 4")

        response = self._send_command(f"setmode {mode_num}")
        return parse_success(response, ["success", "set operation mode"])

    def get_spread_status(self) -> SpreadStatus:
        """
        Get PCIe clock spread status (spread command without args).

        Returns:
            SpreadStatus indicating if SSC is enabled and mode
        """
        response = self._send_command("spread")
        return parse_spread(response)

    def set_spread(self, mode: Union[SpreadMode, str]) -> bool:
        """
        Set PCIe clock spread (spread command).

        Args:
            mode: SpreadMode enum or string ("1", "2", or "off")
                - "1" or DOWN_2500PPM: -0.25% spread (2500 PPM)
                - "2" or DOWN_5000PPM: -0.5% spread (5000 PPM)
                - "off" or OFF: No spread (CFC)

        Returns:
            True if successful

        Example:
            >>> card.set_spread(SpreadMode.DOWN_2500PPM)
            >>> card.set_spread("off")
        """
        if isinstance(mode, SpreadMode):
            mode_str = mode.value
        else:
            mode_str = mode

        if mode_str not in ["1", "2", "off"]:
            raise InvalidParameterError("mode", mode_str, "1, 2, or off")

        response = self._send_command(f"spread {mode_str}")
        return parse_success(response)

    def get_clock_status(self) -> ClockStatus:
        """
        Get PCIe clock output status (clk command without args).

        Returns:
            ClockStatus with enabled/disabled state for each connector
        """
        response = self._send_command("clk")
        return parse_clk(response)

    def set_clock_output(self, enable: bool) -> bool:
        """
        Enable or disable PCIe clock output to MCIO and straddle connectors (clk command).

        Note: The PCIe reference clock to Atlas3 switch is always enabled.
        This setting is stored and persists across power cycles.

        Args:
            enable: True to enable clock output, False to disable

        Returns:
            True if successful
        """
        cmd = "clk en" if enable else "clk dis"
        response = self._send_command(cmd)
        return parse_success(response)

    def get_flit_status(self) -> FlitStatus:
        """
        Get flit mode status for all stations (flit command without args).

        Returns:
            FlitStatus indicating flit disable mode for each station
        """
        response = self._send_command("flit")
        return parse_flit(response)

    def set_flit_mode(
        self,
        station: Union[int, str],
        disable: bool,
    ) -> bool:
        """
        Configure flit disable mode for a station (flit command).

        Flit mode is required for PCIe Gen6 (64 GT/s) operation.
        Disabling flit mode also disables data rates of 64 GT/s or higher.

        Args:
            station: Station number (2, 5, 7, 8) or "all"
            disable: True to disable flit mode, False to enable

        Returns:
            True if successful

        Example:
            >>> card.set_flit_mode("all", False)  # Enable flit on all stations
            >>> card.set_flit_mode(2, True)  # Disable flit on station 2
        """
        if isinstance(station, int):
            if station not in [2, 5, 7, 8]:
                raise InvalidParameterError("station", str(station), "2, 5, 7, 8, or 'all'")
            station_str = str(station)
        else:
            station_str = station.lower()
            if station_str != "all":
                raise InvalidParameterError("station", station_str, "2, 5, 7, 8, or 'all'")

        mode = "on" if disable else "off"
        response = self._send_command(f"flit {station_str} {mode}")
        return parse_success(response, ["set to", "success"])

    def get_sdb_target(self) -> str:
        """
        Get current SDB UART port routing.

        Returns:
            Current SDB target ("usb" or "mcu")
        """
        # The sdb command without args shows current state
        response = self._send_command("sdb")
        if "usb" in response.lower():
            return "usb"
        return "mcu"

    def set_sdb_target(self, target: Union[SdbTarget, str]) -> bool:
        """
        Set SDB UART port routing (sdb command).

        Args:
            target: SdbTarget enum or string ("usb" or "mcu")
                - USB: Route to USB connector CN6 (for SwitchCLID, ARCTIC utilities)
                - MCU: Route to MCU (for normal CLI operation)

        Returns:
            True if successful
        """
        if isinstance(target, SdbTarget):
            target_str = target.value
        else:
            target_str = target.lower()

        if target_str not in ["usb", "mcu"]:
            raise InvalidParameterError("target", target_str, "usb or mcu")

        response = self._send_command(f"sdb {target_str}")
        return parse_success(response)

    # =========================================================================
    # Reset Commands
    # =========================================================================

    def reset_connector(self, connector: Union[int, str]) -> bool:
        """
        Send PERST# reset to devices on MCIO connector (conrst command).

        Sends a 300ms duration PERST# signal to attached devices.

        Args:
            connector: Connector number (0-4) or "all"
                - 0: CON0 (EXT MCIO upper, Port 112)
                - 1: CON1 (EXT MCIO lower, Port 120)
                - 2: CON2 (INT MCIO upper, Port 128)
                - 3: CON3 (INT MCIO lower, Port 136)
                - 4: CON4 (PCIe Straddle, Port 80)
                - "all": All connectors

        Returns:
            True if successful

        Example:
            >>> card.reset_connector(0)  # Reset devices on CON0
            >>> card.reset_connector("all")  # Reset all connectors
        """
        if isinstance(connector, int):
            if connector not in range(5):
                raise InvalidParameterError("connector", str(connector), "0, 1, 2, 3, 4, or 'all'")
            con_str = str(connector)
        else:
            con_str = connector.lower()
            if con_str != "all":
                raise InvalidParameterError("connector", con_str, "0, 1, 2, 3, 4, or 'all'")

        response = self._send_command(f"conrst {con_str}")
        return parse_success(response)

    def reset_mcu(self) -> bool:
        """
        Reset the on-board MCU (reset command).

        Note: This only resets the MCU, not the PCIe switch.

        Returns:
            True if successful
        """
        response = self._send_command("reset", timeout=10.0)
        return "Reset" in response

    # =========================================================================
    # Register Access Commands
    # =========================================================================

    def read_register(self, address: int, count: int = 16) -> RegisterDump:
        """
        Dump switch registers (dr command).

        Args:
            address: Starting register address (0x00000000 - 0xFFFFFFFC)
            count: Number of 32-bit values to read (in hex)

        Returns:
            RegisterDump with address-value mapping

        Example:
            >>> dump = card.read_register(0x60800000)
            >>> print(hex(dump.values[0x60800000]))
        """
        if address < 0 or address > 0xFFFFFFFC:
            raise InvalidParameterError("address", hex(address), "0x00000000 - 0xFFFFFFFC")

        cmd = f"dr {address:x}"
        if count != 16:
            cmd += f" {count:x}"

        response = self._send_command(cmd)
        return parse_register_dump(response)

    def write_register(self, address: int, data: int) -> bool:
        """
        Write to a switch register (mw command).

        Args:
            address: Register address (0x00000000 - 0xFFFFFFFC)
            data: 32-bit data value (0x00000000 - 0xFFFFFFFF)

        Returns:
            True if successful

        Example:
            >>> card.write_register(0xFFF0017C, 0xFFFFFFFF)
        """
        if address < 0 or address > 0xFFFFFFFC:
            raise InvalidParameterError("address", hex(address), "0x00000000 - 0xFFFFFFFC")
        if data < 0 or data > 0xFFFFFFFF:
            raise InvalidParameterError("data", hex(data), "0x00000000 - 0xFFFFFFFF")

        response = self._send_command(f"mw {address:x} {data:x}")
        # mw command typically doesn't return success message
        return self.PROMPT in response

    def read_port_registers(self, port_number: int) -> RegisterDump:
        """
        Dump registers for a specific port (dp command).

        Args:
            port_number: Port number (0-143)

        Returns:
            RegisterDump with port register values

        Example:
            >>> dump = card.read_port_registers(32)  # Golden finger port
        """
        if port_number < 0 or port_number > 143:
            raise InvalidParameterError("port_number", str(port_number), "0 - 143")

        response = self._send_command(f"dp {port_number}")
        return parse_register_dump(response)

    def read_flash(self, address: int, count: int = 16) -> FlashDump:
        """
        Dump switch flash memory (df command).

        Args:
            address: Starting flash address (0x00000000 - 0xFFFFFFFC)
            count: Number of 32-bit values to read (in hex)

        Returns:
            FlashDump with address-value mapping

        Example:
            >>> dump = card.read_flash(0x400)
        """
        if address < 0 or address > 0xFFFFFFFC:
            raise InvalidParameterError("address", hex(address), "0x00000000 - 0xFFFFFFFC")

        cmd = f"df {address:x}"
        if count != 16:
            cmd += f" {count:x}"

        response = self._send_command(cmd)
        return parse_flash_dump(response)

    # =========================================================================
    # I2C/SMBus Commands
    # =========================================================================

    def i2c_read(
        self,
        address: int,
        connector: int,
        channel: str,
        read_bytes: int,
        register: int = 0,
    ) -> I2CReadResult:
        """
        Read data from I2C device on MCIO connector (iicwr command).

        Args:
            address: I2C device address (hex)
            connector: Connector number (0-4)
            channel: MCIO channel ("a" or "b")
                - Channel A: pins B8/B9
                - Channel B: pins B26/B27
            read_bytes: Number of bytes to read (max 128)
            register: Register offset to start reading from

        Returns:
            I2CReadResult with read data

        Example:
            >>> result = card.i2c_read(0xD4, 2, "a", 8, 0)
            >>> print([hex(b) for b in result.data])
        """
        if connector < 0 or connector > 4:
            raise InvalidParameterError("connector", str(connector), "0 - 4")
        if channel.lower() not in ["a", "b"]:
            raise InvalidParameterError("channel", channel, "a or b")
        if read_bytes < 1 or read_bytes > 128:
            raise InvalidParameterError("read_bytes", str(read_bytes), "1 - 128")

        response = self._send_command(
            f"iicwr {address:x} {connector} {channel.lower()} {read_bytes} {register:x}"
        )
        return parse_iicwr(response, address, connector, channel)

    def i2c_write(
        self,
        address: int,
        connector: int,
        channel: str,
        data: List[int],
    ) -> I2CWriteResult:
        """
        Write data to I2C device on MCIO connector (iicw command).

        Args:
            address: I2C device address (hex)
            connector: Connector number (0-4)
            channel: MCIO channel ("a" or "b")
            data: List of bytes to write (max 128 bytes)

        Returns:
            I2CWriteResult confirming write

        Example:
            >>> card.i2c_write(0xD4, 2, "a", [0xFF])
        """
        if connector < 0 or connector > 4:
            raise InvalidParameterError("connector", str(connector), "0 - 4")
        if channel.lower() not in ["a", "b"]:
            raise InvalidParameterError("channel", channel, "a or b")
        if len(data) < 1 or len(data) > 128:
            raise InvalidParameterError("data length", str(len(data)), "1 - 128")

        data_str = " ".join(f"{b:x}" for b in data)
        response = self._send_command(f"iicw {address:x} {connector} {channel.lower()} {data_str}")
        return parse_iicw(response, address, connector, channel, data)

    # =========================================================================
    # Firmware Update Commands
    # =========================================================================

    def update_firmware(
        self,
        firmware_type: Union[FirmwareType, str],
        file_path: str,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> bool:
        """
        Update firmware via XMODEM transfer (fdl command).

        Note: This method initiates the firmware update but requires an external
        XMODEM transfer to complete. For automated updates, consider using
        a library like xmodem.

        Args:
            firmware_type: Type of firmware to update
                - MINI: Atlas3 unmanaged mini SBR
                - MAIN: Atlas3 unmanaged main SBR
                - FW: Atlas3 managed firmware
                - MCU: On-board MCU firmware
            file_path: Path to firmware binary file
            progress_callback: Optional callback(bytes_sent, total_bytes)

        Returns:
            True if successful

        Raises:
            FirmwareUpdateError: If update fails

        Note:
            After updating MINI, MAIN, or FW firmware, power cycle the host card.
            After updating MCU firmware, use reset() command.
        """
        if isinstance(firmware_type, FirmwareType):
            fw_type = firmware_type.value
        else:
            fw_type = firmware_type.lower()

        if fw_type not in ["mini", "main", "fw", "mcu"]:
            raise InvalidParameterError("firmware_type", fw_type, "mini, main, fw, or mcu")

        # This is a simplified implementation
        # Full implementation would use xmodem library
        raise NotImplementedError(
            "Firmware update requires XMODEM transfer. "
            "Use a terminal emulator like TeraTerm or minicom, "
            "or implement XMODEM transfer externally."
        )

    def prepare_firmware_update(self, firmware_type: Union[FirmwareType, str]) -> str:
        """
        Prepare for firmware update and return instructions.

        This sends the fdl command to prepare the device for XMODEM transfer.

        Args:
            firmware_type: Type of firmware to update

        Returns:
            Response string with transfer instructions

        Warning:
            After calling this, the device expects XMODEM transfer.
            Press Ctrl+X to cancel if not proceeding.
        """
        if isinstance(firmware_type, FirmwareType):
            fw_type = firmware_type.value
        else:
            fw_type = firmware_type.lower()

        if fw_type not in ["mini", "main", "fw", "mcu"]:
            raise InvalidParameterError("firmware_type", fw_type, "mini, main, fw, or mcu")

        response = self._send_command(f"fdl {fw_type}", timeout=10.0)
        return response
