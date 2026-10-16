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

    def test_auto_match_needs_a_standard_size(self):
        self.assertEqual(BD.auto_match("60", 8.0, "Shaft").name, "608")
        self.assertEqual(BD.auto_match("60", 22.004, "Housing").name, "608")
        self.assertIsNone(BD.auto_match("60", 13.0, "Shaft"), "no 60xx has a 13 mm bore")
        e = BD.NoFitError("60", 13.0, "Shaft")
        self.assertEqual(e.what(), "a 13 mm shaft")
        self.assertEqual(e.nearest_text(), "6001 (12 mm bore) or 6002 (15 mm bore)")
        e = BD.NoFitError("62", 29.0, "Housing")
        self.assertEqual(
            str(e),
            "No series 62 bearing fits a 29 mm hole. Nearest: 629 (26 mm OD) or 6200 (30 mm OD)",
        )

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

    def test_angular_follows_62_and_63(self):
        """ISO 15: 72xx / 73xx have the boundary dimensions of 62xx / 63xx."""
        for series, base in (("72", "62"), ("73", "63")):
            rows = BD.load_table(series)
            self.assertTrue(rows)
            for r in rows:
                twin = BD.get_row(base, base + r.name[2:])
                self.assertEqual((r.d, r.D, r.B, r.r), (twin.d, twin.D, twin.B, twin.r), r.name)
                self.assertFalse(r.has_flange)

    def test_derived_series_match_their_source(self):
        """ISO 15 gives 12 / 13 / NU2 / NU3 the dimensions of 62 / 63, NU22 / NU23 those of
        the 22 / 23 table."""
        for series, (source, prefix, min_bore) in BD.DERIVED.items():
            base = {"62": "62", "63": "63", "22": "22", "23": "23"}[source]
            base_series = {"62": "62", "63": "63", "22": "22", "23": "23"}[base]
            for r in BD.load_table(series):
                twin = BD.get_row(base_series, base + r.name[len(prefix) :])
                with self.subTest(row=r.name):
                    self.assertEqual((r.d, r.D, r.B), (twin.d, twin.D, twin.B))
                    self.assertGreaterEqual(r.d, min_bore)

    def test_wide_series_22_23(self):
        """Series 22 / 23 share d and D with 62 / 63 and are wider."""
        for wide, narrow in (("22", "62"), ("23", "63")):
            for r in BD.load_table(wide):
                twin = BD.get_row(narrow, "6" + narrow[1] + r.name[2:])
                self.assertEqual((r.d, r.D), (twin.d, twin.D), r.name)
                self.assertGreater(r.B, twin.B, r.name)

    def test_tapered_table(self):
        for series in ("302", "303", "320"):
            for r in BD.load_table(series):
                with self.subTest(row=r.name):
                    self.assertTrue(r.name.startswith(series))
                    self.assertTrue(r.cup_C < r.cone_B <= r.B, "C < B <= T")
        r = BD.get_row("302", "30204")
        self.assertEqual((r.d, r.D, r.B, r.cone_B, r.cup_C), (20, 47, 15.25, 14, 12))

    def test_needle_tables(self):
        self.assertEqual([r.name for r in BD.load_table("HK")][:2], ["HK0306", "HK0408"])
        hk = BD.get_row("HK", "HK0810")
        self.assertEqual((hk.d, hk.D, hk.B, hk.drawn), (8, 12, 10, True))
        self.assertFalse(BD.get_row("NK", "NK10/16").drawn)
        axk = BD.get_row("AXK", "AXK1528")
        self.assertEqual((axk.d, axk.D, axk.B), (15, 28, 2))

    def test_thrust_table(self):
        rows = BD.load_table("511")
        self.assertEqual(rows[0].name, "51100")
        r = BD.get_row("511", "51104")
        self.assertEqual((r.d, r.D, r.B), (20, 35, 10))
        self.assertTrue(all(0 < x.d < x.D and 0 < x.B < x.D - x.d for x in rows))

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
            "7204B": ("7204", None, False),
            "7204 BEP": ("7204", None, False),
            "51104": ("51104", None, False),
            "NJ204": ("NU204", None, False),
            "NU2205 ECP": ("NU2205", None, False),
            "30204 J2/Q": ("30204", None, False),
            "HK 0810": ("HK0810", None, False),
            "AXK 1528": ("AXK1528", None, False),
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
        ball = {r.name for s, r in BD.search(D=22) if BD.family(s) == "deepgroove"}
        self.assertEqual(ball, {"636", "627", "608", "6900"}, "by OD")
        self.assertIn("HK1612", names(BD.search(D=22)), "needle bearings too")
        self.assertEqual(names(BD.search(name="8x22x7")), ["608"], "size text")
        self.assertIn("6801", names(BD.search(D=22, tol=1)), "tolerance")

    def test_new_families(self):
        self.assertEqual(
            names(BD.search(name="LMK8")), ["LM8UU", "LM8LUU"], "flanged LM, by prefix"
        )
        self.assertEqual(names(BD.search(name="FR188")), ["R188"])
        self.assertEqual(names(BD.search(d=8, D=15)), ["NK8/12", "LM8UU", "LM8LUU"], "by width")

    def test_angular_and_thrust(self):
        self.assertEqual(names(BD.search(name="7204 BEP")), ["7204"])
        self.assertEqual(names(BD.search(name="511", d=20)), ["51104"])
        self.assertEqual(BD.full_designation(BD.get_row("72", "7204"), "ZZ", True), "7204B")
        self.assertEqual(BD.full_designation(BD.get_row("511", "51104"), "2RS", False), "51104")

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
