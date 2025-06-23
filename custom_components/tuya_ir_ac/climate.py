from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import HVACMode, ClimateEntityFeature
from homeassistant.const import UnitOfTemperature
from homeassistant.const import STATE_UNKNOWN, STATE_UNAVAILABLE
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers import config_validation as cv
from .const import DOMAIN, CONF_AC_NAME, CONF_DEVICE_ID, CONF_DEVICE_LOCAL_KEY, CONF_DEVICE_IP, CONF_DEVICE_VERSION, CONF_DEVICE_MODEL, CONF_TEMPERATURE_SENSOR

import tinytuya
import os
import json
import codecs
import logging


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):

    def get_config_value(key):
        return config_entry.options.get(key, config_entry.data.get(key))

    ac_name = get_config_value(CONF_AC_NAME)
    device_id = get_config_value(CONF_DEVICE_ID)
    device_model = get_config_value(CONF_DEVICE_MODEL)
    device_local_key = get_config_value(CONF_DEVICE_LOCAL_KEY)
    device_ip = get_config_value(CONF_DEVICE_IP)
    device_version = get_config_value(CONF_DEVICE_VERSION)
    temperature_sensor = get_config_value(CONF_TEMPERATURE_SENSOR)

    if any(value is None for value in [ac_name, device_id, device_model, device_local_key, device_ip, device_version]):
        hass.async_create_task(
            hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": "Tuya IR Climate Entegrasyon Hatası",
                    "message": "Gerekli config seçenekleri eksik. Lütfen entegrasyonu kontrol edin.",
                },
            )
        )
        return False
    
    try:
        device = await hass.async_add_executor_job(tinytuya.Device, device_id, device_ip, device_local_key, "default", 5, device_version)
        entity = TuyaIrClimateEntity(hass, f"{device_id}", ac_name, device, temperature_sensor, device_model)

        commands_path = os.path.join(hass.config.path(), "custom_components", DOMAIN, f'{device_model}.json')
        entity._ir_codes = await entity.async_load_ir_codes(commands_path)
        
        async_add_entities([entity])
        return True
    except Exception as e:
        _LOGGER.error(f"Cihaz oluşturma hatası: {e}")
        return False
    

