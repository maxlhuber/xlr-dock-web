"""Elgato XLR Dock / Wave XLR control helpers."""

from .protocol import (
    CONFIG_LEN,
    XlrConfig,
    clamp_gain_raw,
    clamp_headphone_volume_db,
    clamp_mix_percent,
)

__all__ = [
    "CONFIG_LEN",
    "XlrConfig",
    "clamp_gain_raw",
    "clamp_headphone_volume_db",
    "clamp_mix_percent",
]
