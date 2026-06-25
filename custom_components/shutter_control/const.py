"""Constants for the Shutter Control integration."""

from __future__ import annotations

DOMAIN = "shutter_control"
PLATFORMS = ["switch", "sensor"]

# Subentry type
SUBENTRY_TYPE_COVER = "cover"

# Dispatcher signal (per config entry)
SIGNAL_UPDATE = "shutter_control_update_{entry_id}"

# ---------------------------------------------------------------------------
# Global config (config entry data / options)
# ---------------------------------------------------------------------------
CONF_SUN_ENTITY = "sun_entity"
CONF_CLOUD_SENSOR = "cloud_sensor"
CONF_CLOUD_THRESHOLD = "cloud_threshold"
CONF_TEMP_SENSOR = "temperature_sensor"
CONF_TEMP_THRESHOLD = "temperature_threshold"
CONF_UPDATE_INTERVAL = "update_interval"
CONF_SHADE_ONLY_LOWER = "shade_only_lower"
CONF_SHADE_KEEP_UNTIL_DOWN = "shade_keep_until_down"
CONF_DOOR_DELAY = "door_delay"

DEFAULT_SUN_ENTITY = "sun.sun"
# Max. cloud cover (%) at which shading still happens (low clouds = sunny).
DEFAULT_CLOUD_THRESHOLD = 40.0
DEFAULT_TEMP_THRESHOLD = 22.0  # °C
DEFAULT_UPDATE_INTERVAL = 60  # seconds
# Only lower for shading, never raise a shutter that is already further down.
DEFAULT_SHADE_ONLY_LOWER = True
# Keep the shade position once shading engaged (don't reopen); close fully at down time.
DEFAULT_SHADE_KEEP_UNTIL_DOWN = False
# Door/window contact must be stable this long (s) before acting (debounce).
DEFAULT_DOOR_DELAY = 10

# ---------------------------------------------------------------------------
# Per-cover config (subentry data)
# ---------------------------------------------------------------------------
CONF_NAME = "name"
CONF_COVER_ENTITY = "cover_entity"
CONF_AREAS = "areas"
CONF_FLOORS = "floors"
CONF_ROOM_TYPE = "room_type"

CONF_SHADE_ENABLED = "shade_enabled"
CONF_DOOR_SENSOR = "door_sensor"
# Initial defaults for the two runtime door switches (toggled live in the card).
DEFAULT_DOOR_ACTION_ENABLED = True
DEFAULT_DOOR_RESTORE_ENABLED = True
CONF_AZIMUTH_START = "azimuth_start"
CONF_AZIMUTH_END = "azimuth_end"
CONF_ELEVATION_MIN = "elevation_min"
CONF_ELEVATION_MAX = "elevation_max"
CONF_SHADE_POSITION = "shade_position"

CONF_OPEN_POSITION = "open_position"
CONF_CLOSED_POSITION = "closed_position"

CONF_UP_TIME = "up_time"
CONF_UP_TIME_WEEKEND = "up_time_weekend"
CONF_DOWN_TIME = "down_time"
CONF_DOWN_TIME_WEEKEND = "down_time_weekend"

CONF_AUTO_DOWN_ENABLED = "auto_down_enabled"
CONF_AUTO_UP_ENABLED = "auto_up_enabled"

# Trigger type for up / down + sun-event offset and bounds.
CONF_UP_TRIGGER = "up_trigger"
CONF_UP_OFFSET = "up_offset"
CONF_UP_EARLIEST = "up_earliest"
CONF_UP_LATEST = "up_latest"
CONF_DOWN_TRIGGER = "down_trigger"
CONF_DOWN_OFFSET = "down_offset"
CONF_DOWN_EARLIEST = "down_earliest"
CONF_DOWN_LATEST = "down_latest"

# Trigger types
TRIGGER_TIME = "time"
TRIGGER_SUNRISE = "sunrise"
TRIGGER_SUNSET = "sunset"
# Order tuned per direction (most common choice first).
UP_TRIGGERS = [TRIGGER_TIME, TRIGGER_SUNRISE, TRIGGER_SUNSET]
DOWN_TRIGGERS = [TRIGGER_TIME, TRIGGER_SUNSET, TRIGGER_SUNRISE]

DEFAULT_UP_TRIGGER = TRIGGER_TIME
DEFAULT_DOWN_TRIGGER = TRIGGER_TIME
DEFAULT_UP_OFFSET = 0
DEFAULT_DOWN_OFFSET = 0

# Room types
ROOM_LIVING = "living"
ROOM_SLEEPING = "sleeping"
ROOM_TYPES = [ROOM_LIVING, ROOM_SLEEPING]

# Defaults (south facade, living room)
DEFAULT_ROOM_TYPE = ROOM_LIVING
DEFAULT_AZIMUTH_START = 100.0
DEFAULT_AZIMUTH_END = 260.0
DEFAULT_ELEVATION_MIN = 15.0
DEFAULT_ELEVATION_MAX = 60.0
DEFAULT_SHADE_POSITION = 40  # % open while shading
DEFAULT_OPEN_POSITION = 100
DEFAULT_CLOSED_POSITION = 0
DEFAULT_UP_TIME = "07:00:00"
DEFAULT_UP_TIME_WEEKEND = "08:30:00"
DEFAULT_DOWN_TIME = "21:30:00"
DEFAULT_DOWN_TIME_WEEKEND = "22:00:00"

# Modes reported by the status sensor
MODE_IDLE = "idle"
MODE_OPEN = "open"
MODE_CLOSED = "closed"
MODE_SHADING = "shading"
MODE_MANUAL = "manual"
MODE_DISABLED = "disabled"
MODE_DOOR = "door_open"

# Tolerance (in %) when comparing cover positions
POSITION_TOLERANCE = 3
# Window after issuing a command during which state changes are treated as
# our own movement and not as a manual override (seconds).
COMMAND_IGNORE_WINDOW = 150
