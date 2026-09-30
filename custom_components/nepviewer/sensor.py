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
    CURRENCY_EURO,
    EntityCategory,
    UnitOfEnergy,
    UnitOfLength,
    UnitOfMass,
    UnitOfPower,
)
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


def _nested_value(site: dict[str, Any], section: str, key: str) -> Any:
    overview = site.get("_overview")
    if not isinstance(overview, dict):
        return None
    values = overview.get(section)
    return values.get(key) if isinstance(values, dict) else None


def _money(site: dict[str, Any], period: str) -> float | None:
    """Return API income or calculate it when the API sends a false zero."""
    energy = _nested_value(site, "production", period)
    raw_money = _nested_value(site, "production", f"{period}Money")
    try:
        energy_value = float(energy)
        money_value = float(raw_money)
    except (TypeError, ValueError):
        return None
    if money_value or not energy_value:
        return money_value

    overview = site.get("_overview") or {}
    detail = site.get("_device_detail") or {}
    price = overview.get("local_electric_price", detail.get("local_electric_price"))
    try:
        return round(energy_value * float(price), 2)
    except (TypeError, ValueError):
        return money_value


def _last_update(site: dict[str, Any]) -> datetime | None:
    overview = site.get("_overview") or {}
    timestamp = overview.get("lastUpdateTime") or site.get("lastUpdateTime")
    try:
        return datetime.fromtimestamp(int(timestamp), UTC)
    except (TypeError, ValueError, OSError):
        return None


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
        key="energy_yesterday",
        translation_key="energy_yesterday",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda site: _nested_value(site, "production", "yesterday"),
    ),
    NepviewerSensorDescription(
        key="energy_month",
        translation_key="energy_month",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda site: _nested_value(site, "production", "month"),
    ),
    NepviewerSensorDescription(
        key="energy_year",
        translation_key="energy_year",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda site: _nested_value(site, "production", "year"),
    ),
    *(
        NepviewerSensorDescription(
            key=f"income_{period}",
            translation_key=f"income_{period}",
            native_unit_of_measurement=CURRENCY_EURO,
            device_class=SensorDeviceClass.MONETARY,
            state_class=SensorStateClass.TOTAL,
            suggested_display_precision=2,
            value_fn=lambda site, period=period: _money(site, period),
        )
        for period in ("today", "yesterday", "month", "total")
    ),
    NepviewerSensorDescription(
        key="co2_savings",
        translation_key="co2_savings",
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda site: _nested_value(site, "environmentalBenefit", "co2"),
    ),
    NepviewerSensorDescription(
        key="driving_distance",
        translation_key="driving_distance",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda site: _nested_value(site, "environmentalBenefit", "car"),
    ),
    NepviewerSensorDescription(
        key="oil_savings",
        translation_key="oil_savings",
        native_unit_of_measurement="bbl",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda site: _nested_value(site, "environmentalBenefit", "oil"),
    ),
    NepviewerSensorDescription(
        key="tree_equivalent",
        translation_key="tree_equivalent",
        native_unit_of_measurement="trees",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda site: _nested_value(site, "environmentalBenefit", "tree"),
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
        site = next(
            (
                candidate
                for index, candidate in enumerate(coordinator.data)
                if site_identifier(candidate, index) == site_id
            ),
            {},
        )
        detail = site.get("_device_detail") or {}
        devices = site.get("sn") or []
        first_device = devices[0] if devices and isinstance(devices[0], dict) else {}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, site_id)},
            name=site_name,
            manufacturer="Northern Electric & Power",
            model=detail.get("modelTitle") or first_device.get("model"),
            serial_number=detail.get("sn") or first_device.get("sn"),
            sw_version=detail.get("version") or None,
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
    def available(self) -> bool:
        """Return whether the site remains present in the API response."""
        return super().available and self._site is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose static API information on the status entity."""
        site = self._site
        if not site or self.entity_description.key != "status":
            return {}
        attributes = {"last_poll": site.get("_fetched_at")}
        detail = site.get("_device_detail") or {}
        devices = site.get("sn") or []
        first_device = devices[0] if devices and isinstance(devices[0], dict) else {}
        attributes.update(
            {
                "last_update": (site.get("_overview") or {}).get("lastUpdate")
                or site.get("lastUpdate"),
                "serial_number": detail.get("sn") or first_device.get("sn"),
                "model": detail.get("modelTitle") or first_device.get("model"),
                "version": detail.get("version"),
                "user": detail.get("userEmail") or site.get("userEmail"),
                "installer": detail.get("installerEmail") or site.get("installerEmail"),
                "country": detail.get("countryName") or site.get("countryName"),
                "timezone": detail.get("timezone"),
                "temperature_unit": detail.get("temperatureUnit"),
                "commissioned": detail.get("isCommission", site.get("isCommission")),
                "register_date": detail.get("registerDate") or site.get("registerDate"),
            }
        )
        return {key: value for key, value in attributes.items() if value is not None}

    @property
    def _site(self) -> dict[str, Any] | None:
        for index, site in enumerate(self.coordinator.data):
            if site_identifier(site, index) == self._site_id:
                return site
        return None
