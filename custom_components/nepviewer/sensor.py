"""Sensors provided by NEPViewer Solar."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    EntityCategory,
    UnitOfEnergy,
    UnitOfLength,
    UnitOfMass,
    UnitOfPower,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import NepviewerConfigEntry
from .api import site_identifier
from .const import DOMAIN
from .data import devices, energy_kwh, income, number, site_value
from .coordinator import NepviewerCoordinator


@dataclass(frozen=True, kw_only=True)
class NepviewerSensorDescription(SensorEntityDescription):
    """Describe a NEPViewer sensor."""

    value_fn: Callable[[dict[str, Any]], Any]
    last_reset_fn: Callable[[], datetime] | None = None


def _nested_value(site: dict[str, Any], section: str, key: str) -> Any:
    overview = site.get("_site_overview") or {}
    values = overview.get(section) or {}
    value = number(values.get(key))
    if value is not None and key == "car" and values.get("carUnit") == "km(*1000)":
        return value * 1000
    return value


def _money(site: dict[str, Any], period: str) -> float | None:
    return income(site.get("_site_overview") or {}, period)


def _power(site: dict[str, Any]) -> float | None:
    production = (site.get("_site_overview") or {}).get("statisticsProduction") or {}
    value = number(production.get("totalNow"))
    factor = {"W": 1, "kW": 1000}.get(production.get("totalNowUnit"))
    return value * factor if value is not None and factor is not None else None


def _start_of_month() -> datetime:
    return dt_util.start_of_local_day().replace(day=1)


def _last_update(site: dict[str, Any]) -> datetime | None:
    overview = site.get("_site_overview") or {}
    timestamp = overview.get("lastUpdateTime") or site.get("lastUpdateTime")
    if timestamp is not None:
        try:
            return datetime.fromtimestamp(int(timestamp), UTC)
        except (TypeError, ValueError, OSError):
            pass
    # Portal supplies a local date/time and the Home Assistant timezone is used.
    try:
        local = datetime.strptime(overview.get("lastUpdate", ""), "%d/%m/%Y %H:%M")
        return local.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)
    except (TypeError, ValueError):
        return None


SENSORS = (
    NepviewerSensorDescription(
        key="power",
        translation_key="power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_power,
    ),
    NepviewerSensorDescription(
        key="energy_today",
        translation_key="energy_today",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda site: site_value(site, "today"),
    ),
    NepviewerSensorDescription(
        key="energy_total",
        translation_key="energy_total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda site: site_value(site, "total"),
    ),
    NepviewerSensorDescription(
        key="energy_yesterday",
        translation_key="energy_yesterday",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=None,
        value_fn=lambda site: site_value(site, "yesterday"),
    ),
    NepviewerSensorDescription(
        key="energy_month",
        translation_key="energy_month",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda site: site_value(site, "month"),
    ),
    NepviewerSensorDescription(
        key="energy_year",
        translation_key="energy_year",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda site: site_value(site, "year"),
    ),
    *(
        NepviewerSensorDescription(
            key=f"income_{period}",
            translation_key=f"income_{period}",
            device_class=SensorDeviceClass.MONETARY,
            # Monetary sensors only allow TOTAL, so periodic ones need a last_reset.
            state_class=SensorStateClass.TOTAL if period != "yesterday" else None,
            suggested_display_precision=2,
            value_fn=lambda site, period=period: _money(site, period),
            last_reset_fn=last_reset_fn,
        )
        for period, last_reset_fn in (
            ("today", dt_util.start_of_local_day),
            ("yesterday", None),
            ("month", _start_of_month),
            ("total", None),
        )
    ),
    NepviewerSensorDescription(
        key="co2_savings",
        translation_key="co2_savings",
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda site: _nested_value(site, "benefit", "co2"),
    ),
    NepviewerSensorDescription(
        key="driving_distance",
        translation_key="driving_distance",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda site: _nested_value(site, "benefit", "car"),
    ),
    NepviewerSensorDescription(
        key="oil_savings",
        translation_key="oil_savings",
        native_unit_of_measurement="bbl",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda site: _nested_value(site, "benefit", "oil"),
    ),
    NepviewerSensorDescription(
        key="tree_equivalent",
        translation_key="tree_equivalent",
        native_unit_of_measurement="trees",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda site: _nested_value(site, "benefit", "tree"),
    ),
    NepviewerSensorDescription(
        key="last_update",
        translation_key="last_update",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_last_update,
    ),
    NepviewerSensorDescription(
        key="status",
        translation_key="status",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda site: (site.get("_site_overview") or {}).get("statusTitle"),
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
    known: set[tuple[str, str, str]] = set()

    def discover() -> None:
        new_entities = []
        for index, site in enumerate(coordinator.data):
            sid = site_identifier(site, index)
            name = _site_name(site, index)
            for description in SENSORS:
                key = (sid, "site", description.key)
                if key not in known:
                    known.add(key)
                    new_entities.append(NepviewerSensor(coordinator, sid, name, description))
            for device in devices(site):
                serial = str(device["sn"])
                for description in INVERTER_SENSORS:
                    key = (sid, serial, description.key)
                    if key not in known:
                        known.add(key)
                        new_entities.append(NepviewerInverterSensor(
                            coordinator, sid, name, device, description))
        if new_entities:
            async_add_entities(new_entities)

    discover()
    entry.async_on_unload(coordinator.async_add_listener(discover))


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
        site = next(
            (
                candidate
                for index, candidate in enumerate(coordinator.data)
                if site_identifier(candidate, index) == site_id
            ),
            {},
        )
        if description.device_class == SensorDeviceClass.MONETARY:
            selected = (site.get("_site_overview") or {}).get("selected") or {}
            self._attr_native_unit_of_measurement = (
                selected.get("currency_unit") or coordinator.hass.config.currency
            )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, site_id)},
            name=site_name,
            manufacturer="Northern Electric & Power",
            model="Solar site",
            configuration_url="https://user.nepviewer.com/",
        )

    @property
    def native_value(self) -> Any:
        """Return the current sensor value."""
        site = self._site
        if site is None:
            return None
        return self.entity_description.value_fn(site)

    @property
    def last_reset(self) -> datetime | None:
        """Return when a periodic total last started from zero."""
        if self.entity_description.last_reset_fn is None:
            return None
        return self.entity_description.last_reset_fn()

    @property
    def available(self) -> bool:
        """Return whether the site remains present in the API response."""
        return super().available and self._site is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose static API information on the status entity."""
        site = self._site
        if not site or self.entity_description.key != "status":
            return {}
        overview = site.get("_site_overview") or {}
        return {
            "last_poll": site.get("_fetched_at"),
            "last_update": overview.get("lastUpdate"),
            "inverter_count": len(devices(site)),
            "data_source": "v2/site/overview",
        }

    @property
    def _site(self) -> dict[str, Any] | None:
        for index, site in enumerate(self.coordinator.data):
            if site_identifier(site, index) == self._site_id:
                return site
        return None


