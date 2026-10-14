# SPDX-License-Identifier: GPL-3.0-or-later
"""Render the README images (images/*.png) with the workbench's own code.

Needs the FreeCAD GUI (the 3D view does the rendering), so run it with the GUI binary,
not freecadcmd, from the repository root:

    path/to/FreeCAD tools/render_images.py

On macOS the binary is FreeCAD.app/Contents/MacOS/FreeCAD. A FreeCAD window opens, the
images are written to images/ and FreeCAD quits by itself (exit code 1 if something
failed). Leave the window alone while it runs: resizing it changes the framing.
RENDER_ONLY=hero,closures renders only those scenes (the function names below).

The shapes are built with the workbench modules, copied into a scene document with
their own colors, cut away where useful, and saved with View.saveImage(). Pillow
(bundled with FreeCAD) crops them and adds captions.
"""

import os
import sys
import tempfile
import traceback

import FreeCAD as App
import FreeCADGui as Gui
import Part
from PIL import Image, ImageChops, ImageDraw, ImageFont
from PySide import QtCore, QtGui


def _repo_dir():
    """The repository root, one level above this script (FreeCAD may not set __file__)."""
    try:
        here = os.path.dirname(os.path.abspath(__file__))
    except NameError:
        here = next(
            os.path.dirname(os.path.abspath(a)) for a in sys.argv if a.endswith("render_images.py")
        )
    return os.path.dirname(here)


REPO = _repo_dir()
sys.path.insert(0, REPO)
OUT = os.path.join(REPO, "images")
WORK = tempfile.mkdtemp(prefix="bearings-render-")
os.makedirs(OUT, exist_ok=True)

import BearingBase  # noqa: E402
import BearingData as BD  # noqa: E402
import BearingGeometry as BG  # noqa: E402
import PrintableBearing as PB  # noqa: E402

failed = False


def say(*a):
    line = "render_images: " + " ".join(str(x) for x in a) + "\n"
    App.Console.PrintMessage(line)
    # the GUI captures print(); stdout may be ASCII-only
    sys.__stdout__.write(line.encode("ascii", "replace").decode())
    sys.__stdout__.flush()


# printable bearing colors, as in the macro's README: races blue, cage orange, balls red
RACE, CAGE, BALL = (0.42, 0.55, 0.72), (0.96, 0.58, 0.12), (0.86, 0.16, 0.16)
PART, EDGE = (0.72, 0.72, 0.72), (0.1, 0.75, 0.2)
FONTS = (
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "DejaVuSans.ttf",
)
V = App.Vector
P608 = dict(PB.CAGE_DEFAULTS, ID=8, OD=22, Height=7, BallDiameter=4, NumBalls=7)
# the animations: a 6808 (40 x 52 x 7) with 4.5 mm BBs
P6808 = dict(PB.CAGE_DEFAULTS, ID=40, OD=52, Height=7, BallDiameter=4.5, NumBalls=24)
ISO = (-1, 1, -0.8)  # looking from (+x, -y, +z)

# ------------------------------------------------------------------ model
model = App.newDocument("Model")


def clear(doc):
    for name in [o.Name for o in doc.Objects]:
        if doc.getObject(name):
            doc.removeObject(name)


def big_box(x0, y0, z0, x1, y1, z1):
    return Part.makeBox(x1 - x0, y1 - y0, z1 - z0, V(x0, y0, z0))


def quarter(center=None, size=200):
    """Box removing the quarter x > cx, y < cy, for cutaways."""
    center = center or V()
    return big_box(center.x, center.y - size, -size, center.x + size, center.y, size)


def standard_parts(
    series, name, closure="Open", flanged=False, detail="Standard", pl=None, shape="Round"
):
    """[(solid, rgb)] of a standard bearing or linear bushing, as the workbench colors it."""
    row = BD.get_row(series, name)
    out = []
    flanged = flanged and row.has_flange
    if BD.is_linear(row):
        made = BG.make_linear(row, flanged, shape, detail)
    else:
        made = BG.make_deep_groove(row, closure, flanged, detail)
    for solid, rgb in made:
        s = solid.copy()
        if pl is not None:
            s.Placement = pl.multiply(s.Placement)
        out.append((s, rgb))
    return out


