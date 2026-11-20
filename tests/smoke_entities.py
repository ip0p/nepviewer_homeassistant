"""Exercise real coordinator/platform code with small HA interface stand-ins.
This checks mappings and lifecycle, not Home Assistant runtime compatibility.
"""
import asyncio
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import sys
import types
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parents[1]))
from test_site_data import OVERVIEW


def module(name, **attrs):
    value = types.ModuleType(name)
    value.__dict__.update(attrs)
    sys.modules[name] = value
    return value


class CoordinatorEntity:
    def __class_getitem__(cls, item):
        return cls

    def __init__(self, coordinator):
        self.coordinator = coordinator

    @property
    def available(self):
        return self.coordinator.last_update_success


class DataUpdateCoordinator:
    def __class_getitem__(cls, item):
        return cls

    def __init__(self, hass, **kwargs):
        self.hass = hass
        self.listeners = []
        self.last_update_success = True

    def async_add_listener(self, listener):
        self.listeners.append(listener)
        return lambda: self.listeners.remove(listener)


@dataclass(frozen=True, kw_only=True)
class Description:
    key: str
    translation_key: str = ''
    native_unit_of_measurement: object = None
    device_class: object = None
    state_class: object = None
    entity_category: object = None
    suggested_display_precision: object = None


module('homeassistant')
module('homeassistant.components')
module('homeassistant.components.sensor', SensorDeviceClass=types.SimpleNamespace(
    POWER='power', ENERGY='energy', MONETARY='money', WEIGHT='weight',
    DISTANCE='distance', TIMESTAMP='timestamp'), SensorEntity=type('SensorEntity', (), {}),
    SensorEntityDescription=Description,
    SensorStateClass=types.SimpleNamespace(MEASUREMENT='measurement', TOTAL='total', TOTAL_INCREASING='total_increasing'))
module('homeassistant.const', EntityCategory=types.SimpleNamespace(DIAGNOSTIC='diagnostic'),
    UnitOfEnergy=types.SimpleNamespace(KILO_WATT_HOUR='kWh'),
    UnitOfLength=types.SimpleNamespace(KILOMETERS='km'),
    UnitOfMass=types.SimpleNamespace(KILOGRAMS='kg'),
    UnitOfPower=types.SimpleNamespace(WATT='W'))
module('homeassistant.config_entries', ConfigEntryAuthFailed=type('ConfigEntryAuthFailed', (Exception,), {}))
module('homeassistant.core', HomeAssistant=object)
module('homeassistant.helpers')
module('homeassistant.helpers.device_registry', DeviceInfo=dict)
module('homeassistant.helpers.entity_platform', AddConfigEntryEntitiesCallback=object)
module('homeassistant.helpers.update_coordinator', CoordinatorEntity=CoordinatorEntity,
    DataUpdateCoordinator=DataUpdateCoordinator, UpdateFailed=type('UpdateFailed', (Exception,), {}))
module('homeassistant.util')
module('homeassistant.util.dt', DEFAULT_TIME_ZONE=ZoneInfo('America/New_York'),
    start_of_local_day=lambda: datetime(2026, 11, 15, tzinfo=ZoneInfo('America/New_York')))
package=sys.modules['custom_components.nepviewer']
package.NepviewerConfigEntry=object
sys.modules.pop('custom_components.nepviewer.data', None)
from custom_components.nepviewer import sensor
from custom_components.nepviewer.coordinator import NepviewerCoordinator
from custom_components.nepviewer.api import NepviewerError


class Client:
    async def async_get_sites(self):
        return [{'sid': 'TEST_SITE', 'siteName': 'Test plant', 'now': 999,
                 'todayPower': 99, 'totalPower': 99999,
                 '_overview': {'production': {'yesterday': '1.30'}}}]

    async def async_get_site_overview(self, sid):
        assert sid == 'TEST_SITE'
        return OVERVIEW


hass=types.SimpleNamespace(config=types.SimpleNamespace(currency='EUR'))
coordinator=NepviewerCoordinator(hass, Client())
coordinator.data=asyncio.run(coordinator._async_update_data())
entry=types.SimpleNamespace(runtime_data=coordinator, async_on_unload=lambda callback: None)
entities=[]
asyncio.run(sensor.async_setup_entry(hass, entry, entities.extend))
assert len(entities) == 40  # 16 site + eight times three inverter sensors
ids=[e._attr_unique_id for e in entities]
assert len(set(ids)) == 40
by_key={e.entity_description.key: e for e in entities[:16]}
assert by_key['power'].native_value == 2481
assert by_key['energy_yesterday'].native_value == 6.2
assert by_key['energy_month'].native_value == 134.8
assert round(by_key['income_month'].native_value, 2) == 32.35
assert by_key['income_month']._attr_native_unit_of_measurement == 'USD'
assert by_key['driving_distance'].native_value == 27730
assert by_key['last_update'].native_value.isoformat() == '2026-11-15T15:02:00-05:00'
assert entities[16].native_value == 286
assert entities[17].native_value == 1.097
assert entities[16]._attr_device_info['via_device'] == ('nepviewer', 'TEST_SITE')
assert by_key['power']._attr_unique_id == 'TEST_SITE_power'
coordinator.listeners[0]()
assert len(entities) == 40  # no duplicates across polls
coordinator.data[0]['_site_overview'] = {**OVERVIEW, 'deviceList': []}
assert entities[16].available is False
assert by_key['power'].available is True
coordinator.data[0]['_site_overview'] = {**OVERVIEW, 'deviceList': [
    *OVERVIEW['deviceList'], {'sn': 'NEW', 'now': '10', 'nowUnit': 'W',
                            'today': '.1', 'todayUnit': 'kWh'}]}
coordinator.listeners[0]()
assert len(entities) == 43  # newly discovered inverter
coordinator.last_update_success=False
assert not by_key['power'].available
assert not entities[16].available


class BrokenClient(Client):
    async def async_get_site_overview(self, sid):
        raise NepviewerError('site request failed')

try:
    asyncio.run(NepviewerCoordinator(hass, BrokenClient())._async_update_data())
except sys.modules['homeassistant.helpers.update_coordinator'].UpdateFailed:
    pass
else:
    raise AssertionError('Site failures must not silently show stale device totals')
print('PASS: 40 entities, site/inverter separation, units, currency, discovery, unavailable/error handling')
