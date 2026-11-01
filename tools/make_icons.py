# SPDX-License-Identifier: GPL-3.0-or-later
"""Generate the SVG icons in Icons/ from the workbench's own shapes.

Run with FreeCAD's command-line binary from the repository root:

    path/to/freecadcmd tools/make_icons.py

On macOS the binary is FreeCAD.app/Contents/Resources/bin/freecadcmd.

The icons follow the FreeCAD Fasteners workbench style: a TechDraw hidden-line view of
the part from the isometric direction, black line art over a flat silhouette, orange for
metric parts and teal for inch parts, 48 x 48 px with a 2 px margin. Each bearing is cut
open by the quadrant facing the viewer so its rolling elements show, and carries its
series name on a badge in the bottom-right corner.
"""

import os
import sys

import FreeCAD as App
import Part
import TechDraw


def _repo_dir():
    """The repository root, one level above this script (FreeCAD may not set __file__)."""
    try:
        here = os.path.dirname(os.path.abspath(__file__))
    except NameError:
        here = next(
            os.path.dirname(os.path.abspath(a)) for a in sys.argv if a.endswith("make_icons.py")
        )
    return os.path.dirname(here)


REPO = _repo_dir()
sys.path.insert(0, REPO)
OUT = os.path.join(REPO, "Icons")

import BearingData as BD  # noqa: E402
import BearingGeometry as BG  # noqa: E402
import PrintableBearing as PB  # noqa: E402

V = App.Vector
SIZE, MARGIN = 48.0, 2.0
STROKE = 1.0  # px
METRIC, INCH = "#FFAF00", "#5FD3C2"  # the Fasteners workbench colors
BADGE = "#1f6feb"
LINE = "#000000"

# view direction (viewer at +x -y +z, FreeCAD's isometric) -> +Z, then roll the
# bearing axis to point up on the screen
_ROT = App.Rotation(V(1, -1, 1).normalize(), V(0, 0, 1))
_up = _ROT.multVec(V(0, 0, 1))
VIEW = App.Rotation(V(_up.x, _up.y, 0), V(0, 1, 0)).multiply(_ROT)


def quarter_cut(shape):
    """Remove the quadrant facing the viewer (x > 0, y < 0)."""
    bb = shape.BoundBox
    big = 2 * max(bb.XLength, bb.YLength, bb.ZLength) + 10
    return shape.cut(Part.makeBox(big, big, big, V(0, -big, bb.ZMin - 1)))


def _points(edge, scale):
    return [(p.x, p.y) for p in edge.discretize(Deflection=0.15 / scale)]


def _d(polys, closed):
    out = []
    for pts in polys:
        out.append("M" + " ".join(f"{x:.2f},{y:.2f}" for x, y in pts) + (" Z" if closed else ""))
    return " ".join(out)


def drawing(shape, fill):
    """SVG elements of the line drawing of shape, fitted into the 48 px canvas."""
    s = shape.copy()
    s.Placement = App.Placement(V(), VIEW).multiply(s.Placement)
    projection = TechDraw.projectEx(s, V(0, 0, 1))
    visible = [c for c in (projection[0], projection[3]) if not c.isNull()]  # sharp, outline
    edges = [e for c in visible for e in c.Edges]
    # the outer boundary of the line drawing is the silhouette
    outline = TechDraw.findOuterWire(edges)
    bb = outline.BoundBox
    scale = (SIZE - 2 * MARGIN - STROKE) / max(bb.XLength, bb.YLength)
    ox = (SIZE - bb.XLength * scale) / 2
    oy = (SIZE - bb.YLength * scale) / 2

    def tf(pts):
        # SVG y points down
        return [(ox + (x - bb.XMin) * scale, SIZE - oy - (y - bb.YMin) * scale) for x, y in pts]

    fill_pts = tf([(p.x, p.y) for p in outline.discretize(Deflection=0.15 / scale)])
    lines = [tf(_points(e, scale)) for e in edges]
    return [
        # stroked in its own color: the silhouette grows by half a stroke, as Inkscape's
        # Stroke to Path does in the Fasteners recipe, so it reaches past the outline
        f'<path d="{_d([fill_pts], True)}" fill="{fill}" stroke="{fill}" '
        f'stroke-width="{STROKE}" stroke-linejoin="round"/>',
        f'<path d="{_d(lines, False)}" fill="none" stroke="{LINE}" stroke-width="{STROKE}" '
        'stroke-linecap="round" stroke-linejoin="round"/>',
    ]


