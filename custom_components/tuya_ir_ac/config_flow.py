from homeassistant import config_entries
import voluptuous as vol
import ipaddress
from .const import DOMAIN, CONF_AC_NAME, CONF_DEVICE_ID, CONF_DEVICE_LOCAL_KEY, CONF_DEVICE_IP, CONF_DEVICE_VERSION, CONF_DEVICE_MODEL, DEVICE_MODELS, DEVICE_VERSIONS, CONF_TEMPERATURE_SENSOR

class TuyaIrClimateConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Custom Climate entegrasyonu için config flow."""

    async def async_step_user(self, user_input=None):
        """İlk adımı yönet."""
        errors = {}
        if user_input is not None:

            if not user_input[CONF_AC_NAME]:
                errors[CONF_AC_NAME] = "device_ac_name"

            if not user_input[CONF_DEVICE_ID]:
                errors[CONF_DEVICE_ID] = "device_id_required"

            if not user_input[CONF_DEVICE_LOCAL_KEY]:
                errors[CONF_DEVICE_LOCAL_KEY] = "device_local_key_required"

            if not user_input[CONF_DEVICE_IP]:
                errors[CONF_DEVICE_IP] = "device_ip_required"

            try:
                ipaddress.ip_address(user_input[CONF_DEVICE_IP])
            except ipaddress.AddressValueError:
                errors[CONF_DEVICE_IP] = "invalid_ip_address"

            if not user_input[CONF_DEVICE_VERSION]:
                errors[CONF_DEVICE_VERSION] = "device_version_required"

            if not user_input[CONF_DEVICE_MODEL]:
                errors[CONF_DEVICE_MODEL] = "device_device_model_required"

            if not errors:
                await self.async_set_unique_id(user_input[CONF_DEVICE_ID])
                self._abort_if_unique_id_configured(updates=True)
                return self.async_create_entry(title=user_input[CONF_AC_NAME], data=user_input)

        data_schema = vol.Schema({
            vol.Required(CONF_AC_NAME): str,
            vol.Required(CONF_DEVICE_ID): str,
            vol.Required(CONF_DEVICE_LOCAL_KEY): str,
            vol.Required(CONF_DEVICE_IP): str,
            vol.Required(CONF_DEVICE_VERSION): vol.In(DEVICE_VERSIONS),
            vol.Required(CONF_DEVICE_MODEL): vol.In(DEVICE_MODELS),
            vol.Optional(CONF_TEMPERATURE_SENSOR, default=""): str,
        })

        return self.async_show_form(step_id="user", data_schema=data_schema, errors=errors)

    @staticmethod
    def async_get_options_flow(config_entry):
        return TuyaIrClimateOptionsFlow(config_entry)

class TuyaIrClimateOptionsFlow(config_entries.OptionsFlow):
    """Custom Climate entegrasyonu için seçenekler akışı."""

    def __init__(self, config_entry):
        """Seçenekler akışını başlat."""
        self.config_entry = config_entry

    def _get_option_value(self, option):
        return self.config_entry.options.get(option, self.config_entry.data.get(option))        

    async def async_step_init(self, user_input=None):
        """Seçenekleri yönet."""
        if user_input is not None:
            # Seçenekleri güncelle
            return self.async_create_entry(title="", data=user_input)
        
        data_schema = vol.Schema({
            vol.Optional(CONF_AC_NAME, default=self._get_option_value(CONF_AC_NAME)): str,
            vol.Optional(CONF_DEVICE_ID, default=self._get_option_value(CONF_DEVICE_ID)): str,
            vol.Optional(CONF_DEVICE_LOCAL_KEY, default=self._get_option_value(CONF_DEVICE_LOCAL_KEY)): str,
            vol.Optional(CONF_DEVICE_IP, default=self._get_option_value(CONF_DEVICE_IP)): str,
            vol.Optional(CONF_DEVICE_VERSION, default=self._get_option_value(CONF_DEVICE_VERSION)): vol.In(DEVICE_VERSIONS),
            vol.Optional(CONF_DEVICE_MODEL, default=self._get_option_value(CONF_DEVICE_MODEL)): vol.In(DEVICE_MODELS),
            vol.Optional(CONF_TEMPERATURE_SENSOR, default=self._get_option_value(CONF_TEMPERATURE_SENSOR)): str,
        })

        return self.async_show_form(step_id="init", data_schema=data_schema)
