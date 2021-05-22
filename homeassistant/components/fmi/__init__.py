"""The FMI (Finnish Meteorological Institute) component."""

from async_timeout import timeout
import fmi_weather_client as fmi
from fmi_weather_client.errors import ClientError, ServerError

from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_OFFSET
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    _LOGGER,
    COORDINATOR,
    DOMAIN,
    MIN_TIME_BETWEEN_UPDATES,
    UNDO_UPDATE_LISTENER,
)

PLATFORMS = ["weather"]


async def async_setup_entry(hass, config_entry) -> bool:
    """Set up FMI as config entry."""

    hass.data.setdefault(DOMAIN, {})

    latitude = config_entry.data[CONF_LATITUDE]
    longitude = config_entry.data[CONF_LONGITUDE]
    time_step = config_entry.options.get(CONF_OFFSET, 1)

    _LOGGER.debug("Using lat: %s and long: %s", latitude, longitude)

    coordinator = FMIDataUpdateCoordinator(hass, latitude, longitude, time_step)
    await coordinator.async_refresh()

    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    undo_listener = config_entry.add_update_listener(update_listener)

    hass.data[DOMAIN][config_entry.entry_id] = {
        COORDINATOR: coordinator,
        UNDO_UPDATE_LISTENER: undo_listener,
    }

    hass.config_entries.async_setup_platforms(config_entry, PLATFORMS)

    return True


async def async_unload_entry(hass, config_entry):
    """Unload an FMI config entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )

    if unload_ok:
        hass.data[DOMAIN][config_entry.entry_id][UNDO_UPDATE_LISTENER]()
    hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok


async def update_listener(hass, config_entry):
    """Update FMI listener."""
    await hass.config_entries.async_reload(config_entry.entry_id)


class FMIDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching FMI data API."""

    def __init__(self, hass, latitude, longitude, time_step):
        """Initialize."""
        self.latitude = latitude
        self.longitude = longitude
        self.unique_id = f"{self.latitude}_{self.longitude}"
        self.time_step = time_step
        self.current = None
        self.forecast = None
        self._hass = hass

        _LOGGER.debug("Data will be updated every %s min", MIN_TIME_BETWEEN_UPDATES)

        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=MIN_TIME_BETWEEN_UPDATES
        )

    async def _async_update_data(self):
        """Update data via Open API."""
        try:
            async with timeout(10):
                self.current = await fmi.async_weather_by_coordinates(
                    self.latitude, self.longitude
                )
                self.forecast = await fmi.async_forecast_by_coordinates(
                    self.latitude, self.longitude, self.time_step
                )
        except (ClientError, ServerError) as error:
            raise UpdateFailed(error) from error
        return {}