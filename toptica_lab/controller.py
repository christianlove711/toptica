from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Any


class ControllerError(RuntimeError):
    """Raised when a controller operation fails."""


@dataclass(slots=True)
class ConnectionSettings:
    host: str
    connection_type: str = "network"
    timeout: int = 5
    command_line_port: int = 1998
    monitoring_line_port: int = 1999
    serial_port: str = ""
    baudrate: int = 115200
    demo_mode: bool = False


@dataclass(slots=True)
class LaserStatus:
    connected: bool
    mode: str
    host: str
    system_type: str = "Unknown"
    serial_number: str = "Unknown"
    system_label: str = "Unknown"
    user_level: str = "Unknown"
    uptime_text: str = "Unknown"
    diode_current_ma: str = "Unknown"
    last_updated: str = "Never"
    message: str = ""


class TOOPTICAController:
    """Small wrapper around the TOOPTICA LaserSDK low-level client."""

    def __init__(self) -> None:
        self._settings: ConnectionSettings | None = None
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def settings(self) -> ConnectionSettings | None:
        return self._settings

    def connect(self, settings: ConnectionSettings) -> LaserStatus:
        self._validate_settings(settings)

        self._settings = settings
        status = self.read_basic_status()
        self._connected = True
        return status

    def disconnect(self) -> None:
        self._connected = False

    def read_basic_status(self) -> LaserStatus:
        if self._settings is None:
            raise ControllerError("Connect the controller before reading status.")

        if self._settings.demo_mode or self._settings.host.strip().lower() == "demo":
            return self._demo_status()

        try:
            return self._device_status()
        except Exception as exc:
            self._connected = False
            raise ControllerError(str(exc)) from exc

    def read_parameter(self, parameter: str) -> str:
        if not parameter.strip():
            raise ControllerError("Parameter name cannot be empty.")

        results = self.read_parameters([parameter])
        return results[parameter]

    def read_parameters(self, parameters: list[str]) -> dict[str, str]:
        if self._settings is None:
            raise ControllerError("Connect the controller before reading parameters.")

        clean_parameters = [param.strip() for param in parameters if param.strip()]
        if not clean_parameters:
            return {}

        if self._settings.demo_mode or self._settings.host.strip().lower() == "demo":
            return {param: self._demo_parameter_value(param) for param in clean_parameters}

        try:
            with self._open_client() as client:
                return {param: self._safe_get(client, param) for param in clean_parameters}
        except Exception as exc:
            self._connected = False
            raise ControllerError(str(exc)) from exc

    def _device_status(self) -> LaserStatus:
        assert self._settings is not None
        with self._open_client() as client:
            status = LaserStatus(
                connected=True,
                mode=self._settings.connection_type,
                host=self._display_target(),
                system_type=self._safe_get(client, "system-type"),
                serial_number=self._safe_get(client, "serial-number"),
                system_label=self._safe_get(client, "system-label"),
                user_level=self._safe_get(client, "ul"),
                uptime_text=self._safe_get(client, "uptime-txt"),
                diode_current_ma=self._format_current(
                    self._safe_get(client, "laser1:dl:cc:current-act")
                ),
                last_updated=self._timestamp(),
                message=self._build_status_message(),
            )

        self._connected = True
        return status

    @contextmanager
    def _open_client(self) -> Any:
        client_module = self._load_sdk()
        Client = client_module["Client"]
        connection = self._build_connection(client_module)
        with Client(connection) as client:
            yield client

    def _load_sdk(self) -> dict[str, Any]:
        try:
            from toptica.lasersdk.client import Client, NetworkConnection, SerialConnection
        except ImportError as exc:
            raise ControllerError(
                "Missing dependency 'toptica-lasersdk'. Install requirements first."
            ) from exc

        return {
            "Client": Client,
            "NetworkConnection": NetworkConnection,
            "SerialConnection": SerialConnection,
        }

    def _safe_get(self, client: Any, parameter: str) -> str:
        try:
            value = client.get(parameter)
        except Exception as exc:
            return f"Unavailable ({exc})"
        return str(value)

    def _demo_status(self) -> LaserStatus:
        assert self._settings is not None
        self._connected = True
        return LaserStatus(
            connected=True,
            mode="demo",
            host=self._settings.host or "demo",
            system_type="DLC pro (Demo)",
            serial_number="SIM-0001",
            system_label="Lab Demo Laser",
            user_level="NORMAL",
            uptime_text="03:42:17",
            diode_current_ma="98.5 mA",
            last_updated=self._timestamp(),
            message="Demo mode is active. No hardware is being controlled.",
        )

    def _demo_parameter_value(self, parameter: str) -> str:
        demo_values = {
            "system-type": "DLC pro (Demo)",
            "serial-number": "SIM-0001",
            "system-label": "Lab Demo Laser",
            "ul": "NORMAL",
            "uptime-txt": "03:42:17",
            "laser1:dl:cc:current-act": "98.5",
            "laser1:dl:cc:enabled": "true",
            "laser1:dl:tc:temp-act": "24.8",
            "laser1:dl:tc:temp-set": "25.0",
            "laser1:emission": "false",
        }
        return demo_values.get(parameter, "Unavailable (not in demo catalog)")

    def _validate_settings(self, settings: ConnectionSettings) -> None:
        if settings.demo_mode:
            return

        if settings.connection_type == "network" and not settings.host.strip():
            raise ControllerError("Network connection requires a host, IP, or device label.")

        if settings.connection_type == "serial" and not settings.serial_port.strip():
            raise ControllerError("Serial connection requires a serial port path.")

        if settings.timeout < 1:
            raise ControllerError("Timeout must be at least 1 second.")

    def _build_connection(self, client_module: dict[str, Any]) -> Any:
        assert self._settings is not None
        if self._settings.connection_type == "serial":
            SerialConnection = client_module["SerialConnection"]
            return SerialConnection(
                self._settings.serial_port,
                baudrate=self._settings.baudrate,
                timeout=self._settings.timeout,
            )

        NetworkConnection = client_module["NetworkConnection"]
        return NetworkConnection(
            self._settings.host,
            command_line_port=self._settings.command_line_port,
            monitoring_line_port=self._settings.monitoring_line_port,
            timeout=self._settings.timeout,
        )

    def _display_target(self) -> str:
        assert self._settings is not None
        if self._settings.connection_type == "serial":
            return self._settings.serial_port
        return self._settings.host

    def _build_status_message(self) -> str:
        assert self._settings is not None
        if self._settings.connection_type == "serial":
            return (
                f"Connected over serial port {self._settings.serial_port} "
                f"at {self._settings.baudrate} baud."
            )
        return (
            f"Connected over network to {self._settings.host} "
            f"(cmd {self._settings.command_line_port}, mon {self._settings.monitoring_line_port})."
        )

    def _format_current(self, raw_value: str) -> str:
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            return str(raw_value)
        return f"{value:.3f} mA"

    def _timestamp(self) -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
