from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator
import aiohttp
import asyncio

DOMAIN = "nepviewer"

class NepviewerCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, session, sn, token):
        super().__init__(hass, name=DOMAIN, update_interval=60)
        self.session = session
        self.sn = sn
        self.token = token
        self.status = "unknown"

    async def _async_update_data(self):
        headers = {
            "Authorization": self.token,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        payload = {"sn": self.sn}
        async with self.session.post(
            "https://api.nepviewer.net/v2/device/statistics/overview",
            headers=headers,
            json=payload
        ) as resp:
            if resp.status == 200:
                self.status = "ok"
            else:
                self.status = "error"
            return await resp.json()

class NepviewerSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, name, value_path, unit):
        super().__init__(coordinator)
        self._attr_name = name
        self._value_path = value_path
        self._attr_unit_of_measurement = unit

    @property
    def state(self):
        data = self.coordinator.data.get("data", {})
        for key in self._value_path.split("."):
            data = data.get(key, {})
        return data or None

    @property
    def extra_state_attributes(self):
        return {"status": self.coordinator.status}

class NepviewerStatusSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_name = "Nepviewer Status"

    @property
    def state(self):
        return self.coordinator.status

async def async_setup_entry(hass, entry, async_add_entities):
    session = aiohttp.ClientSession()
    sn = entry.data["sn"]
    token = entry.data["token"]
    coordinator = NepviewerCoordinator(hass, session, sn, token)
    await coordinator.async_config_entry_first_refresh()

    sensors = [
        NepviewerSensor(coordinator, "Solar Power", "totalNow", "W"),
        NepviewerSensor(coordinator, "Solar Today", "production.today", "kWh"),
        NepviewerSensor(coordinator, "Solar Total", "production.total", "kWh"),
        NepviewerStatusSensor(coordinator)
    ]

    async_add_entities(sensors)
