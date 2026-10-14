# SPDX-License-Identifier: GPL-3.0-or-later
"""3D-printable deep groove ball bearings, built as PartDesign bodies.

Ported from the DeepGrooveBallBearing macro (same author, originally MIT). The geometry
and parameters are unchanged from the macro:

- "Groove selected body": the ball groove is cut into the PartDesign Body a selected
  edge belongs to, and the body itself becomes the races.
- "Create races": a new ring with both races is built. Races, cage and balls go into
  one App::Part labelled with the bearing's size.

Parameters live on a "BearingParameters" datum coordinate system inside the races Body
(one per bearing). The datum is the bearing frame: origin on the axis at mid-height,
Z = bearing axis. The groove sketch is attached to its XZ plane, and the Cage and Balls
bodies follow it.

Groove profile:
  - Ball circle (construction), centered at the pitch diameter, mid-height
  - Slot of width = ball diameter / 2, centered on the ball, through the full height
  - Outline = the slot walls + the ball arcs that bulge into each race
Cage:
  - Ring of CageThickness centered on the pitch diameter, from the bottom face up to
    CageTopOffset below where the slot walls meet the ball
  - Ball pocket of Ø (BallDiameter + PocketClearance), rising PocketRise above the
    cage top (snap-in opening), polar-patterned NumBalls times
  - Shown seated: in use the balls pull the cage along the axis until the pockets are
    centered on them, so the whole cage is shifted by that amount.
Balls:
  - Sphere of BallDiameter at the pitch diameter, mid-height, patterned NumBalls times

Sketch coordinate system (groove and cage sketches):
  - Origin  : on the bearing axis, at mid-height
  - X axis  : radial direction (outward)
  - Y axis  : bearing axis (V_Axis) -- grooves and revolutions turn around this

Additions over the macro: catalog sizes (BearingData), ball presets, and a
PrintableBearing check object that validates edits to BearingParameters and keeps the
Part label in step with the size.
"""

import math
import textwrap

import FreeCAD as App
import Part
import Sketcher

import BearingData as BD
from BearingGeometry import revolve
from BRselection import (  # noqa: F401  (frame_placement is part of this module's API)
    cylinder_side,
    frame_placement,
    global_placement,
    nearest_solid,
)

TOL = 1e-6
PARAMS = "BearingParameters"
GROOVE = "Groove selected body"
CREATE = "Create races"
SIN60 = math.sqrt(3) / 2  # slot = ball Ø / 2, so the slot walls meet the ball at 60°

# What each parameter means: the datum's property descriptions, also used as tooltips by
# the task panel. Describe the bearing here; the panel's own behaviour is described in
# PrintableBearingGui.UI_HELP.
BEARING_DOCS = {
    "ID": "Bore of the inner race, i.e. the shaft diameter the bearing fits on.",
    "OD": "Outside diameter of the outer race, i.e. the housing bore the bearing fits in.",
    "Height": "Axial width of the bearing (B in bearing catalogues). The balls and race "
    "grooves are centered in it.",
    "BallDiameter": "Diameter of the balls. The balls run on the pitch diameter, midway between "
    "ID and OD, and the gap between the two races is half the ball diameter. "
    "Must be smaller than the ring wall, (OD - ID) / 2, and than the height.",
    "NumBalls": "How many balls (and cage pockets) are spaced evenly around the bearing. "
    "The maximum depends on the ball size and the pitch diameter.",
}
DEFAULT_NUM_BALLS = 10
DEFAULT_BALL_DIAMETER = 4.0
DEFAULT_HEIGHT = 8.0  # new races; grooving keeps the selected bore's length
OTHER_DIAMETER_OFFSET = 15.0  # starting OD = selected ID + 15 mm (or ID = selected OD - 15)
CAGE_DEFAULTS = {
    "CageThickness": 1.5,
    "CageTopOffset": 0.5,
    "PocketClearance": 0.35,
    "PocketRise": 0.6,
}
CAGE_DOCS = {
    "CageThickness": "Radial thickness of the cage ring. It sits in the gap between the races, "
    "which is always half the ball diameter (2 mm for a 4 mm ball), so it can be at most "
    "that; what is left over is running clearance on each side.",
    "CageTopOffset": "Sets how tall the cage is. As designed, the cage reaches from the races' "
    "face to this distance short of where the race grooves meet the ball. "
    "Larger value = shorter cage.",
    "PocketClearance": "Extra diameter given to each ball pocket so the balls turn freely. "
    "Pocket diameter = ball diameter + this value.",
    "PocketRise": "How far each pocket circle reaches past the cage's open edge. A smaller value "
    "makes the pocket mouth narrower than the ball, so the balls snap in and are "
    "held. The cage is drawn seated: moved along the axis until the pockets are "
    "centered on the balls.",
}


