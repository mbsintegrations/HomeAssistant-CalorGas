# SPDX-FileCopyrightText: 2026 MBS Integrations
# SPDX-License-Identifier: GPL-3.0-only

"""Portal estimates and source dates, with explicit freshness metadata."""

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .calor_portal import TANK_URL
from .const import DOMAIN

DESCRIPTIONS = (
    SensorEntityDescription(key="tank_level", name="Tank level", icon="mdi:storage-tank",
                            native_unit_of_measurement="%", state_class=SensorStateClass.MEASUREMENT,
                            suggested_display_precision=0),
    SensorEntityDescription(key="days_remaining", name="Estimated days remaining", icon="mdi:calendar-clock",
                            native_unit_of_measurement=UnitOfTime.DAYS, device_class=SensorDeviceClass.DURATION,
                            suggested_display_precision=0),
    SensorEntityDescription(key="last_reading", name="Last reading", device_class=SensorDeviceClass.DATE),
    SensorEntityDescription(key="run_out_date", name="Estimated run out", device_class=SensorDeviceClass.DATE),
    SensorEntityDescription(key="delivery_status", name="Delivery status", icon="mdi:truck-delivery-outline"),
    SensorEntityDescription(key="last_successful_sync", name="Last successful sync",
                            device_class=SensorDeviceClass.TIMESTAMP, entity_category=EntityCategory.DIAGNOSTIC),
)


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(CalorSensor(entry.runtime_data, description) for description in DESCRIPTIONS)


class CalorSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, description):
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.account_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.account_id)}, name="Calor Gas",
            manufacturer="Calor", model="MyCalorGas tank telemetry", configuration_url=TANK_URL,
        )

    @property
    def available(self):
        return bool(self.coordinator.data)

    @property
    def native_value(self):
        return (self.coordinator.data or {}).get(self.entity_description.key)

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data or {}
        sync = data.get("last_successful_sync")
        attrs = {
            "data_stale": self.coordinator.data_stale,
            "portal_available": self.coordinator.portal_available,
            "last_refresh_error": self.coordinator.last_refresh_error,
            "last_successful_sync": sync.isoformat() if sync else None,
        }
        if self.entity_description.key == "days_remaining":
            attrs.update({
                "estimated": True,
                "is_lower_bound": data.get("days_remaining_is_lower_bound", False),
            })
        if self.entity_description.key == "tank_level":
            attrs.update({
                "estimated": True,
                "last_reading": data["last_reading"].isoformat() if data.get("last_reading") else None,
                "last_delivery": data["last_delivery"].isoformat() if data.get("last_delivery") else None,
                "refresh_interval_hours": 6,
                "days_remaining": data.get("days_remaining"),
                "days_remaining_is_lower_bound": data.get("days_remaining_is_lower_bound", False),
                "run_out_date": data["run_out_date"].isoformat() if data.get("run_out_date") else None,
                "delivery_status": data.get("delivery_status"),
            })
        return attrs