def printable_parts(values=P608, placement=None, reverse=False):
    """{"races", "cage", "balls"} global shapes of a printable bearing made by create_races."""
    clear(model)
    params = PB.create_races(model, placement or App.Placement(), values, reverse, True, True)
    part = params.getParentGeoFeatureGroup().getParentGeoFeatureGroup()
    return {n.lower(): Part.getShape(part, n + ".") for n in ("Races", "Cage", "Balls")}


def colored(sh, cut=None, which=("races", "cage", "balls")):
    out = []
    for key, col in (("races", RACE), ("cage", CAGE), ("balls", BALL)):
        if key in which:
            out.append((sh[key].cut(cut) if cut is not None else sh[key], col))
    return out


def cut_all(items, cut):
    return [(s.cut(cut), c) for s, c in items]


def highlight(edge, thickness=0.35):
    """Selected-edge highlight as a thin green tube (a line can hide behind the solid's edge)."""
    c = edge.Curve
    return (Part.makeTorus(c.Radius, thickness, V(c.Location), c.Axis), EDGE)


def circle_edge(shape, r, z):
    for e in shape.Edges:
        c = e.Curve
        if isinstance(c, Part.Circle) and abs(c.Radius - r) < 1e-6 and abs(c.Location.z - z) < 1e-6:
            return e
    raise ValueError("no circle r=%g at z=%g" % (r, z))


# ------------------------------------------------------------------ rendering
scene = App.newDocument("Scene")


def view():
    return Gui.getDocument(scene.Name).activeView()


def show(items, outlines=True):
    """items: list of (shape, rgb). Without `outlines`, faces only (no edge lines)."""
    clear(scene)
    for i, (shape, color) in enumerate(items):
        f = scene.addObject("Part::Feature", "S%d" % i)
        f.Shape = shape
        vo = f.ViewObject
        vo.ShapeColor = color
        vo.LineColor = (0.15, 0.15, 0.15)
        vo.LineWidth = 1.5
        if not outlines:
            vo.DisplayMode = "Shaded"
    scene.recompute()
    QtGui.QApplication.processEvents()


def look(v, direction):
    """Point the camera along `direction` with the model's Z axis pointing up on screen."""
    d = V(*direction).normalize()
    zc = -d
    xc = V(0, 0, 1).cross(zc).normalize()
    yc = zc.cross(xc)
    m = App.Matrix(xc.x, yc.x, zc.x, 0, xc.y, yc.y, zc.y, 0, xc.z, yc.z, zc.z, 0, 0, 0, 0, 1)
    v.setCameraOrientation(App.Rotation(m).Q)


def render(items, direction=ISO, camera=None, keep_scene=False, scale=1, outlines=True):
    """Render `items` and return (image, model point -> image pixel, camera).

    `scale` renders at that multiple of the view's size, for sharper images."""
    if not keep_scene:
        show(items, outlines)
    v = view()
    v.setAnimationEnabled(False)
    v.setCameraType("Orthographic")
    if camera:
        v.setCamera(camera)
    else:
        look(v, direction)
        v.fitAll()
    for _ in range(5):
        QtGui.QApplication.processEvents()
    w, h = v.getSize()
    path = WORK + "/tmp.png"
    v.saveImage(path, w * scale, h * scale, "White")
    img = Image.open(path).convert("RGB")

    def proj(p):
        x, y = v.getPointOnScreen(V(*p))
        return (x * scale, (h - y) * scale)

    return img, proj, v.getCamera()


def content_box(img, extra=()):
    bg = Image.new("RGB", img.size, (255, 255, 255))
    x0, y0, x1, y1 = ImageChops.difference(img, bg).getbbox()
    for x, y in extra:
        x0, y0, x1, y1 = min(x0, x), min(y0, y), max(x1, x), max(y1, y)
    return x0, y0, x1, y1


def finish(img, box, width, margin=40):
    x0, y0, x1, y1 = box
    x0, y0 = max(0, x0 - margin), max(0, y0 - margin)
    img = img.crop((x0, y0, min(img.width, x1 + margin), min(img.height, y1 + margin)))
    s = width / img.width
    return img.resize((width, int(img.height * s)), Image.LANCZOS), (x0, y0, s)


def font(size):
    for f in FONTS:
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            pass
    return ImageFont.load_default(size)


def save(img, name):
    path = os.path.join(OUT, name)
    img.save(path, optimize=True)
    say("saved", path, img.size)