# Balls makers can buy, (label, diameter). Airsoft BBs are nominally 6 mm but 5.95 mm.
BALL_PRESETS = [
    ("3 mm steel ball", 3.0),
    ('1/8" steel ball (3.175 mm)', 3.175),
    ("4 mm steel ball", 4.0),
    ("4.5 mm steel BB (.177)", 4.5),
    ("5 mm steel ball", 5.0),
    ("6 mm airsoft BB (5.95 mm)", 5.95),
    ("6 mm steel ball", 6.0),
    ('1/4" steel ball (6.35 mm)', 6.35),
]


def catalog_rows():
    """Every catalog size once, (designation, d, D, B) sorted by bore then OD."""
    seen, rows = set(), []
    for series in BD.SERIES:
        for r in BD.load_table(series):
            if (r.d, r.D, r.B) not in seen:
                seen.add((r.d, r.D, r.B))
                rows.append((r.name, r.d, r.D, r.B))
    return sorted(rows, key=lambda r: (r[1], r[2], r[3]))


def catalog_match(values, tol=1e-6):
    """Designation of the catalog bearing with these ID x OD x Height, or None.

    The height may be the open or the shielded width (688 is 4 mm open, 5 mm as 688ZZ).
    """
    for series in BD.SERIES:
        for r in BD.load_table(series):
            if abs(values["ID"] - r.d) >= tol or abs(values["OD"] - r.D) >= tol:
                continue
            widths = [r.B] + ([r.B_shielded] if r.B_shielded is not None else [])
            if any(abs(values["Height"] - b) < tol for b in widths):
                return r.name
    return None


def wrapped(text, width=50):
    """Break help text into short lines so tooltips stay narrow."""
    return "\n".join(textwrap.fill(para, width) for para in text.split("\n"))


# ---------------------------------------------------------------- geometry helpers


def find_body(feature):
    """Return the PartDesign Body the selected feature belongs to, or None."""
    if feature.TypeId == "PartDesign::Body":
        return feature
    parent = feature.getParentGeoFeatureGroup()
    if parent and parent.TypeId == "PartDesign::Body":
        return parent
    return None


def measure_body(body, edge):
    """Measure the selected body around the edge, for grooving it into races.

    `edge` is in document coordinates. Returns the edge's diameter, whether it is the
    bearing's ID (a bore) or OD (an outer surface), the selected cylinder's length and
    the axial offset of its middle from the edge's plane.
    """
    # body.Shape includes the body's own placement but not its containers' (App::Part),
    # so bring the edge into the body's container coordinates first
    container = global_placement(body).multiply(body.Placement.inverse())
    edge = edge.copy()
    edge.transformShape(container.inverse().toMatrix())

    solid = nearest_solid(body.Shape, edge)
    side, lo, hi = cylinder_side(solid, edge)
    if side is None:
        raise ValueError("Could not find the cylindrical face of the selected edge on the body.")
    return {
        "dia": 2 * edge.Curve.Radius,
        "is_inner": side == "outside",  # a bore is the bearing's inner diameter
        "height": hi - lo,
        "mid": (lo + hi) / 2,
    }


def origin_feature(body, role):
    return next(f for f in body.Origin.OriginFeatures if f.Role == role)


def attach(sketch, target, mode="FlatFace"):
    prop = "AttachmentSupport" if hasattr(sketch, "AttachmentSupport") else "Support"
    setattr(sketch, prop, [(target, "")])
    sketch.MapMode = mode


def max_balls(id_, od, ball_dia, clearance=0.0):
    """Most pockets that fit around the pitch circle without overlapping."""
    ratio = (ball_dia + clearance) / ((id_ + od) / 2)
    return int(math.pi / math.asin(ratio)) if ratio < 1 else 0


