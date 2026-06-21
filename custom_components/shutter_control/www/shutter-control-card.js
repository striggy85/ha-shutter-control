/* Shutter Control – Lovelace card
 * Shows each room/group with: status, next up/down time, predicted shading
 * window, an automatic on/off toggle and manual up/stop/down controls.
 *
 * Add as a dashboard resource (JavaScript Module), then use:
 *   type: custom:shutter-control-card
 * Optional config:
 *   title: My shutters
 *   entities: [sensor.living_room_status, ...]   # otherwise auto-discovered
 */

const STATUS = {
  idle: { label: "Bereit", color: "var(--secondary-text-color)" },
  open: { label: "Offen", color: "var(--primary-color)" },
  closed: { label: "Geschlossen", color: "var(--secondary-text-color)" },
  shading: { label: "Beschattung", color: "#f9a825" },
  manual: { label: "Manuell", color: "#e53935" },
  disabled: { label: "Aus", color: "var(--disabled-text-color)" },
  door_open: { label: "Tür offen", color: "#fb8c00" },
};

class ShutterControlCard extends HTMLElement {
  setConfig(config) {
    this._config = config || {};
  }

  set hass(hass) {
    this._hass = hass;
    const sig = this._signature();
    if (sig !== this._sig) {
      this._sig = sig;
      this._render();
    }
  }

  getCardSize() {
    return 1 + this._groups().length * 2;
  }

  _groups() {
    const hass = this._hass;
    if (!hass) return [];
    let ids = this._config.entities;
    if (!ids) {
      ids = Object.keys(hass.states).filter(
        (id) =>
          id.startsWith("sensor.") &&
          Array.isArray(hass.states[id].attributes.controlled_entities)
      );
      ids.sort();
    }
    const out = [];
    for (const id of ids) {
      const st = hass.states[id];
      if (!st) continue;
      const reg = hass.entities ? hass.entities[id] : null;
      const devId = reg ? reg.device_id : null;
      let sw = null;
      if (devId && hass.entities) {
        for (const eid of Object.keys(hass.entities)) {
          const e = hass.entities[eid];
          if (e.device_id === devId && eid.startsWith("switch.")) {
            sw = eid;
            break;
          }
        }
      }
      let name = st.attributes.friendly_name || id;
      name = name.replace(/\s*Status$/i, "");
      if (devId && hass.devices && hass.devices[devId]) {
        name = hass.devices[devId].name_by_user || hass.devices[devId].name || name;
      }
      out.push({
        id,
        st,
        sw,
        name,
        covers: st.attributes.controlled_entities || [],
      });
    }
    return out;
  }

  _signature() {
    const hass = this._hass;
    if (!hass) return "";
    return this._groups()
      .map((g) => {
        const a = g.st.attributes;
        const swState = g.sw && hass.states[g.sw] ? hass.states[g.sw].state : "";
        const pos = g.covers
          .map((c) =>
            hass.states[c] ? hass.states[c].attributes.current_position : ""
          )
          .join(",");
        return [
          g.id,
          g.st.state,
          a.next_up,
          a.next_down,
          a.next_action,
          a.next_action_at,
          a.shade_forecast_start,
          a.shade_forecast_end,
          a.manual_override,
          swState,
          pos,
        ].join("|");
      })
      .join(";");
  }

  _fmt(iso, withDay) {
    if (!iso) return "–";
    const d = new Date(iso);
    if (isNaN(d.getTime())) return "–";
    const t = d.toLocaleTimeString("de-DE", {
      hour: "2-digit",
      minute: "2-digit",
    });
    if (!withDay) return t;
    const now = new Date();
    const tom = new Date(now);
    tom.setDate(now.getDate() + 1);
    if (d.toDateString() === now.toDateString()) return t;
    if (d.toDateString() === tom.toDateString()) return "morgen " + t;
    return d.toLocaleDateString("de-DE", { weekday: "short" }) + " " + t;
  }

  _window(a) {
    if (a.shade_forecast_start && a.shade_forecast_end) {
      return this._fmt(a.shade_forecast_start) + "–" + this._fmt(a.shade_forecast_end);
    }
    return "keine";
  }

  _nextAction(a) {
    const map = {
      up: "Auf",
      down: "Zu",
      shading: "Beschattung",
      shading_end: "Beschattung endet",
    };
    if (!a.next_action || !a.next_action_at) return "–";
    const verb = map[a.next_action] || a.next_action;
    return verb + " um " + this._fmt(a.next_action_at, true);
  }

  _svc(domain, service, data) {
    this._hass.callService(domain, service, data);
  }

