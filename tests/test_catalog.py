# SPDX-License-Identifier: GPL-3.0-or-later
"""Offline coverage of the complete Tashev-Galving bearing category, 2026-10-18."""

import unittest
from collections import Counter

import BearingCatalog as BC
import BearingData as BD


class SupplierCoverage(unittest.TestCase):
    def test_complete_snapshot(self):
        products = BC.products()
        self.assertEqual(len(products), 335)
        self.assertEqual(len({p["SKU"] for p in products}), 335)
        self.assertEqual(
            Counter(p["Category"] for p in products),
            dict(ball=284, thrust=22, roller=18, housing=11),
        )
        self.assertEqual(Counter(p["Status"] for p in products), dict(bearing=333, accessory=2))

    def test_every_article_resolves_with_insertion_options(self):
        for product in BC.products():
            with self.subTest(article=product["SKU"]):
                expected = BC.components(product)
                hits = BD.search(product["SKU"])
                self.assertEqual({(s, r.name) for s, r in hits}, {(s, n) for s, n, c in expected})
                self.assertTrue(expected)
                for series, row in hits:
                    options = BD.search_options(product["SKU"], series, row)
                    self.assertIn((series, row.name, options["Closure"]), expected)
                    self.assertIn(options["Closure"], BD.CLOSURES)
                self.assertTrue(product["URL"].startswith("https://tashev-galving.com/product/"))

    def test_suffixes_keep_closures(self):
        for query, name, closure in (
            ("608 2RSL/C3", "608", "2RS"),
            ("6204 ZZC3", "6204", "ZZ"),
            ("6001 ZZ/SBB", "6001", "ZZ"),
            ("61904 2RS", "6904", "2RS"),
            ("166 ZZ", "R166", "ZZ"),
        ):
            series, row = BD.search(query)[0]
            self.assertEqual(row.name, name)
            self.assertEqual(BD.search_options(query, series, row)["Closure"], closure)

    def test_kit_has_separately_selectable_bearings(self):
        hits = BD.search("VKBA 542")
        self.assertEqual({r.name for _, r in hits}, {"VKBA542-1", "VKBA542-2"})
        self.assertEqual([r.name for _, r in BD.search("VKBA542-2")], ["VKBA542-2"])
        self.assertEqual(len(BD.search("139 FRV 138")), 11)
        self.assertEqual([r.D for _, r in BD.search("056 PRZ 631")], [6])

    def test_manufacturer_corrections_and_special_bores(self):
        for series, name, dims in (
            ("322", "32210", (50, 90, 24.75)),
            ("511", "51122", (110, 145, 25)),
            ("Wheel", "VKBA577", (34, 62, 37)),
            ("KR", "KR19PP", (8, 19, 32)),
        ):
            row = BD.get_row(series, name)
            self.assertEqual((row.d, row.D, row.B), dims)
        self.assertEqual(BD.search("1306 K/236725")[0][1].taper, 12)
        self.assertEqual(BD.search("NN 3015 SKMSP")[0][1].taper, 12)
        self.assertEqual(
            BD.search_options("NJ204", "NU2", BD.get_row("NU2", "NU204"))["Variant"], "NJ"
        )

    def test_each_additional_row_has_provenance(self):
        for series in BD.SERIES:
            for row in BD.load_table(series):
                if isinstance(row, BD.CatalogRow):
                    self.assertTrue(row.source.startswith("https://"), row.name)

    def test_non_annular_mounting_sizes(self):
        self.assertEqual(BD.auto_match("KR", 8.1, "Housing").name, "KR19PP")
        self.assertIsNone(BD.auto_match("KR", 8, "Shaft"))
        self.assertEqual(BD.auto_match("UCP", 25, "Shaft").name, "UCP205")
        self.assertIsNone(BD.auto_match("UCP", 52, "Housing"))
        self.assertEqual(BD.best_match_kind("KR", 8), "Housing")