def other_diameter(selected, selected_is_inner):
    """Starting value for the diameter the selected edge doesn't fix: 15 mm larger for a
    selected ID; 15 mm smaller for a selected OD, or half of it when that leaves no bore."""
    if selected_is_inner:
        return round(selected + OTHER_DIAMETER_OFFSET, 2)
    smaller = selected - OTHER_DIAMETER_OFFSET
    return round(smaller if smaller > 0 else selected / 2, 2)


def validate(v, cage=False, balls=False):
    id_, od, height, ball = v["ID"], v["OD"], v["Height"], v["BallDiameter"]
    for name, label in (
        ("ID", "Inner diameter"),
        ("Height", "Height"),
        ("BallDiameter", "Ball diameter"),
    ):
        if v[name] <= 0:
            raise ValueError("%s must be greater than 0." % label)
    if od <= id_:
        raise ValueError("Outer diameter must be larger than the inner diameter.")
    if ball >= (od - id_) / 2:
        raise ValueError(
            "Ball diameter Ø%.2f must be smaller than the ring wall (%.2f)."
            % (ball, (od - id_) / 2)
        )
    if ball >= height:
        raise ValueError(
            "Ball diameter Ø%.2f must be smaller than the height (%.2f)." % (ball, height)
        )
    if balls or cage:
        clearance = v["PocketClearance"] if cage else 0.0
        n = max_balls(id_, od, ball, clearance)
        if not 1 <= v.get("NumBalls", DEFAULT_NUM_BALLS) <= n:
            raise ValueError("Number of balls must be between 1 and %d for these sizes." % n)
    if not cage:
        return
    if v["CageThickness"] <= 0:
        raise ValueError("Cage thickness must be greater than 0.")
    if v["CageThickness"] > ball / 2 + 1e-9:
        raise ValueError(
            "Cage thickness %.2f can be at most the gap between the races "
            "(half the ball diameter, %.2f)." % (v["CageThickness"], ball / 2)
        )
    if ball * SIN60 / 2 - v["CageTopOffset"] <= -height / 2:
        raise ValueError("Cage top offset %.2f leaves no cage." % v["CageTopOffset"])


# ---------------------------------------------------------------- features


def make_params(body, values, placement, readonly=()):
    """BearingParameters datum inside the races Body: the bearing frame + all parameters.

    `placement` is in body coordinates (origin on the axis at mid-height, Z = axis).
    Names in `readonly` (the diameter taken from the selected edge) can't be edited.
    """
    lcs = body.newObject("PartDesign::CoordinateSystem", PARAMS)
    lcs.MapMode = "Deactivated"
    lcs.Placement = placement
    for name, doc_str in BEARING_DOCS.items():
        if name in readonly:
            doc_str += " (taken from the selected edge)"
        kind = "App::PropertyInteger" if name == "NumBalls" else "App::PropertyLength"
        lcs.addProperty(kind, name, "Bearing", wrapped(doc_str))
        setattr(
            lcs,
            name,
            values.get(name, DEFAULT_NUM_BALLS) if name == "NumBalls" else values[name],
        )
        if name in readonly:
            lcs.setEditorMode(name, ["ReadOnly"])
    for name, default in CAGE_DEFAULTS.items():
        lcs.addProperty("App::PropertyLength", name, "Cage", wrapped(CAGE_DOCS[name]))
        setattr(lcs, name, values.get(name, default))
    lcs.Visibility = False
    return lcs


def values_of(params):
    names = tuple(BEARING_DOCS) + tuple(CAGE_DEFAULTS)
    return {n: getattr(params, n).Value if n != "NumBalls" else params.NumBalls for n in names}


# The groove and cage dimensions are computed once here, for both the PartDesign
# features (initial sketch geometry) and the task panel preview. The sketches are then
# driven by expressions on BearingParameters, which repeat these formulas;
# tests/test_printable.py checks that a built bearing matches preview_shapes(), also
# after its parameters are edited.


def groove_profile(v):
    """Groove profile dimensions in the bearing frame (X radial, Y = Z axial, origin on
    the axis at mid-height): pitch radius rp, ball radius rb, half slot width w, half
    height h, and yi, the height where the slot walls meet the ball circle."""
    ball = v["BallDiameter"]
    return {
        "rp": (v["ID"] + v["OD"]) / 4,  # ball center
        "rb": ball / 2,
        "w": ball / 4,  # slot = ball diameter / 2
        "h": v["Height"] / 2,
        "yi": ball / 2 * SIN60,
    }


