from homeassistant import config_entries
from homeassistant.const import CONF_TOKEN
import voluptuous as vol

DOMAIN = "nepviewer"

class NepviewerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    async def async_step_user(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="Nepviewer", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("token"): str
            })
        )