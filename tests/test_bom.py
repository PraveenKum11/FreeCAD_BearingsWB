# SPDX-License-Identifier: GPL-3.0-or-later
"""Bill of materials (BearingBOM)."""

import csv
import os
import tempfile

import FreeCAD

import BearingBase
import BearingBOM
import PrintableBearing as PB
from testutil import DocumentTest

P608 = dict(PB.CAGE_DEFAULTS, ID=8, OD=22, Height=7, BallDiameter=4.5, NumBalls=9)


class BOM(DocumentTest):
    def setUp(self):
        super().setUp()
        doc = self.doc
        for _ in range(3):
            BearingBase.make_bearing("60", "608", doc=doc)
        hidden = BearingBase.make_bearing("60", "608", doc=doc)
        hidden.Visibility = False
        BearingBase.make_bearing("60", "608", doc=doc, Closure="ZZ")
        BearingBase.make_bearing("LM", "LM8UU", doc=doc, Flanged=True, FlangeShape="Square")
        array = doc.addObject("App::Link", "Array")
        array.LinkedObject = doc.getObject("Bearing")  # the first 608
        array.ElementCount = 4
        BearingBase.make_bearing("AXK", "AXK1528", doc=doc, Variant="AXK + 2 AS")
        PB.create_races(doc, FreeCAD.Placement(), P608, False, True, False)
        doc.recompute()

    def by_item(self, skip_hidden=True):
        return {r["Item"]: r for r in BearingBOM.bom_items(self.doc, skip_hidden)}

    def test_counts(self):
        items = self.by_item()
        self.assertEqual(items["608"]["Quantity"], 3 + 4, "three bearings and a link array of 4")
        self.assertEqual(items["608ZZ"]["Quantity"], 1)
        self.assertEqual(items["LMK8UU"]["Quantity"], 1)
        self.assertEqual(items["608"]["Bore d (mm)"], 8)
        self.assertEqual(
            self.by_item(skip_hidden=False)["608"]["Quantity"], 8, "with the hidden one"
        )

    def test_printable_bearing_and_its_balls(self):
        items = self.by_item()
        printable = items["Printable bearing 608 (22x8x7)"]
        self.assertEqual(printable["Quantity"], 1)
        self.assertEqual(printable["Description"], "3D-printed races and cage")
        balls = items["4.5 mm steel BB (.177)"]
        self.assertEqual((balls["Quantity"], balls["OD D (mm)"]), (9, 4.5))

    def test_order_and_csv(self):
        items = BearingBOM.bom_items(self.doc)
        kinds = [r["Item"] for r in items]
        self.assertLess(kinds.index("608"), kinds.index("Printable bearing 608 (22x8x7)"))
        self.assertEqual(kinds[-1], "4.5 mm steel BB (.177)", "balls last")
        path = os.path.join(tempfile.mkdtemp(), "bom.csv")
        BearingBOM.write_csv(path, items)
        with open(path, newline="") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(list(rows[0]), BearingBOM.COLUMNS)
        self.assertEqual(len(rows), len(items))

    def test_axk_washers(self):
        items = self.by_item()
        self.assertEqual(items["AXK1528"]["Quantity"], 1)
        self.assertEqual(items["AS1528"]["Quantity"], 2, "an AS washer on each side")

    def test_spreadsheet(self):
        items = BearingBOM.bom_items(self.doc)
        sheet = BearingBOM.write_sheet(self.doc, items)
        self.assertEqual(sheet.Label, "Bearing BOM")
        header = [sheet.getContents(c + "1").lstrip("'") for c in "ABCDEFG"]
        self.assertEqual(header, BearingBOM.COLUMNS[:-1] + [""], "no Objects column")
        row = 2 + [r["Item"] for r in items].index("608")
        self.assertEqual(sheet.get("A%d" % row), "608", "designations stay text")
        self.assertEqual((sheet.get("C%d" % row), sheet.get("F%d" % row)), (8, 7))
        total = len(items) + 3
        self.assertEqual(sheet.get("A%d" % total), "Total parts")
        self.assertEqual(sheet.get("F%d" % total), sum(r["Quantity"] for r in items))

    def test_each_spreadsheet_is_new(self):
        items = BearingBOM.bom_items(self.doc)
        sheets = [BearingBOM.write_sheet(self.doc, items) for _ in range(2)]
        self.assertEqual([s.Label for s in sheets], ["Bearing BOM", "Bearing BOM_001"])
        self.assertEqual(sheets[1].get("A1"), "Item")