def cage_profile(v):
    """Cage ring cross-section (r_in, r_out, bottom, top) in the bearing frame.

    As designed the cage reaches from the bottom face to CageTopOffset below where the
    slot walls meet the ball, with the pocket rising PocketRise above its top. It is
    shown seated: shifted along the axis so the pocket center lands on the ball center.
    """
    g = groove_profile(v)
    t = v["CageThickness"]
    design_top = g["yi"] - v["CageTopOffset"]
    top = (v["BallDiameter"] + v["PocketClearance"]) / 2 - v["PocketRise"]
    bottom = -g["h"] + (top - design_top)
    return g["rp"] - t / 2, g["rp"] + t / 2, bottom, top


def draw_race_profile(sketch, v):
    """Ball circle + slot through the full height, as in deep-groove-bb.FCStd.

    Origin at mid-height on the axis. Driving constraints are named
    PitchRadius, BallDiameter, SlotWidth, Height.
    """
    V = App.Vector
    Z = V(0, 0, 1)
    g = groove_profile(v)
    rp, rb, w, h, yi = g["rp"], g["rb"], g["w"], g["h"], g["yi"]
    phi = math.atan2(yi, w)

    def line(x1, y1, x2, y2):
        return sketch.addGeometry(Part.LineSegment(V(x1, y1, 0), V(x2, y2, 0)))

    def arc(a1, a2):
        return sketch.addGeometry(Part.ArcOfCircle(Part.Circle(V(rp, 0, 0), Z, rb), a1, a2))

    ball = sketch.addGeometry(Part.Circle(V(rp, 0, 0), Z, rb), True)
    l1 = line(rp - w, -yi, rp - w, -h)  # bottom slot, inner wall
    l2 = line(rp - w, -h, rp + w, -h)  # bottom face
    l3 = line(rp + w, -h, rp + w, -yi)  # bottom slot, outer wall
    l4 = line(rp - w, yi, rp - w, h)  # top slot, inner wall
    l5 = line(rp - w, h, rp + w, h)  # top face
    l6 = line(rp + w, h, rp + w, yi)  # top slot, outer wall
    a_in = arc(math.pi - phi, math.pi + phi)  # ball arc into the inner race
    a_out = arc(-phi, phi)  # ball arc into the outer race

    C = Sketcher.Constraint
    named = {
        "PitchRadius": C("DistanceX", -1, 1, ball, 3, rp),
        "BallDiameter": C("Diameter", ball, 2 * rb),
        "SlotWidth": C("DistanceX", l2, 1, l2, 2, 2 * w),
        "Height": C("DistanceY", l2, 1, l5, 1, 2 * h),
    }
    for name, con in named.items():
        sketch.renameConstraint(sketch.addConstraint(con), name)

    sketch.addConstraint(
        [
            # Ball center on the mid-height line
            C("PointOnObject", ball, 3, -1),
            # Ball arcs follow the ball circle
            C("Coincident", a_in, 3, ball, 3),
            C("Coincident", a_out, 3, ball, 3),
            C("Equal", a_in, ball),
            C("Equal", a_out, ball),
            # Closed outline
            C("Coincident", l1, 2, l2, 1),
            C("Coincident", l2, 2, l3, 1),
            C("Coincident", l4, 2, l5, 1),
            C("Coincident", l5, 2, l6, 1),
            C("Coincident", a_in, 1, l4, 1),
            C("Coincident", a_in, 2, l1, 1),
            C("Coincident", a_out, 1, l3, 2),
            C("Coincident", a_out, 2, l6, 2),
            C("Vertical", l1),
            C("Vertical", l3),
            C("Vertical", l4),
            C("Vertical", l6),
            C("Horizontal", l2),
            C("Horizontal", l5),
            # Slot centered on the ball
            C("Equal", l2, l5),
            C("Vertical", l2, 1, l5, 1),
            C("Symmetric", l2, 1, l5, 2, ball, 3),
        ]
    )


