"""Tests for the Serial Cables Atlas3 library."""

import pytest

from serialcables_atlas3 import LinkSpeed, LinkStatus, OperationMode, PortType, SpreadMode
from serialcables_atlas3.exceptions import InvalidParameterError, ParseError
from serialcables_atlas3.models import (
    BistResult,
    ErrorCounters,
    HostCardInfo,
    I2CDevice,
    PortInfo,
    PortStatus,
    VersionInfo,
)
from serialcables_atlas3.parsers import (
    parse_bist,
    parse_clk,
    parse_counters,
    parse_flit,
    parse_lsd,
    parse_showmode,
    parse_showport,
    parse_spread,
    parse_version,
)


class TestEnums:
    """Test enum classes."""

    def test_link_speed_from_string(self):
        assert LinkSpeed.from_string("Gen1") == LinkSpeed.GEN1
        assert LinkSpeed.from_string("Gen6") == LinkSpeed.GEN6
        assert LinkSpeed.from_string("gen4") == LinkSpeed.GEN4

    def test_link_speed_invalid(self):
        with pytest.raises(ValueError):
            LinkSpeed.from_string("Gen7")

    def test_link_status_from_string(self):
        assert LinkStatus.from_string("Active") == LinkStatus.ACTIVE
        assert LinkStatus.from_string("Degraded") == LinkStatus.DEGRADED
        assert LinkStatus.from_string("idle") == LinkStatus.IDLE

    def test_operation_mode_values(self):
        assert OperationMode.MODE_1.value == 1
        assert OperationMode.MODE_4.value == 4

    def test_spread_mode_values(self):
        assert SpreadMode.OFF.value == "off"
        assert SpreadMode.DOWN_2500PPM.value == "1"
        assert SpreadMode.DOWN_5000PPM.value == "2"


