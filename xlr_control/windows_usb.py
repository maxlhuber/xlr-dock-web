"""Native WinUSB backend for Elgato XLR Dock controls on Windows."""

from __future__ import annotations

import ctypes
import os
import threading
import winreg
from ctypes import wintypes
from dataclasses import dataclass
from typing import Iterable

from .protocol import CONFIG_LEN, XlrConfig
from .usb import (
    BREQUEST_READ,
    BREQUEST_WRITE,
    PRODUCT_NAMES,
    PRODUCT_WAVE_XLR,
    PRODUCT_XLR_DOCK,
    RT_CLASS_IN_INTERFACE,
    RT_CLASS_OUT_INTERFACE,
    VENDOR_ID,
    WINDEX_LINUX_CONTROL_INTERFACE,
    WINDEX_NATIVE,
    WRITE_MODE_PERSISTENT,
    WRITE_MODE_TEMPORARY,
    WVALUE_CONFIG,
    WVALUE_DEVICE_INFO,
    WVALUE_METERS,
    DeviceInfo,
    DeviceNotFoundError,
    UsbError,
)


if os.name != "nt":  # pragma: no cover - import guard for non-Windows tests.
    raise ImportError("xlr_control.windows_usb ist nur unter Windows nutzbar")


DEFAULT_WINUSB_WINDEXES = (WINDEX_LINUX_CONTROL_INTERFACE, WINDEX_NATIVE)
CONTROL_INTERFACE_BY_PRODUCT = {
    PRODUCT_XLR_DOCK: "VID_0FD9&PID_00A6&MI_03",
    # The standalone Wave XLR also uses the same 34-byte config block, but the
    # Windows interface number can differ by firmware. Keep this explicit until
    # we have a confirmed capture for the user's device.
    PRODUCT_WAVE_XLR: "VID_0FD9&PID_007D",
}


class WinUsbError(UsbError):
    pass


@dataclass(frozen=True)
class WindowsDevicePath:
    product_id: int
    instance_id: str
    interface_guid: str
    path: str


class _WinUsb:
    def __init__(self) -> None:
        self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self.winusb = ctypes.WinDLL("winusb", use_last_error=True)

        self.kernel32.CreateFileW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        ]
        self.kernel32.CreateFileW.restype = wintypes.HANDLE
        self.kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel32.CloseHandle.restype = wintypes.BOOL

        self.winusb.WinUsb_Initialize.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(wintypes.HANDLE),
        ]
        self.winusb.WinUsb_Initialize.restype = wintypes.BOOL
        self.winusb.WinUsb_Free.argtypes = [wintypes.HANDLE]
        self.winusb.WinUsb_Free.restype = wintypes.BOOL
        self.winusb.WinUsb_ControlTransfer.argtypes = [
            wintypes.HANDLE,
            _WINUSB_SETUP_PACKET,
            ctypes.POINTER(ctypes.c_ubyte),
            wintypes.ULONG,
            ctypes.POINTER(wintypes.ULONG),
            wintypes.LPVOID,
        ]
        self.winusb.WinUsb_ControlTransfer.restype = wintypes.BOOL


class _WINUSB_SETUP_PACKET(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("RequestType", ctypes.c_ubyte),
        ("Request", ctypes.c_ubyte),
        ("Value", ctypes.c_ushort),
        ("Index", ctypes.c_ushort),
        ("Length", ctypes.c_ushort),
    ]


_WINUSB: _WinUsb | None = None
_WINUSB_LOCK = threading.Lock()


def _get_winusb() -> _WinUsb:
    global _WINUSB
    with _WINUSB_LOCK:
        if _WINUSB is None:
            _WINUSB = _WinUsb()
        return _WINUSB


def _last_error(prefix: str) -> WinUsbError:
    code = ctypes.get_last_error()
    message = ctypes.FormatError(code).strip()
    return WinUsbError(f"{prefix}: {message} ({code})")


def _enum_subkeys(root: winreg.HKEYType, path: str) -> Iterable[str]:
    with winreg.OpenKey(root, path) as key:
        index = 0
        while True:
            try:
                yield winreg.EnumKey(key, index)
            except OSError:
                return
            index += 1