def make_groove(body, params):
    """Groove the race profile around the bearing axis, on the datum's XZ plane."""
    v = values_of(params)
    p = params.Name
    sketch = body.newObject("Sketcher::SketchObject", "BearingSketch")
    attach(sketch, params, "ObjectXZ")
    draw_race_profile(sketch, v)
    for name, expr in (
        ("PitchRadius", "(%s.ID + %s.OD) / 4" % (p, p)),
        ("BallDiameter", p + ".BallDiameter"),
        ("SlotWidth", p + ".BallDiameter / 2"),
        ("Height", p + ".Height"),
    ):
        sketch.setExpression(".Constraints." + name, expr)

    groove = body.newObject("PartDesign::Groove", "BearingGroove")
    groove.Profile = sketch
    groove.ReferenceAxis = (sketch, ["V_Axis"])
    groove.Angle = 360.0
    sketch.Visibility = False
    return groove


def make_cage(doc, races, params):
    """Snap-in cage between the races, in its own Body that follows the bearing frame."""
    v = values_of(params)
    p = params.Name
    r_in, r_out, bottom, top = cage_profile(v)
    pocket_d = v["BallDiameter"] + v["PocketClearance"]

    body = doc.addObject("PartDesign::Body", "Cage")
    follow_bearing(body, races, params)

    # Cage ring cross-section on XZ: X radial, Y = bearing axis
    V = App.Vector
    C = Sketcher.Constraint
    ring = body.newObject("Sketcher::SketchObject", "CageSketch")
    attach(ring, origin_feature(body, "XZ_Plane"))
    pts = [V(r_in, bottom, 0), V(r_out, bottom, 0), V(r_out, top, 0), V(r_in, top, 0)]
    lines = [ring.addGeometry(Part.LineSegment(pts[i], pts[(i + 1) % 4])) for i in range(4)]
    ring.addConstraint(
        [C("Coincident", lines[i], 2, lines[(i + 1) % 4], 1) for i in range(4)]
        + [
            C("Horizontal", lines[0]),
            C("Horizontal", lines[2]),
            C("Vertical", lines[1]),
            C("Vertical", lines[3]),
        ]
    )
    # the expressions of cage_profile()
    design_top_expr = "(%s.BallDiameter * sqrt(3) / 4 - %s.CageTopOffset)" % (p, p)
    top_expr = "(%s.BallDiameter + %s.PocketClearance) / 2 - %s.PocketRise" % (p, p, p)
    for name, con, expr in (
        (
            "CageInner",
            C("DistanceX", -1, 1, lines[0], 1, r_in),
            "(%s.ID + %s.OD) / 4 - %s.CageThickness / 2" % (p, p, p),
        ),
        (
            "CageThickness",
            C("DistanceX", lines[0], 1, lines[0], 2, r_out - r_in),
            p + ".CageThickness",
        ),
        (
            "CageBottom",
            C("DistanceY", -1, 1, lines[0], 1, bottom),
            "-%s.Height / 2 + (%s) - %s" % (p, top_expr, design_top_expr),
        ),
        ("CageTop", C("DistanceY", -1, 1, lines[2], 1, top), top_expr),
    ):
        ring.renameConstraint(ring.addConstraint(con), name)
        ring.setExpression(".Constraints." + name, expr)

    rev = body.newObject("PartDesign::Revolution", "CageRing")
    rev.Profile = ring
    rev.ReferenceAxis = (ring, ["V_Axis"])
    rev.Angle = 360.0
    ring.Visibility = False

    # Ball pocket on YZ (normal = radial X), cut outward through the cage at +X
    pk = body.newObject("Sketcher::SketchObject", "PocketSketch")
    attach(pk, origin_feature(body, "YZ_Plane"))
    circle = pk.addGeometry(Part.Circle(V(0, 0, 0), V(0, 0, 1), pocket_d / 2))
    pk.addConstraint(C("Coincident", circle, 3, -1, 1))  # centered on the ball (seated cage)
    c = pk.addConstraint(C("Diameter", circle, pocket_d))
    pk.renameConstraint(c, "PocketDiameter")
    pk.setExpression(".Constraints.PocketDiameter", "%s.BallDiameter + %s.PocketClearance" % (p, p))

    pocket = body.newObject("PartDesign::Pocket", "BallPocket")
    pocket.Profile = pk
    pocket.Type = "ThroughAll"
    pocket.Reversed = True  # cut toward +X only, so a single pocket per ball
    pk.Visibility = False

    pattern = body.newObject("PartDesign::PolarPattern", "BallPockets")
    pattern.Originals = [pocket]
    pattern.Axis = (origin_feature(body, "Z_Axis"), [""])
    pattern.Angle = 360.0
    pattern.setExpression("Occurrences", p + ".NumBalls")
    body.Tip = pattern  # patterns don't become the tip on their own
    return body


