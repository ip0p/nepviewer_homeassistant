"""Tests for NEPViewer sensor descriptions."""

import ast
from pathlib import Path

SENSOR_PATH = (
    Path(__file__).parents[1]
    / "custom_components"
    / "nepviewer"
    / "sensor.py"
)


def test_energy_sensor_state_classes():
    module = ast.parse(SENSOR_PATH.read_text())
    sensors = next(
        node.value
        for node in module.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "SENSORS"
            for target in node.targets
        )
    )
    energy_sensors = [
        node
        for node in ast.walk(sensors)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "NepviewerSensorDescription"
        and any(
            keyword.arg == "device_class"
            and isinstance(keyword.value, ast.Attribute)
            and keyword.value.attr == "ENERGY"
            for keyword in node.keywords
        )
    ]

    assert energy_sensors
    for sensor in energy_sensors:
        key = next(k.value.value for k in sensor.keywords if k.arg == "key")
        state_class = next(k.value for k in sensor.keywords if k.arg == "state_class")
        if key == "energy_yesterday":
            assert isinstance(state_class, ast.Constant) and state_class.value is None
        else:
            assert state_class.attr == "TOTAL_INCREASING"
