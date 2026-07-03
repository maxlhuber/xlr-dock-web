# XLR-Dock-Protokollnotizen

Diese Datei ist das Arbeitsnotizbuch fuer das reverse-engineerte USB-Control-
Protokoll.

## Geraeteidentitaet

- Hersteller: Elgato
- Produkt: Stream Deck Plus mit XLR Dock
- Windows-ID XLR Dock: `0fd9:00a6`
- Windows-ID Stream Deck Plus: `0fd9:0084`
- Linux-Status: erscheint voraussichtlich bereits als Audio-Eingang und Audio-
  Ausgang; Hardware-Gain und Monitor-Mix muessen separat gesteuert werden.

Diesen Abschnitt ausfuellen, sobald Linux installiert ist:

```text
lsusb:

arecord -l:

aplay -l:

wpctl status:

```

## Protokollbasis

Die erste Implementierung nutzt die bereits reverse-engineerte Wave-XLR-
Kommandostruktur. Diese Struktur ist fuer das XLR Dock unter Windows per
WinUSB read/write bestaetigt.

Quellen:

- `OpenWave`: <https://github.com/rikkichy/openwave>
- `tidal-wave`: <https://github.com/titaniumtraveler/tidal-wave>
- Linux-Audio-Fix mit XLR-Dock-Bezug: <https://github.com/jmansar/wavexlr-on-linux-cfg>

Die Kommandos laufen ueber USB-Control-Transfers auf Endpoint 0:

| Feld | Wert |
| --- | --- |
| Vendor-ID | `0x0fd9` |
| XLR-Dock Product-ID | `0x00a6` |
| Wave-XLR Product-ID | `0x007d` |
| Read request | `bmRequestType=0xa1`, `bRequest=0x85` |
| Write request | `bmRequestType=0x21`, `bRequest=0x05` |
| Config `wValue` | `0x0000` |
| Linux `wIndex` | `0x3303` |
| Config-Laenge | 34 Bytes |

`wIndex=0x3303` ist wichtig: die Firmware akzeptiert nach aktuellem Stand den
`0x33`-Praefix, waehrend Linux den Transfer Interface 3 zuordnet und dadurch
den belegten Audio-Treiber auf Interface 0 nicht detachen muss.

Unter Windows wurden `0x3303` und `0x3300` erfolgreich gelesen. Der Schreibtest
nutzt `0x3303`, damit der Linux-Pfad und der Windows-Beleg dieselbe Form haben.

## Bekannte Config-Offsets

Noch nicht alle Felder sind XLR-Dock-spezifisch funktional getestet. Der
aktuelle Code schreibt nur per Read-Modify-Write und erhaelt dadurch unbekannte
Felder.

| Offset | Laenge | Bedeutung | Format | Implementiert |
| ---: | ---: | --- | --- | --- |
| 0 | 2 | Hardware-Gain | `u16`, Q8.8 dB | ja |
| 4 | 1 | Mikrofon-Mute | bool | ja |
| 5 | 1 | Clipguard | bool | nur lesen/erhalten |
| 6 | 1 | Phantom Power | bool | nur lesen/erhalten |
| 7 | 2 | Lowcut | `u16` | nur lesen/erhalten |
| 9 | 2 | Kopfhoererlautstaerke | `i16`, Q8.8 dB | ja |
| 12 | 1 | Monitor-Mix-Begleitbyte | `0x01` bei Mix 41/47, sonst `0x00` | ja |
| 13 | 1 | Kopfhoerer-Monitor-Mix | Mikrofon-Anteil in Prozent, `0` PC bis `100` Mic | ja, Windows bestaetigt |
| 28 | 1 | Gain Lock | bool | nur lesen/erhalten |
| 32 | 1 | Clipguard Indicator | bool | nur lesen/erhalten |
| 33 | 1 | Low-Impedance-Mode | bool | ja |

## Implementierter Stand

| Funktion | Richtung | Transport | Status |
| --- | --- | --- | --- |
| Geraetezustand lesen | Geraet -> Host | USB-Control Config Read | Windows bestaetigt, Linux-Test ausstehend |
| Kopfhoerer-Monitor-Mix | Host -> Geraet | USB-Control Read-Modify-Write | Windows bestaetigt, Linux-Test ausstehend |
| Hardware-Gain | Host -> Geraet | USB-Control Read-Modify-Write | CLI implementiert, Einzeltest ausstehend |
| Kopfhoererlautstaerke | Host -> Geraet | USB-Control Read-Modify-Write | CLI implementiert, Einzeltest ausstehend |
| Low-Impedance-Mode | Host -> Geraet | USB-Control Read-Modify-Write | CLI implementiert, Einzeltest ausstehend |
| Mikrofon-Mute | Host -> Geraet | USB-Control Read-Modify-Write | CLI implementiert, Einzeltest ausstehend |

Phantom Power wird absichtlich nicht als CLI-Kommando angeboten.

## Windows-Bestaetigung 2026-06-29

Gelesener Config-Block des XLR Dock (`0fd9:00a6`, Interface `MI_03`):

```text
00390000000100010000fa00006400ff0000ffffffffffffffffff0001ff37000101
```

Dekodiert:

- Gain raw: `14592` (`0x3900`)
- Mute: aus
- Phantom Power: aus
- Kopfhoererlautstaerke raw: `-1536` (`-6.0 dB`)
- Monitor-Mix: `100`
- Low-Impedance: an

Read-Modify-Write-Test:

```text
Monitor-Mix 100 -> 50:
00390000000100010000fa00006400ff0000ffffffffffffffffff0001ff37000101
00390000000100010000fa00003200ff0000ffffffffffffffffff0001ff37000101

Monitor-Mix 50 -> 100:
00390000000100010000fa00003200ff0000ffffffffffffffffff0001ff37000101
00390000000100010000fa00006400ff0000ffffffffffffffffff0001ff37000101
```

Damit ist bestaetigt, dass Offset 13 beim XLR Dock der hardwareseitige
Kopfhoerer-Monitor-Mix ist.

## Arbeitshypothesen

- Audio-Streaming ist class-compliant USB Audio.
- Geraeteeinstellungen laufen ueber USB-Control-Transfers auf Endpoint 0.
- Der Monitor-Mix muss hardwareseitig gesteuert werden, damit das Live-
  Monitoring latenzfrei bleibt.
- Wave-XLR-Protokoll und XLR-Dock-Protokoll teilen den Config-Block fuer die
  bisher getesteten Felder. Der CachyOS-Test bestaetigt als naechstes den
  Linux-libusb-Pfad.
