# SPDX-License-Identifier: GPL-3.0-or-later
"""The standard bearing FeaturePython object: attachment, auto size, labels, persistence."""

import FreeCAD
import Part

import BearingBase
import BRselection as BRS
from testutil import DocumentTest, V, close, find_circle, is_invalid, plate_with_hole, tight_bb


class HousingAttach(DocumentTest):
    """A 22 mm hole: a 608 sits inside the hole, flush with the top face."""

    def setUp(self):
        super().setUp()
        self.plate = plate_with_hole(self.doc, 22.0)
        self.doc.recompute()
        target = (self.plate, [find_circle(self.plate, 11, 10)])
        self.b = BearingBase.make_bearing("60", attach_to=target, doc=self.doc)

    def test_auto_size(self):
        self.assertEqual(self.b.MatchTo, "Housing")
        self.assertEqual(self.b.FullDesignation, "608")
        self.assertEqual(self.b.Label, "608")

    def test_placement(self):
        bb = tight_bb(self.b.Shape)
        self.assertTrue(close(bb.ZMax, 10, 0.01) and close(bb.ZMin, 3, 0.01), (bb.ZMin, bb.ZMax))
        self.assertLess(
            self.b.Shape.common(self.plate.Shape).Volume, 1e-3, "bearing intersects the plate"
        )

    def test_invert_and_offset(self):
        self.b.Invert = True
        self.doc.recompute()
        bb = tight_bb(self.b.Shape)
        self.assertTrue(close(bb.ZMin, 10, 0.01) and close(bb.ZMax, 17, 0.01), (bb.ZMin, bb.ZMax))
        self.b.Invert = False
        self.b.Offset = -1.0
        self.b.Closure = "2RS"
        self.doc.recompute()
        self.assertTrue(close(tight_bb(self.b.Shape).ZMax, 9, 0.01))
        self.assertEqual(self.b.Label, "608-2RS", "label follows closure")


class ShaftAttach(DocumentTest):
    def test_shaft_end(self):
        """An 8 mm shaft end: a 608 slides onto the shaft."""
        shaft = self.doc.addObject("Part::Feature", "Shaft")
        shaft.Shape = Part.makeCylinder(4, 30, V(50, 0, 0))
        self.doc.recompute()
        s = BearingBase.make_bearing(
            "60", attach_to=(shaft, [find_circle(shaft, 4, 30)]), doc=self.doc
        )
        self.assertEqual(s.MatchTo, "Shaft")
        self.assertEqual(s.FullDesignation, "608")
        bb = tight_bb(s.Shape)
        self.assertTrue(close(bb.ZMax, 30, 0.01) and close(bb.ZMin, 23, 0.01), (bb.ZMin, bb.ZMax))


class Flanged(DocumentTest):
    def test_flanged_series_change(self):
        f = BearingBase.make_bearing("68", "688", doc=self.doc, Flanged=True, Closure="ZZ")
        self.assertEqual(f.FullDesignation, "F688ZZ")
        self.assertTrue(close(tight_bb(f.Shape).XLength, 18, 0.01), "flange diameter")
        f.Series = "MR"
        f.Designation = "MR105"
        self.doc.recompute()
        self.assertEqual(f.FullDesignation, "MF105ZZ")
        self.assertTrue(close(f.Width.Value, 4.0), "MR105ZZ shielded width %.2f" % f.Width.Value)


class Persistence(DocumentTest):
    def test_save_reopen_recompute(self):
        plate = plate_with_hole(self.doc, 22.0)
        self.doc.recompute()
        auto = BearingBase.make_bearing(
            "60", attach_to=(plate, [find_circle(plate, 11, 10)]), doc=self.doc
        )
        BearingBase.make_bearing("68", "688", doc=self.doc, Flanged=True, Closure="ZZ")
        name = auto.Name
        doc = self.reopen()
        objs = [o for o in doc.Objects if hasattr(o, "FullDesignation")]
        self.assertEqual(len(objs), 2)
        for o in objs:
            o.touch()
        doc.recompute()
        for o in objs:
            self.assertTrue(
                o.Shape.isValid() and not is_invalid(o), "%s failed to recompute" % o.Label
            )
        self.assertEqual(doc.getObject(name).Designation, "Auto", "Designation not persisted")