def _read_reg_value(root: winreg.HKEYType, path: str, name: str) -> str | None:
    try:
        with winreg.OpenKey(root, path) as key:
            value, _kind = winreg.QueryValueEx(key, name)
            return str(value)
    except OSError:
        return None


def _find_matching_instances(product_id: int) -> list[tuple[str, str]]:
    prefix = CONTROL_INTERFACE_BY_PRODUCT.get(product_id)
    if not prefix:
        return []

    enum_path = "SYSTEM\\CurrentControlSet\\Enum\\USB"
    matches: list[tuple[str, str]] = []
    for device_key in _enum_subkeys(winreg.HKEY_LOCAL_MACHINE, enum_path):
        if not device_key.upper().startswith(prefix):
            continue
        device_path = f"{enum_path}\\{device_key}"
        for instance_key in _enum_subkeys(winreg.HKEY_LOCAL_MACHINE, device_path):
            instance_id = f"USB\\{device_key}\\{instance_key}"
            params = f"{device_path}\\{instance_key}\\Device Parameters"
            guid = _read_reg_value(winreg.HKEY_LOCAL_MACHINE, params, "DeviceInterfaceGUID")
            if guid:
                matches.append((instance_id, guid.strip("{}")))
    return matches


def get_xlr_device_path(
    product_id: int = PRODUCT_XLR_DOCK,
    *,
    device_instance_id: str | None = None,
    interface_guid: str | None = None,
) -> WindowsDevicePath:
    """Resolve the Windows device path for the XLR Dock WinUSB interface."""

    candidates: list[tuple[str, str]] = []
    if device_instance_id:
        if interface_guid is None:
            reg_path = f"SYSTEM\\CurrentControlSet\\Enum\\{device_instance_id}\\Device Parameters"
            interface_guid = _read_reg_value(
                winreg.HKEY_LOCAL_MACHINE,
                reg_path,
                "DeviceInterfaceGUID",
            )
        if interface_guid:
            candidates.append((device_instance_id, interface_guid.strip("{}")))
    else:
        candidates.extend(_find_matching_instances(product_id))

    for instance_id, guid in candidates:
        normalized_guid = guid.strip("{}").lower()
        class_path = (
            "SYSTEM\\CurrentControlSet\\Control\\DeviceClasses"
            f"\\{{{normalized_guid}}}"
        )
        needle = instance_id.replace("\\", "#").lower()
        try:
            children = list(_enum_subkeys(winreg.HKEY_LOCAL_MACHINE, class_path))
        except OSError:
            children = []

        for child in children:
            child_lower = child.lower()
            if needle not in child_lower or not child.startswith("##?#"):
                continue
            return WindowsDevicePath(
                product_id=product_id,
                instance_id=instance_id,
                interface_guid=normalized_guid,
                path="\\\\?\\" + child[4:],
            )

    raise DeviceNotFoundError(
        "Kein Elgato-XLR-Dock-WinUSB-Interface gefunden. "
        "Pruefe, ob das XLR Dock angeschlossen ist und Wave Link den Controls-Treiber installiert hat."
    )


