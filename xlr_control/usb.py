"""libusb backend for Elgato XLR Dock / Wave XLR control transfers."""

from __future__ import annotations

import ctypes
import ctypes.util
import threading
from dataclasses import dataclass
from typing import Iterable

from .protocol import CONFIG_LEN, XlrConfig


VENDOR_ID = 0x0FD9
PRODUCT_XLR_DOCK = 0x00A6
PRODUCT_WAVE_XLR = 0x007D
PRODUCT_NAMES = {
    PRODUCT_XLR_DOCK: "Elgato XLR Dock",
    PRODUCT_WAVE_XLR: "Elgato Wave XLR",
}
DEFAULT_PRODUCTS = (PRODUCT_XLR_DOCK, PRODUCT_WAVE_XLR)

BREQUEST_READ = 0x85
BREQUEST_WRITE = 0x05
WVALUE_CONFIG = 0x0000
WVALUE_METERS = 0x0001
WVALUE_DEVICE_INFO = 0x000A

WINDEX_LINUX_CONTROL_INTERFACE = 0x3303
WINDEX_NATIVE = 0x3300

RT_CLASS_IN_INTERFACE = 0xA1
RT_CLASS_OUT_INTERFACE = 0x21

WRITE_MODE_TEMPORARY = 0x0000
WRITE_MODE_PERSISTENT = 0x0002


class UsbError(RuntimeError):
    pass


class DeviceNotFoundError(UsbError):
    pass


class LibusbMissingError(UsbError):
    pass


@dataclass(frozen=True)
class DeviceInfo:
    vendor_id: int
    product_id: int
    name: str
    windex: int


class _Libusb:
    def __init__(self) -> None:
        lib_path = ctypes.util.find_library("usb-1.0") or "libusb-1.0.so.0"
        try:
            self.lib = ctypes.CDLL(lib_path)
        except OSError as exc:
            raise LibusbMissingError(
                "libusb-1.0 wurde nicht gefunden. Auf CachyOS: sudo pacman -S libusb"
            ) from exc

        self.lib.libusb_init.argtypes = [ctypes.POINTER(ctypes.c_void_p)]
        self.lib.libusb_init.restype = ctypes.c_int
        self.lib.libusb_open_device_with_vid_pid.argtypes = [
            ctypes.c_void_p,
            ctypes.c_uint16,
            ctypes.c_uint16,
        ]
        self.lib.libusb_open_device_with_vid_pid.restype = ctypes.c_void_p
        self.lib.libusb_close.argtypes = [ctypes.c_void_p]
        self.lib.libusb_close.restype = None
        self.lib.libusb_control_transfer.argtypes = [
            ctypes.c_void_p,
            ctypes.c_uint8,
            ctypes.c_uint8,
            ctypes.c_uint16,
            ctypes.c_uint16,
            ctypes.POINTER(ctypes.c_ubyte),
            ctypes.c_uint16,
            ctypes.c_uint,
        ]
        self.lib.libusb_control_transfer.restype = ctypes.c_int

        self.ctx = ctypes.c_void_p()
        ret = self.lib.libusb_init(ctypes.byref(self.ctx))
        if ret < 0:
            raise UsbError(f"libusb_init fehlgeschlagen: {ret}")


_LIBUSB: _Libusb | None = None
_LIBUSB_LOCK = threading.Lock()


def _get_libusb() -> _Libusb:
    global _LIBUSB
    with _LIBUSB_LOCK:
        if _LIBUSB is None:
            _LIBUSB = _Libusb()
        return _LIBUSB


def parse_product_id(value: str | int | None) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, int):
        return value
    return int(value.lower().removeprefix("0x"), 16)


