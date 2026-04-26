from __future__ import annotations

from functools import partial

from PySide6.QtCore import QObject, QSignalBlocker, QThread, QTimer, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from demo_dlcpro_current.controller import (
    DemoConnectionSettings,
    DemoControllerError,
    DemoDeviceStatus,
    DlcproCurrentDemoController,
)


class DeviceOperationWorker(QObject):
    finished = Signal(str, object, object)

    def __init__(
        self,
        controller: DlcproCurrentDemoController,
        operation: str,
        *,
        settings: DemoConnectionSettings | None = None,
        value_ma: float | None = None,
    ) -> None:
        super().__init__()
        self._controller = controller
        self._operation = operation
        self._settings = settings
        self._value_ma = value_ma

    @Slot()
    def run(self) -> None:
        try:
            if self._operation == "connect":
                assert self._settings is not None
                result = self._controller.connect(self._settings)
            elif self._operation == "refresh":
                result = self._controller.read_status()
            elif self._operation == "write":
                assert self._value_ma is not None
                result = self._controller.set_current(self._value_ma)
            else:
                raise DemoControllerError(f"不支持的操作：{self._operation}")
        except Exception as exc:  # noqa: BLE001 - 统一转回主线程处理
            self.finished.emit(self._operation, None, exc)
            return

        self.finished.emit(self._operation, result, None)


class DemoMainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.controller = DlcproCurrentDemoController()
        self._pending_current_ma: float | None = None
        self._write_in_flight_ma: float | None = None
        self._active_operation: str | None = None
        self._operation_thread: QThread | None = None
        self._operation_worker: DeviceOperationWorker | None = None

        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(1500)
        self.refresh_timer.timeout.connect(self.refresh_status)

        # 用一个很短的防抖定时器，让键盘步进时不会频繁打满设备写入。
        self.write_timer = QTimer(self)
        self.write_timer.setSingleShot(True)
        self.write_timer.setInterval(180)
        self.write_timer.timeout.connect(self._commit_pending_current)

        self.setWindowTitle("DLC pro 电流控制 Demo")
        self.resize(1080, 760)
        self._build_ui()
        self._apply_styles()
        self._set_idle_state()

    def _build_ui(self) -> None:
        central = QWidget(self)
        root = QVBoxLayout(central)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(18)

        header = self._build_header()
        root.addWidget(header)

        body = QHBoxLayout()
        body.setSpacing(18)
        body.addWidget(self._build_connection_card(), 4)
        body.addWidget(self._build_status_card(), 5)
        root.addLayout(body)

        root.addWidget(self._build_current_card())
        root.addStretch(1)

        self.setCentralWidget(central)
        self.setStatusBar(QStatusBar(self))
        self.statusBar().showMessage("准备就绪。")

    def _build_header(self) -> QWidget:
        card = QFrame()
        card.setObjectName("heroCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(8)

        title = QLabel("DLC pro 电流控制演示")
        title.setObjectName("heroTitle")
        subtitle = QLabel(
            "基于 TOOPTICA 官方 SDK `toptica.lasersdk.dlcpro.v2_6_0` 的最小高层接口演示"
        )
        subtitle.setObjectName("heroSubtitle")
        subtitle.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        return card

    def _build_connection_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("panelCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        title = QLabel("连接")
        title.setObjectName("panelTitle")
        layout.addWidget(title)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.host_input = QLineEdit("demo")
        self.host_input.setPlaceholderText("例如 169.254.215.1")

        self.timeout_input = QSpinBox()
        self.timeout_input.setRange(1, 30)
        self.timeout_input.setValue(5)
        self.timeout_input.setSuffix(" s")

        self.command_port_input = QSpinBox()
        self.command_port_input.setRange(0, 65535)
        self.command_port_input.setValue(1998)

        self.monitor_port_input = QSpinBox()
        self.monitor_port_input.setRange(0, 65535)
        self.monitor_port_input.setValue(1999)

        self.demo_checkbox = QCheckBox("演示模式")
        self.demo_checkbox.setChecked(True)

        form.addRow("DLC pro 地址", self.host_input)
        form.addRow("超时", self.timeout_input)
        form.addRow("命令端口", self.command_port_input)
        form.addRow("监控端口", self.monitor_port_input)
        form.addRow("", self.demo_checkbox)
        layout.addLayout(form)

        button_row = QHBoxLayout()
        self.connect_button = QPushButton("连接设备")
        self.connect_button.clicked.connect(self.handle_connect)
        self.disconnect_button = QPushButton("断开连接")
        self.disconnect_button.clicked.connect(self.handle_disconnect)
        self.refresh_button = QPushButton("刷新状态")
        self.refresh_button.clicked.connect(self.refresh_status)
        button_row.addWidget(self.connect_button)
        button_row.addWidget(self.disconnect_button)
        button_row.addWidget(self.refresh_button)
        layout.addLayout(button_row)

        note = QLabel(
            "说明：真实设备模式下默认使用 DLC pro 网络连接。"
            "SDK 网络能力常见依赖包括 ifaddr。"
        )
        note.setObjectName("noteText")
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch(1)
        return card

    def _build_status_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("panelCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        title = QLabel("设备状态")
        title.setObjectName("panelTitle")
        layout.addWidget(title)

        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(12)

        self.status_labels: dict[str, QLabel] = {}
        rows = [
            "连接状态",
            "主机地址",
            "系统类型",
            "序列号",
            "系统标签",
            "运行时间",
            "电流驱动已使能",
            "电流驱动出光状态",
            "数据来源",
            "更新时间",
        ]

        for row, title_text in enumerate(rows):
            name = QLabel(title_text)
            name.setObjectName("fieldLabel")
            value = QLabel("-")
            value.setObjectName("fieldValue")
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            grid.addWidget(name, row, 0)
            grid.addWidget(value, row, 1)
            self.status_labels[title_text] = value

        layout.addLayout(grid)
        layout.addStretch(1)
        return card

    def _build_current_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("currentCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(16)

        title = QLabel("电流控制")
        title.setObjectName("panelTitle")
        desc = QLabel(
            "这里采用键盘友好的精细调节方式：修改数值框后，"
            "程序会自动把最新电流值写到 DLC pro。"
        )
        desc.setObjectName("noteText")
        desc.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(desc)

        stat_row = QHBoxLayout()
        self.current_value_label = self._make_metric_card("当前电流值")
        stat_row.addWidget(self.current_value_label["card"])
        layout.addLayout(stat_row)

        control_row = QHBoxLayout()
        control_row.setSpacing(16)

        self.current_spin = QDoubleSpinBox()
        self.current_spin.setRange(0.0, 5000.0)
        self.current_spin.setDecimals(3)
        self.current_spin.setSingleStep(0.1)
        self.current_spin.setSuffix(" mA")
        self.current_spin.valueChanged.connect(self._on_spin_changed)

        self.current_step_combo = QComboBox()
        self.current_step_combo.addItem("0.1 mA", 0.1)
        self.current_step_combo.addItem("0.001 mA", 0.001)
        self.current_step_combo.currentIndexChanged.connect(self._on_step_changed)

        self.quick_refresh_button = QPushButton("立即读取电流")
        self.quick_refresh_button.clicked.connect(self.refresh_status)

        control_row.addWidget(QLabel("目标电流"))
        control_row.addWidget(self.current_spin)
        control_row.addWidget(QLabel("上下键步进"))
        control_row.addWidget(self.current_step_combo)
        control_row.addStretch(1)
        control_row.addWidget(self.quick_refresh_button)
        layout.addLayout(control_row)

        self.current_hint = QLabel("尚未连接设备。")
        self.current_hint.setObjectName("noteText")
        self.current_hint.setWordWrap(True)
        layout.addWidget(self.current_hint)
        return card

    def _make_metric_card(self, title: str) -> dict[str, QWidget | QLabel]:
        card = QFrame()
        card.setObjectName("metricCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(6)

        title_label = QLabel(title)
        title_label.setObjectName("metricTitle")
        value_label = QLabel("--")
        value_label.setObjectName("metricValue")

        layout.addWidget(title_label)
        layout.addWidget(value_label)
        return {"card": card, "value": value_label}

    def handle_connect(self) -> None:
        if self._active_operation is not None:
            return

        settings = DemoConnectionSettings(
            host=self.host_input.text().strip(),
            timeout=self.timeout_input.value(),
            command_line_port=self.command_port_input.value(),
            monitoring_line_port=self.monitor_port_input.value(),
            demo_mode=self.demo_checkbox.isChecked(),
        )
        self._pending_current_ma = None
        self._set_controls_enabled(False)
        self.current_hint.setText("正在连接设备，请稍候...")
        self.statusBar().showMessage("正在连接设备...")
        self._start_operation("connect", settings=settings)

    def handle_disconnect(self) -> None:
        if self._active_operation is not None:
            return

        self.refresh_timer.stop()
        self.write_timer.stop()
        self.controller.disconnect()
        self._pending_current_ma = None
        self._set_idle_state()
        self.statusBar().showMessage("已断开连接。")

    def refresh_status(self) -> None:
        if self.controller.settings is None or self._active_operation is not None:
            return
        self.statusBar().showMessage("正在刷新状态...")
        self._start_operation("refresh")

    def _on_spin_changed(self, value: float) -> None:
        if not self.current_spin.isEnabled() or self._active_operation == "connect":
            return
        self._schedule_current_write(value)

    def _on_step_changed(self) -> None:
        step = float(self.current_step_combo.currentData())
        self.current_spin.setSingleStep(step)

    def _schedule_current_write(self, value_ma: float) -> None:
        if self.controller.settings is None:
            return
        self._pending_current_ma = float(value_ma)
        self.current_hint.setText(
            f"准备更新电流值：{value_ma:.3f} mA"
        )
        if self._active_operation == "write":
            return
        self.write_timer.start()

    def _commit_pending_current(self) -> None:
        if self._pending_current_ma is None or self._active_operation is not None:
            return
        self._write_in_flight_ma = self._pending_current_ma
        self.statusBar().showMessage(
            f"正在写入电流值 {self._write_in_flight_ma:.3f} mA..."
        )
        self._start_operation("write", value_ma=self._write_in_flight_ma)

    def _apply_status(self, status: DemoDeviceStatus) -> None:
        self.status_labels["连接状态"].setText("已连接" if status.connected else "未连接")
        self.status_labels["主机地址"].setText(status.host)
        self.status_labels["系统类型"].setText(status.system_type)
        self.status_labels["序列号"].setText(status.serial_number)
        self.status_labels["系统标签"].setText(status.system_label)
        self.status_labels["运行时间"].setText(status.uptime_text)
        self.status_labels["电流驱动已使能"].setText("是" if status.current_driver_enabled else "否")
        self.status_labels["电流驱动出光状态"].setText("开" if status.current_driver_emission else "关")
        self.status_labels["数据来源"].setText(status.source)
        self.status_labels["更新时间"].setText(status.updated_at)

        self.current_value_label["value"].setText(f"{status.current_ma:.3f} mA")
        self.current_hint.setText(
            "用键盘上下键调节数值框，程序会自动更新 DLC pro 电流。"
        )

        with QSignalBlocker(self.current_spin):
            self.current_spin.setValue(status.current_ma)

        self.connect_button.setEnabled(True)
        self.disconnect_button.setEnabled(True)
        self.refresh_button.setEnabled(True)
        self.quick_refresh_button.setEnabled(True)
        self.current_spin.setEnabled(True)
        self.current_step_combo.setEnabled(True)

    def _set_idle_state(self) -> None:
        for label in self.status_labels.values():
            label.setText("-")

        self.current_value_label["value"].setText("--")
        self.current_hint.setText("尚未连接设备。")

        with QSignalBlocker(self.current_spin):
            self.current_spin.setValue(0.0)

        self.connect_button.setEnabled(True)
        self.disconnect_button.setEnabled(False)
        self.refresh_button.setEnabled(False)
        self.quick_refresh_button.setEnabled(False)
        self.current_spin.setEnabled(False)
        self.current_step_combo.setEnabled(False)

    def _show_error(self, title: str, detail: str) -> None:
        QMessageBox.critical(self, title, detail)

    def _start_operation(
        self,
        operation: str,
        *,
        settings: DemoConnectionSettings | None = None,
        value_ma: float | None = None,
    ) -> None:
        if self._active_operation is not None:
            return

        self._active_operation = operation
        thread = QThread(self)
        worker = DeviceOperationWorker(
            self.controller,
            operation,
            settings=settings,
            value_ma=value_ma,
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._finish_operation)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(partial(self._clear_operation, thread))
        self._operation_thread = thread
        self._operation_worker = worker
        thread.start()

    def _clear_operation(self, thread: QThread) -> None:
        if self._operation_thread is thread:
            self._operation_thread = None
            self._operation_worker = None

    def _finish_operation(self, operation: str, result: object, error: object) -> None:
        self._active_operation = None

        if error is not None:
            self._handle_operation_error(operation, error)
            return

        status = result
        assert isinstance(status, DemoDeviceStatus)
        self._apply_status(status)

        if operation == "connect":
            self.refresh_timer.start()
            self.statusBar().showMessage("连接成功。")
            return

        if operation == "refresh":
            self.statusBar().showMessage(f"状态已刷新：{status.updated_at}")
            return

        if operation == "write":
            self.statusBar().showMessage(
                f"电流值已更新到 {status.current_ma:.3f} mA"
            )
            self._write_in_flight_ma = None
            if (
                self._pending_current_ma is not None
                and abs(self._pending_current_ma - status.current_ma) > 0.0005
            ):
                self.write_timer.start()
            else:
                self._pending_current_ma = status.current_ma

    def _handle_operation_error(self, operation: str, error: object) -> None:
        message = str(error)

        if operation == "connect":
            self.refresh_timer.stop()
            self.write_timer.stop()
            self._write_in_flight_ma = None
            self._show_error("连接失败", message)
            self._set_idle_state()
            self.current_hint.setText("连接失败，请检查 IP 和端口后重试。")
            self.statusBar().showMessage("连接失败。")
            return

        if operation == "refresh":
            self.refresh_timer.stop()
            self.write_timer.stop()
            self._write_in_flight_ma = None
            self.controller.disconnect()
            self._set_idle_state()
            self._show_error("刷新失败", message)
            self.statusBar().showMessage("刷新失败，已断开连接。")
            return

        if operation == "write":
            self.write_timer.stop()
            self._write_in_flight_ma = None
            self._pending_current_ma = None
            self._show_error("写入电流失败", message)
            self.current_hint.setText("电流写入失败，请检查设备状态后重试。")
            self.statusBar().showMessage("电流写入失败。")

    def _set_controls_enabled(self, enabled: bool) -> None:
        self.connect_button.setEnabled(enabled)
        self.disconnect_button.setEnabled(enabled and self.controller.settings is not None)
        self.refresh_button.setEnabled(enabled and self.controller.settings is not None)
        self.quick_refresh_button.setEnabled(enabled and self.controller.settings is not None)
        self.current_spin.setEnabled(enabled and self.controller.settings is not None)
        self.current_step_combo.setEnabled(enabled and self.controller.settings is not None)

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QWidget {
                background: #f5f7fb;
                color: #102033;
                font-family: "PingFang SC", "Helvetica Neue", sans-serif;
                font-size: 14px;
            }
            QFrame#heroCard {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #13223d, stop:1 #1e4d8c
                );
                border-radius: 20px;
            }
            QLabel#heroTitle {
                color: white;
                font-size: 30px;
                font-weight: 700;
            }
            QLabel#heroSubtitle {
                color: rgba(255, 255, 255, 210);
                font-size: 14px;
            }
            QFrame#panelCard, QFrame#currentCard, QFrame#metricCard {
                background: white;
                border-radius: 18px;
                border: 1px solid #dde5f0;
            }
            QLabel#panelTitle {
                font-size: 20px;
                font-weight: 700;
                color: #163256;
            }
            QLabel#fieldLabel {
                color: #5f7188;
                font-weight: 600;
            }
            QLabel#fieldValue {
                color: #13223d;
                font-weight: 600;
            }
            QLabel#metricTitle {
                color: #5f7188;
                font-size: 13px;
                font-weight: 600;
            }
            QLabel#metricValue {
                color: #0f3f7a;
                font-size: 28px;
                font-weight: 700;
            }
            QLabel#noteText {
                color: #617287;
                line-height: 1.4;
            }
            QLineEdit, QSpinBox, QDoubleSpinBox {
                background: #fbfcfe;
                border: 1px solid #c9d4e3;
                border-radius: 12px;
                padding: 8px 10px;
                min-height: 22px;
            }
            QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
                border: 2px solid #2374d4;
            }
            QPushButton {
                background: #1d66c2;
                color: white;
                border: none;
                border-radius: 12px;
                padding: 10px 16px;
                font-weight: 700;
            }
            QPushButton:hover {
                background: #1656a6;
            }
            QPushButton:disabled {
                background: #aebfd5;
                color: #eef3f8;
            }
            QComboBox {
                background: #fbfcfe;
                border: 1px solid #c9d4e3;
                border-radius: 12px;
                padding: 8px 10px;
                min-height: 22px;
            }
            QStatusBar {
                background: #edf2f8;
            }
            """
        )