def follow_bearing(body, races, params):
    """Make `body` follow the bearing frame (races Body placement x datum placement).

    The body goes in the same container (e.g. App::Part) as the races, since the
    placements are relative to it.
    """
    container = races.getParentGeoFeatureGroup()
    if container:
        container.addObject(body)
    body.Placement = races.Placement.multiply(params.Placement)
    body.setExpression("Placement", "%s.Placement * %s.Placement" % (races.Name, params.Name))


def make_balls(doc, races, params):
    """One sphere at the pitch diameter, mid-height, patterned NumBalls times, in its own Body."""
    v = values_of(params)
    p = params.Name
    body = doc.addObject("PartDesign::Body", "Balls")
    follow_bearing(body, races, params)

    ball = body.newObject("PartDesign::AdditiveSphere", "Ball")
    attach(ball, origin_feature(body, "XY_Plane"))
    ball.Radius = v["BallDiameter"] / 2
    ball.setExpression("Radius", p + ".BallDiameter / 2")
    ball.AttachmentOffset = App.Placement(App.Vector((v["ID"] + v["OD"]) / 4, 0, 0), App.Rotation())
    ball.setExpression(".AttachmentOffset.Base.x", "(%s.ID + %s.OD) / 4" % (p, p))

    pattern = body.newObject("PartDesign::PolarPattern", "BallPattern")
    pattern.Originals = [ball]
    pattern.Axis = (origin_feature(body, "Z_Axis"), [""])
    pattern.Angle = 360.0
    pattern.setExpression("Occurrences", p + ".NumBalls")
    body.Tip = pattern  # patterns don't become the tip on their own
    return body


def check(doc, *features):
    doc.recompute()
    for f in features:
        if not f.isValid():
            raise RuntimeError("%s failed: %s" % (f.Label, f.getStatusString()))


def groove_body(feature, edge, values, cage=True, balls=False):
    """Groove the body the edge belongs to, so the body itself becomes the races.

    The edge's diameter (ID on a bore, OD on an outer surface) replaces the one in
    `values`; the other diameter and Height in `values` set where the groove goes,
    centered on the selected cylinder. `edge` must be in global coordinates.
    """
    doc = feature.Document
    body = find_body(feature)
    if body is None:
        raise ValueError("To groove the selected body, the edge must belong to a PartDesign Body.")
    m = measure_body(body, edge)
    key = "ID" if m["is_inner"] else "OD"
    values = dict(values, **{key: m["dia"]})
    validate(values, cage, balls)

    # Bearing frame (on the axis, mid-way along the selected cylinder), in body coordinates
    frame = global_placement(body).inverse().multiply(frame_placement(edge, m["mid"]))
    params = make_params(body, values, frame, readonly=(key,))

    feats = [make_groove(body, params)]
    if cage:
        feats.append(make_cage(doc, body, params).Tip)
    if balls:
        feats.append(make_balls(doc, body, params).Tip)
    check(doc, *feats)
    return params


def bearing_label(values):
    """Part label with the bearing's size, OD x ID x Height, e.g. "Bearing 32x20x8".

    A catalog size is named too: "Bearing 608 (22x8x7)".
    """

    def num(x):
        return ("%.2f" % x).rstrip("0").rstrip(".")

    size = "%sx%sx%s" % (num(values["OD"]), num(values["ID"]), num(values["Height"]))
    name = catalog_match(values)
    return "Bearing %s (%s)" % (name, size) if name else "Bearing " + size


