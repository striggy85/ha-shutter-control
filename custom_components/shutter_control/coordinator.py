"""Core automation logic for Shutter Control.

This module ports the essential behaviour of the ioBroker ``shuttercontrol``
adapter to Home Assistant:

* Sun-based shading per facade (azimuth window, elevation window, cloud-cover /
  temperature thresholds).
* Automatic up in the morning / down in the evening (separate week / weekend
  times).
* Living-room vs sleeping-room behaviour.
* Manual override detection (pauses automation until the next up/down event).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date as date_cls
from datetime import datetime, time, timedelta, timezone

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_SET_COVER_POSITION,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.sun import get_astral_event_date
import homeassistant.util.dt as dt_util

from .const import (
    COMMAND_IGNORE_WINDOW,
    CONF_AUTO_DOWN_ENABLED,
    CONF_AUTO_UP_ENABLED,
    CONF_AREAS,
    CONF_AZIMUTH_END,
    CONF_AZIMUTH_START,
    CONF_CLOSED_POSITION,
    CONF_FLOORS,
    CONF_CLOUD_SENSOR,
    CONF_CLOUD_THRESHOLD,
    CONF_COVER_ENTITY,
    CONF_DOWN_EARLIEST,
    CONF_DOWN_LATEST,
    CONF_DOWN_OFFSET,
    CONF_DOWN_TIME,
    CONF_DOWN_TIME_WEEKEND,
    CONF_DOWN_TRIGGER,
    CONF_ELEVATION_MAX,
    CONF_ELEVATION_MIN,
    CONF_NAME,
    CONF_OPEN_POSITION,
    CONF_ROOM_TYPE,
    CONF_SHADE_ENABLED,
    CONF_SHADE_ONLY_LOWER,
    CONF_SHADE_POSITION,
    CONF_SUN_ENTITY,
    CONF_TEMP_SENSOR,
    CONF_TEMP_THRESHOLD,
    CONF_UP_EARLIEST,
    CONF_UP_LATEST,
    CONF_UP_OFFSET,
    CONF_UP_TIME,
    CONF_UP_TIME_WEEKEND,
    CONF_UP_TRIGGER,
    CONF_UPDATE_INTERVAL,
    DEFAULT_AZIMUTH_END,
    DEFAULT_AZIMUTH_START,
    DEFAULT_CLOSED_POSITION,
    DEFAULT_CLOUD_THRESHOLD,
    DEFAULT_DOWN_OFFSET,
    DEFAULT_DOWN_TIME,
    DEFAULT_DOWN_TIME_WEEKEND,
    DEFAULT_DOWN_TRIGGER,
    DEFAULT_ELEVATION_MAX,
    DEFAULT_ELEVATION_MIN,
    DEFAULT_OPEN_POSITION,
    DEFAULT_ROOM_TYPE,
    DEFAULT_SHADE_ONLY_LOWER,
    DEFAULT_SHADE_POSITION,
    DEFAULT_SUN_ENTITY,
    DEFAULT_TEMP_THRESHOLD,
    DEFAULT_UP_OFFSET,
    DEFAULT_UP_TIME,
    DEFAULT_UP_TIME_WEEKEND,
    DEFAULT_UP_TRIGGER,
    DEFAULT_UPDATE_INTERVAL,
    MODE_CLOSED,
    MODE_DISABLED,
    MODE_IDLE,
    MODE_MANUAL,
    MODE_OPEN,
    MODE_SHADING,
    POSITION_TOLERANCE,
    ROOM_SLEEPING,
    SIGNAL_UPDATE,
    TRIGGER_SUNRISE,
    TRIGGER_SUNSET,
    TRIGGER_TIME,
)

_LOGGER = logging.getLogger(__name__)

COVER_DOMAIN = "cover"
ATTR_POSITION = "current_position"


def _parse_time(value: str | None, default: str) -> time:
    """Parse a ``HH:MM:SS`` string into a ``time`` object."""
    raw = value or default
    try:
        parts = [int(p) for p in str(raw).split(":")]
        while len(parts) < 3:
            parts.append(0)
        return time(parts[0], parts[1], parts[2])
    except (ValueError, IndexError):
        h, m, s = (int(p) for p in default.split(":"))
        return time(h, m, s)


def _parse_opt_time(value: str | None) -> time | None:
    """Parse an optional ``HH:MM:SS`` string, returning None when unset."""
    if value in (None, ""):
        return None
    try:
        parts = [int(p) for p in str(value).split(":")]
        while len(parts) < 3:
            parts.append(0)
        return time(parts[0], parts[1], parts[2])
    except (ValueError, IndexError):
        return None


def _azimuth_in_range(azimuth: float, start: float, end: float) -> bool:
    """Return True if azimuth is within [start, end], handling 360° wrap."""
    start %= 360
    end %= 360
    azimuth %= 360
    if start <= end:
        return start <= azimuth <= end
    # Wrapped range, e.g. 300 -> 60 (passing through north)
    return azimuth >= start or azimuth <= end


@dataclass
class CoverState:
    """Runtime state for a single managed cover (one subentry)."""

    subentry_id: str
    config: dict

    # User-toggled automation switch (persisted by the switch entity).
    automatic_enabled: bool = True

    # Reported mode for the status sensor.
    mode: str = MODE_IDLE

    # Manual override: paused until the next up/down event.
    manual_override: bool = False

    # Edge tracking so up/down fire only once per day.
    last_up_date: object | None = None
    last_down_date: object | None = None

    # Continuous shading state (so we only command on change).
    shading_active: bool = False

    # Set on the first evaluation so we don't replay already-passed up/down
    # events (and move shutters) right after a Home Assistant restart.
    initialized: bool = False

    # Last position we commanded + window during which state changes are ours.
    last_commanded: int | None = None
    ignore_until: datetime | None = None

    # Forecast for the dashboard card.
    next_up: datetime | None = None
    next_down: datetime | None = None
    shade_start: datetime | None = None  # predicted (geometric) shading window
    shade_end: datetime | None = None
    _shade_pred_date: object | None = None  # date the prediction was computed for

    # Soonest upcoming action (for the overview): label + time.
    next_action: str | None = None  # up | down | shading | shading_end
    next_action_at: datetime | None = None

    # Covers resolved from explicit list + selected areas/floors.
    resolved_entities: list[str] = field(default_factory=list)

    @property
    def name(self) -> str:
        return self.config.get(CONF_NAME) or self.subentry_id

    @property
    def explicit_entities(self) -> list[str]:
        """Cover entities listed directly in the config (always a list)."""
        value = self.config.get(CONF_COVER_ENTITY)
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        return list(value)

    @property
    def entity_ids(self) -> list[str]:
        """All controlled cover entities (explicit + resolved areas/floors)."""
        return self.resolved_entities or self.explicit_entities


class ShutterControlManager:
    """Owns all cover states and drives the automation loop for one entry."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.covers: dict[str, CoverState] = {}
        self._unsub_interval = None
        self._unsub_state = None

    # ------------------------------------------------------------------ setup
    async def async_setup(self) -> None:
        """Build cover states and register listeners."""
        for subentry_id, subentry in self.entry.subentries.items():
            if subentry.subentry_type != "cover":
                continue
            cover = CoverState(subentry_id=subentry_id, config=dict(subentry.data))
            cover.resolved_entities = self._resolve_targets(cover)
            self.covers[subentry_id] = cover

        interval = timedelta(
            seconds=self.entry.options.get(
                CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
            )
        )
        self._unsub_interval = async_track_time_interval(
            self.hass, self._handle_interval, interval
        )

        # React immediately to sun / sensor / cover changes.
        tracked = {self._sun_entity}
        if (sensor := self._cloud_sensor) is not None:
            tracked.add(sensor)
        if (sensor := self._temp_sensor) is not None:
            tracked.add(sensor)
        for cover in self.covers.values():
            tracked.update(cover.entity_ids)

        self._unsub_state = async_track_state_change_event(
            self.hass, list(tracked), self._handle_state_event
        )

        # Run once shortly after startup.
        self.hass.async_create_task(self._async_evaluate_all())

    async def async_shutdown(self) -> None:
        if self._unsub_interval is not None:
            self._unsub_interval()
            self._unsub_interval = None
        if self._unsub_state is not None:
            self._unsub_state()
            self._unsub_state = None

    # ------------------------------------------------------ global config read
    @property
    def _sun_entity(self) -> str:
        return self.entry.options.get(CONF_SUN_ENTITY, DEFAULT_SUN_ENTITY)

    @property
    def _cloud_sensor(self) -> str | None:
        return self.entry.options.get(CONF_CLOUD_SENSOR)

    @property
    def _temp_sensor(self) -> str | None:
        return self.entry.options.get(CONF_TEMP_SENSOR)

    def _resolve(self, cfg: dict, key: str, default):
        """Per-group override if set, otherwise the global default, else ``default``.

        An empty value (None or "") in the group config means "inherit", so we
        fall back to the global option for that key.
        """
        value = cfg.get(key)
        if value is None or value == "":
            return self.entry.options.get(key, default)
        return value

    def _sun_attrs(self) -> tuple[float | None, float | None]:
        """Return (azimuth, elevation) from the sun entity."""
        state = self.hass.states.get(self._sun_entity)
        if state is None:
            return None, None
        az = state.attributes.get("azimuth")
        el = state.attributes.get("elevation")
        return (
            float(az) if az is not None else None,
            float(el) if el is not None else None,
        )

    def _read_float(self, entity_id: str | None) -> float | None:
        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        if state is None or state.state in ("unknown", "unavailable", None, ""):
            return None
        try:
            return float(state.state)
        except (ValueError, TypeError):
            return None

    def _read_cloud(self) -> float | None:
        """Read cloud cover (%) from the configured sensor or weather entity."""
        entity_id = self._cloud_sensor
        if not entity_id:
            return None
        # Weather entities expose cloud cover as the ``cloud_coverage`` attribute
        # rather than as the (textual) state.
        if entity_id.startswith("weather."):
            state = self.hass.states.get(entity_id)
            if state is None:
                return None
            value = state.attributes.get("cloud_coverage")
            try:
                return float(value) if value is not None else None
            except (ValueError, TypeError):
                return None
        return self._read_float(entity_id)

    # --------------------------------------------------------- event handlers
    @callback
    def _handle_interval(self, _now: datetime) -> None:
        self.hass.async_create_task(self._async_evaluate_all())

    @callback
    def _handle_state_event(self, event: Event) -> None:
        entity_id = event.data.get(ATTR_ENTITY_ID)
        # A managed cover changed -> maybe a manual override.
        for cover in self.covers.values():
            if entity_id in cover.entity_ids:
                self._check_manual_override(cover, event)
        self.hass.async_create_task(self._async_evaluate_all())

    @callback
    def _check_manual_override(self, cover: CoverState, event: Event) -> None:
        new_state = event.data.get("new_state")
        if new_state is None:
            return
        now = dt_util.utcnow()
        # Within the command window the movement is our own.
        if cover.ignore_until is not None and now < cover.ignore_until:
            return
        position = new_state.attributes.get(ATTR_POSITION)
        if position is None:
            return
        if (
            cover.last_commanded is None
            or abs(int(position) - cover.last_commanded) > POSITION_TOLERANCE
        ):
            if not cover.manual_override:
                _LOGGER.debug(
                    "Manual override detected for %s (pos=%s)",
                    cover.name,
                    position,
                )
            cover.manual_override = True
            cover.mode = MODE_MANUAL

    # ------------------------------------------------------------- public API
    def set_automatic(self, subentry_id: str, enabled: bool) -> None:
        cover = self.covers.get(subentry_id)
        if cover is None:
            return
        cover.automatic_enabled = enabled
        if enabled:
            # Re-enabling clears a previous manual override.
            cover.manual_override = False
            cover.mode = MODE_IDLE
        else:
            cover.mode = MODE_DISABLED
        self._notify()
        self.hass.async_create_task(self._async_evaluate_all())

    # ------------------------------------------------------------- evaluation
    async def _async_evaluate_all(self) -> None:
        now = dt_util.now()  # local time, tz-aware
        azimuth, elevation = self._sun_attrs()
        cloud = self._read_cloud()
        temperature = self._read_float(self._temp_sensor)
        for cover in self.covers.values():
            # Re-resolve area/floor membership so covers added later are picked up.
            if cover.config.get(CONF_AREAS) or cover.config.get(CONF_FLOORS):
                cover.resolved_entities = self._resolve_targets(cover)
            try:
                await self._evaluate_cover(
                    cover, now, azimuth, elevation, cloud, temperature
                )
            except Exception:  # noqa: BLE001 - never let one cover kill the loop
                _LOGGER.exception("Error evaluating cover %s", cover.name)
        self._notify()

    async def _evaluate_cover(
        self,
        cover: CoverState,
        now: datetime,
        azimuth: float | None,
        elevation: float | None,
        cloud: float | None,
        temperature: float | None,
    ) -> None:
        cfg = cover.config
        if not cover.automatic_enabled:
            cover.mode = MODE_DISABLED
            return

        room_type = cfg.get(CONF_ROOM_TYPE, DEFAULT_ROOM_TYPE)
        open_pos = int(cfg.get(CONF_OPEN_POSITION, DEFAULT_OPEN_POSITION))
        closed_pos = int(cfg.get(CONF_CLOSED_POSITION, DEFAULT_CLOSED_POSITION))

        today = now.date()
        tzinfo = now.tzinfo
        up_dt, down_dt = self._compute_up_down(cfg, today, tzinfo)

        # Forecast data for the dashboard card (next up/down, predicted shading).
        self._update_forecast(cover, now, up_dt, down_dt)

        # On the very first evaluation (e.g. after a restart) treat already
        # passed up/down events as done so we don't suddenly move the shutter.
        # Continuous shading below still brings it to the correct daytime state.
        if not cover.initialized:
            cover.initialized = True
            if now >= up_dt:
                cover.last_up_date = today
            if now >= down_dt:
                cover.last_down_date = today

        # ---- Edge: morning up -------------------------------------------
        if (
            cfg.get(CONF_AUTO_UP_ENABLED, True)
            and now >= up_dt
            and cover.last_up_date != today
        ):
            cover.last_up_date = today
            cover.manual_override = False  # new day clears the override
            cover.shading_active = False
            await self._apply(cover, open_pos, MODE_OPEN)
            return

        # ---- Edge: evening down -----------------------------------------
        if (
            cfg.get(CONF_AUTO_DOWN_ENABLED, True)
            and now >= down_dt
            and cover.last_down_date != today
        ):
            cover.last_down_date = today
            cover.manual_override = False
            cover.shading_active = False
            await self._apply(cover, closed_pos, MODE_CLOSED)
            return

        if cover.manual_override:
            cover.mode = MODE_MANUAL
            return

        # ---- Continuous shading (only during the day, between up & down) -
        in_day_window = up_dt <= now < down_dt
        if not cfg.get(CONF_SHADE_ENABLED, True) or not in_day_window:
            return

        should_shade = self._should_shade(
            cfg, azimuth, elevation, cloud, temperature
        )

        if should_shade and not cover.shading_active:
            shade_pos = (
                closed_pos
                if room_type == ROOM_SLEEPING
                else int(cfg.get(CONF_SHADE_POSITION, DEFAULT_SHADE_POSITION))
            )
            only_lower = self.entry.options.get(
                CONF_SHADE_ONLY_LOWER, DEFAULT_SHADE_ONLY_LOWER
            )
            max_pos = self._group_max_position(cover)
            if (
                only_lower
                and max_pos is not None
                and max_pos <= shade_pos + POSITION_TOLERANCE
            ):
                # Shutter is already at/below the shade position - never raise
                # it for shading (and don't mark shading active, so the end of
                # the shading period won't open it either).
                cover.mode = MODE_IDLE
            else:
                cover.shading_active = True
                await self._apply(cover, shade_pos, MODE_SHADING)
        elif not should_shade and cover.shading_active:
            cover.shading_active = False
            await self._apply(cover, open_pos, MODE_OPEN)
        elif not cover.shading_active and cover.mode not in (MODE_OPEN,):
            cover.mode = MODE_IDLE

    def _event_datetime(
        self,
        target_date: date_cls,
        tzinfo,
        trigger: str,
        fixed_time: time,
        offset_min: int,
        earliest: time | None,
        latest: time | None,
    ) -> datetime:
        """Resolve an up/down trigger to a local datetime on ``target_date``.

        ``trigger`` is one of ``time`` (use ``fixed_time``), ``sunrise`` or
        ``sunset`` (astral event of that day, shifted by ``offset_min`` and
        clamped to the optional ``earliest`` / ``latest`` bounds).
        """
        if trigger == TRIGGER_TIME:
            return datetime.combine(target_date, fixed_time, tzinfo=tzinfo)

        event = "sunrise" if trigger == TRIGGER_SUNRISE else "sunset"
        base = get_astral_event_date(self.hass, event, target_date)
        if base is None:
            # Polar day/night: no sunrise/sunset -> fall back to the fixed time.
            return datetime.combine(target_date, fixed_time, tzinfo=tzinfo)

        result = dt_util.as_local(base) + timedelta(minutes=offset_min)
        if earliest is not None:
            lower = datetime.combine(target_date, earliest, tzinfo=tzinfo)
            if result < lower:
                result = lower
        if latest is not None:
            upper = datetime.combine(target_date, latest, tzinfo=tzinfo)
            if result > upper:
                result = upper
        return result

    def _compute_up_down(
        self, cfg: dict, target_date: date_cls, tzinfo
    ) -> tuple[datetime, datetime]:
        """Return (up_dt, down_dt) for ``target_date`` honouring overrides."""
        is_weekend = target_date.weekday() >= 5
        up_t = _parse_time(
            self._resolve(cfg, CONF_UP_TIME_WEEKEND, None)
            if is_weekend
            else self._resolve(cfg, CONF_UP_TIME, None),
            DEFAULT_UP_TIME_WEEKEND if is_weekend else DEFAULT_UP_TIME,
        )
        down_t = _parse_time(
            self._resolve(cfg, CONF_DOWN_TIME_WEEKEND, None)
            if is_weekend
            else self._resolve(cfg, CONF_DOWN_TIME, None),
            DEFAULT_DOWN_TIME_WEEKEND if is_weekend else DEFAULT_DOWN_TIME,
        )
        up_dt = self._event_datetime(
            target_date,
            tzinfo,
            self._resolve(cfg, CONF_UP_TRIGGER, DEFAULT_UP_TRIGGER),
            up_t,
            int(self._resolve(cfg, CONF_UP_OFFSET, DEFAULT_UP_OFFSET)),
            _parse_opt_time(self._resolve(cfg, CONF_UP_EARLIEST, None)),
            _parse_opt_time(self._resolve(cfg, CONF_UP_LATEST, None)),
        )
        down_dt = self._event_datetime(
            target_date,
            tzinfo,
            self._resolve(cfg, CONF_DOWN_TRIGGER, DEFAULT_DOWN_TRIGGER),
            down_t,
            int(self._resolve(cfg, CONF_DOWN_OFFSET, DEFAULT_DOWN_OFFSET)),
            _parse_opt_time(self._resolve(cfg, CONF_DOWN_EARLIEST, None)),
            _parse_opt_time(self._resolve(cfg, CONF_DOWN_LATEST, None)),
        )
        return up_dt, down_dt

    def _update_forecast(
        self, cover: CoverState, now: datetime, up_dt: datetime, down_dt: datetime
    ) -> None:
        """Compute next up/down time and today's predicted shading window."""
        cfg = cover.config
        tzinfo = now.tzinfo
        today = now.date()
        tomorrow = today + timedelta(days=1)

        # Next morning up: today's if still ahead, else tomorrow's.
        if cfg.get(CONF_AUTO_UP_ENABLED, True):
            cover.next_up = up_dt if now < up_dt else (
                self._compute_up_down(cfg, tomorrow, tzinfo)[0]
            )
        else:
            cover.next_up = None

        # Next evening down: today's if still ahead, else tomorrow's.
        if cfg.get(CONF_AUTO_DOWN_ENABLED, True):
            cover.next_down = down_dt if now < down_dt else (
                self._compute_up_down(cfg, tomorrow, tzinfo)[1]
            )
        else:
            cover.next_down = None

        # Predicted shading window (geometry only) - recompute once per day.
        if cfg.get(CONF_SHADE_ENABLED, True):
            if cover._shade_pred_date != today:
                cover._shade_pred_date = today
                window = self._predict_shading(cfg, today, tzinfo, up_dt, down_dt)
                cover.shade_start, cover.shade_end = (
                    window if window else (None, None)
                )
        else:
            cover.shade_start = cover.shade_end = None
            cover._shade_pred_date = today

        # Soonest upcoming action across up / down / predicted shading.
        candidates: list[tuple[datetime, str]] = []
        if cover.next_up:
            candidates.append((cover.next_up, "up"))
        if cover.next_down:
            candidates.append((cover.next_down, "down"))
        if (
            cover.shade_start
            and cover.shade_start > now
            and not cover.shading_active
        ):
            candidates.append((cover.shade_start, "shading"))
        if cover.shading_active and cover.shade_end and cover.shade_end > now:
            candidates.append((cover.shade_end, "shading_end"))

        candidates = [(t, lab) for (t, lab) in candidates if t and t > now]
        if candidates:
            candidates.sort(key=lambda c: c[0])
            cover.next_action_at, cover.next_action = candidates[0]
        else:
            cover.next_action_at = None
            cover.next_action = None

    def _predict_shading(
        self,
        cfg: dict,
        target_date: date_cls,
        tzinfo,
        up_dt: datetime,
        down_dt: datetime,
    ) -> tuple[datetime, datetime] | None:
        """Predict today's shading window from sun geometry (ignores clouds).

        Scans the daytime hours and returns the first/last time at which the sun
        is within the facade azimuth window and the elevation window, clamped to
        the up/down period. Returns None if shading is not expected today.
        """
        try:
            from astral import Observer
            from astral.sun import azimuth as _az, elevation as _el
        except ImportError:  # astral ships with HA, but stay defensive
            return None

        az_start = float(self._resolve(cfg, CONF_AZIMUTH_START, DEFAULT_AZIMUTH_START))
        az_end = float(self._resolve(cfg, CONF_AZIMUTH_END, DEFAULT_AZIMUTH_END))
        el_min = float(self._resolve(cfg, CONF_ELEVATION_MIN, DEFAULT_ELEVATION_MIN))
        el_max = float(self._resolve(cfg, CONF_ELEVATION_MAX, DEFAULT_ELEVATION_MAX))

        observer = Observer(
            latitude=self.hass.config.latitude,
            longitude=self.hass.config.longitude,
            elevation=self.hass.config.elevation or 0.0,
        )

        start: datetime | None = None
        end: datetime | None = None
        base = datetime.combine(target_date, time(0, 0), tzinfo=tzinfo)
        step = timedelta(minutes=10)
        for i in range(0, 24 * 6 + 1):
            cur = base + step * i
            if cur < up_dt or cur > down_dt:
                continue
            cur_utc = cur.astimezone(timezone.utc)
            try:
                el = _el(observer, cur_utc)
                if not (el_min <= el <= el_max):
                    continue
                az = _az(observer, cur_utc)
            except (ValueError, TypeError):
                continue
            if _azimuth_in_range(az, az_start, az_end):
                if start is None:
                    start = cur
                end = cur
        if start is None or end is None:
            return None
        return start, end

    def _should_shade(
        self,
        cfg: dict,
        azimuth: float | None,
        elevation: float | None,
        cloud: float | None,
        temperature: float | None,
    ) -> bool:
        if azimuth is None or elevation is None:
            return False

        az_start = float(self._resolve(cfg, CONF_AZIMUTH_START, DEFAULT_AZIMUTH_START))
        az_end = float(self._resolve(cfg, CONF_AZIMUTH_END, DEFAULT_AZIMUTH_END))
        el_min = float(self._resolve(cfg, CONF_ELEVATION_MIN, DEFAULT_ELEVATION_MIN))
        el_max = float(self._resolve(cfg, CONF_ELEVATION_MAX, DEFAULT_ELEVATION_MAX))

        if not _azimuth_in_range(azimuth, az_start, az_end):
            return False
        if not (el_min <= elevation <= el_max):
            return False

        # Cloud-cover gate (only if a sensor is configured): shade only when the
        # sky is clear enough, i.e. cloud cover at or below the threshold.
        threshold = self.entry.options.get(
            CONF_CLOUD_THRESHOLD, DEFAULT_CLOUD_THRESHOLD
        )
        if cloud is not None and cloud > threshold:
            return False

        # Temperature gate (only if a sensor is configured).
        temp_threshold = self.entry.options.get(
            CONF_TEMP_THRESHOLD, DEFAULT_TEMP_THRESHOLD
        )
        if temperature is not None and temperature < temp_threshold:
            return False

        return True

    # ----------------------------------------------------------- command path
    async def _apply(self, cover: CoverState, position: int, mode: str) -> None:
        """Send every cover in the group to ``position`` unless already there."""
        position = max(0, min(100, int(position)))
        entity_ids = cover.entity_ids
        if not entity_ids:
            return

        cover.last_commanded = position
        cover.mode = mode

        # Skip the service call if all known members are already in position.
        if self._all_at_position(cover, position):
            return

        cover.ignore_until = dt_util.utcnow() + timedelta(
            seconds=COMMAND_IGNORE_WINDOW
        )
        _LOGGER.debug(
            "Moving %s (%d cover(s)) to %s%% (mode=%s)",
            cover.name,
            len(entity_ids),
            position,
            mode,
        )
        await self.hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_SET_COVER_POSITION,
            {ATTR_ENTITY_ID: entity_ids, "position": position},
            blocking=False,
        )

    def _all_at_position(self, cover: CoverState, position: int) -> bool:
        """True if every member with a known position is already at ``position``.

        Returns False when no member position is known, so we still command.
        """
        any_known = False
        for entity_id in cover.entity_ids:
            state = self.hass.states.get(entity_id)
            if state is None:
                continue
            pos = state.attributes.get(ATTR_POSITION)
            if pos is None:
                continue
            try:
                if abs(int(pos) - position) > POSITION_TOLERANCE:
                    return False
            except (ValueError, TypeError):
                continue
            any_known = True
        return any_known

    def _resolve_targets(self, cover: CoverState) -> list[str]:
        """Resolve the cover entities from explicit list + areas + floors."""
        cfg = cover.config
        ids: set[str] = set(cover.explicit_entities)

        areas: set[str] = set(cfg.get(CONF_AREAS) or [])
        floors = cfg.get(CONF_FLOORS) or []
        if floors:
            area_reg = ar.async_get(self.hass)
            for area in area_reg.async_list_areas():
                if area.floor_id in floors:
                    areas.add(area.id)

        if areas:
            ent_reg = er.async_get(self.hass)
            dev_reg = dr.async_get(self.hass)
            for entry in ent_reg.entities.values():
                if entry.domain != COVER_DOMAIN:
                    continue
                area_id = entry.area_id
                if area_id is None and entry.device_id:
                    device = dev_reg.async_get(entry.device_id)
                    area_id = device.area_id if device else None
                if area_id in areas:
                    ids.add(entry.entity_id)

        return sorted(ids)

    def _group_max_position(self, cover: CoverState) -> int | None:
        """Highest (most open) current position among the group's members."""
        best: int | None = None
        for entity_id in cover.entity_ids:
            state = self.hass.states.get(entity_id)
            if state is None:
                continue
            pos = state.attributes.get(ATTR_POSITION)
            try:
                pos = int(pos)
            except (ValueError, TypeError):
                continue
            if best is None or pos > best:
                best = pos
        return best

    @callback
    def _notify(self) -> None:
        async_dispatcher_send(
            self.hass, SIGNAL_UPDATE.format(entry_id=self.entry.entry_id)
        )
