# SPDX-License-Identifier: GPL-3.0-or-later
"""3D-printable bearings (PrintableBearing): values, preview, builders, check object."""

import unittest

import FreeCAD
import Part

import BearingBase
import PrintableBearing as PB
from testutil import DocumentTest, V, close, find_circle, is_invalid, tight_bb

V608 = dict(PB.CAGE_DEFAULTS, ID=8, OD=22, Height=7, BallDiameter=4, NumBalls=7)


class Values(unittest.TestCase):
    def test_catalog_match(self):
        self.assertEqual(PB.catalog_match({"ID": 8, "OD": 22, "Height": 7}), "608")
        self.assertEqual(
            PB.catalog_match({"ID": 8, "OD": 16, "Height": 5}), "688", "shielded width (688ZZ)"
        )

    def test_catalog_has_ball_bearings_only(self):
        names = [r[0] for r in PB.catalog_rows()]
        self.assertIn("R188", names, "inch sizes are offered")
        self.assertFalse([n for n in names if n.startswith("LM")], "no linear bushings")
        self.assertIsNone(
            PB.catalog_match({"ID": 8, "OD": 15, "Height": 24}), "LM8UU is not a match"
        )

    def test_other_diameter(self):
        self.assertEqual(PB.other_diameter(30, True), 45, "ID 30 -> OD 45")
        self.assertEqual(PB.other_diameter(22, False), 7, "OD 22 -> ID 7")
        self.assertEqual(PB.other_diameter(10, False), 5, "OD 10 -> ID 5 (half, no negative bore)")

    def test_defaults(self):
        self.assertEqual(PB.DEFAULT_HEIGHT, 8.0)

    def test_validate(self):
        PB.validate(V608, cage=True, balls=True)
        n = PB.max_balls(8, 22, 4, PB.CAGE_DEFAULTS["PocketClearance"])
        with self.assertRaisesRegex(ValueError, "between 1 and %d" % n):
            PB.validate(dict(V608, NumBalls=n + 1), cage=True)
        with self.assertRaisesRegex(ValueError, "ring wall"):
            PB.validate(dict(V608, BallDiameter=8))


class Preview(unittest.TestCase):
    def setUp(self):
        self.shapes = PB.preview_shapes(V608)

    def test_roles(self):
        roles = [r for r, _ in self.shapes]
        self.assertEqual(roles.count("ball"), 7)
        self.assertTrue({"inner race", "outer race", "cage"} <= set(roles), roles)
        self.assertTrue(all(sh.isValid() for _, sh in self.shapes))

    def test_outer_race_size(self):
        obb = tight_bb(dict(self.shapes)["outer race"])
        self.assertTrue(
            close(obb.XLength, 22, 0.01)
            and close(obb.ZMin, -3.5, 0.01)
            and close(obb.ZMax, 3.5, 0.01)
        )

    def test_balls_clear_races(self):
        races = dict(self.shapes)
        balls = [sh for r, sh in self.shapes if r == "ball"]
        worst = max(races[k].common(b).Volume for k in ("inner race", "outer race") for b in balls)
        self.assertLess(worst, 1e-6)

    def test_impossible_values(self):
        self.assertEqual(PB.preview_shapes(dict(V608, BallDiameter=20)), [])

    def test_without_cage(self):
        self.assertNotIn("cage", [r for r, _ in PB.preview_shapes(V608, cage=False)])