class ElgatoXlrDevice:
    def __init__(
        self,
        product_id: int | None = None,
        *,
        windex: int = WINDEX_LINUX_CONTROL_INTERFACE,
        timeout_ms: int = 1000,
    ) -> None:
        self.product_id = product_id
        self.windex = windex
        self.timeout_ms = timeout_ms
        self._handle: ctypes.c_void_p | None = None
        self._opened_product_id: int | None = None
        self._lock = threading.Lock()

    @property
    def is_open(self) -> bool:
        return self._handle is not None

    @property
    def info(self) -> DeviceInfo:
        product_id = self._opened_product_id or self.product_id or PRODUCT_XLR_DOCK
        return DeviceInfo(
            vendor_id=VENDOR_ID,
            product_id=product_id,
            name=PRODUCT_NAMES.get(product_id, f"Elgato 0fd9:{product_id:04x}"),
            windex=self.windex,
        )

    def open(self) -> "ElgatoXlrDevice":
        usb = _get_libusb()
        products: Iterable[int]
        if self.product_id is None:
            products = DEFAULT_PRODUCTS
        else:
            products = (self.product_id,)

        for product_id in products:
            handle = usb.lib.libusb_open_device_with_vid_pid(
                usb.ctx,
                VENDOR_ID,
                product_id,
            )
            if handle:
                self._handle = handle
                self._opened_product_id = product_id
                return self

        wanted = (
            ", ".join(f"0fd9:{product:04x}" for product in products)
            if self.product_id is None
            else f"0fd9:{self.product_id:04x}"
        )
        raise DeviceNotFoundError(f"Kein passendes Elgato-Geraet gefunden ({wanted})")

    def close(self) -> None:
        if self._handle is not None:
            usb = _get_libusb()
            usb.lib.libusb_close(self._handle)
            self._handle = None
            self._opened_product_id = None

    def __enter__(self) -> "ElgatoXlrDevice":
        return self.open()

    def __exit__(self, _exc_type, _exc, _tb) -> None:
        self.close()

    def _require_handle(self) -> ctypes.c_void_p:
        if self._handle is None:
            raise UsbError("USB-Geraet ist nicht geoeffnet")
        return self._handle

    def control_read(self, value: int, length: int) -> bytes:
        usb = _get_libusb()
        buf = (ctypes.c_ubyte * length)()
        with self._lock:
            ret = usb.lib.libusb_control_transfer(
                self._require_handle(),
                RT_CLASS_IN_INTERFACE,
                BREQUEST_READ,
                value,
                self.windex,
                buf,
                length,
                self.timeout_ms,
            )
        if ret < 0:
            raise UsbError(f"USB-Lesen fehlgeschlagen: {ret}")
        return bytes(buf[:ret])

    def control_write(self, value: int, data: bytes | bytearray) -> None:
        usb = _get_libusb()
        payload = bytes(data)
        buf = (ctypes.c_ubyte * len(payload))(*payload)
        with self._lock:
            ret = usb.lib.libusb_control_transfer(
                self._require_handle(),
                RT_CLASS_OUT_INTERFACE,
                BREQUEST_WRITE,
                value,
                self.windex,
                buf,
                len(payload),
                self.timeout_ms,
            )
        if ret < 0:
            raise UsbError(f"USB-Schreiben fehlgeschlagen: {ret}")

    def read_config(self) -> XlrConfig:
        data = self.control_read(WVALUE_CONFIG, CONFIG_LEN)
        return XlrConfig.from_bytes(data)

    def write_config(
        self,
        config: XlrConfig,
        *,
        persistent: bool = False,
    ) -> None:
        mode = WRITE_MODE_PERSISTENT if persistent else WRITE_MODE_TEMPORARY
        self.control_write(mode, config.to_bytes())

    def read_device_info(self) -> dict[str, str]:
        data = self.control_read(WVALUE_DEVICE_INFO, 51)
        serial = data[27:47].decode("ascii", errors="replace").rstrip("\x00")
        return {
            "api_version": f"{data[0]}.{data[1]}" if len(data) > 1 else "?",
            "firmware_version": f"{data[6]}.{data[7]}.{data[8]}" if len(data) > 8 else "?",
            "serial": serial,
        }

    def read_meters(self) -> tuple[int, int]:
        data = self.control_read(WVALUE_METERS, 10)
        if len(data) < 8:
            raise UsbError(f"Meter-Block zu kurz: {len(data)}")
        left = int.from_bytes(data[0:4], "little", signed=False)
        right = int.from_bytes(data[4:8], "little", signed=False)
        return left, right
