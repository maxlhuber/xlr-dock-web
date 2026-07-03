"""Local HTTP service for the Elgato XLR Dock web app."""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from xlr_control.protocol import (
    GAIN_RAW_MAX,
    GAIN_RAW_MIN,
    HEADPHONE_DB_MAX,
    HEADPHONE_DB_MIN,
)
from xlr_control.usb import (
    PRODUCT_XLR_DOCK,
    WINDEX_LINUX_CONTROL_INTERFACE,
    ElgatoXlrDevice,
    parse_product_id,
)


STATIC_DIR = Path(__file__).with_name("static")


def _parse_windex(value: str | int | None) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, int):
        return value
    return int(value.lower().removeprefix("0x"), 16)


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on", "ja"}
    return False


class XlrWebController:
    def __init__(
        self,
        *,
        product_id: int | None,
        windex: int | None,
        timeout_ms: int,
        persistent: bool,
    ) -> None:
        self.product_id = product_id or PRODUCT_XLR_DOCK
        self.windex = windex
        self.timeout_ms = timeout_ms
        self.persistent = persistent
        self._lock = threading.Lock()

    def _open_device(self):
        if os.name == "nt":
            from xlr_control.windows_usb import ElgatoXlrWinUsbDevice

            return ElgatoXlrWinUsbDevice(
                product_id=self.product_id,
                windex=self.windex,
                timeout_ms=self.timeout_ms,
            )
        return ElgatoXlrDevice(
            product_id=self.product_id,
            windex=self.windex or WINDEX_LINUX_CONTROL_INTERFACE,
            timeout_ms=self.timeout_ms,
        )

    def status(self) -> dict[str, Any]:
        with self._open_device() as device:
            config = device.read_config()
            info = device.info
            data: dict[str, Any] = {
                "ok": True,
                "platform": os.name,
                "device": {
                    "vendor_id": f"{info.vendor_id:04x}",
                    "product_id": f"{info.product_id:04x}",
                    "name": info.name,
                    "windex": f"0x{info.windex:04x}",
                },
                "config": config.summary(),
                "limits": {
                    "gain_db": [GAIN_RAW_MIN / 256.0, GAIN_RAW_MAX / 256.0],
                    "headphone_volume_db": [HEADPHONE_DB_MIN, HEADPHONE_DB_MAX],
                    "monitor_mix": [0, 100],
                },
            }
            windows_path = getattr(device, "windows_path", None)
            if windows_path is not None:
                data["windows"] = {
                    "instance_id": windows_path.instance_id,
                    "interface_guid": windows_path.interface_guid,
                }
            try:
                data["device_info"] = device.read_device_info()
            except Exception as exc:  # pragma: no cover - depends on firmware.
                data["device_info_error"] = str(exc)
            return data

    def meters(self) -> dict[str, Any]:
        with self._open_device() as device:
            left, right = device.read_meters()
            return {"ok": True, "left": left, "right": right}

    def patch_config(self, patch: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            with self._open_device() as device:
                config = device.read_config()
                before = config.summary()

                if "monitor_mix" in patch:
                    config.monitor_mix = patch["monitor_mix"]
                if "gain_db" in patch:
                    config.gain_db = patch["gain_db"]
                if "gain_raw" in patch:
                    raw = patch["gain_raw"]
                    if isinstance(raw, str):
                        raw = int(raw.lower().removeprefix("0x"), 16)
                    config.gain_raw = int(raw)
                if "headphone_volume_db" in patch:
                    config.headphone_volume_db = patch["headphone_volume_db"]
                if "muted" in patch:
                    config.muted = _truthy(patch["muted"])
                if "low_impedance" in patch:
                    config.low_impedance = _truthy(patch["low_impedance"])
                if "clipguard" in patch:
                    config.clipguard = _truthy(patch["clipguard"])

                persistent = _truthy(patch.get("persistent", self.persistent))
                device.write_config(config, persistent=persistent)
                after_config = device.read_config()
                info = device.info
                return {
                    "ok": True,
                    "persistent": persistent,
                    "device": {
                        "vendor_id": f"{info.vendor_id:04x}",
                        "product_id": f"{info.product_id:04x}",
                        "name": info.name,
                        "windex": f"0x{info.windex:04x}",
                    },
                    "before": before,
                    "config": after_config.summary(),
                }

    def toggle_mute(self) -> dict[str, Any]:
        with self._lock:
            with self._open_device() as device:
                config = device.read_config()
                before = config.summary()
                config.muted = not config.muted
                device.write_config(config, persistent=self.persistent)
                after_config = device.read_config()
                return {
                    "ok": True,
                    "persistent": self.persistent,
                    "before": before,
                    "config": after_config.summary(),
                }


class XlrRequestHandler(BaseHTTPRequestHandler):
    server_version = "XlrDockWeb/0.1"

    @property
    def controller(self) -> XlrWebController:
        return self.server.controller  # type: ignore[attr-defined]

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"{self.address_string()} - {fmt % args}")

    def _send_json(self, data: dict[str, Any], status: int = 200) -> None:
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(payload)

    def _send_static(self, path: str) -> None:
        relative = "index.html" if path in {"", "/"} else path.lstrip("/")
        target = (STATIC_DIR / relative).resolve()
        static_root = STATIC_DIR.resolve()
        if static_root not in target.parents and target != static_root:
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        if not target.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content = target.read_bytes()
        content_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def _read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        body = self.rfile.read(length)
        data = json.loads(body.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("JSON-Body muss ein Objekt sein")
        return data

    def do_OPTIONS(self) -> None:
        self._send_json({"ok": True})

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        try:
            if path == "/api/status":
                self._send_json(self.controller.status())
            elif path == "/api/meters":
                self._send_json(self.controller.meters())
            elif path.startswith("/api/"):
                self._send_json({"ok": False, "error": "Unbekannter API-Endpunkt"}, 404)
            else:
                self._send_static(path)
        except Exception as exc:
            self._send_json({"ok": False, "error": str(exc)}, 500)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            data = self._read_json_body()
            if path == "/api/config":
                self._send_json(self.controller.patch_config(data))
            elif path == "/api/actions/toggle-mute":
                self._send_json(self.controller.toggle_mute())
            else:
                self._send_json({"ok": False, "error": "Unbekannter API-Endpunkt"}, 404)
        except Exception as exc:
            self._send_json({"ok": False, "error": str(exc)}, 500)


class XlrThreadingHTTPServer(ThreadingHTTPServer):
    controller: XlrWebController


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Lokale Web-App fuer Elgato XLR Dock / Wave XLR Steuerung.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host/IP fuer den lokalen Dienst")
    parser.add_argument("--port", type=int, default=7137, help="Port fuer die Web-App")
    parser.add_argument("--product", help="USB-Product-ID, Standard ist XLR Dock 00a6")
    parser.add_argument(
        "--windex",
        help="USB-wIndex. Unter Windows leer lassen, damit 0x3303/0x3300 getestet werden.",
    )
    parser.add_argument("--timeout", type=int, default=1000, help="USB-Timeout in Millisekunden")
    parser.add_argument(
        "--persistent",
        action="store_true",
        help="Aenderungen dauerhaft im Geraet speichern. Standard ist temporaer.",
    )
    parser.add_argument("--open", action="store_true", help="Web-App beim Start im Browser oeffnen")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Nur eine Statusabfrage ausfuehren und danach beenden",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    controller = XlrWebController(
        product_id=parse_product_id(args.product),
        windex=_parse_windex(args.windex),
        timeout_ms=args.timeout,
        persistent=args.persistent,
    )
    if args.check:
        print(json.dumps(controller.status(), indent=2, ensure_ascii=False))
        return 0

    server = XlrThreadingHTTPServer((args.host, args.port), XlrRequestHandler)
    server.controller = controller
    url = f"http://{args.host}:{args.port}/"
    print(f"XLR-Dock-Web-App laeuft auf {url}")
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("XLR-Dock-Web-App wird beendet.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