INVERTER_SENSORS = (
    NepviewerSensorDescription(
        key="power", translation_key="power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: _device_power(device),
    ),
    NepviewerSensorDescription(
        key="energy_today", translation_key="energy_today",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda device: energy_kwh(device, "today"),
    ),
    NepviewerSensorDescription(
        key="status", translation_key="status",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.get("statusTitle"),
    ),
)


def _device_power(device):
    value = number(device.get("now"))
    factor = {"W": 1, "kW": 1000}.get(device.get("nowUnit"))
    return value * factor if value is not None and factor is not None else None


class NepviewerInverterSensor(CoordinatorEntity[NepviewerCoordinator], SensorEntity):
    """One inverter's observed power, daily energy, or reported status."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, site_id, site_name, device, description):
        super().__init__(coordinator)
        self._site_id = site_id
        self._serial = str(device["sn"])
        self.entity_description = description
        self._attr_unique_id = f"{site_id}_inverter_{self._serial}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{site_id}_inverter_{self._serial}")},
            via_device=(DOMAIN, site_id),
            name=f"{site_name} inverter {self._serial}",
            manufacturer="Northern Electric & Power",
            model=device.get("modelTitle") or device.get("modelName"),
            serial_number=self._serial,
            configuration_url="https://user.nepviewer.com/",
        )

    @property
    def _device(self):
        for index, site in enumerate(self.coordinator.data):
            if site_identifier(site, index) == self._site_id:
                return next((d for d in devices(site)
                             if str(d["sn"]) == self._serial), None)
        return None

    @property
    def native_value(self):
        device = self._device
        return self.entity_description.value_fn(device) if device is not None else None

    @property
    def available(self):
        return super().available and self._device is not None
