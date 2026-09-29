"""NEPViewer Solar integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntry

from .api import NepviewerApiClient, site_identifier
from .const import CONF_ACCOUNT, CONF_COMPANY_ID, DOMAIN
from .coordinator import NepviewerCoordinator

PLATFORMS = ["sensor"]

type NepviewerConfigEntry = ConfigEntry[NepviewerCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: NepviewerConfigEntry) -> bool:
    """Set up NEPViewer from a config entry."""
    client = NepviewerApiClient(
        async_get_clientsession(hass),
        account=entry.data.get(CONF_ACCOUNT),
        password=entry.data.get(CONF_PASSWORD),
        token=entry.data.get(CONF_TOKEN),
        company_id=entry.data.get(CONF_COMPANY_ID, 0),
    )
    coordinator = NepviewerCoordinator(hass, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: NepviewerConfigEntry) -> bool:
    """Unload a NEPViewer config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    entry: NepviewerConfigEntry,
    device_entry: DeviceEntry,
) -> bool:
    """Allow removal of devices left behind by an obsolete site identifier."""
    active_identifiers = {
        (DOMAIN, site_identifier(site, index))
        for index, site in enumerate(entry.runtime_data.data)
    }
    return not bool(active_identifiers & device_entry.identifiers)