def create_races(doc, placement, values, reverse=False, cage=True, balls=False):
    """Build a parametric ring blank, then groove it into two races.

    `placement` is the global frame of the bearing: Z = axis, origin = one face center.
    The ring is padded along +Z (or -Z when `reverse`). The races, cage and balls bodies
    go into one App::Part (labelled by bearing_label()) that carries this placement.
    """
    validate(values, cage, balls)
    part = doc.addObject("App::Part", "Bearing")
    part.Label = bearing_label(values)
    part.Placement = placement
    body = doc.addObject("PartDesign::Body", "Races")
    part.addObject(body)  # the cage and balls bodies join it (follow_bearing)

    # Datum at mid-height; it follows Height so the frame stays centered
    params = make_params(
        body,
        values,
        App.Placement(
            App.Vector(0, 0, (-0.5 if reverse else 0.5) * values["Height"]),
            App.Rotation(),
        ),
    )
    params.setExpression(".Placement.Base.z", "%sHeight / 2" % ("-" if reverse else ""))
    p = params.Name

    # Ring blank: two circles padded to the bearing height
    ring = body.newObject("Sketcher::SketchObject", "RingSketch")
    attach(ring, origin_feature(body, "XY_Plane"))
    for name in ("ID", "OD"):
        g = ring.addGeometry(Part.Circle(App.Vector(), App.Vector(0, 0, 1), values[name] / 2))
        ring.addConstraint(Sketcher.Constraint("Coincident", g, 3, -1, 1))
        ring.renameConstraint(
            ring.addConstraint(Sketcher.Constraint("Diameter", g, values[name])), name
        )
        ring.setExpression(".Constraints." + name, "%s.%s" % (p, name))

    pad = body.newObject("PartDesign::Pad", "Blank")
    pad.Profile = ring
    pad.Reversed = reverse
    pad.setExpression("Length", p + ".Height")
    ring.Visibility = False

    feats = [make_groove(body, params)]
    if cage:
        feats.append(make_cage(doc, body, params).Tip)
    if balls:
        feats.append(make_balls(doc, body, params).Tip)
    add_check(doc, params, part, cage, balls)
    check(doc, *feats)
    return params


# ---------------------------------------------------------------- preview


def preview_shapes(v, cage=True):
    """Light Part shapes of the bearing, in the bearing frame (origin on the axis at
    mid-height, Z = axis), for the task panel preview: [(role, shape), ...].

    Same groove_profile() and cage_profile() as the PartDesign features, but revolved
    directly from 2D profiles (no booleans, no cage pockets) so it is fast enough to
    rebuild on every edit. Returns [] when the values can't be drawn.
    """
    id_, od, height, ball = v["ID"], v["OD"], v["Height"], v["BallDiameter"]
    if not (0 < id_ < od and height > 0 and 0 < ball < min((od - id_) / 2, height)):
        return []
    g = groove_profile(v)
    rp, rb, w, h, yi = g["rp"], g["rb"], g["w"], g["h"], g["yi"]
    inner = [
        ("p", id_ / 2, -h, 0),
        ("p", rp - w, -h, 0),
        ("p", rp - w, -yi, 0),
        ("a", rp - rb, 0),  # ball arc into the inner race
        ("p", rp - w, yi, 0),
        ("p", rp - w, h, 0),
        ("p", id_ / 2, h, 0),
    ]
    outer = [
        ("p", rp + w, -h, 0),
        ("p", od / 2, -h, 0),
        ("p", od / 2, h, 0),
        ("p", rp + w, h, 0),
        ("p", rp + w, yi, 0),
        ("a", rp + rb, 0),  # ball arc into the outer race
        ("p", rp + w, -yi, 0),
    ]
    try:
        shapes = [("inner race", revolve(inner)), ("outer race", revolve(outer))]
        n = max(1, int(v.get("NumBalls", DEFAULT_NUM_BALLS)))
        sphere = Part.makeSphere(rb, App.Vector(rp, 0, 0))
        for k in range(n):
            s = sphere.copy()
            s.rotate(App.Vector(), App.Vector(0, 0, 1), 360.0 * k / n)
            shapes.append(("ball", s))
        if cage and 0 < v["CageThickness"] <= rb + 1e-9:
            r_in, r_out, bottom, top = cage_profile(v)
            if top > bottom:
                ring = [(r_in, bottom), (r_out, bottom), (r_out, top), (r_in, top)]
                shapes.append(("cage", revolve([("p", x, z, 0) for x, z in ring])))
    except Part.OCCError:
        return []
    return shapes


def preview_frame(mode, edge, measured, height, reverse=False, bearing=None):
    """Global placement of the bearing frame (origin on the axis at mid-height) that
    groove_body() / create_races() / convert_bearing() would use."""
    if bearing is not None:  # the standard bearing occupies z in [-B, 0]
        return global_placement(bearing).multiply(
            App.Placement(App.Vector(0, 0, -height / 2), App.Rotation())
        )
    if mode == GROOVE:
        return frame_placement(edge, measured["mid"])
    face = frame_placement(edge) if edge is not None else App.Placement()
    return face.multiply(
        App.Placement(App.Vector(0, 0, (-0.5 if reverse else 0.5) * height), App.Rotation())
    )


