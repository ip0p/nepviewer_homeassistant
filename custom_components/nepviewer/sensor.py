"""Sensors provided by NEPViewer Solar."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import NepviewerConfigEntry
from .api import site_identifier
from .const import DOMAIN
from .coordinator import NepviewerCoordinator


@dataclass(frozen=True, kw_only=True)
class NepviewerSensorDescription(SensorEntityDescription):
    """Describe a NEPViewer sensor."""

    value_fn: Callable[[dict[str, Any]], Any]


SENSORS = (
    NepviewerSensorDescription(
        key="power",
        translation_key="power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda site: site.get("now"),
    ),
    NepviewerSensorDescription(
        key="energy_today",
        translation_key="energy_today",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda site: site.get("todayPower"),
    ),
    NepviewerSensorDescription(
        key="energy_total",
        translation_key="energy_total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda site: site.get("totalPower"),
    ),
    NepviewerSensorDescription(
        key="status",
        translation_key="status",
        value_fn=lambda site: site.get("statusTitle"),
    ),
)


def _site_name(site: dict[str, Any], index: int) -> str:
    for key in ("siteName", "site_name", "name"):
        value = site.get(key)
        if value:
            return str(value)
    return f"NEPViewer Solar {index + 1}"


async def async_setup_entry(
    hass,
    entry: NepviewerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up NEPViewer sensor entities."""
    coordinator = entry.runtime_data
    async_add_entities(
        NepviewerSensor(coordinator, site_id, site_name, description)
        for index, site in enumerate(coordinator.data)
        for site_id, site_name in [
            (site_identifier(site, index), _site_name(site, index))
        ]
        for description in SENSORS
    )


class NepviewerSensor(CoordinatorEntity[NepviewerCoordinator], SensorEntity):
    """Representation of one value from a NEPViewer solar site."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: NepviewerCoordinator,
        site_id: str,
        site_name: str,
        description: NepviewerSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._site_id = site_id
        self._attr_unique_id = f"{site_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, site_id)},
            name=site_name,
            manufacturer="Northern Electric & Power",
            model="NEPViewer solar site",
        )

    @property
    def native_value(self) -> Any:
        """Return the current sensor value."""
        site = self._site
        if site is None:
            return None
        return self.entity_description.value_fn(site)

    @property
    def available(self) -> bool:
        """Return whether the site remains present in the API response."""
        return super().available and self._site is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the API's last-update timestamp."""
        site = self._site
        return (
            {
                "last_update": site.get("lastUpdate"),
                "last_poll": site.get("_fetched_at"),
            }
            if site
            else {}
        )

    @property
    def _site(self) -> dict[str, Any] | None:
        for index, site in enumerate(self.coordinator.data):
            if site_identifier(site, index) == self._site_id:
                return site
        return None
