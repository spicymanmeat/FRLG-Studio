"""Single entry point for the packaged FRLG Studio executable.

PyInstaller freezes one binary.  A normal launch starts the Qt studio, while
the two headless modes are dispatched *before* any PyQt import so they can run
under sudo without a display:

    frlg-studio --trade-cli ...   # frlgtrade.py live/replay
    frlg-studio --mg-host ...     # Wonder Card broadcast host

A source checkout still launches ``trade_gui.py`` directly.
"""

from __future__ import annotations

import sys

import paths

# The source checkout has the GUI modules in src/ and frlgtrade.py one level
# up; a PyInstaller bundle already has both importable at the bundle root.
for _entry in (paths.APP_DIR, paths.SRC_DIR):
    _text = str(_entry)
    if _text not in sys.path:
        sys.path.insert(0, _text)


def main() -> int:
    args = list(sys.argv[1:])
    if args and args[0] in ("--trade-cli", "--mg-host"):
        mode = args.pop(0)
        # Keep argv consistent for argparse defaults.
        sys.argv = [sys.argv[0], *args]
        if mode == "--trade-cli":
            import frlgtrade

            return int(frlgtrade.main(args) or 0)
        import frlg_mg_host

        return int(frlg_mg_host.main(args) or 0)

    from trade_gui import main as gui_main

    return int(gui_main())


if __name__ == "__main__":
    raise SystemExit(main())