  _render() {
    if (!this._root) {
      this._root = this.attachShadow({ mode: "open" });
    }
    const groups = this._groups();
    const title = this._config.title || "Rollläden";

    const rows = groups
      .map((g, i) => {
        const a = g.st.attributes;
        const s = STATUS[g.st.state] || { label: g.st.state, color: "var(--primary-text-color)" };
        const autoOn = a.automatic_enabled !== false && g.st.state !== "disabled";
        const cover0 = g.covers[0] ? this._hass.states[g.covers[0]] : null;
        const pos = cover0 && cover0.attributes.current_position != null
          ? cover0.attributes.current_position
          : "";
        return `
        <div class="grp">
          <div class="head">
            <div class="name">${g.name}</div>
            <span class="badge" style="background:${s.color}">${s.label}</span>
          </div>
          <div class="next"><ha-icon icon="mdi:clock-fast"></ha-icon> Nächste Aktion: <b>${this._nextAction(a)}</b></div>
          <div class="info">
            <div><ha-icon icon="mdi:weather-sunset-up"></ha-icon> ${this._fmt(a.next_up, true)}</div>
            <div><ha-icon icon="mdi:weather-sunset-down"></ha-icon> ${this._fmt(a.next_down, true)}</div>
            <div><ha-icon icon="mdi:weather-sunny"></ha-icon> ${this._window(a)}</div>
          </div>
          <div class="ctl">
            <button class="auto ${autoOn ? "on" : "off"}" data-i="${i}" data-act="auto">
              <ha-icon icon="mdi:robot${autoOn ? "" : "-off"}"></ha-icon>
              Automatik ${autoOn ? "an" : "aus"}
            </button>
            <span class="spacer"></span>
            <button data-i="${i}" data-act="open" title="Auf"><ha-icon icon="mdi:arrow-up"></ha-icon></button>
            <button data-i="${i}" data-act="stop" title="Stopp"><ha-icon icon="mdi:stop"></ha-icon></button>
            <button data-i="${i}" data-act="close" title="Zu"><ha-icon icon="mdi:arrow-down"></ha-icon></button>
            <input class="pos" type="range" min="0" max="100" step="1" value="${pos}" data-i="${i}" title="Position ${pos}%">
          </div>
        </div>`;
      })
      .join("");

    const empty = `<div class="empty">Keine Shutter-Control-Gruppen gefunden.</div>`;

    this._root.innerHTML = `
      <style>
        ha-card { padding: 12px 16px 16px; }
        .title { font-size: 1.2em; font-weight: 500; margin-bottom: 6px; }
        .grp { padding: 10px 0; border-top: 1px solid var(--divider-color); }
        .grp:first-of-type { border-top: none; }
        .head { display: flex; align-items: center; justify-content: space-between; }
        .name { font-weight: 500; }
        .badge { color: #fff; border-radius: 12px; padding: 2px 10px; font-size: .8em; }
        .next { margin: 6px 0 2px; font-size: .95em; color: var(--primary-text-color); }
        .next ha-icon { --mdc-icon-size: 18px; vertical-align: -4px; color: var(--primary-color); }
        .next b { font-weight: 500; }
        .info { display: flex; flex-wrap: wrap; gap: 14px; color: var(--secondary-text-color);
                font-size: .9em; margin: 4px 0 8px; }
        .info ha-icon { --mdc-icon-size: 18px; vertical-align: -4px; }
        .ctl { display: flex; align-items: center; gap: 6px; }
        .ctl .spacer { flex: 1; }
        button { display: inline-flex; align-items: center; gap: 4px; cursor: pointer;
                 border: 1px solid var(--divider-color); background: var(--card-background-color);
                 color: var(--primary-text-color); border-radius: 8px; padding: 6px 8px; font: inherit; }
        button ha-icon { --mdc-icon-size: 20px; }
        button.auto.on { border-color: var(--primary-color); color: var(--primary-color); }
        button.auto.off { color: var(--disabled-text-color); }
        input.pos { width: 90px; }
        .empty { color: var(--secondary-text-color); padding: 8px 0; }
      </style>
      <ha-card>
        <div class="title">${title}</div>
        ${groups.length ? rows : empty}
      </ha-card>`;

    this._root.querySelectorAll("button").forEach((b) => {
      b.addEventListener("click", () => this._onAction(groups, b.dataset));
    });
    this._root.querySelectorAll("input.pos").forEach((inp) => {
      inp.addEventListener("change", () => {
        const g = groups[Number(inp.dataset.i)];
        if (g.covers.length) {
          this._svc("cover", "set_cover_position", {
            entity_id: g.covers,
            position: Number(inp.value),
          });
        }
      });
    });
  }

  _onAction(groups, ds) {
    const g = groups[Number(ds.i)];
    if (!g) return;
    switch (ds.act) {
      case "auto":
        if (g.sw) this._svc("switch", "toggle", { entity_id: g.sw });
        break;
      case "open":
        if (g.covers.length) this._svc("cover", "open_cover", { entity_id: g.covers });
        break;
      case "close":
        if (g.covers.length) this._svc("cover", "close_cover", { entity_id: g.covers });
        break;
      case "stop":
        if (g.covers.length) this._svc("cover", "stop_cover", { entity_id: g.covers });
        break;
    }
  }
}

if (!customElements.get("shutter-control-card")) {
  customElements.define("shutter-control-card", ShutterControlCard);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "shutter-control-card",
    name: "Shutter Control Card",
    description: "Rollläden/Gruppen mit Fahrzeiten, Beschattungsvorschau und Steuerung.",
  });
  console.info("%c SHUTTER-CONTROL-CARD ", "background:#2d7ff9;color:#fff", "loaded");
}
