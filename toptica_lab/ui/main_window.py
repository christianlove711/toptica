from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QStatusBar,
    QTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from toptica_lab.controller import ConnectionSettings, ControllerError, LaserStatus, TOOPTICAController
from toptica_lab.favorites import FavoriteParameter, FavoriteStore
from toptica_lab.parameter_catalog import DEFAULT_PARAMETER_CATALOG, ParameterDefinition


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.controller = TOOPTICAController()
        self.favorite_store = FavoriteStore()
        self.favorite_parameters = self.favorite_store.load()
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(2000)
        self.refresh_timer.timeout.connect(self.refresh_status)

        self.setWindowTitle("TOOPTICA Lab Control")
        self.resize(880, 520)
        self._build_ui()
        self._set_idle_state()

    def _build_ui(self) -> None:
        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        layout.addWidget(self._build_connection_panel())
        self.pages = QTabWidget()
        self.pages.addTab(self._build_status_panel(), "Overview")
        self.pages.addTab(self._build_parameter_browser_panel(), "Parameter Browser")
        self.pages.addTab(self._build_favorites_panel(), "Favorites")
        layout.addWidget(self.pages)
        layout.addStretch(1)

        self.setCentralWidget(central)
        self.setStatusBar(QStatusBar(self))
        self.statusBar().showMessage("Ready.")

    def _build_connection_panel(self) -> QWidget:
        box = QGroupBox("Connection")
        form = QFormLayout(box)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.connection_type_input = QComboBox()
        self.connection_type_input.addItem("Network", "network")
        self.connection_type_input.addItem("Serial", "serial")
        self.connection_type_input.currentIndexChanged.connect(self._update_connection_fields)

        self.host_input = QLineEdit("demo")
        self.host_input.setPlaceholderText("192.168.178.12 or device label")

        self.serial_port_input = QLineEdit("/dev/tty.usbserial")
        self.serial_port_input.setPlaceholderText("/dev/tty.usbserial or COM3")

        self.baudrate_input = QSpinBox()
        self.baudrate_input.setRange(1200, 3000000)
        self.baudrate_input.setValue(115200)

        self.timeout_input = QSpinBox()
        self.timeout_input.setRange(1, 60)
        self.timeout_input.setValue(5)
        self.timeout_input.setSuffix(" s")

        self.command_port_input = QSpinBox()
        self.command_port_input.setRange(0, 65535)
        self.command_port_input.setValue(1998)

        self.monitor_port_input = QSpinBox()
        self.monitor_port_input.setRange(0, 65535)
        self.monitor_port_input.setValue(1999)

        self.demo_checkbox = QCheckBox("Demo mode")
        self.demo_checkbox.setChecked(True)

        button_row = QHBoxLayout()
        self.connect_button = QPushButton("Connect")
        self.connect_button.clicked.connect(self.handle_connect)
        self.disconnect_button = QPushButton("Disconnect")
        self.disconnect_button.clicked.connect(self.handle_disconnect)
        self.refresh_button = QPushButton("Refresh now")
        self.refresh_button.clicked.connect(self.refresh_status)
        button_row.addWidget(self.connect_button)
        button_row.addWidget(self.disconnect_button)
        button_row.addWidget(self.refresh_button)
        button_row.addStretch(1)

        form.addRow("Connection type", self.connection_type_input)
        form.addRow("Host", self.host_input)
        form.addRow("Serial port", self.serial_port_input)
        form.addRow("Baudrate", self.baudrate_input)
        form.addRow("Timeout", self.timeout_input)
        form.addRow("Command port", self.command_port_input)
        form.addRow("Monitor port", self.monitor_port_input)
        form.addRow("", self.demo_checkbox)
        form.addRow("", button_row)

        self._update_connection_fields()
        return box

    def _build_status_panel(self) -> QWidget:
        box = QGroupBox("Laser Overview")
        grid = QGridLayout(box)
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(14)

        self.connection_value = QLabel("-")
        self.mode_value = QLabel("-")
        self.host_value = QLabel("-")
        self.type_value = QLabel("-")
        self.serial_value = QLabel("-")
        self.label_value = QLabel("-")
        self.user_level_value = QLabel("-")
        self.uptime_value = QLabel("-")
        self.current_value = QLabel("-")
        self.updated_value = QLabel("-")
        self.message_value = QLabel("Not connected.")
        self.message_value.setWordWrap(True)

        rows = [
            ("Connection", self.connection_value),
            ("Mode", self.mode_value),
            ("Host", self.host_value),
            ("System type", self.type_value),
            ("Serial number", self.serial_value),
            ("System label", self.label_value),
            ("User level", self.user_level_value),
            ("Uptime", self.uptime_value),
            ("Diode current", self.current_value),
            ("Last updated", self.updated_value),
            ("Message", self.message_value),
        ]

        for index, (title, value) in enumerate(rows):
            title_label = QLabel(title)
            title_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            grid.addWidget(title_label, index, 0)
            grid.addWidget(value, index, 1)

        return box

    def _build_parameter_browser_panel(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        browser_box = QGroupBox("Recommended Parameters")
        browser_layout = QVBoxLayout(browser_box)

        filter_row = QHBoxLayout()
        self.parameter_filter_input = QLineEdit()
        self.parameter_filter_input.setPlaceholderText("Filter by name, group, or description")
        self.parameter_filter_input.textChanged.connect(self._populate_parameter_table)
        self.refresh_parameters_button = QPushButton("Refresh listed values")
        self.refresh_parameters_button.clicked.connect(self.refresh_parameter_browser)
        self.add_selected_button = QPushButton("Add selected to favorites")
        self.add_selected_button.clicked.connect(self.add_selected_parameter_to_favorites)
        filter_row.addWidget(self.parameter_filter_input)
        filter_row.addWidget(self.refresh_parameters_button)
        filter_row.addWidget(self.add_selected_button)
        browser_layout.addLayout(filter_row)

        self.parameter_table = QTableWidget(0, 5)
        self.parameter_table.setHorizontalHeaderLabels(
            ["Group", "Parameter", "Access", "Description", "Current Value"]
        )
        self.parameter_table.setAlternatingRowColors(True)
        self.parameter_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.parameter_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.parameter_table.verticalHeader().setVisible(False)
        header = self.parameter_table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft)
        browser_layout.addWidget(self.parameter_table)

        probe_box = QGroupBox("Parameter Probe")
        probe_form = QFormLayout(probe_box)
        probe_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.probe_input = QLineEdit()
        self.probe_input.setPlaceholderText("laser1:dl:cc:current-act")
        self.probe_button = QPushButton("Read parameter")
        self.probe_button.clicked.connect(self.probe_parameter)
        self.favorite_probe_button = QPushButton("Save probe to favorites")
        self.favorite_probe_button.clicked.connect(self.add_probe_to_favorites)
        self.probe_value = QLabel("Enter a parameter name and connect to a device.")
        self.probe_value.setWordWrap(True)
        self.probe_value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        probe_form.addRow("Parameter", self.probe_input)
        probe_form.addRow("", self.probe_button)
        probe_form.addRow("", self.favorite_probe_button)
        probe_form.addRow("Value", self.probe_value)

        layout.addWidget(browser_box)
        layout.addWidget(probe_box)

        self._populate_parameter_table()
        return page

    def _build_favorites_panel(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        favorites_box = QGroupBox("Favorite Parameters")
        favorites_layout = QVBoxLayout(favorites_box)

        button_row = QHBoxLayout()
        self.refresh_favorites_button = QPushButton("Refresh favorites")
        self.refresh_favorites_button.clicked.connect(self.refresh_favorites)
        self.remove_favorite_button = QPushButton("Remove selected")
        self.remove_favorite_button.clicked.connect(self.remove_selected_favorite)
        button_row.addWidget(self.refresh_favorites_button)
        button_row.addWidget(self.remove_favorite_button)
        button_row.addStretch(1)
        favorites_layout.addLayout(button_row)

        self.favorites_table = QTableWidget(0, 6)
        self.favorites_table.setHorizontalHeaderLabels(
            ["Group", "Parameter", "Access", "Description", "Notes", "Current Value"]
        )
        self.favorites_table.setAlternatingRowColors(True)
        self.favorites_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.favorites_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.favorites_table.verticalHeader().setVisible(False)
        header = self.favorites_table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft)
        favorites_layout.addWidget(self.favorites_table)

        layout.addWidget(favorites_box)
        self._populate_favorites_table()
        return page

    def handle_connect(self) -> None:
        settings = ConnectionSettings(
            connection_type=self.connection_type_input.currentData(),
            host=self.host_input.text().strip(),
            serial_port=self.serial_port_input.text().strip(),
            baudrate=self.baudrate_input.value(),
            timeout=self.timeout_input.value(),
            command_line_port=self.command_port_input.value(),
            monitoring_line_port=self.monitor_port_input.value(),
            demo_mode=self.demo_checkbox.isChecked(),
        )

        try:
            status = self.controller.connect(settings)
        except ControllerError as exc:
            self._show_error("Connection failed", str(exc))
            self._set_idle_state()
            return

        self._apply_status(status)
        self.refresh_timer.start()
        self.statusBar().showMessage("Connected.")
        self.refresh_parameter_browser()

    def handle_disconnect(self) -> None:
        self.refresh_timer.stop()
        self.controller.disconnect()
        self._set_idle_state()
        self.statusBar().showMessage("Disconnected.")

    def refresh_status(self) -> None:
        if not self.controller.settings:
            return

        try:
            status = self.controller.read_basic_status()
        except ControllerError as exc:
            self.refresh_timer.stop()
            self._show_error("Refresh failed", str(exc))
            self._set_idle_state()
            self.statusBar().showMessage("Disconnected after refresh failure.")
            return

        self._apply_status(status)
        self.statusBar().showMessage(f"Last refresh: {status.last_updated}")

    def _apply_status(self, status: LaserStatus) -> None:
        self.connection_value.setText("Connected" if status.connected else "Disconnected")
        self.mode_value.setText(status.mode)
        self.host_value.setText(status.host)
        self.type_value.setText(status.system_type)
        self.serial_value.setText(status.serial_number)
        self.label_value.setText(status.system_label)
        self.user_level_value.setText(status.user_level)
        self.uptime_value.setText(status.uptime_text)
        self.current_value.setText(status.diode_current_ma)
        self.updated_value.setText(status.last_updated)
        self.message_value.setText(status.message)

        self.connect_button.setEnabled(False)
        self.disconnect_button.setEnabled(True)
        self.refresh_button.setEnabled(True)
        self.refresh_parameters_button.setEnabled(True)
        self.add_selected_button.setEnabled(True)
        self.probe_button.setEnabled(True)
        self.favorite_probe_button.setEnabled(True)
        self.refresh_favorites_button.setEnabled(True)
        self.remove_favorite_button.setEnabled(True)

    def _set_idle_state(self) -> None:
        for label in (
            self.connection_value,
            self.mode_value,
            self.host_value,
            self.type_value,
            self.serial_value,
            self.label_value,
            self.user_level_value,
            self.uptime_value,
            self.current_value,
            self.updated_value,
        ):
            label.setText("-")

        self.message_value.setText("Not connected.")
        self.probe_value.setText("Enter a parameter name and connect to a device.")
        self.connect_button.setEnabled(True)
        self.disconnect_button.setEnabled(False)
        self.refresh_button.setEnabled(False)
        self.refresh_parameters_button.setEnabled(False)
        self.add_selected_button.setEnabled(False)
        self.probe_button.setEnabled(False)
        self.favorite_probe_button.setEnabled(False)
        self.refresh_favorites_button.setEnabled(False)
        self.remove_favorite_button.setEnabled(False)
        self._populate_parameter_table({})
        self._populate_favorites_table({})

    def _update_connection_fields(self) -> None:
        is_network = self.connection_type_input.currentData() == "network"
        self.host_input.setEnabled(is_network)
        self.command_port_input.setEnabled(is_network)
        self.monitor_port_input.setEnabled(is_network)
        self.serial_port_input.setEnabled(not is_network)
        self.baudrate_input.setEnabled(not is_network)

    def refresh_parameter_browser(self) -> None:
        try:
            values = self.controller.read_parameters(
                [parameter.name for parameter in self._filtered_catalog()]
            )
        except ControllerError as exc:
            self._show_error("Parameter refresh failed", str(exc))
            return

        self._populate_parameter_table(values)

    def probe_parameter(self) -> None:
        parameter = self.probe_input.text().strip()
        if not parameter:
            self._show_error("Missing parameter", "Enter a parameter name to read.")
            return

        try:
            value = self.controller.read_parameter(parameter)
        except ControllerError as exc:
            self._show_error("Parameter read failed", str(exc))
            return

        self.probe_value.setText(value)
        self.statusBar().showMessage(f"Read parameter: {parameter}")

    def add_selected_parameter_to_favorites(self) -> None:
        selected_row = self.parameter_table.currentRow()
        if selected_row < 0:
            self._show_error("No selection", "Select a parameter row first.")
            return

        catalog = self._filtered_catalog()
        if selected_row >= len(catalog):
            self._show_error("Selection error", "The selected parameter row is invalid.")
            return

        selected = catalog[selected_row]
        favorite = self._prompt_favorite_details(
            FavoriteParameter(
                name=selected.name,
                group=selected.group,
                access=selected.access,
                description=selected.description,
            )
        )
        if favorite is None:
            return

        self._upsert_favorite(favorite)
        self.statusBar().showMessage(f"Saved favorite: {favorite.name}")

    def add_probe_to_favorites(self) -> None:
        parameter = self.probe_input.text().strip()
        if not parameter:
            self._show_error("Missing parameter", "Read or enter a parameter before saving.")
            return

        favorite = self._prompt_favorite_details(FavoriteParameter(name=parameter))
        if favorite is None:
            return

        self._upsert_favorite(favorite)
        self.statusBar().showMessage(f"Saved favorite: {favorite.name}")

    def refresh_favorites(self) -> None:
        if not self.favorite_parameters:
            self._populate_favorites_table({})
            return

        try:
            values = self.controller.read_parameters([item.name for item in self.favorite_parameters])
        except ControllerError as exc:
            self._show_error("Favorite refresh failed", str(exc))
            return

        self._populate_favorites_table(values)

    def remove_selected_favorite(self) -> None:
        selected_row = self.favorites_table.currentRow()
        if selected_row < 0:
            self._show_error("No selection", "Select a favorite row first.")
            return

        if selected_row >= len(self.favorite_parameters):
            self._show_error("Selection error", "The selected favorite row is invalid.")
            return

        removed = self.favorite_parameters.pop(selected_row)
        self.favorite_store.save(self.favorite_parameters)
        self._populate_favorites_table()
        self.statusBar().showMessage(f"Removed favorite: {removed.name}")

    def _filtered_catalog(self) -> list[ParameterDefinition]:
        query = self.parameter_filter_input.text().strip().lower()
        if not query:
            return DEFAULT_PARAMETER_CATALOG

        return [
            parameter
            for parameter in DEFAULT_PARAMETER_CATALOG
            if query in parameter.group.lower()
            or query in parameter.name.lower()
            or query in parameter.description.lower()
        ]

    def _populate_parameter_table(self, values: dict[str, str] | None = None) -> None:
        values = values or {}
        catalog = self._filtered_catalog()
        self.parameter_table.setRowCount(len(catalog))

        for row, parameter in enumerate(catalog):
            row_values = [
                parameter.group,
                parameter.name,
                parameter.access,
                parameter.description,
                values.get(parameter.name, "-"),
            ]
            for column, value in enumerate(row_values):
                self.parameter_table.setItem(row, column, QTableWidgetItem(value))

        self.parameter_table.resizeColumnsToContents()

    def _populate_favorites_table(self, values: dict[str, str] | None = None) -> None:
        values = values or {}
        self.favorites_table.setRowCount(len(self.favorite_parameters))

        for row, favorite in enumerate(self.favorite_parameters):
            row_values = [
                favorite.group,
                favorite.name,
                favorite.access,
                favorite.description,
                favorite.notes,
                values.get(favorite.name, "-"),
            ]
            for column, value in enumerate(row_values):
                self.favorites_table.setItem(row, column, QTableWidgetItem(value))

        self.favorites_table.resizeColumnsToContents()

    def _upsert_favorite(self, favorite: FavoriteParameter) -> None:
        existing_index = next(
            (index for index, item in enumerate(self.favorite_parameters) if item.name == favorite.name),
            None,
        )
        if existing_index is None:
            self.favorite_parameters.append(favorite)
        else:
            self.favorite_parameters[existing_index] = favorite

        self.favorite_parameters.sort(key=lambda item: (item.group.lower(), item.name.lower()))
        self.favorite_store.save(self.favorite_parameters)
        self._populate_favorites_table()

    def _prompt_favorite_details(self, favorite: FavoriteParameter) -> FavoriteParameter | None:
        dialog = FavoriteParameterDialog(favorite, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        try:
            return dialog.favorite_parameter()
        except ValueError as exc:
            self._show_error("Invalid favorite", str(exc))
            return None

    def _show_error(self, title: str, detail: str) -> None:
        QMessageBox.critical(self, title, detail)


class FavoriteParameterDialog(QDialog):
    def __init__(self, favorite: FavoriteParameter, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Save Favorite Parameter")
        self._favorite = favorite

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_input = QLineEdit(favorite.name)
        self.group_input = QLineEdit(favorite.group)
        self.access_input = QLineEdit(favorite.access)
        self.description_input = QLineEdit(favorite.description)
        self.notes_input = QTextEdit(favorite.notes)
        self.notes_input.setFixedHeight(100)

        form.addRow("Parameter", self.name_input)
        form.addRow("Group", self.group_input)
        form.addRow("Access", self.access_input)
        form.addRow("Description", self.description_input)
        form.addRow("Notes", self.notes_input)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def favorite_parameter(self) -> FavoriteParameter:
        name = self.name_input.text().strip()
        if not name:
            raise ValueError("Parameter name cannot be empty.")
        return FavoriteParameter(
            name=name,
            group=self.group_input.text().strip() or "Custom",
            access=self.access_input.text().strip() or "Unknown",
            description=self.description_input.text().strip(),
            notes=self.notes_input.toPlainText().strip(),
        )
