# Bearings Workbench for FreeCAD

Parametric rolling bearings for FreeCAD 1.x, aimed at makers: 608, 625, 688, MR/MF
miniatures, flanged variants, shields and seals. Inspired by
[FreeCAD_FastenersWB](https://github.com/shaise/FreeCAD_FastenersWB).

The roadmap and design decisions are in [PLAN.md](PLAN.md).

## Features (v0.1)

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

## Install (development)

Link the repo into the FreeCAD 1.1 Mod folder and restart FreeCAD:

```sh
ln -s /Volumes/Silo/projects/FreeCAD_BearingsWB \
  "$HOME/Library/Application Support/FreeCAD/v1-1/Mod/Bearings"
```

## Scripting

```python
import BearingBase
b = BearingBase.make_bearing("60", "608", Closure="2RS", DetailLevel="Detailed")
```

## Tests

```sh
/Volumes/Silo/brew/FreeCAD.app/Contents/Resources/bin/freecadcmd tests/run_tests.py
```

The suite takes about 2 minutes and checks every table row and closure at every detail
level.

## Icons

`python3 tools/make_icons.py` regenerates `Icons/*.svg`.

## Data accuracy

Boundary dimensions of series 60/62/63/68/69 were cross-checked against SKF's public
table (`python3 tools/verify_skf.py`, see PLAN.md §4.1). Shielded widths and flange dimensions of miniature bearings vary by vendor and are
approximate. Check `BRData/*.csv` against your supplier's sheet before relying on them for
tight fits.
