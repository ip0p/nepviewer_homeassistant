from homeassistant.config_entries import ConfigEntry, ConfigEntryNotReady
from homeassistant.core import HomeAssistant
import aiohttp
import logging

DOMAIN = "nepviewer"

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up nepviewer from a config entry."""
    token = entry.data.get("token")
    
    if not token:
        raise ConfigEntryNotReady("Missing 'token' in configuration")
    
    # Test API connectivity before setting up platforms
    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": token,
                "Accept": "application/json, text/plain, */*",
                "Content-Type": "application/json",
                "app": "0",
                "client": "web",
                "oem": "NEP",
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
            
            logging.getLogger(__name__).info("Testing NEP API connectivity during setup")
            async with session.post(
                "https://api.nepviewer.net/v2/site/listWithSN",
                headers=headers,
                json=payload
            ) as resp:
                if resp.status != 200:
                    raise ConfigEntryNotReady(f"NEP API not accessible (status: {resp.status})")
                
                logging.getLogger(__name__).info("NEP API connectivity test successful")
                
    except aiohttp.ClientError as err:
        raise ConfigEntryNotReady(f"Failed to connect to NEP API: {err}")
    except Exception as err:
        raise ConfigEntryNotReady(f"Unexpected error during NEP API test: {err}")
    
    # API is accessible, proceed with platform setup
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_forward_entry_unload(entry, "sensor")
