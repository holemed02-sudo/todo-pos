# ToDo POS 1.1.0

Offline Windows point of sale for Moroccan shops. This branch implements the first stage of the ToDo Vision: transaction safety, a keyboard-driven sale screen, unified search and traceable stock.

See [the Arabic user guide](README_1_1_AR.md) for startup, importing old data, pricing rules and release limitations. See [validation](VALIDATION.md) for regression tests and measured backend performance.

## Source layout

The runnable source is now tracked directly at the repository root: `ToDo.pyw`, `todo/`, `tests/`. The repository's existing `baseline/` and `overrides/` directories are retained as historical material; they are no longer used to assemble builds. No store database or customer images are included.

## Run and test

Python 3.10+ with Tkinter. Pillow is optional for product thumbnails.

```sh
python ToDo.pyw
python -B -m unittest discover -s tests -v
python -B tests/ui_smoke.py
```

Fresh database: select Administrateur, PIN `1234`. Change the PIN in settings. Before first launch, use `IMPORT_OLD_DATA.bat` to copy an old installation, preserving its accounts, data and images.

## Windows build

GitHub Actions tests the core and Tk interface, then packages a portable Windows folder containing `ToDo.exe` and `ImporterToDo.exe`. Download the `ToDo-POS-1.1.0-Windows` artifact from a successful Windows build. Keep the extracted folder writable; data is stored beside the executable under `todo/`. The source ZIP still requires Python.

The release is a test candidate until its interface and devices are checked on the shop's Windows machine. Current pack/carton pricing, snapshot fields and whole-pack return policy from the prior GitHub version are preserved.