class TestParsers:
    """Test response parsers."""

    def test_parse_version(self):
        response = """
        ------------ Product Info ------------
        Company   : Serial Cables
        Model     : PCI6-AD-x16HI-BG6-144
        Serial No. :
        ------------ MCU Info ----------------
        Version   : 0.2.3
        Build Time : Oct 22 2025 17:15:13
        ------------ SBR Info ----------------
        Version   : 0032A022
        Cmd>
        """
        result = parse_version(response)
        assert isinstance(result, VersionInfo)
        assert result.company == "Serial Cables"
        assert result.model == "PCI6-AD-x16HI-BG6-144"
        assert result.mcu_version == "0.2.3"
        assert result.sbr_version == "0032A022"

    def test_parse_lsd(self):
        response = """
        ★ Host card information★
        [ Thermal ]
        · Switch Temperature  : 46° C
        [ Fan Speed ]
        · Switch Fan          : 6456 RPM
        [ Voltage Sensors ]
        · 1.5V   Voltage      : 1.499 V
        · VDD    Voltage      : 0.962 V
        · VDDA   Voltage      : 0.881 V
        · VDDA12 Voltage      : 1.352 V
        [ Power Consumption ]
        · Power Voltage       : 11.97 V
        · Load Current        : 10.622 A
        · Load Power          : 126.251 W
        Cmd>
        """
        result = parse_lsd(response)
        assert isinstance(result, HostCardInfo)
        assert result.thermal.switch_temperature_celsius == 46.0
        assert result.fan.switch_fan_rpm == 6456
        assert result.voltages.voltage_1v5 == 1.499
        assert result.voltages.voltage_vdd == 0.962
        assert result.power.load_power == 126.251

    def test_parse_showport(self):
        response = """
        Atlas3 chip ver: A0
        ================== Upstream Ports ==================
        Stn2 | USP00 | Port 032 | Speed: Gen4 | Width: 4 | Max: Gen6 x16 | Status: Degraded
        ================== EXT MCIO Ports ==================
        Stn7 | Con00 | Port 112 | Speed: Gen4 | Width: 4 | Max: Gen6 x4 | Status: Degraded
        Stn7 | Con00 | Port 116 | Speed: Gen6 | Width: 4 | Max: Gen6 x4 | Status: Active
        Stn7 | Con01 | Port 120 | Speed: Gen1 | Width: 0 | Max: Gen6 x2 | Status: Idle
        ================== INT MCIO Ports ==================
        Stn8 | Con02 | Port 128 | Speed: Gen1 | Width: 0 | Max: Gen6 x2 | Status: Idle
        Stn8 | Con02 | Port 132 | Speed: Gen6 | Width: 4 | Max: Gen6 x4 | Status: Active
        ================== Straddle Ports ==================
        Stn5 | Con04 | Port 080 | Speed: Gen5 | Width: 8 | Max: Gen6 x16 | Status: Degraded
        Cmd>
        """
        result = parse_showport(response)
        assert isinstance(result, PortStatus)
        assert result.chip_version == "A0"
        assert len(result.upstream_ports) == 1
        assert len(result.ext_mcio_ports) == 3
        assert len(result.int_mcio_ports) == 2
        assert len(result.straddle_ports) == 1

        # Check upstream port
        usp = result.upstream_ports[0]
        assert usp.station == 2
        assert usp.port_number == 32
        assert usp.negotiated_speed == LinkSpeed.GEN4
        assert usp.negotiated_width == 4
        assert usp.max_speed == LinkSpeed.GEN6
        assert usp.status == LinkStatus.DEGRADED

        # Check active MCIO port
        active = result.ext_mcio_ports[1]
        assert active.negotiated_speed == LinkSpeed.GEN6
        assert active.status == LinkStatus.ACTIVE
        assert active.is_linked
        assert not active.is_degraded

        # Check idle port
        idle = result.ext_mcio_ports[2]
        assert idle.status == LinkStatus.IDLE
        assert not idle.is_linked

    def test_parse_bist(self):
        response = """
        Channel  Device     Address    Status
        ----------------------------------------
        CH0      INA231     0x80       OK
        CH0      ADM1177    0xB0       OK
        CH1      PCA9575    0x40       OK
        CH1      PCA9548    0xE0       OK
        CH3      SI52212    0xD2       OK
        CH3      SI53212    0xD4       OK
        Cmd>
        """
        result = parse_bist(response)
        assert isinstance(result, BistResult)
        assert len(result.devices) == 6
        assert result.all_passed

        # Check first device
        dev = result.devices[0]
        assert dev.channel == "CH0"
        assert dev.device_name == "INA231"
        assert dev.address == 0x80
        assert dev.status == "OK"
        assert dev.is_ok

    def test_parse_counters(self):
        response = """
        Port#    PortRx      BadTLP      BadDLLP     RecDiag     LinkDown    FlitError
        --------------------------------------------------------------------------
        32       00000000    00000000    00000000    00000000    00000000    00000000
        80       00000000    00000001    00000000    00000000    00000000    00000000
        112      00000000    00000000    00000000    00000000    00000000    00000000
        Cmd>
        """
        result = parse_counters(response)
        assert len(result.counters) == 3
        assert result.counters[0].port_number == 32
        assert not result.counters[0].has_errors
        assert result.counters[1].bad_tlp == 1
        assert result.counters[1].has_errors
        assert result.total_errors == 1

    def test_parse_showmode(self):
        response = "PCIe switch mode 1\nCmd>"
        result = parse_showmode(response)
        assert result == OperationMode.MODE_1

    def test_parse_spread_off(self):
        response = "Spread status:OFF\nCmd>"
        result = parse_spread(response)
        assert not result.enabled
        assert result.mode == SpreadMode.OFF

    def test_parse_spread_on(self):
        response = "Set down spreading 2500PPM success.\nCmd>"
        result = parse_spread(response)
        assert result.enabled
        assert result.mode == SpreadMode.DOWN_2500PPM

    def test_parse_clk(self):
        response = """
        PCIe Straddle connectotr clock output enable.
        EXT MCIO connectotr clock output enable.
        INT MCIO connectotr clock output disable.
        Cmd>
        """
        result = parse_clk(response)
        assert result.straddle_enabled
        assert result.ext_mcio_enabled
        assert not result.int_mcio_enabled

    def test_parse_flit(self):
        response = """
        Station2 flit disable mode : off:
        Station5 flit disable mode : on:
        Station7 flit disable mode : on:
        Station8 flit disable mode : on:
        Cmd>
        """
        result = parse_flit(response)
        assert not result.station2
        assert result.station5
        assert result.station7
        assert result.station8