class TuyaIrClimateEntity(ClimateEntity, RestoreEntity):
    def __init__(self, hass, unique_id, ac_name, device, temperature_sensor, device_model):
        self._enable_turn_on_off_backwards_compatibility = False
        self.hass = hass
        self._ac_name = ac_name
        self._attr_unique_id = unique_id
        self._device = device
        self._temperature_sensor = temperature_sensor
        self._device_model = device_model
        self._attr_hvac_mode = HVACMode.OFF
        self._attr_fan_mode = "Orta"
        self._attr_target_temperature = 22
        self._attr_current_temperature = None
        self._device_api = None
        self._unsub_state_changed = None
        self._ir_codes = {}
        
    async def async_load_ir_codes(self, commands_path):
        try:
            result = await self.hass.async_add_executor_job(lambda: json.load(open(commands_path, 'r')))
            return result
        except FileNotFoundError:
            _LOGGER.error(f"IR kod dosyası bulunamadı: {commands_path}")
            raise ValueError(f"IR kod dosyası bulunamadı: {commands_path}")

    async def async_added_to_hass(self):

        await super().async_added_to_hass()

        last_state = await self.async_get_last_state()
        if last_state is not None:
            self._attr_hvac_mode = last_state.state
            self._attr_fan_mode = last_state.attributes.get('fan_mode')
            self._attr_target_temperature = last_state.attributes.get('temperature')

        if self._temperature_sensor:
            self._unsub_state_changed = async_track_state_change_event(self.hass, [self._temperature_sensor], self._async_sensor_changed)

    async def async_will_remove_from_hass(self):
        if self._unsub_state_changed:
            self._unsub_state_changed()
            self._unsub_state_changed = None      

    async def _async_sensor_changed(self, event):
        """Sıcaklık sensörünün durumu değiştiğinde çağrılır."""
        new_state = event.data.get("new_state")
        if new_state is None or new_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE, "unknown", "unavailable", ""): # None ve diğer geçersiz durumları kontrol et
            return
        
        try:
            self._attr_current_temperature = float(new_state.state)
        except ValueError:
            _LOGGER.warning(f"Geçersiz sıcaklık sensörü değeri: {new_state.state}")
            self._attr_current_temperature = None

    @property
    def unique_id(self) -> str:
        return f"{self._attr_unique_id}"

    @property
    def name(self):
        return self._ac_name

    @property
    def supported_features(self):
        return (ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE |
                ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF)

    @property
    def temperature_unit(self):
        return UnitOfTemperature.CELSIUS

    @property
    def min_temp(self):
        return 16

    @property
    def max_temp(self):
        return 31

    @property
    def target_temperature_step(self):
        return 1

    @property
    def hvac_modes(self):
        return [HVACMode.OFF, HVACMode.COOL, HVACMode.FAN_ONLY, HVACMode.DRY, HVACMode.HEAT, HVACMode.HEAT_COOL]

    @property
    def hvac_mode(self):
        return self._attr_hvac_mode

    @property
    def fan_modes(self):
        return ['Otomatik', 'Sessiz', 'Düşük', 'Orta', 'Yüksek', 'En Yüksek']
    
    @property
    def fan_mode(self):
        return self._attr_fan_mode
    
    @property
    def current_temperature(self):
        if self._temperature_sensor:
            return self._attr_current_temperature
        return None

    @property
    def target_temperature(self):
        return self._attr_target_temperature
    
    async def async_set_hvac_mode(self, hvac_mode: HVACMode):
        self._attr_hvac_mode = hvac_mode
        await self._set_state()

    async def async_set_fan_mode(self, fan_mode: str):
        self._attr_fan_mode = fan_mode
        if self._attr_hvac_mode == HVACMode.OFF or self._attr_hvac_mode is None:
            self._attr_hvac_mode = HVACMode.HEAT_COOL
        await self._set_state()
    
    async def async_set_temperature(self, **kwargs):
        target_temperature = kwargs.get('temperature')
        if target_temperature is not None:
            self._attr_target_temperature = int(target_temperature)
            if self._attr_hvac_mode == HVACMode.OFF or self._attr_hvac_mode is None:
                self._attr_hvac_mode = HVACMode.HEAT_COOL
            await self._set_state()

    async def async_turn_on(self):
        self._attr_hvac_mode = HVACMode.HEAT_COOL
        await self._set_state()

    async def async_turn_off(self):
        self._attr_hvac_mode = HVACMode.OFF
        await self._set_state()

    async def _set_state(self):

        if self._attr_hvac_mode == HVACMode.OFF:
            hvac_mode_key = "off"
        elif self._attr_hvac_mode == HVACMode.HEAT_COOL:
            hvac_mode_key = "auto"
        elif self._attr_hvac_mode == HVACMode.COOL:
            hvac_mode_key = "cool"
        elif self._attr_hvac_mode == HVACMode.HEAT:
            hvac_mode_key = "heat"
        elif self._attr_hvac_mode == HVACMode.DRY:
            hvac_mode_key = "dry"
        elif self._attr_hvac_mode == HVACMode.FAN_ONLY:
            hvac_mode_key = "fan"
        else:
            msg = 'Mode must be one of off, cool, heat, dry, fan or auto'
            raise Exception(msg)

        if self._attr_fan_mode == 'Otomatik':
            fan_mode_key = 'auto'
        elif self._attr_fan_mode == 'Sessiz':
            fan_mode_key = 'quiet'
        elif self._attr_fan_mode == 'Düşük':
            fan_mode_key = 'low'
        elif self._attr_fan_mode == 'Orta':
            fan_mode_key = 'medium'
        elif self._attr_fan_mode == 'Yüksek':
            fan_mode_key = 'high'
        elif self._attr_fan_mode == 'En Yüksek':
            fan_mode_key = 'highest'                    
        else:
            msg = 'Fan mode must be one of Otomatik, Sessiz, Düşük, Orta, Yüksek or En Yüksek'
            raise Exception(msg)
        
        if hvac_mode_key == "off":
            ir_code = self._ir_codes.get("off")
        else:
            ir_code = self._ir_codes.get(hvac_mode_key, {}).get(fan_mode_key, {}).get(str(self._attr_target_temperature))

        if ir_code is None:
            _LOGGER.error(f"Geçersiz HVAC modu, fan modu veya hedef sıcaklık kombinasyonu.")
            return

        try:
            if self._device_model is "MSZ-GE25VA-v2" or self._device_model is "MSC-GE35VB-v2":
                _LOGGER.error(f"v2 gönderim...")
                await self._async_send_command({"1": "study_key", "7": codecs.encode(codecs.decode(ir_code, 'hex'), 'base64').decode()})
                # head = "010ed8000000000005000f003500260045008c"
                # key = "001^%0070C4D364800024C0E04000000000A2@$"
                # await self._async_send_command({"201": json.dumps({"control": "send_ir", "head": head, "key1": key, "type": 0, "delay":300})})
            else:
                _LOGGER.error(f"v1 gönderim...")
                await self._async_send_command({"1": "study_key", "7": codecs.encode(codecs.decode(ir_code, 'hex'), 'base64').decode()})
        except Exception as e:
            _LOGGER.error(f"Durum ayarlama hatası: {e}")


    async def _async_send_command(self, command):
        try:
            payload = self._device.generate_payload(tinytuya.CONTROL, command) # self._device kullan
            await self.hass.async_add_executor_job(self._device.send, payload) # self._device kullan
        except Exception as e:
            _LOGGER.error(f"Komut gönderme hatası: {e}")
            
