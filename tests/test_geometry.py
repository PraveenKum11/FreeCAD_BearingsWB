# SPDX-License-Identifier: GPL-3.0-or-later
"""Computed internals and standard bearing shapes (BearingGeometry)."""

import math
import unittest

import BearingData as BD
import BearingGeometry as BG
from testutil import V, close, tight_bb


class Internals(unittest.TestCase):
    def test_608(self):
        i = BG.Internals(8, 22, 7)
        self.assertEqual(i.Z, 7)
        self.assertTrue(close(i.Dw, 4.0), i.Dw)

    def test_6204(self):
        i = BG.Internals(20, 47, 14)
        self.assertEqual(i.Z, 8)
        self.assertTrue(close(i.Dw, 8.0), i.Dw)


def expected_solids(row, closure, detail):
    if detail == "Envelope":
        return 1
    if BD.is_linear(row):
        return 3 + BG.internals(row).Z  # sleeve, two seals, balls
    top, bottom = BG._closure_sides(closure)
    return 2 + int(top) + int(bottom) + BG.Internals(row.d, row.D, row.B).Z


class AllShapes(unittest.TestCase):
    """Every table row x closure x flange x detail level.

    Detailed (the cage boolean) runs only on the smallest, a middle and the largest row
    of each series, to keep the suite fast.
    """

    def check_shape(self, row, closure, flanged, detail, flange_shape="Round"):
        shape, colors = BG.build(row, closure, flanged, detail, flange_shape)
        self.assertTrue(shape.isValid(), "invalid shape")
        self.assertEqual(len(colors), len(shape.Faces), "color count")
        bb = tight_bb(shape)
        od = (row.K if flange_shape == "Square" else row.D1) if flanged else row.D
        B = row.width(closure)
        self.assertTrue(
            close(bb.XLength, od, 0.01) and close(bb.YLength, od, 0.01),
            "diameter %.3f != %.3f" % (bb.XLength, od),
        )
        self.assertTrue(
            close(bb.ZMax, 0, 0.01) and close(bb.ZMin, -B, 0.01),
            "z range [%.3f, %.3f] != [-%g, 0]" % (bb.ZMin, bb.ZMax, B),
        )
        probes = [
            V(row.d / 2 * 0.99, 0, -B / 2),
            V(0, -row.d / 2 * 0.99, -0.01 * B),
            V(0, 0, -B / 2),
        ]
        self.assertFalse(any(shape.isInside(p, 1e-7, True) for p in probes), "bore obstructed")
        self.assertTrue(
            shape.isInside(V(row.D / 2 * 0.99, 0, -B / 2), 1e-7, True), "outer ring missing"
        )
        n = expected_solids(row, closure, detail)
        if detail == "Detailed" and not BD.is_linear(row):
            self.assertGreaterEqual(len(shape.Solids), n + 1, "solids (with cage)")
        else:
            self.assertEqual(len(shape.Solids), n, "solids")

    def test_all_shapes(self):
        for series in BD.SERIES:
            rows = BD.load_table(series)
            sample = {rows[0].name, rows[len(rows) // 2].name, rows[-1].name}
            linear = BD.family(series) == "linear"
            closures = ("Open",) if linear else ("Open", "ZZ", "2RS", "Z")
            for row in rows:
                variants = [(False, "Round")]
                if row.has_flange:
                    variants += [(True, s) for s in (BD.FLANGE_SHAPES if linear else ["Round"])]
                for flanged, shape in variants:
                    for closure in closures:
                        for detail in BG.DETAIL_LEVELS:
                            if detail == "Detailed" and row.name not in sample:
                                continue
                            with self.subTest(
                                series=series,
                                row=row.name,
                                closure=closure,
                                flanged=flanged,
                                shape=shape,
                                detail=detail,
                            ):
                                self.check_shape(row, closure, flanged, detail, shape)

    def test_no_overlap(self):
        for series, name in (
            ("LM", "LM8UU"),
            ("LM", "LM20LUU"),
            ("R", "R188"),
            ("60", "608"),
            ("62", "6204"),
            ("68", "688"),
            ("MR", "MR63"),
            ("69", "6920"),
        ):
            with self.subTest(bearing=name):
                row = BD.get_row(series, name)
                solids = BG.build(row, "2RS", False, "Detailed")[0].Solids
                worst = 0.0
                for i in range(len(solids)):
                    for j in range(i + 1, len(solids)):
                        if solids[i].BoundBox.intersect(solids[j].BoundBox):
                            worst = max(worst, solids[i].common(solids[j]).Volume)
                ball_vol = math.pi / 6 * BG.internals(row).Dw ** 3
                self.assertLess(
                    worst, 1e-4 * ball_vol, "parts overlap, worst common volume %.2e" % worst
                )
