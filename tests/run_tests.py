# SPDX-License-Identifier: LGPL-2.1-or-later
"""Headless test suite. Run with:

    /Volumes/Silo/brew/FreeCAD.app/Contents/Resources/bin/freecadcmd tests/run_tests.py

Prints one line per failure and a final "RESULT: ..." line.
"""

import os
import sys
import tempfile
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import FreeCAD  # noqa: E402
import Part  # noqa: E402

import BearingBase  # noqa: E402
import BearingData as BD  # noqa: E402
import BearingGeometry as BG  # noqa: E402

V = FreeCAD.Vector
TOL = 1e-3
failures = []
checks = 0


def check(cond, msg):
    global checks
    checks += 1
    if not cond:
        failures.append(msg)
        print("FAIL:", msg)


def close(a, b, tol=TOL):
    return abs(a - b) <= tol


def tight_bb(shape):
    return shape.optimalBoundingBox(False, False)


def test_tables():
    for series in BD.SERIES:
        rows = BD.load_table(series)
        check(len(rows) > 0, "%s: empty table" % series)
        names = [r.name for r in rows]
        check(len(names) == len(set(names)), "%s: duplicate designations" % series)
        check(BD.SERIES[series][2] in names, "%s: default designation missing" % series)
        for r in rows:
            check(0 < r.d < r.D and r.B > 0, "%s %s: bad boundary dims" % (series, r.name))
            if r.has_flange:
                check(r.D1 > r.D and r.C1 < r.B, "%s %s: bad flange dims" % (series, r.name))
            if r.B_shielded is not None:
                check(r.B_shielded >= r.B, "%s %s: shielded width < open width" % (series, r.name))


def test_internals():
    i608 = BG.Internals(8, 22, 7)
    check(i608.Z == 7 and close(i608.Dw, 4.0), "608 internals: Z=%d Dw=%g" % (i608.Z, i608.Dw))
    i6204 = BG.Internals(20, 47, 14)
    check(i6204.Z == 8 and close(i6204.Dw, 8.0), "6204 internals: Z=%d Dw=%g" % (i6204.Z, i6204.Dw))


def expected_solids(closure, detail):
    if detail == "Envelope":
        return 1
    top, bottom = BG._closure_sides(closure)
    return 2 + int(top) + int(bottom)  # plus balls (and cage), added by caller


