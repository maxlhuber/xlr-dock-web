"""Windows tray launcher for the local XLR Dock web app."""

from __future__ import annotations

import argparse
import ctypes
import os
import threading
import webbrowser
from ctypes import wintypes

from xlr_control.usb import PRODUCT_XLR_DOCK, parse_product_id
from xlr_web.app import (
    XlrRequestHandler,
    XlrThreadingHTTPServer,
    XlrWebController,
    _parse_windex,
)


if os.name != "nt":  # pragma: no cover - Windows-only utility.
    raise SystemExit("Das Tray-Icon ist aktuell nur unter Windows verfuegbar.")


WM_DESTROY = 0x0002
WM_COMMAND = 0x0111
WM_USER = 0x0400
WM_TRAYICON = WM_USER + 37
WM_LBUTTONUP = 0x0202
WM_LBUTTONDBLCLK = 0x0203
WM_RBUTTONUP = 0x0205
WM_CONTEXTMENU = 0x007B

NIM_ADD = 0x00000000
NIM_DELETE = 0x00000002
NIF_MESSAGE = 0x00000001
NIF_ICON = 0x00000002
NIF_TIP = 0x00000004

MF_STRING = 0x00000000
MF_SEPARATOR = 0x00000800
TPM_RIGHTBUTTON = 0x00000002

IDI_APPLICATION = 32512
SW_SHOWNORMAL = 1
MB_ICONERROR = 0x00000010

MENU_OPEN = 1001
MENU_QUIT = 1002

LRESULT = ctypes.c_ssize_t
WPARAM = ctypes.c_size_t
LPARAM = ctypes.c_ssize_t
HCURSOR = wintypes.HANDLE
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, WPARAM, LPARAM)


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", WPARAM),
        ("lParam", LPARAM),
        ("time", wintypes.DWORD),
        ("pt", POINT),
    ]


class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", HCURSOR),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uID", wintypes.UINT),
        ("uFlags", wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT),
        ("hIcon", wintypes.HICON),
        ("szTip", wintypes.WCHAR * 128),
        ("dwState", wintypes.DWORD),
        ("dwStateMask", wintypes.DWORD),
        ("szInfo", wintypes.WCHAR * 256),
        ("uTimeoutOrVersion", wintypes.UINT),
        ("szInfoTitle", wintypes.WCHAR * 64),
        ("dwInfoFlags", wintypes.DWORD),
        ("guidItem", GUID),
        ("hBalloonIcon", wintypes.HICON),
    ]