class ElgatoXlrWinUsbDevice:
    def __init__(
        self,
        product_id: int | None = None,
        *,
        windex: int | None = None,
        timeout_ms: int = 1000,
        device_instance_id: str | None = None,
        interface_guid: str | None = None,
    ) -> None:
        self.product_id = product_id or PRODUCT_XLR_DOCK
        self.timeout_ms = timeout_ms
        self.device_instance_id = device_instance_id
        self.interface_guid = interface_guid
        self._candidate_windexes = (windex,) if windex is not None else DEFAULT_WINUSB_WINDEXES
        self._active_windex: int | None = windex
        self._device_path: WindowsDevicePath | None = None
        self._file_handle: wintypes.HANDLE | None = None
        self._interface_handle: wintypes.HANDLE | None = None
        self._lock = threading.Lock()

    @property
    def is_open(self) -> bool:
        return self._interface_handle is not None

    @property
    def info(self) -> DeviceInfo:
        return DeviceInfo(
            vendor_id=VENDOR_ID,
            product_id=self.product_id,
            name=PRODUCT_NAMES.get(self.product_id, f"Elgato 0fd9:{self.product_id:04x}"),
            windex=self._active_windex or self._candidate_windexes[0],
        )

    @property
    def windows_path(self) -> WindowsDevicePath | None:
        return self._device_path

    def open(self) -> "ElgatoXlrWinUsbDevice":
        winusb = _get_winusb()
        self._device_path = get_xlr_device_path(
            self.product_id,
            device_instance_id=self.device_instance_id,
            interface_guid=self.interface_guid,
        )

        generic_read = 0x80000000
        generic_write = 0x40000000
        file_share_read = 0x00000001
        file_share_write = 0x00000002
        open_existing = 3
        file_attribute_normal = 0x00000080
        file_flag_overlapped = 0x40000000
        invalid_handle_value = ctypes.c_void_p(-1).value

        handle = winusb.kernel32.CreateFileW(
            self._device_path.path,
            generic_read | generic_write,
            file_share_read | file_share_write,
            None,
            open_existing,
            file_attribute_normal | file_flag_overlapped,
            None,
        )
        if handle == invalid_handle_value or not handle:
            raise _last_error("CreateFile fuer XLR Dock fehlgeschlagen")

        interface_handle = wintypes.HANDLE()
        if not winusb.winusb.WinUsb_Initialize(handle, ctypes.byref(interface_handle)):
            winusb.kernel32.CloseHandle(handle)
            raise _last_error("WinUsb_Initialize fehlgeschlagen")

        self._file_handle = handle
        self._interface_handle = interface_handle
        return self

    def close(self) -> None:
        winusb = _get_winusb()
        if self._interface_handle is not None:
            winusb.winusb.WinUsb_Free(self._interface_handle)
            self._interface_handle = None
        if self._file_handle is not None:
            winusb.kernel32.CloseHandle(self._file_handle)
            self._file_handle = None
        self._device_path = None

    def __enter__(self) -> "ElgatoXlrWinUsbDevice":
        return self.open()

    def __exit__(self, _exc_type, _exc, _tb) -> None:
        self.close()

    def _require_interface(self) -> wintypes.HANDLE:
        if self._interface_handle is None:
            raise UsbError("Windows-WinUSB-Interface ist nicht geoeffnet")
        return self._interface_handle

    def _control_transfer(
        self,
        request_type: int,
        request: int,
        value: int,
        index: int,
        data: bytes | bytearray,
    ) -> bytes:
        winusb = _get_winusb()
        payload = bytes(data)
        length = len(payload)
        buffer = (ctypes.c_ubyte * length)(*payload)
        setup = _WINUSB_SETUP_PACKET(
            RequestType=request_type,
            Request=request,
            Value=value,
            Index=index,
            Length=length,
        )
        transferred = wintypes.ULONG()

        with self._lock:
            ok = winusb.winusb.WinUsb_ControlTransfer(
                self._require_interface(),
                setup,
                buffer,
                length,
                ctypes.byref(transferred),
                None,
            )
        if not ok:
            raise _last_error("WinUsb_ControlTransfer fehlgeschlagen")
        return bytes(buffer[: transferred.value])

    def _with_windex_fallback(
        self,
        request_type: int,
        request: int,
        value: int,
        data: bytes | bytearray,
    ) -> bytes:
        errors: list[str] = []
        indexes = (
            (self._active_windex,)
            if self._active_windex is not None
            else self._candidate_windexes
        )
        for index in indexes:
            try:
                result = self._control_transfer(request_type, request, value, index, data)
                self._active_windex = index
                return result
            except UsbError as exc:
                errors.append(f"0x{index:04x}: {exc}")
                if self._active_windex is not None:
                    break
        raise UsbError("; ".join(errors) if errors else "Kein wIndex verfuegbar")

    def control_read(self, value: int, length: int) -> bytes:
        return self._with_windex_fallback(
            RT_CLASS_IN_INTERFACE,
            BREQUEST_READ,
            value,
            bytearray(length),
        )

    def control_write(self, value: int, data: bytes | bytearray) -> None:
        self._with_windex_fallback(
            RT_CLASS_OUT_INTERFACE,
            BREQUEST_WRITE,
            value,
            data,
        )

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
