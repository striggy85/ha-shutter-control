# Brand assets

Original artwork for this integration (window-shutter glyph), drawn from scratch —
**no third-party license or attribution required**, free to use/modify.

- `icon.png` — 256×256, app icon (blue tile + white shutter)
- `icon@2x.png` — 512×512 hi-dpi
- `logo.png` / `logo@2x.png` — same artwork used as the logo

## Making the icon show up in the Home Assistant UI

Home Assistant does **not** read the logo from this custom component; integration
logos are served from the central [home-assistant/brands](https://github.com/home-assistant/brands)
repository. To get the icon shown in *Settings → Devices & Services*:

1. Fork `home-assistant/brands`.
2. Add the files under the **custom integration** path:
   ```
   custom_integrations/shutter_control/icon.png        (256×256)
   custom_integrations/shutter_control/icon@2x.png     (512×512, optional)
   custom_integrations/shutter_control/logo.png        (optional)
   ```
   (Copy them from this `brands/` folder.)
3. Open a pull request. Once merged, HA fetches it from `brands.home-assistant.io`
   automatically — no change needed in this component.

Until then HACS shows the repository's own image; HA core shows a default icon.