class Labels(DocumentTest):
    """Auto labels follow the designation until the user renames the object."""

    def test_initial_label_differs_from_name(self):
        # after a GUI delete FreeCAD gives new objects a label that differs from Name
        obj = self.doc.addObject("Part::FeaturePython", "Bearing")
        obj.Label = "Bearing002"
        BearingBase.BearingObject(obj, "60")
        self.doc.recompute()
        self.assertEqual(obj.Label, "608")

    def test_same_designation_gets_a_counter(self):
        """A second 608 is 608_001, not 609 (FreeCAD increments a trailing number)."""
        labels = [BearingBase.make_bearing("60", "608", doc=self.doc).Label for _ in range(3)]
        self.assertEqual(labels, ["608", "608_001", "608_002"])

    def test_duplicate_designation_keeps_following(self):
        BearingBase.make_bearing("60", "608", doc=self.doc)
        twin = BearingBase.make_bearing("60", "608", doc=self.doc)
        twin.Designation = "609"
        self.doc.recompute()
        self.assertEqual(twin.Label, "609")
        twin.Closure = "ZZ"
        self.doc.recompute()
        self.assertEqual(twin.Label, "609ZZ")

    def test_old_auto_label_gets_a_counter(self):
        """Auto labels from before the counter ("609" for a second 608) are repaired."""
        BearingBase.make_bearing("60", "608", doc=self.doc)
        b = BearingBase.make_bearing("60", "608", doc=self.doc)
        b.Label = "609"
        b.Proxy.auto_label, b.Proxy.auto_target = "609", "608"
        b.touch()
        self.doc.recompute()
        self.assertEqual(b.Label, "608_001")

    def test_freed_label_is_reused(self):
        first = BearingBase.make_bearing("60", "608", doc=self.doc)
        BearingBase.make_bearing("60", "608", doc=self.doc)
        self.doc.removeObject(first.Name)
        self.assertEqual(BearingBase.make_bearing("60", "608", doc=self.doc).Label, "608")

    def test_user_rename_sticks(self):
        obj = BearingBase.make_bearing("60", "608", doc=self.doc)
        obj.Label = "Spindle bearing"
        obj.Closure = "ZZ"
        self.doc.recompute()
        self.assertEqual(obj.Label, "Spindle bearing")
        name = obj.Name
        doc = self.reopen()
        self.assertEqual(
            doc.getObject(name).Label, "Spindle bearing", "user label lost after reopen"
        )

    def test_follows_after_reopen(self):
        name = BearingBase.make_bearing("68", "688", doc=self.doc).Name
        doc = self.reopen()
        auto = doc.getObject(name)
        auto.Closure = "2RS"
        doc.recompute()
        self.assertEqual(auto.Label, "688-2RS")

    def test_stuck_default_label_repaired(self):
        # a label left stuck by the original bug ("Bearing017", auto_label = designation)
        stuck = BearingBase.make_bearing("62", "625", doc=self.doc)
        stuck.Label = "Bearing017"  # differs from its Name
        stuck.Proxy.auto_label = stuck.Proxy.auto_target = "625"
        stuck.touch()
        self.doc.recompute()
        self.assertEqual(stuck.Label, "625")


class NestedAttach(DocumentTest):
    """Edges inside containers with their own placement resolve to global coordinates."""

    def setUp(self):
        super().setUp()
        doc = self.doc
        self.part = doc.addObject("App::Part", "Part")
        self.part.Placement = FreeCAD.Placement(V(100, 0, 0), FreeCAD.Rotation(V(0, 0, 1), 90))
        self.body = doc.addObject("PartDesign::Body", "Body")
        self.part.addObject(self.body)
        self.body.Placement = FreeCAD.Placement(V(0, 50, 0), FreeCAD.Rotation())
        box = self.body.newObject("PartDesign::AdditiveBox", "Box")
        box.Length = box.Width = 40
        box.Height = 10
        box.AttachmentOffset = FreeCAD.Placement(V(-20, -20, 0), FreeCAD.Rotation())
        self.hole = self.body.newObject("PartDesign::SubtractiveCylinder", "Hole")
        self.hole.Radius = 11
        self.hole.Height = 10
        doc.recompute()
        self.edge = find_circle(self.hole, 11, 10)
        # hole center in Body: (0, 0); Body at (0, 50) in Part; Part at (100, 0) rotated 90°
        self.want = self.part.Placement.multVec(self.body.Placement.multVec(V(0, 0, 10)))

    def check_target(self, obj, subname):
        e, _ = BRS.resolve_edge(obj, subname)
        self.assertIsNotNone(e)
        self.assertLess((BRS.center_of(e.Curve) - self.want).Length, 1e-6, "edge center")
        b = BearingBase.make_bearing("60", attach_to=(obj, [subname]), doc=self.doc)
        self.assertEqual((b.MatchTo, b.FullDesignation), ("Housing", "608"))
        bb = tight_bb(b.Shape)
        center = V((bb.XMin + bb.XMax) / 2, (bb.YMin + bb.YMax) / 2, bb.ZMax)
        self.assertLess((center - self.want).Length, 0.01, "bearing top center %s" % center)
        self.assertTrue(close(bb.ZMin, self.want.z - 7, 0.01), "bearing goes into the hole")

    def test_path_from_root(self):
        self.check_target(self.part, "Body.Hole." + self.edge)

    def test_feature(self):
        self.check_target(self.hole, self.edge)