def convert_bearing(bearing, values, cage=True, balls=False):
    """Build a printable bearing in place of a standard Bearing object, and hide it.

    The standard bearing occupies z in [-B, 0] of its placement, so the races are padded
    along -Z from its frame. ID, OD and Height come from the bearing; `values` gives the
    rest (ball size and count, cage options; CAGE_DEFAULTS for any cage option missing).
    """
    v = dict(CAGE_DEFAULTS, **values)
    v.update(
        ID=bearing.BoreDiameter.Value, OD=bearing.OuterDiameter.Value, Height=bearing.Width.Value
    )
    params = create_races(bearing.Document, global_placement(bearing), v, True, cage, balls)
    bearing.Visibility = False
    return params


# ---------------------------------------------------------------- check object


def add_check(doc, params, part, cage, balls):
    """PrintableBearing object in the bearing's Part: keeps the Part label in step with
    the size and validates later edits of BearingParameters.

    Only for "Create races". Grooving a selected body adds none: there is no bearing
    Part to name, and the user's own body and containers are left alone.
    """
    obj = doc.addObject("App::FeaturePython", "PrintableBearing")
    part.addObject(obj)
    PrintableBearingCheck(obj, params, True, cage, balls)
    if App.GuiUp:
        ViewProviderPrintableBearing(obj.ViewObject)
    return obj


class PrintableBearingCheck:
    """Watches BearingParameters: reports invalid values and keeps the Part label current.

    The geometry is plain PartDesign and does not depend on this object, so a document
    opened without the workbench still recomputes (only these checks are missing).
    """

    def __init__(self, obj, params, follow_label, cage, balls):
        obj.Proxy = self
        obj.addProperty(
            "App::PropertyLinkGlobal",
            "Parameters",
            "Printable bearing",
            "BearingParameters datum this bearing is built from",
        )
        obj.addProperty(
            "App::PropertyBool",
            "FollowPartLabel",
            "Printable bearing",
            "Keep the label of the App::Part this object is in equal to the bearing size",
        )
        obj.addProperty("App::PropertyBool", "HasCage", "Printable bearing", "A cage was built")
        obj.addProperty("App::PropertyBool", "HasBalls", "Printable bearing", "Balls were built")
        obj.addProperty(
            "App::PropertyString",
            "Designation",
            "Printable bearing",
            "Catalog bearing with the same ID x OD x Height, if any",
        )
        for name in ("Parameters", "HasCage", "HasBalls", "Designation"):
            obj.setEditorMode(name, 1)
        obj.Parameters = params
        obj.FollowPartLabel = follow_label
        obj.HasCage = cage
        obj.HasBalls = balls
        part = obj.getParentGeoFeatureGroup()
        self.auto_label = part.Label if part else None

    def execute(self, obj):
        # Side effect: this sets the label of another object (the Part it sits in).
        # Generally execute() should only change its own object, since writing others can
        # retrigger recomputes. It is accepted here because a label change doesn't touch
        # the Part or anything depending on it, and there is nowhere else to hook in:
        # BearingParameters is a plain datum, so it has no onChanged() of ours. Don't copy
        # this pattern for properties that do affect geometry.
        params = obj.Parameters
        if params is None:
            return
        v = values_of(params)
        obj.Designation = catalog_match(v) or ""
        # The Part is found through the tree, not a link: linking to the container this
        # object sits in would make a dependency cycle
        part = obj.getParentGeoFeatureGroup()
        if obj.FollowPartLabel and part is not None and part.TypeId == "App::Part":
            target = bearing_label(v)
            auto = getattr(self, "auto_label", None)
            # follow the size until the user renames the Part
            if part.Label in (auto, part.Name) and part.Label != target:
                part.Label = target
                self.auto_label = part.Label
        validate(v, obj.HasCage, obj.HasBalls)  # raises: the object shows the error

    def dumps(self):
        return {"auto_label": getattr(self, "auto_label", None)}

    def loads(self, state):
        self.auto_label = state.get("auto_label") if isinstance(state, dict) else None


class ViewProviderPrintableBearing:
    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        self.Object = vobj.Object

    def getIcon(self):
        from BRutils import icon

        return icon("PrintableBearing.svg")

    def dumps(self):
        return None

    def loads(self, state):
        return None
