from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Any


class DemoControllerError(RuntimeError):
    """Demo 控制器错误。"""


@dataclass(slots=True)
class DemoConnectionSettings:
    host: str
    timeout: int = 5
    command_line_port: int = 1998
    monitoring_line_port: int = 1999
    demo_mode: bool = False


@dataclass(slots=True)
class DemoDeviceStatus:
    connected: bool
    host: str
    system_type: str
    serial_number: str
    system_label: str
    uptime_text: str
    current_driver_enabled: bool
    current_driver_emission: bool
    current_ma: float
    updated_at: str
    source: str


class DlcproCurrentDemoController:
    """基于 DLC pro v2.6.0 官方高层接口的最小演示控制器。"""

    def __init__(self) -> None:
        self._settings: DemoConnectionSettings | None = None

    @property
    def settings(self) -> DemoConnectionSettings | None:
        return self._settings

    def connect(self, settings: DemoConnectionSettings) -> DemoDeviceStatus:
        if not settings.demo_mode and not settings.host.strip():
            raise DemoControllerError("真实设备模式下必须填写 DLC pro 地址。")

        # 先暂存旧配置。若本次连接探测失败，需要回滚，避免残留“已连接”状态。
        previous_settings = self._settings
        self._settings = settings
        try:
            return self.read_status()
        except Exception:
            self._settings = previous_settings
            raise

    def disconnect(self) -> None:
        self._settings = None

    def read_status(self) -> DemoDeviceStatus:
        if self._settings is None:
            raise DemoControllerError("请先连接设备。")

        if self._settings.demo_mode or self._settings.host.strip().lower() == "demo":
            return self._demo_status()

        try:
            with self._open_dlcpro() as dlc:
                return DemoDeviceStatus(
                    connected=True,
                    host=self._settings.host,
                    system_type=str(dlc.system_type.get()),
                    serial_number=str(dlc.serial_number.get()),
                    system_label=str(dlc.system_label.get()),
                    uptime_text=str(dlc.uptime_txt.get()),
                    current_driver_enabled=bool(dlc.laser1.dl.cc.enabled.get()),
                    current_driver_emission=bool(dlc.laser1.dl.cc.emission.get()),
                    current_ma=float(dlc.laser1.dl.cc.current_act.get()),
                    updated_at=self._now(),
                    source="官方 SDK dlcpro.v2_6_0",
                )
        except Exception as exc:
            raise DemoControllerError(f"读取 DLC pro 状态失败：{exc}") from exc

    def set_current(self, value_ma: float) -> DemoDeviceStatus:
        if self._settings is None:
            raise DemoControllerError("请先连接设备。")

        if value_ma < 0:
            raise DemoControllerError("电流值不能小于 0 mA。")

        if self._settings.demo_mode or self._settings.host.strip().lower() == "demo":
            status = self._demo_status()
            status.current_ma = float(value_ma)
            status.updated_at = self._now()
            return status

        try:
            with self._open_dlcpro() as dlc:
                # SDK 中 current_act 为只读，实际写入只能通过 current_set 完成。
                dlc.laser1.dl.cc.current_set.set(float(value_ma))
            return self.read_status()
        except Exception as exc:
            raise DemoControllerError(f"写入电流失败：{exc}") from exc

    @contextmanager
    def _open_dlcpro(self) -> Any:
        if self._settings is None:
            raise DemoControllerError("缺少连接配置。")

        try:
            from toptica.lasersdk.client import NetworkConnection
            from toptica.lasersdk.dlcpro.v2_6_0 import DLCpro
        except ImportError as exc:
            raise DemoControllerError(
                "缺少 TOOPTICA 官方 SDK。请先安装 requirements.txt 中的依赖。"
            ) from exc

        # 真实设备的网络连接就在这里建立。
        # GUI 中填写的主机地址、命令端口、监控端口和超时
        # 最终都会传给官方 SDK 的 NetworkConnection。
        connection = NetworkConnection(
            self._settings.host,
            command_line_port=self._settings.command_line_port,
            monitoring_line_port=self._settings.monitoring_line_port,
            timeout=self._settings.timeout,
        )
        with DLCpro(connection) as dlc:
            yield dlc

    def _demo_status(self) -> DemoDeviceStatus:
        assert self._settings is not None
        return DemoDeviceStatus(
            connected=True,
            host=self._settings.host or "demo",
            system_type="DLC pro (演示)",
            serial_number="SIM-2600",
            system_label="实验室演示激光器",
            uptime_text="05:21:48",
            current_driver_enabled=True,
            current_driver_emission=False,
            current_ma=98.320,
            updated_at=self._now(),
            source="演示模式",
        )

    def _now(self) -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
