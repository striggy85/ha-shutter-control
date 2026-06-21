# Shutter Control für Home Assistant

Eine Custom Integration, die die Kernfunktionen des ioBroker-Adapters
[`shuttercontrol`](https://github.com/iobroker-community-adapters/ioBroker.shuttercontrol)
für Home Assistant nachbildet:

- **Sonnenschutz / Beschattung** pro Fassade – Azimut-Fenster, Sonnenhöhe-Fenster,
  optionale **Bewölkungs-** (%) und Temperaturschwelle (beschattet nur bei niedriger
  Bewölkung = klarem Himmel).
- **Auto-Auf morgens / Auto-Zu abends** – getrennte Zeiten für Wochentag und Wochenende.
- **Wohn- vs. Schlafraum-Logik** – Schlafräume fahren bei Beschattung/abends komplett zu,
  Wohnräume nur auf die Beschattungs-Position.
- **Manuelle Übersteuerung** – fährt jemand den Rollladen von Hand, pausiert die Automatik
  bis zum nächsten Auf-/Zu-Ereignis (nächster Tag).
- **Zimmer / Gruppen** – eine Konfiguration kann mehrere Rollläden gemeinsam steuern
  (ein Schalter, ein Status, eine Logik für die ganze Gruppe).

> Steuert vorhandene `cover.*`-Entitäten, die `set_cover_position` unterstützen
> (Position 100 % = offen, 0 % = geschlossen).

## Installation

### HACS (empfohlen)
1. HACS → Integrationen → ⋮ → *Benutzerdefiniertes Repository* → dieses Repo als
   Kategorie *Integration* hinzufügen.
2. „Shutter Control" installieren, Home Assistant neu starten.

### Manuell
`custom_components/shutter_control/` nach `<config>/custom_components/` kopieren und
Home Assistant neu starten.

## Einrichtung
1. *Einstellungen → Geräte & Dienste → Integration hinzufügen → „Shutter Control"*.
2. Globale Einstellungen (Sonnen-Entität `sun.sun`, optional Bewölkungs-/Temperatursensor,
   Schwellen, Auswerte-Intervall).
3. Auf der Integrationskachel **„Zimmer / Gruppe hinzufügen"** – Namen vergeben und
   **einen oder mehrere** Rollläden auswählen, die diese Gruppe gemeinsam steuert.

Je Zimmer/Gruppe entstehen zwei Entitäten:
- `switch.<name>_automatic` – Automatik der Gruppe an/aus.
- `sensor.<name>_status` – aktueller Modus (`idle`, `open`, `closed`, `shading`,
  `manual`, `disabled`) inkl. Attributen (`manual_override`, `shading_active`,
  `controlled_entities`, …).

> Tipp: Du kannst einen Rollladen einzeln (eine Gruppe = ein Cover) oder zimmerweise
> (eine Gruppe = mehrere Cover) anlegen – beliebig mischbar.

## Globale Vorgaben vs. Gruppen-Override
Sensoren, Schwellen und die **Standardwerte** für Azimut, Elevation sowie Auf-/Zu-Zeiten &
-Trigger werden **einmal** in den Grundeinstellungen der Integration gesetzt
(*Konfigurieren* auf der Integrationskachel). In jeder Gruppe sind diese Felder **optional**:

- **leer** → es gilt die globale Vorgabe,
- **ausgefüllt** → eigener Wert nur für diese Gruppe (z. B. Azimut je Fassade, Schlafzimmer
  abends früher zu).

Pro Gruppe verpflichtend bleiben nur: Name, Rollläden, Raumtyp, Positionen (offen/zu/
Beschattung) und die An/Aus-Schalter für Beschattung/Auto-Auf/Auto-Zu.

## Logik in Kürze
Bei jedem Intervall (und bei Änderungen von Sonne/Sensoren/Rollladen):

1. **Auto-Auf**: Beim Überschreiten der Auf-Zeit einmal pro Tag → Position „offen".
   Auslöser je Rollladen wählbar: feste **Uhrzeit** (getrennt Wochentag/Wochenende),
   **Sonnenaufgang** oder **Sonnenuntergang** – jeweils mit Offset (±Min.) und optionalen
   Grenzen „nicht vor / nicht nach".
2. **Auto-Zu**: Beim Überschreiten der Zu-Zeit einmal pro Tag → Position „geschlossen".
   Gleiche Auslöser-Optionen (Standard: Sonnenuntergang oder feste Uhrzeit).
   Beide Ereignisse setzen eine manuelle Übersteuerung zurück.
3. **Beschattung** (nur tagsüber zwischen Auf- und Zu-Zeit): Wenn Sonnen-Azimut im
   Fassadenfenster, Sonnenhöhe zwischen min/max und – falls Sensoren gesetzt – Bewölkung
   **unter** der Schwelle (klarer Himmel) sowie Temperatur über Schwelle →
   Beschattungs-Position (Schlafraum: komplett zu). Ende der Bedingung → wieder „offen".
4. **Manuell**: Ändert sich die Rollladenposition außerhalb eines eigenen Stellbefehls,
   wird die Automatik bis zum nächsten Auf-/Zu-Ereignis pausiert.

## Hinweise / nicht enthalten
Bewusst nicht portiert (gegenüber dem Original-Adapter): Ferien-/Gäste-/Urlaubsmodus,
Fenster-/Lüftungs-Sperren, Wettervorhersage, individuelle Verzögerungen je Aktion.
Lässt sich bei Bedarf ergänzen.

> Die Sonnenstand-Werte (Azimut/Höhe für Beschattung) und die Astro-Ereignisse
> (Sonnenauf-/-untergang für Auf/Zu) kommen aus `sun.sun` bzw. der Astral-Bibliothek von
> Home Assistant – an deinem konfigurierten Standort.
