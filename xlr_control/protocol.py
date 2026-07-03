"""Config-block parser for Elgato Wave XLR compatible devices.

The XLR Dock exposes a class-compliant audio device plus a vendor control
interface. Existing Wave XLR reverse engineering shows that device settings are
kept in a 34-byte config block transferred over USB control endpoint 0.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass


CONFIG_LEN = 34

OFF_GAIN = 0
OFF_MUTE = 4
OFF_CLIPGUARD = 5
OFF_PHANTOM = 6
OFF_LOWCUT = 7
OFF_HEADPHONE_VOLUME = 9
OFF_MONITOR_MIX_STRAY = 12
OFF_MONITOR_MIX = 13
OFF_VOLUME_SELECT = 14
OFF_GAIN_LOCK = 28
OFF_CLIPGUARD_INDICATOR = 32
OFF_LOW_IMPEDANCE = 33

GAIN_RAW_MIN = 0x0000
GAIN_RAW_MAX = 0x5000
HEADPHONE_DB_MIN = -128.0
HEADPHONE_DB_MAX = 0.0


def clamp_mix_percent(value: int | float) -> int:
    return max(0, min(100, int(round(float(value)))))


def clamp_gain_raw(value: int) -> int:
    return max(GAIN_RAW_MIN, min(GAIN_RAW_MAX, int(value)))


def clamp_headphone_volume_db(value: int | float) -> float:
    return max(HEADPHONE_DB_MIN, min(HEADPHONE_DB_MAX, float(value)))


def _bool_byte(value: bool) -> int:
    return 0x01 if value else 0x00


@dataclass
class XlrConfig:
    raw: bytearray

    @classmethod
    def from_bytes(cls, data: bytes | bytearray) -> "XlrConfig":
        if len(data) != CONFIG_LEN:
            raise ValueError(f"XLR config must be {CONFIG_LEN} bytes, got {len(data)}")
        return cls(bytearray(data))

    @classmethod
    def empty(cls) -> "XlrConfig":
        raw = bytearray(CONFIG_LEN)
        raw[2:4] = b"\x00\xec"
        raw[14] = 0x01
        raw[27] = 0x01
        return cls(raw)

    def to_bytes(self) -> bytes:
        return bytes(self.raw)

    @property
    def gain_raw(self) -> int:
        return struct.unpack_from("<H", self.raw, OFF_GAIN)[0]

    @gain_raw.setter
    def gain_raw(self, value: int) -> None:
        struct.pack_into("<H", self.raw, OFF_GAIN, clamp_gain_raw(value))

    @property
    def gain_db(self) -> float:
        return self.gain_raw / 256.0

    @gain_db.setter
    def gain_db(self, value: int | float) -> None:
        self.gain_raw = int(round(float(value) * 256.0))

    @property
    def muted(self) -> bool:
        return bool(self.raw[OFF_MUTE])

    @muted.setter
    def muted(self, value: bool) -> None:
        self.raw[OFF_MUTE] = _bool_byte(value)

    @property
    def clipguard(self) -> bool:
        return bool(self.raw[OFF_CLIPGUARD])

    @clipguard.setter
    def clipguard(self, value: bool) -> None:
        self.raw[OFF_CLIPGUARD] = _bool_byte(value)

    @property
    def phantom_power(self) -> bool:
        return bool(self.raw[OFF_PHANTOM])

    @phantom_power.setter
    def phantom_power(self, value: bool) -> None:
        self.raw[OFF_PHANTOM] = _bool_byte(value)

    @property
    def lowcut_raw(self) -> int:
        return struct.unpack_from("<H", self.raw, OFF_LOWCUT)[0]

    @lowcut_raw.setter
    def lowcut_raw(self, value: int) -> None:
        struct.pack_into("<H", self.raw, OFF_LOWCUT, int(value) & 0xFFFF)

    @property
    def headphone_volume_raw(self) -> int:
        return struct.unpack_from("<h", self.raw, OFF_HEADPHONE_VOLUME)[0]

    @headphone_volume_raw.setter
    def headphone_volume_raw(self, value: int) -> None:
        value = max(-32768, min(0, int(value)))
        struct.pack_into("<h", self.raw, OFF_HEADPHONE_VOLUME, value)

    @property
    def headphone_volume_db(self) -> float:
        return self.headphone_volume_raw / 256.0

    @headphone_volume_db.setter
    def headphone_volume_db(self, value: int | float) -> None:
        db = clamp_headphone_volume_db(value)
        self.headphone_volume_raw = int(round(db * 256.0))

    @property
    def monitor_mix(self) -> int:
        return int(self.raw[OFF_MONITOR_MIX])

    @monitor_mix.setter
    def monitor_mix(self, value: int | float) -> None:
        mix = clamp_mix_percent(value)
        self.raw[OFF_MONITOR_MIX] = mix
        # Wave XLR captures show this companion byte toggled at specific mix
        # values. Preserve the known behavior for compatibility.
        self.raw[OFF_MONITOR_MIX_STRAY] = 0x01 if mix in (41, 47) else 0x00

    @property
    def low_impedance(self) -> bool:
        return bool(self.raw[OFF_LOW_IMPEDANCE])

    @low_impedance.setter
    def low_impedance(self, value: bool) -> None:
        self.raw[OFF_LOW_IMPEDANCE] = _bool_byte(value)

    @property
    def gain_lock(self) -> bool:
        return bool(self.raw[OFF_GAIN_LOCK])

    @gain_lock.setter
    def gain_lock(self, value: bool) -> None:
        self.raw[OFF_GAIN_LOCK] = _bool_byte(value)

    @property
    def clipguard_indicator(self) -> bool:
        return bool(self.raw[OFF_CLIPGUARD_INDICATOR])

    @clipguard_indicator.setter
    def clipguard_indicator(self, value: bool) -> None:
        self.raw[OFF_CLIPGUARD_INDICATOR] = _bool_byte(value)

    def summary(self) -> dict[str, object]:
        return {
            "gain_raw": self.gain_raw,
            "gain_db": round(self.gain_db, 2),
            "muted": self.muted,
            "clipguard": self.clipguard,
            "phantom_power": self.phantom_power,
            "lowcut_raw": self.lowcut_raw,
            "headphone_volume_db": round(self.headphone_volume_db, 2),
            "monitor_mix": self.monitor_mix,
            "low_impedance": self.low_impedance,
            "gain_lock": self.gain_lock,
            "clipguard_indicator": self.clipguard_indicator,
        }
