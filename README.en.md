# Shutter Control for Home Assistant

🌐 [Deutsch](README.md) | **English**

> [!NOTE]
> **Built with AI.** This integration was developed with the help of an AI assistant
> (Claude / Claude Code) and then tested and maintained by a human. The code has been
> reviewed to the best of our knowledge but may contain bugs – please test it yourself
> before relying on it. Use at your own risk.
>
> 💬 **Feedback welcome!** Bugs, requests and improvement ideas are explicitly welcome –
> please open a [GitHub issue](https://github.com/striggy85/ha-shutter-control/issues)
> (German or English is fine). Pull requests too.

A custom integration that reproduces the core features of the ioBroker adapter
[`shuttercontrol`](https://github.com/iobroker-community-adapters/ioBroker.shuttercontrol)
for Home Assistant:

- **Sun shading** per facade – azimuth window, sun-elevation window, optional **cloud
  cover** (%) and temperature thresholds (only shades when the sky is clear, i.e. low
  cloud cover).
- **Auto-up in the morning / auto-down in the evening** – separate times for weekday and
  weekend.
- **Living-room vs. bedroom logic** – bedrooms close fully for shading/in the evening,
  living rooms only go to the shade position.
- **Manual override** – if someone moves a shutter by hand, automation pauses until the
  next up/down event (next day).
- **Rooms / groups** – one configuration can control several shutters together (one switch,
  one status, one logic for the whole group).
- **Door/window contact** – optional binary sensor per group with two switches (live in the
  card): "Door open → up" (raise + lock automation while open) and "Door closed → restore"
  (on close, move to the **current target state** – i.e. closed if it should be closed/shaded
  now). The contact is **debounced** (global setting, default 10 s): a brief slam/reopen does
  nothing.

> Controls existing `cover.*` entities that support `set_cover_position`
> (position 100 % = open, 0 % = closed).

## Installation

### HACS (recommended)
1. HACS → Integrations → ⋮ → *Custom repositories* → add this repo as category
   *Integration*.
2. Install "Shutter Control", restart Home Assistant.

### Manual
Copy `custom_components/shutter_control/` into `<config>/custom_components/` and restart
Home Assistant.

## Setup
1. *Settings → Devices & Services → Add integration → "Shutter Control"*.
2. Global settings (sun entity `sun.sun`, optional cloud-cover/temperature sensor,
   thresholds, evaluation interval).
3. On the integration tile, **"Add room / group"** – give it a name and choose the target:
   **individual shutters** and/or whole **HA areas** or **floors** (all `cover.*` in them are
   controlled automatically – including ones added later).

Each room/group creates two entities:
- `switch.<name>_automatic` – automation on/off for the group.
- `sensor.<name>_status` – current mode (`idle`, `open`, `closed`, `shading`, `manual`,
  `disabled`, `door_open`) plus attributes (`manual_override`, `shading_active`,
  `controlled_entities`, `next_up`, `next_down`, `next_action`, …).

> Tip: you can create a single shutter (one group = one cover) or a whole room
> (one group = several covers) – mix freely.

## Dashboard card
The integration ships a **Lovelace card** that shows, per group, the status, next up/down
times, the predicted shading window (geometric, from the sun's path, ignoring clouds), an
automation toggle and manual controls (up/stop/down + position).

The card is loaded as a frontend resource **automatically** at setup – nothing to add by
hand. After a restart (clear the browser cache if needed):

1. Dashboard → *Add card* → **"Shutter Control Card"** (or manually):
   ```yaml
   type: custom:shutter-control-card
   title: Shutters
   # entities: [sensor.living_room_status, ...]   # optional, otherwise auto-detected
   ```

Without `entities` the card auto-detects all groups (via the integration's status sensors).
The required data is exposed by `sensor.<name>_status` as attributes (`next_up`, `next_down`,
`shade_forecast_start`, `shade_forecast_end`, …).

The integration also registers a **"Shutters" entry in the left sidebar** (panel) with the
same overview – no dashboard configuration needed.

### Shading only lowers
The global settings include the option **"Shading only lowers"** (on by default): if a
shutter is already further down than the shade position (e.g. closed at night), shading does
**not** raise it. Turn it off to always move exactly to the shade position.

### Keep shade until evening
Option **"Keep shade position until evening"** (off by default): once shading has engaged the
shutter stays at the shade position – even as the sun moves on – and only closes the
**remaining bit** at the evening down time (instead of reopening in between).

## Global defaults vs. per-group overrides
Sensors, thresholds and the **default values** for azimuth, elevation and up/down
times & triggers are set **once** in the integration's global settings (*Configure* on the
integration tile). In each group these fields are **optional**:

- **empty** → the global default applies,
- **filled** → an own value just for that group (e.g. azimuth per facade, bedroom closing
  earlier in the evening).

The only per-group fields that stay mandatory: name, shutters, room type, positions
(open/closed/shade) and the on/off switches for shading/auto-up/auto-down.

## How it works (in short)
On every interval (and on changes of sun/sensors/shutter):

1. **Auto-up**: when the up time passes, once per day → position "open". Trigger per shutter:
   fixed **time** (separate weekday/weekend), **sunrise** or **sunset** – each with an offset
   (±min) and optional "not before / not after" bounds.
2. **Auto-down**: when the down time passes, once per day → position "closed". Same trigger
   options (default: sunset or fixed time). Both events clear a manual override.
3. **Shading** (only during the day, between up and down): if the sun azimuth is within the
   facade window, the elevation is between min/max and – if sensors are set – cloud cover is
   **below** the threshold (clear sky) and temperature above the threshold → shade position
   (bedroom: fully closed). When the condition ends → back to "open".
4. **Manual**: if the shutter position changes outside of our own command, automation pauses
   until the next up/down event – but **at the latest when the day changes**. So a shutter
   moved by hand in the evening shades again normally the next day (even with "auto-up in the
   morning" turned off).

## Notes / not included
Deliberately not ported (compared to the original adapter): holiday/guest/vacation mode,
window/ventilation locks, weather forecast, per-action individual delays. Can be added on
request.

> The sun position values (azimuth/elevation for shading) and the astro events
> (sunrise/sunset for up/down) come from `sun.sun` / Home Assistant's astral library – at
> your configured location.

## Contributing & feedback
This integration was created **with AI assistance (Claude / Claude Code)** and is maintained
by a human. It is provided without warranty.

- 🐞 **Found a bug?** Please open an [issue](https://github.com/striggy85/ha-shutter-control/issues)
  – ideally with your HA version, integration version, the affected group/configuration and
  (if available) the relevant log excerpt.
- 💡 **Idea or improvement?** Also welcome as an issue – small hints count too.
- 🔧 **Pull requests** are welcome.
- Language: German or English.

Since parts of the code are AI-generated, please test changes before relying on them in
production. Feedback helps improve the integration.