class LinearBushings(DocumentTest):
    def test_shaft_and_housing(self):
        shaft = self.doc.addObject("Part::Feature", "Shaft")
        shaft.Shape = Part.makeCylinder(4, 60, V(50, 0, 0))
        plate = plate_with_hole(self.doc, 15.0)
        self.doc.recompute()
        on_shaft = BearingBase.make_bearing(
            "LM", attach_to=(shaft, [find_circle(shaft, 4, 60)]), doc=self.doc
        )
        in_hole = BearingBase.make_bearing(
            "LM", attach_to=(plate, [find_circle(plate, 7.5, 10)]), doc=self.doc
        )
        self.assertEqual((on_shaft.MatchTo, on_shaft.FullDesignation), ("Shaft", "LM8UU"))
        self.assertEqual((in_hole.MatchTo, in_hole.FullDesignation), ("Housing", "LM8UU"))
        bb = tight_bb(on_shaft.Shape)
        self.assertTrue(close(bb.ZMax, 60, 0.01) and close(bb.ZMin, 36, 0.01), (bb.ZMin, bb.ZMax))
        self.assertTrue(close(in_hole.Width.Value, 24) and in_hole.BallCount > 0)

    def test_flanged_rests_on_the_face(self):
        """In a hole, the flange sits on the face and only the body goes in."""
        plate = plate_with_hole(self.doc, 15.0)
        self.doc.recompute()
        b = BearingBase.make_bearing(
            "LM",
            "LM8UU",
            attach_to=(plate, [find_circle(plate, 7.5, 10)]),
            doc=self.doc,
            Flanged=True,
            FlangeShape="Square",
        )
        self.assertEqual(b.FullDesignation, "LMK8UU")
        self.assertEqual(b.Label, "LMK8UU")
        bb = tight_bb(b.Shape)
        self.assertTrue(close(bb.ZMax, 15, 0.01) and close(bb.ZMin, -9, 0.01), (bb.ZMin, bb.ZMax))
        self.assertTrue(close(bb.XLength, 25, 0.01), "square flange 25 mm")
        self.assertLess(b.Shape.common(plate.Shape).Volume, 1e-3, "bushing intersects the plate")

    def test_flanged_ball_bearing_rests_on_the_face(self):
        plate = plate_with_hole(self.doc, 16.0)
        self.doc.recompute()
        b = BearingBase.make_bearing(
            "68", "688", attach_to=(plate, [find_circle(plate, 8, 10)]), doc=self.doc, Flanged=True
        )
        bb = tight_bb(b.Shape)
        self.assertTrue(close(bb.ZMax, 11, 0.01) and close(bb.ZMin, 7, 0.01), (bb.ZMin, bb.ZMax))

    def test_editor_modes_follow_the_family(self):
        b = BearingBase.make_bearing("60", "608", doc=self.doc)
        self.assertIn("Hidden", b.getEditorMode("FlangeShape"))
        self.assertNotIn("Hidden", b.getEditorMode("Closure"))
        b.Series = "LM"
        self.doc.recompute()
        self.assertEqual(b.FullDesignation, "LM8UU", "Series change picks the LM default")
        self.assertNotIn("Hidden", b.getEditorMode("FlangeShape"))
        self.assertIn("Hidden", b.getEditorMode("Closure"))

    def test_old_document_gets_flange_shape(self):
        b = BearingBase.make_bearing("60", "608", doc=self.doc)
        b.removeProperty("FlangeShape")  # as saved before linear bushings existed
        name = b.Name
        doc = self.reopen()
        b = doc.getObject(name)
        self.assertEqual(b.FlangeShape, "Round")
        b.touch()
        doc.recompute()
        self.assertFalse(is_invalid(b))


