"""Data coordinator for NEPViewer."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from homeassistant.config_entries import ConfigEntryAuthFailed
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    NepviewerApiClient,
    NepviewerAuthenticationError,
    NepviewerError,
)
from .const import DOMAIN, UPDATE_INTERVAL_SECONDS

_LOGGER = logging.getLogger(__name__)


class NepviewerCoordinator(DataUpdateCoordinator[list[dict]]):
    """Poll the NEPViewer cloud API."""

    def __init__(self, hass: HomeAssistant, client: NepviewerApiClient) -> None:
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL_SECONDS),
        )
        self.client = client

    async def _async_update_data(self) -> list[dict]:
        try:
            sites = await self.client.async_get_sites()
            if not sites:
                _LOGGER.warning("NEPViewer returned no sites; check this account's site permissions")
            for index, site in enumerate(sites):
                sid = site.get("sid")
                if not isinstance(sid, (str, int)) or not str(sid):
                    raise NepviewerError("Site is missing the sid required by site/overview")
                site["_site_overview"] = await self.client.async_get_site_overview(str(sid))
                for device in site["_site_overview"].get("deviceList", []):
                    if not isinstance(device, dict) or not device.get("sn"):
                        continue
                    try:
                        device["_device_detail"] = await self.client.async_get_device_detail(
                            str(device["sn"])
                        )
                    except NepviewerAuthenticationError:
                        raise
                    except NepviewerError as err:
                        # Optional metadata must not hide valid production readings.
                        _LOGGER.debug("Could not fetch inverter metadata: %s", err)
                _LOGGER.debug(
                    "Site overview received: %s inverter(s)",
                    len(site["_site_overview"].get("deviceList", [])),
                )
        except NepviewerAuthenticationError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except NepviewerError as err:
            raise UpdateFailed(str(err)) from err
        fetched_at = datetime.now(UTC).isoformat()
        return [{**site, "_fetched_at": fetched_at} for site in sites]
