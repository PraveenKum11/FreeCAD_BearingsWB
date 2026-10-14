# Development

The roadmap and design decisions are in `PLAN.md` in the repository.

## Layout

| Module | Role |
|---|---|
| `BearingData.py` | Tables, series, designations, search |
| `BearingGeometry.py` | Computed internals and Part shapes (no FreeCAD documents) |
| `BearingBase.py` | The bearing FeaturePython object |
| `BearingsCmd.py`, `InitGui.py` | Commands, toolbar drop-downs, menus |
| `PrintableBearing.py`, `PrintableBearingGui.py` | 3D-printable bearings |
| `BearingSearchGui.py`, `BearingBOM.py`, `BearingBOMGui.py` | Find bearing, BOM |
| `BRData/*.csv` | The dimension tables |

## Tests

```sh
path/to/freecadcmd tests/run_tests.py                                  # ~3 min
BEARINGS_TESTS=test_printable path/to/freecadcmd tests/run_tests.py    # one module
FREECAD=path/to/FreeCAD tests/gui/run_gui.sh tests/gui/gui_smoke.py /tmp/smoke.log
```

The headless suite builds every row of every table at every detail level and checks the
shape (valid, size, bore clear, part count, no overlaps). The GUI smoke test drives the
panels in a real FreeCAD window and closes it by itself.

## Style, icons, images

```sh
ruff format . && ruff check .
path/to/freecadcmd tools/make_icons.py        # Icons/*.svg
path/to/FreeCAD tools/render_images.py        # README and wiki images
RENDER_ONLY=hero,closures path/to/FreeCAD tools/render_images.py
```

## Adding a bearing table

1. Add a CSV to `BRData/` with at least `Designation,d,D,B` (or reuse a table: see
   `BearingData.DERIVED`).
2. Register the series in `BearingData.SERIES`, and its family's row class if it is new.
3. Add the shape builder in `BearingGeometry.py` if the family is new.
4. Put the series in a toolbar group (`BearingsCmd.GROUPS`) and regenerate the icons
   (`tools/make_icons.py` draws one for every series in `BearingData.SERIES`).
5. The tests pick up every row automatically.
