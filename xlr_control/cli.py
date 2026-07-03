#!/usr/bin/env python3
"""Command line control for Elgato XLR Dock / Wave XLR compatible devices."""

from __future__ import annotations

import argparse
import json
from typing import Callable

from .protocol import clamp_gain_raw, clamp_headphone_volume_db, clamp_mix_percent
from .usb import (
    PRODUCT_NAMES,
    WINDEX_LINUX_CONTROL_INTERFACE,
    ElgatoXlrDevice,
    parse_product_id,
)


def _print(data: object, as_json: bool) -> None:
    if as_json:
        print(json.dumps(data, indent=2))
    else:
        if isinstance(data, dict):
            for key, value in data.items():
                print(f"{key}: {value}")
        else:
            print(data)


def _open(args: argparse.Namespace) -> ElgatoXlrDevice:
    return ElgatoXlrDevice(
        product_id=parse_product_id(args.product),
        windex=int(str(args.windex).removeprefix("0x"), 16),
        timeout_ms=args.timeout,
    )


def cmd_status(args: argparse.Namespace) -> int:
    with _open(args) as device:
        config = device.read_config()
        info = device.info
        data = {
            "device": {
                "vendor_id": f"{info.vendor_id:04x}",
                "product_id": f"{info.product_id:04x}",
                "name": info.name,
                "windex": f"0x{info.windex:04x}",
            },
            "config": config.summary(),
        }
        try:
            data["device_info"] = device.read_device_info()
        except Exception as exc:
            data["device_info_error"] = str(exc)
        _print(data, args.json)
    return 0


def _read_modify_write(
    args: argparse.Namespace,
    mutator: Callable,
    label: str,
) -> int:
    with _open(args) as device:
        config = device.read_config()
        before = config.summary()
        mutator(config)
        device.write_config(config, persistent=args.persistent)
        after = config.summary()
        _print({"changed": label, "before": before, "after": after}, args.json)
    return 0


def cmd_set_mix(args: argparse.Namespace) -> int:
    value = clamp_mix_percent(args.percent)
    return _read_modify_write(
        args,
        lambda config: setattr(config, "monitor_mix", value),
        f"monitor_mix={value}",
    )


def cmd_set_gain(args: argparse.Namespace) -> int:
    raw = clamp_gain_raw(
        int(str(args.raw).lower().removeprefix("0x"), 16)
        if args.hex
        else int(args.raw)
    )
    return _read_modify_write(
        args,
        lambda config: setattr(config, "gain_raw", raw),
        f"gain_raw=0x{raw:04x}",
    )


def cmd_set_headphones(args: argparse.Namespace) -> int:
    db = clamp_headphone_volume_db(args.db)
    return _read_modify_write(
        args,
        lambda config: setattr(config, "headphone_volume_db", db),
        f"headphone_volume_db={db}",
    )


def cmd_set_mute(args: argparse.Namespace) -> int:
    muted = args.state == "on"
    return _read_modify_write(
        args,
        lambda config: setattr(config, "muted", muted),
        f"muted={muted}",
    )


def cmd_set_low_impedance(args: argparse.Namespace) -> int:
    enabled = args.state == "on"
    return _read_modify_write(
        args,
        lambda config: setattr(config, "low_impedance", enabled),
        f"low_impedance={enabled}",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Elgato XLR Dock / Wave XLR per USB-Control-Transfer steuern.",
    )
    parser.add_argument(
        "--product",
        help=(
            "USB-Product-ID. Leer sucht zuerst XLR Dock 00a6, dann Wave XLR 007d. "
            f"Bekannt: {', '.join(f'{pid:04x}={name}' for pid, name in PRODUCT_NAMES.items())}"
        ),
    )
    parser.add_argument(
        "--windex",
        default=f"0x{WINDEX_LINUX_CONTROL_INTERFACE:04x}",
        help="USB-wIndex. Standard 0x3303 fuer Linux ohne Audio-Treiber-Detach.",
    )
    parser.add_argument("--timeout", type=int, default=1000, help="USB-Timeout in Millisekunden")
    parser.add_argument("--json", action="store_true", help="JSON ausgeben")

    sub = parser.add_subparsers(dest="command", required=True)

    status = sub.add_parser("status", help="Aktuellen Hardwarezustand lesen")
    status.set_defaults(func=cmd_status)

    def add_write_common(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--persistent",
            action="store_true",
            help="Aenderung dauerhaft im Geraet speichern. Standard ist temporaer.",
        )

    set_mix = sub.add_parser("set-mix", help="Kopfhoerer-Monitor-Mix in Prozent setzen")
    set_mix.add_argument("percent", type=float, help="Mikrofon-Anteil: 0 = PC, 100 = Mikrofon")
    add_write_common(set_mix)
    set_mix.set_defaults(func=cmd_set_mix)

    set_gain = sub.add_parser("set-gain", help="Hardware-Gain als Rohwert setzen")
    set_gain.add_argument("raw", help="Rohwert, z.B. 8192 fuer 32 dB")
    set_gain.add_argument("--hex", action="store_true", help="raw als Hexwert interpretieren")
    add_write_common(set_gain)
    set_gain.set_defaults(func=cmd_set_gain)

    set_hp = sub.add_parser("set-headphones", help="Kopfhoererlautstaerke in dB setzen")
    set_hp.add_argument("db", type=float, help="-128.0 bis 0.0 dB")
    add_write_common(set_hp)
    set_hp.set_defaults(func=cmd_set_headphones)

    set_mute = sub.add_parser("set-mute", help="Mikrofon-Mute setzen")
    set_mute.add_argument("state", choices=("on", "off"), help="on = stumm, off = aktiv")
    add_write_common(set_mute)
    set_mute.set_defaults(func=cmd_set_mute)

    set_lowz = sub.add_parser("set-low-impedance", help="Low-Impedance-Mode setzen")
    set_lowz.add_argument("state", choices=("on", "off"), help="on oder off")
    add_write_common(set_lowz)
    set_lowz.set_defaults(func=cmd_set_low_impedance)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