def badge(label):
    """The series name on a rounded tag in the bottom-right corner."""
    size = {1: 12, 2: 12, 3: 10.5}.get(len(label), 9)
    w = {1: 16, 2: 22, 3: 26}.get(len(label), 30)
    h = 15
    x, y = SIZE - w, SIZE - h
    return [
        f'<rect x="{x:g}" y="{y:g}" width="{w}" height="{h}" rx="3" fill="{BADGE}"/>',
        f'<text x="{x + w / 2:g}" y="{y + h / 2 + size * 0.36:.2f}" '
        f'font-family="Arial,Helvetica,sans-serif" font-size="{size}" font-weight="bold" '
        f'fill="#ffffff" text-anchor="middle">{label}</text>',
    ]


def bom_sheet():
    """A small parts list in the bottom-right corner."""
    rows = "".join(
        f'<rect x="33" y="{y}" width="10" height="2" rx="1" fill="{LINE}"/>' for y in (32, 37, 42)
    )
    return [
        f'<rect x="28.5" y="26.5" width="19" height="21" rx="2" fill="#ffffff" stroke="{LINE}"/>',
        rows,
        f'<rect x="30" y="31.5" width="2" height="2" fill="{BADGE}"/>',
        f'<rect x="30" y="36.5" width="2" height="2" fill="{BADGE}"/>',
        f'<rect x="30" y="41.5" width="2" height="2" fill="{BADGE}"/>',
    ]


def magnifier():
    """A magnifying glass over the bottom-right corner."""
    return [
        f'<circle cx="31" cy="31" r="9" fill="#ffffff" fill-opacity="0.45" stroke="{BADGE}" stroke-width="3.5"/>',
        f'<line x1="37.5" y1="37.5" x2="45" y2="45" stroke="{BADGE}" stroke-width="5" stroke-linecap="round"/>',
    ]


def gear():
    """A gear (settings) over the bottom-right corner."""
    import math

    cx = cy = 35.0
    teeth, r_out, r_in = 8, 12.0, 9.0
    pts = []
    for i in range(teeth):
        a = 2 * math.pi * i / teeth
        step = 2 * math.pi / teeth
        # each tooth: flat top over 30 % of the pitch, flanks down to the root circle
        for da, r in ((-0.30, r_in), (-0.15, r_out), (0.15, r_out), (0.30, r_in)):
            t = a + da * step
            pts.append(f"{cx + r * math.cos(t):.2f},{cy + r * math.sin(t):.2f}")
    return [
        f'<path d="M{" ".join(pts)}Z" fill="{BADGE}" stroke="#ffffff" stroke-width="1" '
        'stroke-linejoin="round"/>',
        f'<circle cx="{cx:g}" cy="{cy:g}" r="4" fill="#ffffff"/>',
    ]


def svg(parts):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{SIZE:g}" height="{SIZE:g}" '
        f'viewBox="0 0 {SIZE:g} {SIZE:g}">\n' + "\n".join(parts) + "\n</svg>\n"
    )


def bearing(series):
    """The default size of a series, open, at the Standard detail level."""
    row = BD.get_row(series, BD.SERIES[series][2])
    variant = "NU" if BD.SERIES[series][3] == "cylindrical" else None
    shape, _ = BG.build(row, "Open", False, "Standard", "Round", variant)
    return shape


def is_inch(series):
    return BD.SERIES[series][1].startswith("inch_")


def write(name, parts):
    with open(os.path.join(OUT, name), "w") as f:
        f.write(svg(parts))


def main():
    os.makedirs(OUT, exist_ok=True)
    for series in BD.SERIES:
        fill = INCH if is_inch(series) else METRIC
        label = {"Special": "Sp", "Wheel": "WH", "Ball": "B"}.get(series, series)
        write(f"Bearing_{series}.svg", drawing(quarter_cut(bearing(series)), fill) + badge(label))
        print("make_icons:", series, flush=True)

    ball = drawing(quarter_cut(bearing("62")), METRIC)
    write("BearingsWB.svg", ball)
    write("BearingBOM.svg", ball + bom_sheet())
    write("BearingSearch.svg", ball + magnifier())
    write("BearingSettings.svg", ball + gear())

    v = dict(PB.CAGE_DEFAULTS, ID=8, OD=22, Height=7, BallDiameter=4, NumBalls=7)
    printable = Part.makeCompound([s for _, s in PB.preview_shapes(v)])
    write("PrintableBearing.svg", drawing(quarter_cut(printable), METRIC) + badge("3D"))
    print("make_icons: wrote", len(BD.SERIES) + 5, "icons to", OUT, flush=True)


main()
