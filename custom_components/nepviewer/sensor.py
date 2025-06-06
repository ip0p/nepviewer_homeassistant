from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator
import aiohttp
import asyncio
import logging
import datetime

DOMAIN = "nepviewer"

class NepviewerCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, session, sn, token, logger):
        super().__init__(hass, logger=logger, name=DOMAIN, update_interval=datetime.timedelta(seconds=60))
        self.session = session
        self.sn = sn
        self.token = token
        self.status = "unknown"

    async def _async_update_data(self):
        headers = {
            "Authorization": self.token,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "de-DE,de;q=0.9,en-DE;q=0.8,en;q=0.7,en-US;q=0.6",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "application/json",
            "Origin": "https://user.nepviewer.com",
            "Pragma": "no-cache",
            "Referer": "https://user.nepviewer.com/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "cross-site",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
            "app": "0",
            "client": "web",
            "lan": "6",
            "oem": "NEP",
            "sec-ch-ua": '"Google Chrome";v="137", "Chromium";v="137", "Not/A)Brand";v="24"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sign": "C513D70171FB45FD85BE759FABDC6715"
        }

        payload = {
            "page": {
                "size": 10,
                "num": 0
            },
            "filters": {
                "keywords": "",
                "site_name": "",
                "user_email": "",
                "installer_email": "",
                "country_code": "",
                "created_start_date": "",
                "created_end_date": "",
                "street": ""
            },
            "sort": []
        }

        self.logger.info("Making request to NEP site/listWithSN API")
        async with self.session.post(
            "https://api.nepviewer.net/v2/site/listWithSN",
            headers=headers,
            json=payload
        ) as resp:
            self.logger.info(f"Response status: {resp.status}")
            response_data = await resp.json()
            self.logger.debug(f"Response JSON: {response_data}")
            self.status = "ok" if resp.status == 200 else "error"
            return response_data

class NepviewerSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, name, value_path, unit):
        super().__init__(coordinator)
        self._attr_name = name
        self._attr_unique_id = f"nepviewer_{name.lower().replace(' ', '_')}"
        self._value_path = value_path
        self._attr_native_unit_of_measurement = unit

    def _get_value_from_path(self, data, path):
        keys = path.split(".")
        for key in keys:
            if isinstance(data, list):
                key = int(key)
                data = data[key] if len(data) > key else None
            elif isinstance(data, dict):
                data = data.get(key)
            else:
                return None
        return data

    @property
    def native_value(self):
        return self._get_value_from_path(self.coordinator.data.get("data", {}), self._value_path)

    @property
    def extra_state_attributes(self):
        return {
            "status": self.coordinator.status,
            "last_updated": self._get_value_from_path(self.coordinator.data.get("data", {}), "list.0.lastUpdate")
        }

class NepviewerStatusSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_name = "Nepviewer Status"
        self._attr_unique_id = "nepviewer_status"

    @property
    def native_value(self):
        return self.coordinator.status

async def async_setup_entry(hass, entry, async_add_entities):
    session = aiohttp.ClientSession()
    sn = entry.data.get("sn")
    token = entry.data.get("token")
    logger = logging.getLogger(__name__)

    if not sn or not token:
        logger.error("Missing 'sn' or 'token' in configuration.")
        return False

    coordinator = NepviewerCoordinator(hass, session, sn, token, logger)
    await coordinator.async_config_entry_first_refresh()

    sensors = [
        NepviewerSensor(coordinator, "Solar Power", "list.0.now", "W"),
        NepviewerSensor(coordinator, "Solar Today", "list.0.todayPower", "kWh"),
        NepviewerSensor(coordinator, "Solar Total", "list.0.totalPower", "kWh"),
        NepviewerSensor(coordinator, "Solar Status", "list.0.statusTitle", None),
        NepviewerStatusSensor(coordinator)
    ]

    async_add_entities(sensors)
    await session.close()