class PreviewMatchesBuild(DocumentTest):
    """The preview and the PartDesign features compute the same geometry.

    Both use groove_profile() / cage_profile() for the initial geometry, but the built
    sketches are then driven by expressions that repeat those formulas. Editing the
    parameters checks the expressions too.
    """

    EDITED = {
        "ID": 10,
        "OD": 30,
        "Height": 9,
        "BallDiameter": 5,
        "NumBalls": 8,
        "CageThickness": 2.0,
        "CageTopOffset": 0.7,
        "PocketClearance": 0.4,
        "PocketRise": 0.8,
    }

    def setUp(self):
        super().setUp()
        self.params = PB.create_races(self.doc, FreeCAD.Placement(), V608, False, True, True)
        self.races = self.params.getParentGeoFeatureGroup()
        part = self.races.getParentGeoFeatureGroup()
        self.bodies = {o.Label: o for o in part.Group if o.TypeId == "PartDesign::Body"}

    def compare(self):
        v = PB.values_of(self.params)
        frame = PB.preview_frame(PB.CREATE, None, None, v["Height"])
        preview = {}
        for role, shape in PB.preview_shapes(v, cage=True):
            shape = shape.copy()
            shape.Placement = frame.multiply(shape.Placement)
            preview.setdefault(role, []).append(shape)
        cases = (
            ("races", self.races.Shape, preview["inner race"] + preview["outer race"]),
            ("balls", self.bodies["Balls"].Shape, preview["ball"]),
        )
        for name, built, shapes in cases:
            with self.subTest(part=name):
                want = Part.Compound(shapes)
                self.assertTrue(
                    close(built.Volume, want.Volume, 1e-4 * want.Volume),
                    "volume %.4f, preview %.4f" % (built.Volume, want.Volume),
                )
                self.assert_same_box(built, want)
        # the preview cage has no pockets, but the pockets leave the ring's extent alone
        with self.subTest(part="cage"):
            self.assert_same_box(self.bodies["Cage"].Shape, preview["cage"][0])

    def assert_same_box(self, built, want):
        a, b = tight_bb(built), tight_bb(want)
        for attr in ("XMin", "XMax", "YMin", "YMax", "ZMin", "ZMax"):
            self.assertTrue(
                close(getattr(a, attr), getattr(b, attr), 1e-3),
                "%s %.4f, preview %.4f" % (attr, getattr(a, attr), getattr(b, attr)),
            )

    def test_as_built(self):
        self.compare()

    def test_after_editing_parameters(self):
        for name, value in self.EDITED.items():
            setattr(self.params, name, value)
        self.doc.recompute()
        self.assertFalse([o.Label for o in self.doc.Objects if is_invalid(o)])
        self.compare()


class CreateRaces(DocumentTest):
    def setUp(self):
        super().setUp()
        self.params = PB.create_races(self.doc, FreeCAD.Placement(), V608, False, True, True)
        self.races = self.params.getParentGeoFeatureGroup()
        self.part = self.races.getParentGeoFeatureGroup()
        self.bodies = {o.Label: o for o in self.part.Group if o.TypeId == "PartDesign::Body"}
        self.chk = [o for o in self.part.Group if o.Name.startswith("PrintableBearing")][0]

    def test_bodies(self):
        self.assertEqual(len(self.races.Shape.Solids), 2)
        self.assertEqual(len(self.bodies["Cage"].Shape.Solids), 1)
        self.assertEqual(len(self.bodies["Balls"].Shape.Solids), 7)
        self.assertEqual(self.part.Label, "Bearing 608 (22x8x7)")
        self.assertEqual(self.chk.Designation, "608")
        self.assertFalse(is_invalid(self.chk))

    def test_label_follows_size(self):
        self.params.Height = 8
        self.doc.recompute()
        self.assertEqual(self.part.Label, "Bearing 22x8x8")
        self.assertEqual(self.chk.Designation, "")

    def test_same_size_gets_a_counter(self):
        """A second printable of the same size is "..._001": setting the taken label would
        make FreeCAD bump the trailing number ("Bearing 22x8x8" -> "Bearing 22x8x9")."""
        self.params.Height = 8
        self.doc.recompute()
        second = PB.create_races(self.doc, FreeCAD.Placement(), dict(V608, Height=8), False, False)
        self.doc.recompute()
        part = second.getParentGeoFeatureGroup().getParentGeoFeatureGroup()
        self.assertEqual(part.Label, "Bearing 22x8x8_001")
        self.assertEqual(self.part.Label, "Bearing 22x8x8")

    def test_user_label_kept(self):
        self.part.Label = "Spindle"
        self.params.Height = 8
        self.doc.recompute()
        self.assertEqual(self.part.Label, "Spindle")

    def test_check_object_flags_invalid_values(self):
        self.params.NumBalls = 40
        self.doc.recompute()
        self.assertTrue(is_invalid(self.chk), "too many balls should flag the check object")
        self.params.NumBalls = 7
        self.doc.recompute()
        self.assertFalse(
            [o.Label for o in self.doc.Objects if is_invalid(o)], "fixed values clear the error"
        )

    def test_label_follows_after_reopen(self):
        name = self.part.Name
        doc = self.reopen()
        part = doc.getObject(name)
        chk = [o for o in part.Group if o.Name.startswith("PrintableBearing")][0]
        chk.Parameters.OD = 24
        doc.recompute()
        self.assertEqual(part.Label, "Bearing 24x8x7")
        self.assertFalse([o.Label for o in doc.Objects if is_invalid(o)])

    def test_preview_frame_reversed(self):
        fr = PB.preview_frame(PB.CREATE, None, None, 7, reverse=True)
        self.assertTrue(close(fr.Base.z, -3.5, 1e-6), fr.Base)


