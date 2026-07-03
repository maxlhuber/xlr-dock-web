# XLR-Dock-Web-App Unter Windows

Die Web-App besteht aus zwei Teilen:

- einem lokalen Dienst auf `127.0.0.1`
- einer Browser-Oberflaeche, die diesen Dienst anspricht

Dadurch bleibt die Oberflaeche betriebssystemunabhaengig, waehrend der lokale
Dienst den noetigen Hardwarezugriff erledigt.

## Starten

Im Repository:

```powershell
.\scripts\start-xlr-web-windows.ps1
```

Danach oeffnet sich:

```text
http://127.0.0.1:7137/
```

Falls der Browser nicht automatisch geoeffnet werden soll:

```powershell
.\scripts\start-xlr-web-windows.ps1 -NoBrowser
```

Nur Hardware und Backend pruefen:

```powershell
.\scripts\start-xlr-web-windows.ps1 -Check -NoBrowser
```

## Als Tray-App Starten

Fuer den normalen Alltag ist die Tray-App angenehmer:

```powershell
.\scripts\start-xlr-tray-windows.ps1
```

Sie legt ein Symbol im Windows-Infobereich an. Links-Klick oeffnet das
Webinterface. Rechts-Klick zeigt ein Menue mit:

- Webinterface oeffnen
- Beenden

Beim Start direkt das Webinterface oeffnen:

```powershell
.\scripts\start-xlr-tray-windows.ps1 -Open
```

## Funktionen

- XLR-Dock-Status lesen
- Monitor-Mix setzen: `0` = PC, `100` = Mikrofon
- Hardware-Gain setzen
- Kopfhoererlautstaerke setzen
- Mikrofon-Mute toggeln
- Low-Impedance-Modus toggeln
- Clipguard toggeln
- Pegel-Endpunkt vorbereiten

Standardmaessig sind Schreibvorgaenge temporaer. Sie gelten also fuer die
laufende Geraetesitzung, ohne dauerhaft ins Geraet geschrieben zu werden.

Dauerhaftes Speichern kann beim Start aktiviert werden:

```powershell
.\scripts\start-xlr-web-windows.ps1 -Persistent
```

## API

Status:

```text
GET /api/status
```

Pegel:

```text
GET /api/meters
```

Konfiguration aendern:

```text
POST /api/config
```

Beispiel:

```json
{
  "monitor_mix": 50,
  "gain_db": 57,
  "headphone_volume_db": -10,
  "low_impedance": true
}
```

`monitor_mix` ist der Mikrofon-Anteil in Prozent. `0` bedeutet nur PC-Signal,
`100` bedeutet nur Mikrofonsignal.

Mute toggeln:

```text
POST /api/actions/toggle-mute
```

## Hinweise

- Das XLR Dock muss angeschlossen sein.
- Wave Link sollte unter Windows einmal installiert gewesen sein, damit das
  WinUSB-Controls-Interface vorhanden ist.
- Phantom Power wird bewusst nicht als Web-Control angeboten, weil am Setup ein
  dynamisches Mikrofon haengt.
