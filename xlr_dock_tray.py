"""PyInstaller entrypoint for the XLR Dock Windows tray app."""

from xlr_web.tray import main


if __name__ == "__main__":
    raise SystemExit(main())