class InchBearings(DocumentTest):
    def test_fr188(self):
        b = BearingBase.make_bearing("R", "R188", doc=self.doc, Flanged=True, Closure="ZZ")
        self.assertEqual(b.FullDesignation, "FR188ZZ")
        self.assertTrue(close(b.Width.Value, 4.762), b.Width.Value)
        self.assertTrue(close(tight_bb(b.Shape).XLength, 13.894, 0.01), "flange diameter")


class AngularAndThrust(DocumentTest):
    def test_angular_contact(self):
        b = BearingBase.make_bearing("72", doc=self.doc, Closure="ZZ")
        self.assertEqual((b.FullDesignation, b.Label), ("7204B", "7204B"), "no closure codes")
        self.assertIn("Hidden", b.getEditorMode("Closure"))
        self.assertIn("Hidden", b.getEditorMode("Flanged"))
        self.assertTrue(close(tight_bb(b.Shape).XLength, 47, 0.01))

    def test_thrust_on_a_shaft(self):
        shaft = self.doc.addObject("Part::Feature", "Shaft")
        shaft.Shape = Part.makeCylinder(10, 40)
        self.doc.recompute()
        b = BearingBase.make_bearing(
            "511", attach_to=(shaft, [find_circle(shaft, 10, 40)]), doc=self.doc
        )
        self.assertEqual((b.MatchTo, b.FullDesignation), ("Shaft", "51104"))
        bb = tight_bb(b.Shape)
        self.assertTrue(close(bb.ZMax, 40, 0.01) and close(bb.ZMin, 30, 0.01), (bb.ZMin, bb.ZMax))
        self.assertLess(b.Shape.common(shaft.Shape).Volume, 1e-3, "washers clear the shaft")


class V04Types(DocumentTest):
    def test_cylindrical_variant(self):
        b = BearingBase.make_bearing("NU2", "NU204", doc=self.doc)
        self.assertEqual(b.Variant, "NU")
        self.assertNotIn("Hidden", b.getEditorMode("Variant"))
        b.Variant = "NJ"
        self.doc.recompute()
        self.assertEqual((b.FullDesignation, b.Label), ("NJ204", "NJ204"))
        b.Series = "60"
        self.doc.recompute()
        self.assertIn("Hidden", b.getEditorMode("Variant"))

    def test_needle_on_a_shaft(self):
        shaft = self.doc.addObject("Part::Feature", "Shaft")
        shaft.Shape = Part.makeCylinder(4, 30)
        self.doc.recompute()
        b = BearingBase.make_bearing(
            "HK", attach_to=(shaft, [find_circle(shaft, 4, 30)]), doc=self.doc
        )
        self.assertEqual((b.MatchTo, b.FullDesignation), ("Shaft", "HK0808"))
        self.assertLess(b.Shape.common(shaft.Shape).Volume, 1e-3, "needles run on the shaft")

    def test_axk_washers(self):
        b = BearingBase.make_bearing("AXK", "AXK1528", doc=self.doc)
        self.assertTrue(close(b.Width.Value, 2))
        b.Variant = "AXK + 2 AS"
        self.doc.recompute()
        self.assertTrue(close(b.Width.Value, 4) and close(tight_bb(b.Shape).ZLength, 4, 0.01))

    def test_tapered_and_self_aligning(self):
        t = BearingBase.make_bearing("302", "30204", doc=self.doc)
        self.assertTrue(
            close(t.Width.Value, 15.25) and close(tight_bb(t.Shape).ZLength, 15.25, 0.01)
        )
        s = BearingBase.make_bearing("12", "1205", doc=self.doc, Closure="2RS")
        self.assertEqual(s.FullDesignation, "1205", "no closure codes")
        self.assertIn("Hidden", s.getEditorMode("Closure"))
