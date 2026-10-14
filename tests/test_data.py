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

    def test_by_height(self):
        hits = BD.search(B=7)
        self.assertIn("608", names(hits))
        self.assertTrue(all(r.B == 7 or r.B_shielded == 7 for _, r in hits))
        self.assertIn(
            "684", names(BD.search(d=4, B=4)), "height matches shielded width (684ZZ = 4)"
        )