def panels(imgs_captions, name, cell_w=460, gap=24, same_crop=True):
    """Panels side by side with captions underneath (one crop for all if `same_crop`)."""
    boxes = [content_box(img) for img, _ in imgs_captions]
    if same_crop:
        box = (
            min(b[0] for b in boxes),
            min(b[1] for b in boxes),
            max(b[2] for b in boxes),
            max(b[3] for b in boxes),
        )
        boxes = [box] * len(boxes)
    cells = [finish(img, b, cell_w)[0] for (img, _), b in zip(imgs_captions, boxes)]
    f = font(20)
    cap_h = 44
    H = max(c.height for c in cells) + cap_h
    out = Image.new("RGB", (len(cells) * cell_w + (len(cells) - 1) * gap, H), "white")
    d = ImageDraw.Draw(out)
    for i, (c, (_, cap)) in enumerate(zip(cells, imgs_captions)):
        x = i * (cell_w + gap)
        out.paste(c, (x, (H - cap_h - c.height) // 2))
        tw = d.textlength(cap, font=f)
        d.text((x + (cell_w - tw) / 2, H - cap_h + 10), cap, fill=(40, 40, 40), font=f)
    save(out, name)


def grab(widget):
    """Screenshot of a Qt widget as a PIL image."""
    for _ in range(10):
        QtGui.QApplication.processEvents()
    widget.adjustSize()
    QtGui.QApplication.processEvents()
    path = WORK + "/widget.png"
    widget.grab().save(path)
    return Image.open(path).convert("RGB")


def row_with_captions(img, proj, captions, name, width, font_size=26):
    """Crop a rendered row of models and write each caption under its model, all on one
    baseline. captions: [(text, model point whose screen x centers the text)]."""
    xs = [proj(p)[0] for _, p in captions]
    img, (ox, oy, s) = finish(img, content_box(img), width, margin=int(width / 45))
    f = font(font_size)
    out = Image.new("RGB", (img.width, img.height + 2 * font_size), "white")
    out.paste(img, (0, 0))
    d = ImageDraw.Draw(out)
    for (text, _), x in zip(captions, xs):
        d.text(
            ((x - ox) * s, img.height + font_size // 6),
            text,
            fill=(40, 40, 40),
            font=f,
            anchor="mt",
        )
    save(out, name)


def side_by_side(left, right, name, height=720, gap=32):
    """Two images scaled to the same height on a white canvas."""
    scaled = [
        im.resize((int(im.width * height / im.height), height), Image.LANCZOS)
        for im in (left, right)
    ]
    out = Image.new("RGB", (scaled[0].width + gap + scaled[1].width, height), "white")
    out.paste(scaled[0], (0, 0))
    out.paste(scaled[1], (scaled[0].width + gap, 0))
    save(out, name)


# ------------------------------------------------------------------ scenes


def hero():
    """A row of bearings: standard ones (cut away) and a printable one."""
    lineup = [
        ("62", "6204", "2RS", False, "Detailed", "6204-2RS"),
        ("60", "608", "ZZ", False, "Detailed", "608ZZ"),
        ("68", "688", "ZZ", True, "Standard", "F688ZZ"),
        ("MR", "MR105", "Open", False, "Standard", "MR105"),
    ]
    items, captions, x = [], [], 0.0
    for series, name, closure, flanged, detail, caption in lineup:
        row = BD.get_row(series, name)
        od = row.D1 if flanged else row.D
        x += od / 2
        pl = App.Placement(V(x, 0, 0), App.Rotation())
        items += cut_all(
            standard_parts(series, name, closure, flanged, detail, pl), quarter(V(x, 0, 0))
        )
        captions.append((caption, (x, 0, 0)))
        x += od / 2 + 10
    x += 11
    sh = printable_parts(P608, App.Placement(V(x, 0, -7), App.Rotation()))
    items += colored(sh, cut=quarter(V(x, 0, 0)))
    captions.append(("Printable 608", (x, 0, 0)))
    # no edge lines, rendered large and scaled down so it stays sharp on big screens
    img, proj, _ = render(items, direction=(0, 1, -0.6), scale=4, outlines=False)
    row_with_captions(img, proj, captions, "hero.png", 2400, font_size=44)


def detail_levels():
    imgs = []
    cam = None
    for detail in BG.DETAIL_LEVELS:
        items = cut_all(standard_parts("62", "6204", "2RS", detail=detail), quarter())
        img, _, c = render(items, direction=ISO, camera=cam)
        cam = cam or c
        imgs.append((img, detail))
    panels(imgs, "detail-levels.png", cell_w=380)


def closures():
    cases = [
        ("60", "608", "Open", False, "608 (open)"),
        ("60", "608", "ZZ", False, "608ZZ (shields)"),
        ("60", "608", "2RS", False, "608-2RS (seals)"),
        ("68", "688", "ZZ", True, "F688ZZ (flanged)"),
    ]
    imgs = []
    for series, name, closure, flanged, caption in cases:
        img, _, _ = render(
            standard_parts(series, name, closure, flanged), direction=(-0.5, 1, -1.1)
        )
        imgs.append((img, caption))
    panels(imgs, "closures.png", cell_w=300, same_crop=False)


def linear_bushings():
    """LM8UU, LM8LUU, LMF8UU and LMK8UU at Detailed level, cut away, standing on end."""
    cases = [
        ("LM8UU", False, "Round", "LM8UU"),
        ("LM8LUU", False, "Round", "LM8LUU (long)"),
        ("LM8UU", True, "Round", "LMF8UU (round flange)"),
        ("LM8UU", True, "Square", "LMK8UU (square flange)"),
    ]
    items, captions, x = [], [], 0.0
    for name, flanged, shape, caption in cases:
        row = BD.get_row("LM", name)
        w = (row.K if shape == "Square" else row.D1) if flanged else row.D
        x += w / 2
        pl = App.Placement(V(x, 0, 0), App.Rotation())
        parts = standard_parts("LM", name, flanged=flanged, detail="Detailed", pl=pl, shape=shape)
        items += cut_all(parts, quarter(V(x, 0, 0)))
        captions.append((caption, (x, 0, 0)))
        x += w / 2 + 12
    img, proj, _ = render(items, direction=(0, 1, -0.55), scale=3, outlines=False)
    row_with_captions(img, proj, captions, "linear-bushings.png", 1800, font_size=34)


def edge_snap():
    """Hole edge -> the bearing sits in the hole; shaft end -> it slides onto the shaft."""
    clear(model)
    plate = model.addObject("Part::Feature", "Plate")
    plate.Shape = big_box(-20, -20, 0, 20, 20, 10).cut(Part.makeCylinder(11, 12, V(0, 0, -1)))
    shaft = model.addObject("Part::Feature", "Shaft")
    shaft.Shape = Part.makeCylinder(4, 16, V(0, 0, 0))
    model.recompute()
    cells = []
    for obj, r, z, captions in (
        (plate, 11, 10, ("Select a hole edge", "608 sized to the hole")),
        (shaft, 4, 16, ("Select a shaft end", "608 sized to the shaft")),
    ):
        edge = circle_edge(obj.Shape, r, z)
        name = "Edge%d" % (1 + [e.isSame(edge) for e in obj.Shape.Edges].index(True))
        b = BearingBase.make_bearing("60", attach_to=(obj, [name]), doc=model)
        parts = standard_parts("60", b.FullDesignation, pl=b.Placement)
        base = obj.Shape.cut(quarter()) if obj is plate else obj.Shape
        # frame both panels on the "after" scene so the pair shares one scale
        after = render([(base, PART)] + cut_all(parts, quarter()), direction=(-1, 1, -0.6))
        before = render([(obj.Shape, PART), highlight(edge)], camera=after[2])
        box = [content_box(i) for i in (before[0], after[0])]
        box = tuple(f(v) for f, v in zip((min, min, max, max), zip(*box)))
        cells += [
            (finish(before[0], box, 300)[0], captions[0]),
            (finish(after[0], box, 300)[0], captions[1]),
        ]
        model.removeObject(b.Name)
    f = font(20)
    cap_h, gap = 44, 24
    H = max(c.height for c, _ in cells) + cap_h
    out = Image.new("RGB", (4 * 300 + 3 * gap, H), "white")
    d = ImageDraw.Draw(out)
    for i, (c, cap) in enumerate(cells):
        x = i * (300 + gap)
        out.paste(c, (x, (H - cap_h - c.height) // 2))
        d.text((x + 150, H - cap_h + 10), cap, fill=(40, 40, 40), font=f, anchor="mt")
    save(out, "edge-snap.png")


def printable_parts_exploded():
    """Races, cage and balls as separate bodies, ready to print."""
    sh = printable_parts(dict(P608, ID=20, OD=32, Height=8, NumBalls=10))
    items, captions = [], []
    for key, col, dx, text in (
        ("races", RACE, 0, "Races"),
        ("cage", CAGE, 44, "Cage"),
        ("balls", BALL, 88, "Balls"),
    ):
        s = sh[key].copy()
        s.translate(V(dx, 0, 0))
        items.append((s, col))
        captions.append((text, (dx, 0, 0)))
    img, proj, _ = render(items, direction=(0, 1, -0.8))
    row_with_captions(img, proj, captions, "printable-bodies.png", 1100)


def groove_body():
    clear(model)
    body = model.addObject("PartDesign::Body", "Hub")
    disc = body.newObject("PartDesign::AdditiveCylinder", "Disc")
    disc.Radius, disc.Height = 24, 8
    bore = body.newObject("PartDesign::SubtractiveCylinder", "Bore")
    bore.Radius, bore.Height = 10, 8
    model.recompute()
    part = body.Shape.copy()
    edge = circle_edge(body.Shape, 10, 8)
    view_dir = (-1, 1, -0.7)
    a = render([(part, PART), highlight(edge)], direction=view_dir)
    PB.groove_body(
        bore,
        body.Shape.getElement(
            "Edge%d" % (1 + [e.isSame(edge) for e in body.Shape.Edges].index(True))
        ),
        dict(P608, ID=0, OD=32, Height=8, NumBalls=10),
        True,
        True,
    )
    inner, rest = sorted(body.Shape.Solids, key=lambda s: s.BoundBox.XLength)
    cut = quarter()
    items = [(rest.cut(cut), PART), (inner.cut(cut), RACE)]
    items += [(model.getObject(n).Shape.cut(cut), c) for n, c in (("Cage", CAGE), ("Balls", BALL))]
    b = render(items, camera=a[2])
    panels(
        [(a[0], "Your part: select the bore edge"), (b[0], "Grooved: the part is the outer race")],
        "groove-body.png",
    )


def convert():
    """A standard bearing replaced by a printable one of the same size, in the same place."""
    clear(model)
    view_dir = (-1, 1, -0.7)
    a = render(
        cut_all(standard_parts("62", "6204", "2RS", detail="Detailed"), quarter()),
        direction=view_dir,
    )
    std = BearingBase.make_bearing("62", "6204", doc=model)
    PB.convert_bearing(std, dict(BallDiameter=6.35, NumBalls=10), True, True)
    part = [o for o in model.Objects if o.TypeId == "App::Part"][0]
    sh = {n.lower(): Part.getShape(part, n + ".") for n in ("Races", "Cage", "Balls")}
    b = render(colored(sh, cut=quarter()), camera=a[2])
    panels([(a[0], "Standard 6204-2RS"), (b[0], 'Printable 6204, 1/4" balls')], "convert.png")


def printable_panel():
    """The task panel next to the 3D view with its live preview."""
    import PrintableBearingGui as PG

    show([])
    clear(scene)
    plate = scene.addObject("Part::Feature", "Plate")
    plate.Shape = big_box(-20, -20, 0, 20, 20, 10).cut(Part.makeCylinder(11, 12, V(0, 0, -1)))
    plate.ViewObject.ShapeColor = PART
    plate.ViewObject.LineColor = (0.15, 0.15, 0.15)
    scene.recompute()
    edge = circle_edge(plate.Shape, 11, 10)
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(
        scene.Name,
        "Plate",
        "Edge%d" % (1 + [e.isSame(edge) for e in plate.Shape.Edges].index(True)),
    )
    panel = PG.open_panel()
    panel.size.setCurrentIndex(
        [i for i in range(panel.size.count()) if panel.size.itemText(i).startswith("608")][0]
    )
    panel.ball_preset.setCurrentIndex(
        [
            i
            for i in range(panel.ball_preset.count())
            if panel.ball_preset.itemText(i).startswith("3 mm")
        ][0]
    )
    panel.num_balls.setValue(10)
    panel.values_changed()
    Gui.Selection.clearSelection()
    form = grab(panel.form)
    img, _, _ = render([], direction=(-1, 1, -1.2), keep_scene=True)
    img, _ = finish(img, content_box(img), 900, margin=30)
    panel.reject()
    side_by_side(form, img, "printable-panel.png")


def find_panel():
    import BearingSearchGui as SG

    clear(scene)
    Gui.Selection.clearSelection()
    panel = SG.open_panel()
    panel.D.setValue(22)
    panel.form.setMinimumWidth(560)
    form = grab(panel.form)
    Gui.Control.closeDialog()
    save(form, "find-bearing.png")


# ------------------------------------------------------------------ animations


def save_gif(frames, name, durations, colors=255, dither=True):
    """Animated GIF that loops forever; `durations` in ms (one value or one per frame).

    Frames are padded to one size, and one palette is made from all of them, so colors
    that appear only in later frames survive."""
    W, H = max(f.width for f in frames), max(f.height for f in frames)
    padded = []
    for f in frames:
        canvas = Image.new("RGB", (W, H), "white")
        canvas.paste(f, (0, 0))
        padded.append(canvas)
    thumbs = [f.resize((W // 4, H // 4)) for f in padded]
    sheet = Image.new("RGB", (W // 4, H // 4 * len(thumbs)), "white")
    for i, t in enumerate(thumbs):
        sheet.paste(t, (0, i * (H // 4)))
    palette = sheet.quantize(colors=colors, method=Image.Quantize.MEDIANCUT)
    # median cut averages the background slightly off white; make it pure white again
    entries = palette.getpalette()
    for i in range(0, len(entries), 3):
        if min(entries[i : i + 3]) >= 246:
            entries[i : i + 3] = [255, 255, 255]
    palette.putpalette(entries)
    mode = Image.Dither.FLOYDSTEINBERG if dither else Image.Dither.NONE
    pal = [f.quantize(palette=palette, dither=mode) for f in padded]
    path = os.path.join(OUT, name)
    pal[0].save(
        path,
        save_all=True,
        append_images=pal[1:],
        duration=durations,
        loop=0,
        optimize=True,
        disposal=1,
    )
    say("saved", path, (W, H), "%d frames" % len(frames), "%d KB" % (os.path.getsize(path) // 1024))


def turntable_gif():
    """The printable bearing, cut away, turning once around its axis."""
    sh = printable_parts(P6808, App.Placement(V(0, 0, -3.5), App.Rotation()))
    cut = quarter()
    parts = colored(sh, cut=cut)
    # one camera and one crop for every frame, framed on the whole (round) bearing
    full, _, cam = render(colored(sh), direction=(-1, 1, -0.75), scale=2, outlines=False)
    box = content_box(full)
    frames, n = [], 48
    for k in range(n):
        items = []
        for shape, col in parts:
            s = shape.copy()
            s.rotate(V(), V(0, 0, 1), 360.0 * k / n)
            items.append((s, col))
        img = render(items, camera=cam, scale=2, outlines=False)[0]
        frames.append(finish(img, box, 640, margin=20)[0])
    save_gif(frames, "printable-turntable.gif", 70)


def workflow_gif():
    """Select a hole edge, open the panel, pick a size and balls, OK: the bearing is built."""
    import PrintableBearingGui as PG

    W_PANEL, W_VIEW, GAP, CAP = 420, 640, 24, 64
    plate_shape = big_box(-35, -35, 0, 35, 35, 10).cut(Part.makeCylinder(26, 12, V(0, 0, -1)))
    edge = circle_edge(plate_shape, 26, 10)
    view_dir = (-1, 1, -1.1)

    def plate_scene(extra=()):
        show([(plate_shape, PART)] + list(extra))
        return scene.getObject("S0")

    plate_scene()
    _, _, cam = render([], camera=None, direction=view_dir, keep_scene=True, scale=2)
    box = content_box(render([], camera=cam, keep_scene=True, scale=2)[0])

    def view_img():
        img = render([], camera=cam, keep_scene=True, scale=2)[0]
        return finish(img, box, W_VIEW, margin=30)[0]

    def frame(caption, left, right):
        return (caption, left, right)

    def compose(caption, left, right, H):
        out = Image.new("RGB", (W_PANEL + GAP + W_VIEW, H), "white")
        d = ImageDraw.Draw(out)
        d.text((16, CAP // 2), caption, fill=(30, 30, 30), font=font(30), anchor="lm")
        if left is not None:
            out.paste(left, ((W_PANEL - left.width) // 2, CAP))
        out.paste(right, (W_PANEL + GAP, CAP + (H - CAP - right.height) // 2))
        return out

    def scaled(img, width=W_PANEL):
        return img.resize((width, int(img.height * width / img.width)), Image.LANCZOS)

    def icon_tile(text):
        """The command's icon with its menu text, standing in for the toolbar click."""
        path = WORK + "/icon.png"
        QtGui.QIcon(os.path.join(REPO, "Icons", "PrintableBearing.svg")).pixmap(256, 256).save(path)
        tile = Image.new("RGB", (W_PANEL, 360), "white")
        ic = Image.open(path).convert("RGBA").resize((200, 200), Image.LANCZOS)
        tile.paste(ic, ((W_PANEL - 200) // 2, 40), ic)
        ImageDraw.Draw(tile).text(
            (W_PANEL // 2, 290), text, fill=(40, 40, 40), font=font(26), anchor="mt"
        )
        return tile

    frames, durations = [], []

    def add(img, ms):
        frames.append(img)
        durations.append(ms)

    plate_scene()
    add(frame("A part with a 52 mm hole", None, view_img()), 1400)
    plate_scene([highlight(edge)])
    add(frame("1. Select the hole edge", None, view_img()), 1600)
    add(
        frame(
            "2. Bearing tools > 3D-printable bearing", icon_tile("3D-printable bearing"), view_img()
        ),
        1600,
    )

    plate = plate_scene()
    on_plate = circle_edge(plate.Shape, 26, 10)
    name = "Edge%d" % (1 + [e.isSame(on_plate) for e in plate.Shape.Edges].index(True))
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(scene.Name, plate.Name, name)
    panel = PG.open_panel()
    Gui.Selection.clearSelection()

    def panel_frame(caption, ms):
        panel.values_changed()
        add(frame(caption, scaled(grab(panel.form)), view_img()), ms)

    panel_frame("3. The panel previews the bearing in place", 2000)
    panel.size.setCurrentIndex(
        [i for i in range(panel.size.count()) if panel.size.itemText(i).startswith("6808")][0]
    )
    panel_frame("4. Pick a catalog size: 6808", 1800)
    panel.ball_preset.setCurrentIndex(
        [i for i in range(panel.ball_preset.count()) if "4.5" in panel.ball_preset.itemText(i)][0]
    )
    panel_frame("5. Pick the balls: 4.5 mm BBs", 1800)
    panel.num_balls.setValue(P6808["NumBalls"])
    panel_frame("6. Fit 24 of them, then OK", 1800)
    panel.accept()
    QtGui.QApplication.processEvents()

    part = [o for o in scene.Objects if o.TypeId == "App::Part"][0]
    built = [(plate_shape.cut(quarter()), PART)]
    built += [
        (Part.getShape(part, n + ".").cut(quarter()), c)
        for n, c in (("Races", RACE), ("Cage", CAGE))
    ]
    show(built)
    add(frame("7. Races and a snap-in cage, ready to print", None, view_img()), 3000)
    H = CAP + max(max(rt.height, lt.height if lt is not None else 0) for _, lt, rt in frames)
    frames = [compose(c, lt, rt, H) for c, lt, rt in frames]
    save_gif(frames, "printable-workflow.gif", durations, dither=False)


STEPS = (
    hero,
    detail_levels,
    closures,
    linear_bushings,
    edge_snap,
    printable_parts_exploded,
    groove_body,
    convert,
    printable_panel,
    find_panel,
    turntable_gif,
    workflow_gif,
)


def main():
    global failed
    try:
        Gui.activateWorkbench("BearingsWorkbench")
        Gui.getDocument(scene.Name).activeView().setAxisCross(False)
        only = os.environ.get("RENDER_ONLY")
        for step in STEPS:
            if only and step.__name__ not in only.split(","):
                continue
            say("step", step.__name__)
            App.setActiveDocument(scene.Name)
            Gui.setActiveDocument(scene.Name)
            step()
    except Exception:
        failed = True
        say(traceback.format_exc())
    finally:
        QtCore.QTimer.singleShot(300, lambda: os._exit(1 if failed else 0))


QtCore.QTimer.singleShot(2000, main)
