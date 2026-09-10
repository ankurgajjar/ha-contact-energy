"""Sensor platform for Contact Energy."""
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up Contact Energy sensors."""
    coordinator = hass.data[DOMAIN]["coordinator"]

    async_add_entities([
        ContactEnergySensor(coordinator, "Total Consumption", "total_kwh", UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY),
        ContactEnergySensor(coordinator, "Free Consumption", "free_kwh", UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY),
        ContactEnergySensor(coordinator, "Billed Consumption", "billed_kwh", UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY),
        ContactEnergyCostSensor(coordinator, "Monthly Cost", "cost_nzd"),
        ContactEnergyHistorySensor(coordinator, "Usage History"),
    ])

class ContactEnergySensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, name, key, unit, device_class):
        super().__init__(coordinator)
        self._key = key
        self._attr_name = f"Contact Energy {name}"
        self._attr_unique_id = f"contact_energy_{key}"
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = SensorStateClass.TOTAL

    @property
    def native_value(self):
        return self.coordinator.data.get("current", {}).get(self._key)

class ContactEnergyCostSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, name, key):
        super().__init__(coordinator)
        self._key = key
        self._attr_name = f"Contact Energy {name}"
        self._attr_unique_id = f"contact_energy_{key}"
        self._attr_native_unit_of_measurement = "NZD"
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_state_class = SensorStateClass.TOTAL

    @property
    def native_value(self):
        return self.coordinator.data.get("current", {}).get(self._key)

class ContactEnergyHistorySensor(CoordinatorEntity, SensorEntity):
    _attr_name = "Contact Energy Historical Data"
    _attr_unique_id = "contact_energy_historical_data"

    @property
    def native_value(self):
        return len(self.coordinator.data.get("history", []))

    @property
    def extra_state_attributes(self):
        return {
            "months": [
                {
                    "date": item.get("date"),
                    "total_kwh": float(item.get("value", 0)),
                    "free_kwh": float(item.get("unchargedValue", 0)),
                    "billed_kwh": max(0.0, float(item.get("value", 0)) - float(item.get("unchargedValue", 0))),
                    "cost_nzd": float(item.get("dollarValue", 0)),
                }
                for item in self.coordinator.data.get("history", [])
            ]
        }
