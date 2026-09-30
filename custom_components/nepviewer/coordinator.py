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
    site_identifier,
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
            for index, site in enumerate(sites):
                site_id = site_identifier(site, index)
                devices = site.get("sn")
                if not isinstance(devices, list) or not devices:
                    continue
                serial_number = devices[0].get("sn")
                if not serial_number:
                    continue
                try:
                    site["_overview"] = await self.client.async_get_device_overview(
                        str(serial_number)
                    )
                except NepviewerAuthenticationError:
                    raise
                except NepviewerError as err:
                    _LOGGER.debug("Could not fetch overview for %s: %s", site_id, err)
                try:
                    site["_device_detail"] = await self.client.async_get_device_detail(
                        str(serial_number)
                    )
                except NepviewerAuthenticationError:
                    raise
                except NepviewerError as err:
                    _LOGGER.debug(
                        "Could not fetch device details for %s: %s", site_id, err
                    )
        except NepviewerAuthenticationError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except NepviewerError as err:
            raise UpdateFailed(str(err)) from err
        fetched_at = datetime.now(UTC).isoformat()
        return [{**site, "_fetched_at": fetched_at} for site in sites]
