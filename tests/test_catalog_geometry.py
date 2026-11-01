# SPDX-License-Identifier: GPL-3.0-or-later
"""Assembly-fit checks for the added bearing families, run inside FreeCAD."""

import math
import os
import tempfile
import unittest

import FreeCAD
import Part

import BearingBase
import BearingCatalog as BC
import BearingData as BD
import BearingGeometry as BG
from testutil import DocumentTest, V, find_circle, plate_with_hole, tight_bb


class CatalogShapes(unittest.TestCase):
    def test_all_additional_sizes_and_details(self):
        for series in BD.SERIES:
            for row in BD.load_table(series):
                if not isinstance(row, BD.CatalogRow):
                    continue
                for detail in BG.DETAIL_LEVELS:
                    with self.subTest(name=row.name, detail=detail):
                        shape, colors = BG.build(row, "Open", False, detail)
                        self.assertFalse(shape.isNull())
                        self.assertTrue(shape.isValid())
                        self.assertTrue(all(s.Volume > 0 for s in shape.Solids))
                        self.assertEqual(len(colors), len(shape.Faces))
                        bb = tight_bb(shape)
                        self.assertAlmostEqual(bb.ZMin, -row.B, delta=0.01)
                        top = max(0, getattr(row, "cone_B", 0) - row.B)
                        self.assertAlmostEqual(bb.ZMax, top, delta=0.01)
                        if row.kind == "housed":
                            self.assertAlmostEqual(bb.XLength, row.L, delta=0.01)
                            height = row.H2 if row.style == "pillow" else row.H
                            self.assertAlmostEqual(bb.YLength, height, delta=0.01)
                        else:
                            self.assertAlmostEqual(bb.XLength, row.D, delta=0.01)
                            self.assertAlmostEqual(bb.YLength, row.D, delta=0.01)
                        if row.kind == "looseball":
                            self.assertEqual(len(shape.Solids), 1)
                            self.assertAlmostEqual(shape.Volume, math.pi * row.D**3 / 6)
                        elif row.kind != "camfollower":
                            bore = Part.makeCylinder(row.d / 2 - 0.01, row.B, V(0, 0, -row.B))
                            self.assertLess(shape.common(bore).Volume, 1e-5)

    def test_mounted_unit_bolt_holes(self):
        for series in ("UCP", "UCF", "UCFL", "SBLF"):
            for row in BD.load_table(series):
                shape = BG.build(row, "Open", False, "Standard")[0]
                if row.style == "pillow":
                    holes = [
                        Part.makeCylinder(
                            row.hole / 2 - 0.01,
                            row.foot + 2,
                            V(x, -row.H - 1, -row.B / 2),
                            V(0, 1, 0),
                        )
                        for x in (-row.J / 2, row.J / 2)
                    ]
                else:
                    ys = (-row.J / 2, row.J / 2) if row.style == "square" else (0,)
                    holes = [
                        Part.makeCylinder(row.hole / 2 - 0.01, row.B + 2, V(x, y, -row.B - 1))
                        for x in (-row.J / 2, row.J / 2)
                        for y in ys
                    ]
                for hole in holes:
                    with self.subTest(row=row.name):
                        self.assertLess(shape.common(hole).Volume, 1e-5)

    def test_new_parts_do_not_overlap(self):
        for series in ("222", "230", "NN30", "UCP", "UCF", "UCFL", "SBLF", "KR", "Wheel"):
            row = BD.get_row(series, BD.SERIES[series][2])
            parts = BG.build(row, "Open", False, "Standard")[0].Solids
            for i, a in enumerate(parts):
                for b in parts[i + 1 :]:
                    if a.BoundBox.intersect(b.BoundBox):
                        with self.subTest(row=row.name):
                            self.assertLess(a.common(b).Volume, 1e-4)

    def test_tapered_bores_and_stud_are_real_geometry(self):
        for series, name in (("NN30", "NN3015K"), ("Special", "1306K")):
            row = BD.get_row(series, name)
            shape = BG.build(row, "Open", False, "Standard")[0]
            conical = [f.Surface for f in shape.Faces if isinstance(f.Surface, Part.Cone)]
            self.assertTrue(conical, name)
        row = BD.get_row("KR", "KR19PP")
        shape = BG.build(row, "Open", False, "Standard")[0]
        self.assertTrue(shape.isInside(V(0, 0, -31), 1e-6, True))
        self.assertFalse(shape.isInside(V(4.1, 0, -31), 1e-6, True))


class CatalogObjects(DocumentTest):
    def test_complete_ball_assortment_quantities(self):
        import BearingBOM

        balls = BC.make_product("139 FRV 138", doc=self.doc)
        self.assertEqual(len(balls), 450)
        self.assertTrue(all(b.Shape.isValid() for b in balls))
        counts = {r["Item"]: r["Quantity"] for r in BearingBOM.bom_items(self.doc)}
        self.assertEqual(counts["Ball2mm"], 50)
        self.assertEqual(counts["Ball8mm"], 20)
        self.assertEqual(len(counts), 11)
        self.assertEqual(sum(counts.values()), 450)

    def test_equal_kit_bearings_and_source_changes(self):
        import BearingBOM

        bearings = BC.make_product("056 SKF 179", doc=self.doc)
        self.assertEqual(len(bearings), 2)
        self.assertEqual(BearingBOM.bom_items(self.doc)[0]["Quantity"], 2)
        b = BC.make_product("056 GRP 123", doc=self.doc)[0]
        self.assertIn("26.222", b.ModelNotes)
        b.Designation = "92705"
        self.doc.recompute()
        self.assertEqual(b.SupplierArticle, "")
        self.assertNotIn("26.222", b.ModelNotes)

    def test_cam_follower_stud_enters_selected_hole(self):
        plate = plate_with_hole(self.doc, 8)
        self.doc.recompute()
        b = BearingBase.make_bearing(
            "KR", attach_to=(plate, [find_circle(plate, 4, 10)]), doc=self.doc
        )
        self.doc.recompute()
        self.assertEqual(b.FullDesignation, "KR19PP")
        self.assertAlmostEqual(tight_bb(b.Shape).ZMin, -10, delta=0.01)
        self.assertLess(b.Shape.common(plate.Shape).Volume, 1e-5)

    def test_create_recompute_bom_and_restore(self):
        import BearingBOM

        objects = BC.make_product("056 SKF 154", doc=self.doc)
        objects += [BearingBase.make_bearing(s, doc=self.doc) for s in ("UCP", "222", "KR", "NN30")]
        self.doc.recompute()
        self.assertEqual(len(objects), 6)
        for obj in objects:
            self.assertTrue(obj.Shape.isValid())
            self.assertTrue(obj.SourceURL)
        names = {o.FullDesignation for o in objects}
        self.assertIn("VKBA542-2", names)
        self.assertEqual({r["Item"] for r in BearingBOM.bom_items(self.doc)}, names)
        # Saving must retain the series, source and calculated geometry.
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "catalog.FCStd")
            self.doc.saveAs(path)
            FreeCAD.closeDocument(self.doc.Name)
            self.doc = FreeCAD.openDocument(path)
            self.doc.recompute()
            found = [o for o in self.doc.Objects if hasattr(o, "FullDesignation")]
            self.assertEqual({o.FullDesignation for o in found}, names)
            self.assertTrue(all(o.Shape.isValid() and o.SourceURL for o in found))
