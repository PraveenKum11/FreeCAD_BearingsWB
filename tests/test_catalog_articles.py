# SPDX-License-Identifier: GPL-3.0-or-later
"""Create, recompute and round-trip every supplier article, including kit quantities.

Set BEARINGS_CATALOG_OUTPUT to retain one FCStd file per article and a JSON report.
Otherwise the artifacts are kept in a temporary directory for the test's lifetime.
"""

import hashlib
import json
import os
import tempfile
import unittest
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import FreeCAD as App

import BearingBOM
import BearingCatalog as BC
import BearingData as BD
import BearingGeometry as BG
from testutil import tight_bb


class EverySupplierArticle(unittest.TestCase):
    def check_objects(self, objects, expected, article):
        self.assertEqual(
            Counter((o.Series, str(o.Designation), str(o.Closure)) for o in objects),
            Counter(expected),
        )
        for obj in objects:
            self.assertNotIn("Invalid", obj.State, obj.FullDesignation)
            self.assertFalse(obj.Shape.isNull(), obj.FullDesignation)
            self.assertTrue(obj.Shape.isValid(), obj.FullDesignation)
            self.assertGreater(obj.Shape.Volume, 0, obj.FullDesignation)
            self.assertEqual(obj.SupplierArticle, article)
            self.assertTrue(obj.SourceURL.startswith("https://"), obj.FullDesignation)
            row = BD.get_row(obj.Series, str(obj.Designation))
            self.assertAlmostEqual(obj.BoreDiameter.Value, row.d)
            self.assertAlmostEqual(obj.OuterDiameter.Value, row.D)
            self.assertAlmostEqual(obj.Width.Value, row.width(str(obj.Closure)))
            bb = tight_bb(obj.Shape)
            expected_x = row.L if BD.kind(row) == "housed" else row.D
            expected_y = (
                (row.H2 if row.style == "pillow" else row.H) if BD.kind(row) == "housed" else row.D
            )
            self.assertAlmostEqual(bb.XLength, expected_x, delta=0.01)
            self.assertAlmostEqual(bb.YLength, expected_y, delta=0.01)
            self.assertAlmostEqual(bb.ZMin, -row.width(str(obj.Closure)), delta=0.01)
            self.assertAlmostEqual(bb.ZMax, max(0, getattr(row, "cone_B", 0) - row.B), delta=0.01)

    def test_every_article_creates_all_parts_and_survives_save_restore(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(os.environ.get("BEARINGS_CATALOG_OUTPUT", temporary))
            output.mkdir(parents=True, exist_ok=True)
            catalog = Path(BC.__file__).parent / "BRData" / "tashev_catalog.csv"
            report = {
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "freecad_version": App.Version()[:3],
                "catalog_sha256": hashlib.sha256(catalog.read_bytes()).hexdigest(),
                "detail_levels": BG.DETAIL_LEVELS,
                "articles": [],
            }
            try:
                for product in BC.products():
                    article = product["SKU"]
                    record = {"article": article, "status": "failed"}
                    report["articles"].append(record)
                    doc = App.newDocument("CatalogArticle")
                    with self.subTest(article=article):
                        try:
                            expected = BC.components(product)
                            objects = BC.make_product(article, doc=doc)
                            self.assertTrue(objects, "article has no objects")
                            # Real parametric objects, through every detail level; not just
                            # table lookups or isolated calls to the geometry functions.
                            for detail in BG.DETAIL_LEVELS:
                                for obj in objects:
                                    obj.DetailLevel = detail
                                doc.recompute()
                                self.check_objects(objects, expected, article)
                            for obj in objects:
                                obj.DetailLevel = "Standard"
                            doc.recompute()
                            expected_bom = Counter(obj.FullDesignation for obj in objects)
                            bom = BearingBOM.bom_items(doc)
                            self.assertEqual({r["Item"]: r["Quantity"] for r in bom}, expected_bom)
                            path = output / (article + ".FCStd")
                            doc.saveAs(str(path))
                            App.closeDocument(doc.Name)
                            doc = App.openDocument(str(path))
                            doc.recompute(None, True)
                            restored = [o for o in doc.Objects if BearingBOM.is_bearing(o)]
                            self.check_objects(restored, expected, article)
                            self.assertEqual(
                                {r["Item"]: r["Quantity"] for r in BearingBOM.bom_items(doc)},
                                expected_bom,
                            )
                            record.update(
                                status="passed",
                                object_count=len(restored),
                                file=path.name,
                                bom=dict(expected_bom),
                            )
                        except Exception as error:
                            record["error"] = str(error)
                            raise
                        finally:
                            if doc.Name in App.listDocuments():
                                App.closeDocument(doc.Name)
                    print("catalog article:", article, record["status"], flush=True)
            finally:
                report["passed"] = sum(r["status"] == "passed" for r in report["articles"])
                report["failed"] = sum(r["status"] != "passed" for r in report["articles"])
                report["total"] = len(BC.products())
                (output / "validation.json").write_text(
                    json.dumps(report, indent=2), encoding="utf-8"
                )