def test_all_shapes():
    for series in BD.SERIES:
        rows = BD.load_table(series)
        # Detailed (cage boolean) only on a sample: smallest, a mid size, largest
        sample = {rows[0].name, rows[len(rows) // 2].name, rows[-1].name}
        for row in rows:
            ins = BG.Internals(row.d, row.D, row.B)
            for flanged in ([False, True] if row.has_flange else [False]):
                for closure in ("Open", "ZZ", "2RS", "Z"):
                    for detail in BG.DETAIL_LEVELS:
                        if detail == "Detailed" and row.name not in sample:
                            continue
                        tag = "%s %s %s flanged=%s %s" % (series, row.name, closure, flanged, detail)
                        try:
                            shape, colors = BG.build(row, closure, flanged, detail)
                        except Exception as e:
                            check(False, "%s: build raised %r" % (tag, e))
                            continue
                        check(shape.isValid(), tag + ": invalid shape")
                        check(len(colors) == len(shape.Faces), tag + ": color count mismatch")
                        bb = tight_bb(shape)
                        od = row.D1 if flanged else row.D
                        B = row.width(closure)
                        check(close(bb.XLength, od, 0.01) and close(bb.YLength, od, 0.01),
                              "%s: diameter %.3f != %.3f" % (tag, bb.XLength, od))
                        check(close(bb.ZMax, 0, 0.01) and close(bb.ZMin, -B, 0.01),
                              "%s: z range [%.3f, %.3f] != [-%g, 0]" % (tag, bb.ZMin, bb.ZMax, B))
                        probes = [V(row.d / 2 * 0.99, 0, -B / 2), V(0, -row.d / 2 * 0.99, -0.01 * B),
                                  V(0, 0, -B / 2)]
                        check(not any(shape.isInside(p, 1e-7, True) for p in probes), tag + ": bore obstructed")
                        check(shape.isInside(V(row.D / 2 * 0.99, 0, -B / 2), 1e-7, True),
                              tag + ": outer ring missing")
                        n = expected_solids(closure, detail)
                        if detail != "Envelope":
                            n += ins.Z
                        solids = len(shape.Solids)
                        if detail == "Detailed":
                            check(solids >= n + 1, "%s: %d solids, expected >= %d" % (tag, solids, n + 1))
                        else:
                            check(solids == n, "%s: %d solids, expected %d" % (tag, solids, n))


def test_no_overlap():
    for series, name in (("60", "608"), ("62", "6204"), ("68", "688"), ("MR", "MR63"), ("69", "6920")):
        row = BD.get_row(series, name)
        shape, _ = BG.build(row, "2RS", False, "Detailed")
        solids = shape.Solids
        worst = 0.0
        for i in range(len(solids)):
            for j in range(i + 1, len(solids)):
                if not solids[i].BoundBox.intersect(solids[j].BoundBox):
                    continue
                worst = max(worst, solids[i].common(solids[j]).Volume)
        ball_vol = 3.14159 / 6 * BG.Internals(row.d, row.D, row.B).Dw ** 3
        check(worst < 1e-4 * ball_vol, "%s: parts overlap, worst common volume %.2e" % (name, worst))


def plate_with_hole(doc, dia, thickness=10.0):
    box = Part.makeBox(40, 40, thickness, V(-20, -20, 0))
    hole = Part.makeCylinder(dia / 2, thickness + 2, V(0, 0, -1))
    obj = doc.addObject("Part::Feature", "Plate")
    obj.Shape = box.cut(hole)
    return obj


def find_circle(obj, radius, z):
    for i, e in enumerate(obj.Shape.Edges, 1):
        if BearingBase._is_circular_edge(e) and close(e.Curve.Radius, radius) and close(e.Curve.Center.z, z):
            return "Edge%d" % i
    raise AssertionError("edge not found")


def test_feature_python():
    doc = FreeCAD.newDocument("BearingTest")
    try:
        # housing match: 22 mm hole -> 608 sits inside the hole, flush with the top face
        plate = plate_with_hole(doc, 22.0)
        doc.recompute()
        b = BearingBase.make_bearing("60", attach_to=(plate, [find_circle(plate, 11, 10)]), doc=doc)
        check(b.MatchTo == "Housing", "hole edge should be matched as Housing, got " + b.MatchTo)
        check(b.FullDesignation == "608", "auto designation for 22 mm hole: " + b.FullDesignation)
        check(b.Label == "608", "auto label: " + b.Label)
        bb = tight_bb(b.Shape)
        check(close(bb.ZMax, 10, 0.01) and close(bb.ZMin, 3, 0.01),
              "housing placement z range [%.3f, %.3f]" % (bb.ZMin, bb.ZMax))
        check(b.Shape.common(plate.Shape).Volume < 1e-3, "bearing intersects the plate")

        b.Invert = True
        doc.recompute()
        bb = tight_bb(b.Shape)
        check(close(bb.ZMin, 10, 0.01) and close(bb.ZMax, 17, 0.01),
              "inverted placement z range [%.3f, %.3f]" % (bb.ZMin, bb.ZMax))
        b.Invert = False
        b.Offset = -1.0
        b.Closure = "2RS"
        doc.recompute()
        bb = tight_bb(b.Shape)
        check(close(bb.ZMax, 9, 0.01), "offset placement zmax %.3f" % bb.ZMax)
        check(b.Label == "608-2RS", "label should follow closure: " + b.Label)

        # shaft match: 8 mm shaft end -> 608 slides onto the shaft
        shaft = doc.addObject("Part::Feature", "Shaft")
        shaft.Shape = Part.makeCylinder(4, 30, V(50, 0, 0))
        doc.recompute()
        s = BearingBase.make_bearing("60", attach_to=(shaft, [find_circle(shaft, 4, 30)]), doc=doc)
        check(s.MatchTo == "Shaft", "shaft edge should be matched as Shaft, got " + s.MatchTo)
        check(s.FullDesignation == "608", "auto designation for 8 mm shaft: " + s.FullDesignation)
        bb = tight_bb(s.Shape)
        check(close(bb.ZMax, 30, 0.01) and close(bb.ZMin, 23, 0.01),
              "shaft placement z range [%.3f, %.3f]" % (bb.ZMin, bb.ZMax))

        # series change keeps valid designation list; flanged miniature
        f = BearingBase.make_bearing("68", "688", doc=doc, Flanged=True, Closure="ZZ")
        check(f.FullDesignation == "F688ZZ", "flanged designation: " + f.FullDesignation)
        check(close(tight_bb(f.Shape).XLength, 18, 0.01), "flange diameter")
        f.Series = "MR"
        f.Designation = "MR105"
        doc.recompute()
        check(f.FullDesignation == "MF105ZZ", "MR flanged designation: " + f.FullDesignation)
        check(close(f.Width.Value, 4.0), "MR105ZZ shielded width %.2f" % f.Width.Value)

        # save / reopen / recompute
        bname = b.Name
        path = os.path.join(tempfile.mkdtemp(), "bearings.FCStd")
        doc.saveAs(path)
        FreeCAD.closeDocument(doc.Name)
        doc = FreeCAD.openDocument(path)
        objs = [o for o in doc.Objects if hasattr(o, "FullDesignation")]
        check(len(objs) == 3, "reopened document has %d bearings" % len(objs))
        for o in objs:
            o.touch()
        doc.recompute()
        for o in objs:
            check(o.Shape.isValid() and "Invalid" not in o.State, "reopened %s failed to recompute" % o.Label)
        check(doc.getObject(bname).Designation == "Auto", "Designation not persisted")
    finally:
        FreeCAD.closeDocument(doc.Name)


def test_labels():
    """Auto labels follow the designation until the user renames the object."""
    doc = FreeCAD.newDocument("BearingLabels")
    try:
        # after a GUI delete FreeCAD gives new objects a label that differs from Name
        obj = doc.addObject("Part::FeaturePython", "Bearing")
        obj.Label = "Bearing002"
        BearingBase.BearingObject(obj, "60")
        doc.recompute()
        check(obj.Label == "608", "label with initial Label != Name: " + obj.Label)

        # same designation twice: FreeCAD may make the label unique; it must keep following
        twin = BearingBase.make_bearing("60", "608", doc=doc)
        twin.Designation = "609"
        doc.recompute()
        check(twin.Label == "609", "duplicate-designation label should follow change: " + twin.Label)

        # a user rename sticks
        obj.Label = "Spindle bearing"
        obj.Closure = "ZZ"
        doc.recompute()
        check(obj.Label == "Spindle bearing", "user label overwritten: " + obj.Label)

        # still following after save / reopen
        auto = BearingBase.make_bearing("68", "688", doc=doc)
        name = auto.Name
        path = os.path.join(tempfile.mkdtemp(), "labels.FCStd")
        doc.saveAs(path)
        FreeCAD.closeDocument(doc.Name)
        doc = FreeCAD.openDocument(path)
        auto = doc.getObject(name)
        auto.Closure = "2RS"
        doc.recompute()
        check(auto.Label == "688-2RS", "label after reopen: " + auto.Label)
        check(doc.getObject("Bearing").Label == "Spindle bearing",
              "user label lost after reopen")

        # a label left stuck by the original bug ("Bearing017", auto_label = designation)
        stuck = BearingBase.make_bearing("62", "625", doc=doc)
        stuck.Label = "Bearing017"  # differs from its Name
        stuck.Proxy.auto_label = stuck.Proxy.auto_target = "625"
        stuck.touch()
        doc.recompute()
        check(stuck.Label == "625", "stuck default label not repaired: " + stuck.Label)
    finally:
        FreeCAD.closeDocument(doc.Name)


def test_search():
    cases = {"608": ("608", None, False), "F688-2RS": ("688", "2RS", True),
             "MF105ZZ": ("MR105", "ZZ", True), "6204-2RS1": ("6204", "2RS", False),
             "6204-2Z": ("6204", "ZZ", False), "618/8": ("688", None, False), "mr63": ("MR63", None, False)}
    for text, want in cases.items():
        got = BD.parse_designation(text)
        check(got == want, "parse_designation(%r) = %r, want %r" % (text, got, want))
    names = lambda hits: [r.name for _, r in hits]  # noqa: E731
    check(names(BD.search(name="608")) == ["608"], "search name 608")
    check(set(names(BD.search(name="62"))) == set(BD.designations("62")), "search name prefix 62")
    check("608" in names(BD.search(d=8)) and "688" in names(BD.search(d=8)), "search by ID 8")
    check(set(names(BD.search(D=22))) == {"636", "627", "608", "6900"}, "search by OD 22")
    check("608" in names(BD.search(B=7)) and all(r.B == 7 or r.B_shielded == 7 for _, r in BD.search(B=7)),
          "search by height 7")
    check("684" in names(BD.search(d=4, B=4)), "height matches shielded width (684ZZ = 4)")
    check(names(BD.search(name="8x22x7")) == ["608"], "search by size text")
    check(names(BD.search(name="F688-2RS")) == ["688"], "search flanged designation")
    check("6801" in names(BD.search(D=22, tol=1)), "search tolerance")
    check(BD.search(name="999") == [], "search with no match")


def test_nested_attach():
    """Edges inside containers with their own placement resolve to global coordinates."""
    import BRselection as BRS

    doc = FreeCAD.newDocument("BearingNested")
    try:
        part = doc.addObject("App::Part", "Part")
        part.Placement = FreeCAD.Placement(V(100, 0, 0), FreeCAD.Rotation(V(0, 0, 1), 90))
        body = doc.addObject("PartDesign::Body", "Body")
        part.addObject(body)
        body.Placement = FreeCAD.Placement(V(0, 50, 0), FreeCAD.Rotation())
        box = body.newObject("PartDesign::AdditiveBox", "Box")
        box.Length = box.Width = 40
        box.Height = 10
        box.AttachmentOffset = FreeCAD.Placement(V(-20, -20, 0), FreeCAD.Rotation())
        hole = body.newObject("PartDesign::SubtractiveCylinder", "Hole")
        hole.Radius = 11
        hole.Height = 10
        doc.recompute()
        edge = find_circle(hole, 11, 10)
        # hole center in Body: (0, 0); Body at (0, 50) in Part; Part at (100, 0) rotated 90°
        want = part.Placement.multVec(body.Placement.multVec(V(0, 0, 10)))
        for label, target in (("path from root", (part, ["Body.Hole." + edge])), ("feature", (hole, [edge]))):
            e, _ = BRS.resolve_edge(target[0], target[1][0])
            check(e is not None and (BRS.center_of(e.Curve) - want).Length < 1e-6,
                  "%s: edge center %s, want %s" % (label, e and BRS.center_of(e.Curve), want))
            b = BearingBase.make_bearing("60", attach_to=target, doc=doc)
            check(b.MatchTo == "Housing" and b.FullDesignation == "608", "%s: auto size %s %s" % (label, b.MatchTo, b.FullDesignation))
            bb = tight_bb(b.Shape)
            center = V((bb.XMin + bb.XMax) / 2, (bb.YMin + bb.YMax) / 2, bb.ZMax)
            check((center - want).Length < 0.01, "%s: bearing top center %s, want %s" % (label, center, want))
            check(close(bb.ZMin, want.z - 7, 0.01), "%s: bearing goes into the hole" % label)
    finally:
        FreeCAD.closeDocument(doc.Name)


def test_printable():
    import PrintableBearing as PB

    v = PB.fit_values(dict(PB.CAGE_DEFAULTS, ID=5, OD=16, Height=5, BallDiameter=4, NumBalls=10))
    check(v["NumBalls"] == PB.max_balls(5, 16, 4, PB.CAGE_DEFAULTS["PocketClearance"]) and v["NumBalls"] < 10,
          "fit_values lowers the ball count to what fits (625: %d)" % v["NumBalls"])
    check(PB.catalog_match({"ID": 8, "OD": 22, "Height": 7}) == "608", "catalog_match 608")
    check(PB.catalog_match({"ID": 8, "OD": 16, "Height": 5}) == "688", "catalog_match shielded width (688ZZ)")
    small = PB.fit_values(dict(PB.CAGE_DEFAULTS, ID=8, OD=16, Height=5, BallDiameter=4, NumBalls=10), reset=True)
    check(small["BallDiameter"] in BG.STANDARD_BALLS, "fallback ball is a standard size: %g" % small["BallDiameter"])

    doc = FreeCAD.newDocument("BearingPrintable")
    try:
        params = PB.create_races(doc, FreeCAD.Placement(), dict(PB.CAGE_DEFAULTS, ID=8, OD=22, Height=7,
                                                                  BallDiameter=4, NumBalls=7), False, True, True)
        races = params.getParentGeoFeatureGroup()
        part = races.getParentGeoFeatureGroup()
        bodies = {o.Label: o for o in part.Group if o.TypeId == "PartDesign::Body"}
        check(len(races.Shape.Solids) == 2, "printable races: %d solids" % len(races.Shape.Solids))
        check(len(bodies["Cage"].Shape.Solids) == 1, "printable cage")
        check(len(bodies["Balls"].Shape.Solids) == 7, "printable balls")
        check(part.Label == "Bearing 608 (22x8x7)", "printable label: " + part.Label)
        chk = [o for o in part.Group if o.Name.startswith("PrintableBearing")][0]
        check(chk.Designation == "608" and "Invalid" not in chk.State, "check object ok")

        params.Height = 8
        doc.recompute()
        check(part.Label == "Bearing 22x8x8" and chk.Designation == "", "label follows size: " + part.Label)
        params.NumBalls = 40
        doc.recompute()
        check("Invalid" in chk.State, "too many balls should flag the check object")
        params.NumBalls = 7
        doc.recompute()
        check("Invalid" not in chk.State, "fixed values should clear the error")
        check(not any("Invalid" in o.State for o in doc.Objects), "no invalid objects")
        part.Label = "Spindle"
        params.Height = 7
        doc.recompute()
        check(part.Label == "Spindle", "user Part label kept")

        std = BearingBase.make_bearing("62", "625", doc=doc)
        std.Placement = FreeCAD.Placement(V(60, 0, 0), FreeCAD.Rotation())
        doc.recompute()
        p2 = PB.convert_bearing(std, True, False)
        part2 = p2.getParentGeoFeatureGroup().getParentGeoFeatureGroup()
        bb = p2.getParentGeoFeatureGroup().Shape.BoundBox
        check(part2.Label == "Bearing 625 (16x5x5)" and not std.Visibility, "convert: " + part2.Label)
        check(close(part2.Placement.Base.x, 60) and close(bb.ZMin, -5, 0.01) and close(bb.ZMax, 0, 0.01),
              "converted races sit where the standard bearing was")

        body = doc.addObject("PartDesign::Body", "Hub")
        disc = body.newObject("PartDesign::AdditiveCylinder", "Disc")
        disc.Radius, disc.Height = 20, 8
        bore = body.newObject("PartDesign::SubtractiveCylinder", "Bore")
        bore.Radius, bore.Height = 5, 8
        doc.recompute()
        edge = body.Shape.getElement(find_circle(body, 5, 8))
        PB.groove_body(bore, edge, dict(PB.CAGE_DEFAULTS, ID=0, OD=24, Height=8, BallDiameter=4,
                                        NumBalls=10), True, False)
        check(len(body.Shape.Solids) == 2, "grooved body splits into 2 races")

        name = part.Name
        path = os.path.join(tempfile.mkdtemp(), "printable.FCStd")
        doc.saveAs(path)
        FreeCAD.closeDocument(doc.Name)
        doc = FreeCAD.openDocument(path)
        part = doc.getObject(name)
        part.Label = "Bearing 22x8x7"  # back to automatic
        chk = [o for o in part.Group if o.Name.startswith("PrintableBearing")][0]
        chk.Proxy.auto_label = part.Label
        params = chk.Parameters
        params.OD = 24
        doc.recompute()
        check(part.Label == "Bearing 24x8x7", "label follows after reopen: " + part.Label)
        check(not any("Invalid" in o.State for o in doc.Objects), "reopened printable document recomputes")
    finally:
        FreeCAD.closeDocument(doc.Name)


for test in (test_tables, test_internals, test_all_shapes, test_no_overlap, test_feature_python, test_labels,
             test_search, test_nested_attach, test_printable):
    try:
        test()
    except Exception:
        failures.append(test.__name__ + " raised")
        traceback.print_exc()

print("RESULT: %s (%d checks, %d failures)" % ("PASS" if not failures else "FAIL", checks, len(failures)))