user32 = ctypes.WinDLL("user32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
user32.RegisterClassW.restype = wintypes.ATOM
user32.CreateWindowExW.argtypes = [
    wintypes.DWORD,
    wintypes.LPCWSTR,
    wintypes.LPCWSTR,
    wintypes.DWORD,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.HWND,
    wintypes.HMENU,
    wintypes.HINSTANCE,
    wintypes.LPVOID,
]
user32.CreateWindowExW.restype = wintypes.HWND
user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, WPARAM, LPARAM]
user32.DefWindowProcW.restype = LRESULT
user32.DestroyWindow.argtypes = [wintypes.HWND]
user32.PostQuitMessage.argtypes = [ctypes.c_int]
user32.GetMessageW.argtypes = [ctypes.POINTER(MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
user32.GetMessageW.restype = wintypes.BOOL
user32.TranslateMessage.argtypes = [ctypes.POINTER(MSG)]
user32.DispatchMessageW.argtypes = [ctypes.POINTER(MSG)]
user32.LoadIconW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR]
user32.LoadIconW.restype = wintypes.HICON
user32.CreatePopupMenu.restype = wintypes.HMENU
user32.AppendMenuW.argtypes = [wintypes.HMENU, wintypes.UINT, WPARAM, wintypes.LPCWSTR]
user32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.TrackPopupMenu.argtypes = [
    wintypes.HMENU,
    wintypes.UINT,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.HWND,
    wintypes.LPVOID,
]
user32.DestroyMenu.argtypes = [wintypes.HMENU]
user32.MessageBoxW.argtypes = [wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.UINT]

shell32.Shell_NotifyIconW.argtypes = [wintypes.DWORD, ctypes.POINTER(NOTIFYICONDATAW)]
shell32.Shell_NotifyIconW.restype = wintypes.BOOL
kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.GetModuleHandleW.restype = wintypes.HMODULE


def _make_int_resource(value: int) -> wintypes.LPCWSTR:
    return ctypes.cast(ctypes.c_void_p(value), wintypes.LPCWSTR)


class TrayApp:
    def __init__(self, server: XlrThreadingHTTPServer, url: str, *, open_on_start: bool) -> None:
        self.server = server
        self.url = url
        self.open_on_start = open_on_start
        self.hinstance = kernel32.GetModuleHandleW(None)
        self.hwnd: wintypes.HWND | None = None
        self.hicon: wintypes.HICON | None = None
        self._wndproc = WNDPROC(self._window_proc)
        self._server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def run(self) -> int:
        self._server_thread.start()
        self._create_window()
        self._add_icon()
        if self.open_on_start:
            self.open_webinterface()
        return self._message_loop()

    def open_webinterface(self) -> None:
        webbrowser.open(self.url)

    def quit(self) -> None:
        self._delete_icon()
        self.server.shutdown()
        self.server.server_close()
        if self.hwnd:
            user32.DestroyWindow(self.hwnd)

    def _create_window(self) -> None:
        class_name = "XlrDockWebTrayWindow"
        wndclass = WNDCLASSW()
        wndclass.lpfnWndProc = self._wndproc
        wndclass.hInstance = self.hinstance
        wndclass.lpszClassName = class_name
        if not user32.RegisterClassW(ctypes.byref(wndclass)):
            # The class may already exist after a quick restart; window creation
            # still succeeds in that case.
            pass
        self.hwnd = user32.CreateWindowExW(
            0,
            class_name,
            "XLR Dock",
            0,
            0,
            0,
            0,
            0,
            None,
            None,
            self.hinstance,
            None,
        )
        if not self.hwnd:
            raise ctypes.WinError(ctypes.get_last_error())

    def _notify_data(self) -> NOTIFYICONDATAW:
        if not self.hwnd:
            raise RuntimeError("Tray-Fenster ist nicht initialisiert")
        data = NOTIFYICONDATAW()
        data.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        data.hWnd = self.hwnd
        data.uID = 1
        data.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        data.uCallbackMessage = WM_TRAYICON
        data.hIcon = self.hicon or user32.LoadIconW(None, _make_int_resource(IDI_APPLICATION))
        data.szTip = "XLR Dock Web-App"
        return data

    def _add_icon(self) -> None:
        self.hicon = user32.LoadIconW(None, _make_int_resource(IDI_APPLICATION))
        data = self._notify_data()
        if not shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(data)):
            raise ctypes.WinError(ctypes.get_last_error())

    def _delete_icon(self) -> None:
        try:
            data = self._notify_data()
            shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(data))
        except Exception:
            pass

    def _show_menu(self) -> None:
        if not self.hwnd:
            return
        menu = user32.CreatePopupMenu()
        user32.AppendMenuW(menu, MF_STRING, MENU_OPEN, "Webinterface oeffnen")
        user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
        user32.AppendMenuW(menu, MF_STRING, MENU_QUIT, "Beenden")
        point = POINT()
        user32.GetCursorPos(ctypes.byref(point))
        user32.SetForegroundWindow(self.hwnd)
        user32.TrackPopupMenu(menu, TPM_RIGHTBUTTON, point.x, point.y, 0, self.hwnd, None)
        user32.DestroyMenu(menu)

    def _window_proc(self, hwnd: wintypes.HWND, msg: int, wparam: int, lparam: int) -> int:
        if msg == WM_TRAYICON:
            if lparam in (WM_LBUTTONUP, WM_LBUTTONDBLCLK):
                self.open_webinterface()
                return 0
            if lparam in (WM_RBUTTONUP, WM_CONTEXTMENU):
                self._show_menu()
                return 0
        if msg == WM_COMMAND:
            command = int(wparam) & 0xFFFF
            if command == MENU_OPEN:
                self.open_webinterface()
                return 0
            if command == MENU_QUIT:
                self.quit()
                return 0
        if msg == WM_DESTROY:
            self._delete_icon()
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _message_loop(self) -> int:
        message = MSG()
        while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(message))
            user32.DispatchMessageW(ctypes.byref(message))
        return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="XLR-Dock-Web-App als Windows-Tray-App starten.")
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
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        controller = XlrWebController(
            product_id=parse_product_id(args.product) or PRODUCT_XLR_DOCK,
            windex=_parse_windex(args.windex),
            timeout_ms=args.timeout,
            persistent=args.persistent,
        )
        server = XlrThreadingHTTPServer((args.host, args.port), XlrRequestHandler)
        server.controller = controller
        url = f"http://{args.host}:{args.port}/"
        return TrayApp(server, url, open_on_start=args.open).run()
    except Exception as exc:
        user32.MessageBoxW(None, str(exc), "XLR Dock Web-App", MB_ICONERROR)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
