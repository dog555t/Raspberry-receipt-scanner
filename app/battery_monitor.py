"""Battery monitor for MakerFocus UPS.

The MakerFocus Raspberry Pi 4 Battery Pack UPS typically exposes an INA219
fuel gauge over I2C at address 0x40. This module reads voltage/current to
estimate percentage. Adjust the implementation for your specific board if
needed.
"""
import logging
import os
import time
from dataclasses import dataclass
from typing import Optional

try:
    import smbus
except ImportError:  # pragma: no cover - allows running on non-Pi hosts
    smbus = None

I2C_BUS_ID = 1
INA219_ADDRESS = 0x40
SHUTDOWN_THRESHOLD = 10
SHUTDOWN_COMMAND = "sudo shutdown -h now"
LOG_FILE = "battery.log"


@dataclass
class BatteryStatus:
    voltage: Optional[float]
    current: Optional[float]
    percentage: Optional[float]
    charging: Optional[bool]


class BatteryMonitor:
    def __init__(self, bus_id: int = I2C_BUS_ID, address: int = INA219_ADDRESS):
        self.bus_id = bus_id
        self.address = address
        self.bus = smbus.SMBus(bus_id) if smbus else None

    def read_voltage(self) -> Optional[float]:
        if not self.bus:
            return None
        try:
            raw = self.bus.read_word_data(self.address, 0x02)
            voltage = (raw >> 3) * 4e-3  # From INA219 datasheet
            return round(voltage, 3)
        except Exception:
            return None

    def read_current(self) -> Optional[float]:
        if not self.bus:
            return None
        try:
            raw = self.bus.read_word_data(self.address, 0x04)
            current = raw * 0.001  # Placeholder scaling
            return round(current, 3)
        except Exception:
            return None

    def estimate_percentage(self, voltage: Optional[float]) -> Optional[float]:
        if voltage is None:
            return None
        # Simple linear estimate between 3.3V (empty) and 4.2V (full)
        percent = (voltage - 3.3) / (4.2 - 3.3) * 100
        return max(0, min(100, round(percent, 1)))

    def status(self) -> BatteryStatus:
        voltage = self.read_voltage()
        current = self.read_current()
        percentage = self.estimate_percentage(voltage)
        charging = current is not None and current < 0
        return BatteryStatus(voltage, current, percentage, charging)


class BatteryLogger:
    def __init__(self, log_file: str = LOG_FILE):
        logging.basicConfig(
            filename=log_file,
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(message)s",
        )
        self.logger = logging.getLogger(__name__)

    def log(self, status: BatteryStatus) -> None:
        self.logger.info(
            "Voltage=%sV Current=%sA Percent=%s%% Charging=%s",
            status.voltage,
            status.current,
            status.percentage,
            status.charging,
        )


def shutdown_system(command: str = SHUTDOWN_COMMAND) -> None:
    os.system(command)


def monitor_loop(interval: int = 60, threshold: int = SHUTDOWN_THRESHOLD) -> None:
    monitor = BatteryMonitor()
    logger = BatteryLogger()
    while True:
        status = monitor.status()
        logger.log(status)
        if status.percentage is not None and status.percentage <= threshold:
            logger.logger.warning("Battery low (%.1f%%). Shutting down...", status.percentage)
            shutdown_system()
            break
        time.sleep(interval)