class ConvertBearing(DocumentTest):
    def setUp(self):
        super().setUp()
        self.std = BearingBase.make_bearing("62", "625", doc=self.doc)
        self.std.Placement = FreeCAD.Placement(V(60, 0, 0), FreeCAD.Rotation())
        self.doc.recompute()

    def test_convert(self):
        values = {"BallDiameter": 3.0, "NumBalls": 8}
        params = PB.convert_bearing(self.std, values, cage=True, balls=False)
        races = params.getParentGeoFeatureGroup()
        part = races.getParentGeoFeatureGroup()
        bb = races.Shape.BoundBox
        self.assertEqual(part.Label, "Bearing 625 (16x5x5)")
        self.assertFalse(self.std.Visibility)
        self.assertTrue(
            close(part.Placement.Base.x, 60)
            and close(bb.ZMin, -5, 0.01)
            and close(bb.ZMax, 0, 0.01),
            "races sit where the standard bearing was",
        )

    def test_preview_frame(self):
        fr = PB.preview_frame(PB.CREATE, None, None, 5, bearing=self.std)
        self.assertLess((fr.Base - V(60, 0, -2.5)).Length, 1e-6, fr.Base)


class GrooveBody(DocumentTest):
    def setUp(self):
        super().setUp()
        self.body = self.doc.addObject("PartDesign::Body", "Hub")
        disc = self.body.newObject("PartDesign::AdditiveCylinder", "Disc")
        disc.Radius, disc.Height = 20, 8
        self.bore = self.body.newObject("PartDesign::SubtractiveCylinder", "Bore")
        self.bore.Radius, self.bore.Height = 5, 8
        self.doc.recompute()
        self.edge = self.body.Shape.getElement(find_circle(self.body, 5, 8))

    def test_measure(self):
        m = PB.measure_body(self.body, self.edge)
        self.assertEqual((m["dia"], m["is_inner"]), (10, True))
        self.assertTrue(close(m["height"], 8) and close(abs(m["mid"]), 4), m)

    def test_groove(self):
        values = dict(PB.CAGE_DEFAULTS, ID=0, OD=24, Height=8, BallDiameter=4, NumBalls=10)
        PB.groove_body(self.bore, self.edge, values, True, False)
        self.assertEqual(len(self.body.Shape.Solids), 2, "grooved body splits into 2 races")
        check_objects = [o for o in self.doc.Objects if o.Name.startswith("PrintableBearing")]
        self.assertEqual(check_objects, [], "grooving adds no PrintableBearing object")

    def test_preview_frame(self):
        m = PB.measure_body(self.body, self.edge)
        fr = PB.preview_frame(PB.GROOVE, self.edge, m, 8)
        self.assertTrue(close(fr.Base.z, 4, 1e-6), "frame at mid-height of the bore: %s" % fr.Base)
