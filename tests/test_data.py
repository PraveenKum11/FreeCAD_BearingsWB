# SPDX-License-Identifier: GPL-3.0-or-later
"""Bearing tables and search (BearingData)."""

import unittest

import BearingData as BD


class Tables(unittest.TestCase):
    def test_every_series_loads(self):
        for series in BD.SERIES:
            with self.subTest(series=series):
                rows = BD.load_table(series)
                self.assertTrue(rows, "empty table")
                names = [r.name for r in rows]
                self.assertEqual(len(names), len(set(names)), "duplicate designations")
                self.assertIn(BD.SERIES[series][2], names, "default designation missing")

    def test_dimensions_are_plausible(self):
        for series in BD.SERIES:
            for r in BD.load_table(series):
                with self.subTest(series=series, row=r.name):
                    self.assertTrue(0 < r.d < r.D and r.B > 0, "bad boundary dims")
                    if r.has_flange:
                        self.assertTrue(r.D1 > r.D and r.C1 < r.B, "bad flange dims")
                    if r.B_shielded is not None:
                        self.assertGreaterEqual(r.B_shielded, r.B, "shielded width < open width")

    def test_linear_dimensions(self):
        for r in BD.load_table("LM"):
            with self.subTest(row=r.name):
                self.assertTrue(r.name.startswith("LM") and r.name.endswith("UU"))
                self.assertTrue(r.d < r.groove_D < r.D, "groove diameter outside the wall")
                self.assertTrue(2 * r.groove_W < r.groove_B < r.B, "grooves don't fit the length")
                self.assertIn(r.rows, (4, 5, 6))
                if r.has_flange:
                    d1, d2, h = r.hole
                    self.assertTrue(r.D < r.K < r.D1, "square flange side between D and D1")
                    # bolt holes (on the diagonals) clear the body and stay inside D1
                    self.assertTrue(r.D < r.pcd - d2 and r.pcd + d2 < r.D1, "bolt circle")
                    self.assertTrue(d1 < d2 and h < r.C1, "counterbored hole")

    def test_inch_sizes(self):
        """R sizes are inch fractions: 1/4 x 1/2 x 1/8 (R188), 1/2 x 1-1/8 (R8)."""
        r188, r8 = BD.get_row("R", "R188"), BD.get_row("R", "R8")
        self.assertEqual((r188.d, r188.D, r188.B, r188.B_shielded), (6.35, 12.7, 3.175, 4.762))
        self.assertEqual((r8.d, r8.D), (12.7, 28.575))


class Designations(unittest.TestCase):
    def test_parse_designation(self):
        cases = {
            "608": ("608", None, False),
            "F688-2RS": ("688", "2RS", True),
            "MF105ZZ": ("MR105", "ZZ", True),
            "6204-2RS1": ("6204", "2RS", False),
            "6204-2Z": ("6204", "ZZ", False),
            "618/8": ("688", None, False),
            "mr63": ("MR63", None, False),
            "FR188ZZ": ("R188", "ZZ", True),
            "R188-2RS": ("R188", "2RS", False),
            "LM8UU": ("LM8UU", None, False),
            "LMF8LUU": ("LM8LUU", None, "Round"),
            "lmk8uu": ("LM8UU", None, "Square"),
        }
        for text, want in cases.items():
            with self.subTest(text=text):
                self.assertEqual(BD.parse_designation(text), want)


def names(hits):
    return [r.name for _, r in hits]


class Search(unittest.TestCase):
    def test_by_name(self):
        self.assertEqual(names(BD.search(name="608")), ["608"])
        self.assertEqual(
            set(names(BD.search(name="62"))), set(BD.designations("62")), "name prefix"
        )
        self.assertEqual(names(BD.search(name="F688-2RS")), ["688"], "flanged designation")
        self.assertEqual(BD.search(name="999"), [])

    def test_by_size(self):
        self.assertTrue({"608", "688"} <= set(names(BD.search(d=8))), "by ID")
        self.assertEqual(set(names(BD.search(D=22))), {"636", "627", "608", "6900"}, "by OD")
        self.assertEqual(names(BD.search(name="8x22x7")), ["608"], "size text")
        self.assertIn("6801", names(BD.search(D=22, tol=1)), "tolerance")

    def test_new_families(self):
        self.assertEqual(
            names(BD.search(name="LMK8")), ["LM8UU", "LM8LUU"], "flanged LM, by prefix"
        )
        self.assertEqual(names(BD.search(name="FR188")), ["R188"])
        self.assertEqual(names(BD.search(d=8, D=15)), ["LM8UU", "LM8LUU"])

    def test_full_designation(self):
        lm, r = BD.get_row("LM", "LM8LUU"), BD.get_row("R", "R188")
        self.assertEqual(BD.full_designation(lm, "ZZ", True, "Square"), "LMK8LUU")
        self.assertEqual(BD.full_designation(lm, "Open", True), "LMF8LUU")
        self.assertEqual(BD.full_designation(lm, "2RS", False), "LM8LUU", "no closure codes")
        self.assertEqual(BD.full_designation(r, "ZZ", True), "FR188ZZ")

    def test_by_height(self):
        hits = BD.search(B=7)
        self.assertIn("608", names(hits))
        self.assertTrue(all(r.B == 7 or r.B_shielded == 7 for _, r in hits))
        self.assertIn(
            "684", names(BD.search(d=4, B=4)), "height matches shielded width (684ZZ = 4)"
        )
