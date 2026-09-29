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
        except NepviewerAuthenticationError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except NepviewerError as err:
            raise UpdateFailed(str(err)) from err
        fetched_at = datetime.now(UTC).isoformat()
        return [{**site, "_fetched_at": fetched_at} for site in sites]
