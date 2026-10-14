# Bearings Workbench for FreeCAD

Parametric rolling bearings for FreeCAD 1.x, aimed at makers: 608, 625, 688, MR/MF
miniatures, flanged variants, shields and seals. Inspired by
[FreeCAD_FastenersWB](https://github.com/shaise/FreeCAD_FastenersWB).

The roadmap and design decisions are in [PLAN.md](PLAN.md).

## Standard bearings

- Deep groove ball bearing series **60, 62, 63, 68 (618), 69 (619)**, including the
  miniature 60x/62x/63x/68x/69x sizes, plus the metric miniature **MR** series
- Closures: Open, Z, ZZ, RS, 2RS (wider shielded widths for miniatures)
- Flanged **F** / **MF** variants for miniature sizes
- Detail levels: **Envelope** (one fast solid), **Standard** (rings, balls, shields),
  **Detailed** (adds a cage)
- **Edge snap**: select a hole or shaft-end edge, then click a series button. The size is
  matched automatically to the OD (hole) or bore (shaft), and the bearing follows the edge.
  `Invert` and `Offset` adjust the placement.
- The tables hold only boundary dimensions (ISO 15). Ball size, ball count and raceways are
  computed.

## 3D-printable bearings

**Bearing tools → 3D-printable bearing** builds a printable deep groove ball bearing as
PartDesign bodies: races, a snap-in cage and optionally the balls, each exportable on its
own. It is the DeepGrooveBallBearing macro, now part of the workbench.

- Select a shaft end or housing bore edge, a PartDesign bore to groove, a standard
  bearing to replace, or nothing.
- Pick a catalog size (608, 625 …) or enter ID/OD/height, and pick a ball preset
  (4.5 mm BB, 6 mm airsoft …).
- A live **preview** shows the inner and outer diameter as labelled rings and a
  see-through view of the races, balls and cage while you edit, including when grooving
  an existing body.
- Edit it later on the **BearingParameters** datum. For new races, the
  **PrintableBearing** object in the bearing's Part keeps the Part's label in step with
  the size and reports invalid values. Grooving an existing body adds no such object.

## Find bearing

**Bearing tools → Find bearing** searches by **name** (`608`, `62`, `F688-2RS`, `618/8`,
`8x22x7`), **inner diameter**, **outer diameter** or **height**, alone or combined, with
an optional tolerance. Insert the result as a standard bearing, or open it as a printable
one.

## Install (development)

Link your clone into FreeCAD's `Mod` folder as `Bearings` and restart FreeCAD. On macOS
with FreeCAD 1.1:

```sh
ln -s "$PWD" "$HOME/Library/Application Support/FreeCAD/v1-1/Mod/Bearings"
```

(run from the repository root). On Linux the folder is usually
`~/.local/share/FreeCAD/v1-1/Mod`; in FreeCAD, `App.getUserAppDataDir()` shows the base.

## Scripting

```python
import BearingBase

b = BearingBase.make_bearing("60", "608", Closure="2RS", DetailLevel="Detailed")
```

## Tests

Headless tests (`unittest`, run inside FreeCAD's own Python):

```sh
path/to/freecadcmd tests/run_tests.py
BEARINGS_TESTS=test_printable path/to/freecadcmd tests/run_tests.py   # one module
```

On macOS `freecadcmd` is in `FreeCAD.app/Contents/Resources/bin/`. The suite takes about
2 minutes and checks every table row and closure at every detail level.

GUI smoke test (needs the workbench installed, opens and closes FreeCAD by itself):

```sh
FREECAD=path/to/FreeCAD tests/gui/run_gui.sh tests/gui/gui_smoke.py /tmp/smoke.log
```

## Code style

Formatting and linting use [Ruff](https://docs.astral.sh/ruff/), configured in
`pyproject.toml`:

```sh
ruff format . && ruff check .
```

## Icons

`python3 tools/make_icons.py` regenerates `Icons/*.svg`.

## Data accuracy

Boundary dimensions of series 60/62/63/68/69 were cross-checked against SKF's public
table (`python3 tools/verify_skf.py`, see PLAN.md §4.1). Shielded widths and flange dimensions of miniature bearings vary by vendor and are
approximate. Check `BRData/*.csv` against your supplier's sheet before relying on them for
tight fits.

The repository holds no manufacturer catalogue data. `tools/verify_skf.py` fetches SKF's
table each time it runs and doesn't store it. PLAN.md records only the conclusions drawn
from such checks.

## License

GPL-3.0-or-later, see [LICENSE](LICENSE).
