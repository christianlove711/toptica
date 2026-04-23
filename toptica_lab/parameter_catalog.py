from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ParameterDefinition:
    group: str
    name: str
    access: str
    description: str


DEFAULT_PARAMETER_CATALOG: list[ParameterDefinition] = [
    ParameterDefinition("Identity", "system-type", "R", "Device family or controller type."),
    ParameterDefinition("Identity", "serial-number", "R", "Hardware serial number."),
    ParameterDefinition("Identity", "system-label", "R/W", "Human-readable system label."),
    ParameterDefinition("Identity", "ul", "R", "Current user level."),
    ParameterDefinition("Health", "uptime-txt", "R", "Controller uptime as formatted text."),
    ParameterDefinition("Laser", "laser1:dl:cc:current-act", "R", "Actual diode current."),
    ParameterDefinition("Laser", "laser1:dl:cc:current-set", "R/W", "Requested diode current setpoint."),
    ParameterDefinition("Laser", "laser1:dl:cc:enabled", "R/W", "Current controller enabled flag."),
    ParameterDefinition("Laser", "laser1:dl:tc:temp-act", "R", "Actual diode temperature."),
    ParameterDefinition("Laser", "laser1:dl:tc:temp-set", "R/W", "Diode temperature setpoint."),
    ParameterDefinition("Laser", "laser1:emission", "R/W", "Laser emission state."),
    ParameterDefinition("Scan", "laser1:scan:enabled", "R/W", "WideScan or scan subsystem enabled."),
    ParameterDefinition("Scan", "laser1:scan:output-channel", "R/W", "Selected scan output channel."),
    ParameterDefinition("Lock", "laser1:dl:lock:state", "R", "Lock controller state."),
    ParameterDefinition("Lock", "laser1:dl:lock:enabled", "R/W", "Lock controller enabled flag."),
    ParameterDefinition("Recorder", "laser1:recorder:data:recorded-sample-count", "R", "Recorded sample count."),
    ParameterDefinition("Recorder", "laser1:recorder:data:recorded-sampling-interval", "R", "Recorder sample interval."),
    ParameterDefinition("System", "display:brightness", "R/W", "Front panel display brightness."),
    ParameterDefinition("Messages", "system-messages:count", "R", "Number of system messages."),
]