class TestModels:
    """Test data models."""

    def test_port_info_properties(self):
        port = PortInfo(
            station=7,
            connector="Con00",
            port_number=112,
            negotiated_speed=LinkSpeed.GEN6,
            negotiated_width=4,
            max_speed=LinkSpeed.GEN6,
            max_width=4,
            status=LinkStatus.ACTIVE,
            port_type=PortType.MCIO_EXT,
        )
        assert port.is_linked
        assert not port.is_degraded

    def test_port_info_idle(self):
        port = PortInfo(
            station=7,
            connector="Con01",
            port_number=120,
            negotiated_speed=None,
            negotiated_width=0,
            max_speed=LinkSpeed.GEN6,
            max_width=2,
            status=LinkStatus.IDLE,
            port_type=PortType.MCIO_EXT,
        )
        assert not port.is_linked
        assert not port.is_degraded

    def test_port_info_degraded(self):
        port = PortInfo(
            station=2,
            connector=None,
            port_number=32,
            negotiated_speed=LinkSpeed.GEN4,
            negotiated_width=4,
            max_speed=LinkSpeed.GEN6,
            max_width=16,
            status=LinkStatus.DEGRADED,
            port_type=PortType.USP,
        )
        assert port.is_linked
        assert port.is_degraded

    def test_error_counters_has_errors(self):
        no_errors = ErrorCounters(
            port_number=32,
            port_rx=0,
            bad_tlp=0,
            bad_dllp=0,
            rec_diag=0,
            link_down=0,
            flit_error=0,
        )
        assert not no_errors.has_errors

        has_errors = ErrorCounters(
            port_number=80,
            port_rx=0,
            bad_tlp=1,
            bad_dllp=0,
            rec_diag=0,
            link_down=0,
            flit_error=0,
        )
        assert has_errors.has_errors

    def test_bist_result_all_passed(self):
        devices = [
            I2CDevice("CH0", "INA231", 0x80, "OK"),
            I2CDevice("CH0", "ADM1177", 0xB0, "OK"),
        ]
        result = BistResult(devices=devices)
        assert result.all_passed

        devices_fail = [
            I2CDevice("CH0", "INA231", 0x80, "OK"),
            I2CDevice("CH0", "ADM1177", 0xB0, "FAIL"),
        ]
        result_fail = BistResult(devices=devices_fail)
        assert not result_fail.all_passed


class TestValidation:
    """Test parameter validation."""

    def test_invalid_parameter_error(self):
        err = InvalidParameterError("mode", "5", "1, 2, 3, or 4")
        assert "mode" in str(err)
        assert "5" in str(err)
        assert "1, 2, 3, or 4" in str(err)

    def test_parse_error(self):
        err = ParseError("invalid response", "Custom message")
        assert "Custom message" in str(err)


class TestImports:
    """Test package imports."""

    def test_main_imports(self):
        from serialcables_atlas3 import Atlas3, Atlas3Error, LinkSpeed

        assert Atlas3 is not None
        assert Atlas3Error is not None
        assert LinkSpeed is not None

    def test_version(self):
        from serialcables_atlas3 import __version__

        assert __version__ == "0.1.0"
