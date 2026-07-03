# XLR Dock Web

Lokale Web-App fuer das Elgato XLR Dock. Die App laeuft zuerst unter Windows
und steuert das Dock direkt ueber das WinUSB-Controls-Interface.

## Aktueller Stand

- Windows-Webinterface auf `http://127.0.0.1:7137/`
- Windows-Tray-App mit Menue zum Oeffnen und Beenden
- Hardware-Monitor-Mix: `0` = PC, `100` = Mikrofon
- Hardware-Gain
- Kopfhoererlautstaerke
- Mikrofon-Mute
- Low-Impedance-Modus
- Clipguard
- Status- und API-Endpunkte fuer spaetere StreamController-Integration

Phantom Power wird bewusst nicht als Schalter angeboten, weil das aktuelle
Setup ein dynamisches Mikrofon verwendet.

## Start Unter Windows

Tray-App:

```powershell
.\scripts\start-xlr-tray-windows.ps1
```

Nur Webdienst mit Browser:

```powershell
.\scripts\start-xlr-web-windows.ps1
```

Backend pruefen:

```powershell
.\scripts\start-xlr-web-windows.ps1 -Check -NoBrowser
```

## Bedienung

Nach dem Start erscheint ein Symbol im Windows-Infobereich.

- Links-Klick: Webinterface oeffnen
- Rechts-Klick: Menue mit `Webinterface oeffnen` und `Beenden`

## API

```text
GET  /api/status
GET  /api/meters
POST /api/config
POST /api/actions/toggle-mute
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

## Entwicklung

Tests:

```powershell
python -m unittest discover -s tests
```

Syntaxcheck:

```powershell
python -m compileall xlr_control xlr_web
```

Die Linux-Anbindung soll spaeter dieselbe API verwenden, aber mit libusb,
PipeWire/PipeWeaver und Autostart auf CachyOS.
