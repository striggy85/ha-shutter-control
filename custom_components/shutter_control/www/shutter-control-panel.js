/* Shutter Control – sidebar panel
 * A full-page panel (registered in the left sidebar) that simply hosts the
 * shutter-control-card with auto-discovery of all groups.
 */

import "./shutter-control-card.js";

class ShutterControlPanel extends HTMLElement {
  set hass(hass) {
    this._hass = hass;
    if (this._card) this._card.hass = hass;
  }

  // Home Assistant assigns these; we don't need them but must accept them.
  set narrow(_v) {}
  set route(_v) {}
  set panel(_v) {}

  connectedCallback() {
    if (this._card) return;
    this.style.display = "block";
    this.style.padding = "16px";
    this.style.maxWidth = "760px";
    this.style.margin = "0 auto";

    const card = document.createElement("shutter-control-card");
    card.setConfig({ title: "Rollläden" });
    if (this._hass) card.hass = this._hass;
    this._card = card;
    this.appendChild(card);
  }
}

if (!customElements.get("shutter-control-panel")) {
  customElements.define("shutter-control-panel", ShutterControlPanel);
}
