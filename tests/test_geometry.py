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


# families whose Detailed level adds a cage (the others: Detailed is Standard)
WITH_CAGE = ("deepgroove", "angular", "thrust")


def expected_solids(row, closure, detail, variant=None):
    if detail == "Envelope":
        return 1
    kind = BD.kind(row)
    z = BG.internals(row).Z if kind not in ("deepgroove", "angular") else 0
    if kind in ("selfaligning", "cylindrical", "tapered"):
        return 2 + z  # inner and outer ring, rolling elements
    if kind == "needle":
        return 1 + z  # the cup / ring and the needles
    if kind == "axk":
        return 1 + z + (2 if variant == "AXK + 2 AS" else 0)  # cage, needles, washers
    if BD.is_linear(row):
        # sleeve, two seals, retainer; Detailed adds the balls
        return 4 + (BG.internals(row).Z if detail == "Detailed" else 0)
    if getattr(row, "is_thrust", False):
        return 2 + BG.internals(row).Z  # two washers and the balls
    top, bottom = BG._closure_sides(closure)
    return 2 + int(top) + int(bottom) + BG.Internals(row.d, row.D, row.B).Z


class AllShapes(unittest.TestCase):
    """Every table row x closure x flange x detail level.

    Detailed (the cage boolean) runs only on the smallest, a middle and the largest row
    of each series, to keep the suite fast.
    """

    def check_shape(self, row, closure, flanged, detail, flange_shape="Round", variant=None):
        shape, colors = BG.build(row, closure, flanged, detail, flange_shape, variant)
        self.assertTrue(shape.isValid(), "invalid shape")
        self.assertEqual(len(colors), len(shape.Faces), "color count")
        bb = tight_bb(shape)
        od = (row.K if flange_shape == "Square" else row.D1) if flanged else row.D
        B = row.width(closure) + (2 * BD.AS_WASHER if variant == "AXK + 2 AS" else 0)
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
        # thrust bearings: the outside is the top (housing) washer, not the ball gap
        z_out = -BG.internals(row).washer / 2 if getattr(row, "is_thrust", False) else -B / 2
        self.assertTrue(
            shape.isInside(V(row.D / 2 * 0.99, 0, z_out), 1e-7, True), "outer ring missing"
        )
        n = expected_solids(row, closure, detail, variant)
        if detail == "Detailed" and BD.kind(row) in WITH_CAGE:
            self.assertGreaterEqual(len(shape.Solids), n + 1, "solids (with cage)")
        else:
            self.assertEqual(len(shape.Solids), n, "solids")

    def test_all_shapes(self):
        for series in BD.SERIES:
            rows = BD.load_table(series)
            sample = {rows[0].name, rows[len(rows) // 2].name, rows[-1].name}
            linear = BD.family(series) == "linear"
            closures = (
                ("Open",) if BD.family(series) in BD.NO_CLOSURES else ("Open", "ZZ", "2RS", "Z")
            )
            for row in rows:
                variants = [(False, "Round", v) for v in BD.VARIANTS.get(BD.family(series), [None])]
                if row.has_flange:
                    shapes = BD.FLANGE_SHAPES if linear else ["Round"]
                    variants += [(True, s, None) for s in shapes]
                for flanged, shape, variant in variants:
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
                                variant=variant,
                                detail=detail,
                            ):
                                self.check_shape(row, closure, flanged, detail, shape, variant)

    def test_no_overlap(self):
        for series, name in (
            ("LM", "LM8UU"),
            ("LM", "LM20LUU"),
            ("R", "R188"),
            ("72", "7204"),
            ("511", "51104"),
            ("511", "51120"),
            ("12", "1205"),
            ("23", "2310"),
            ("NU2", "NU204"),
            ("302", "30204"),
            ("303", "30320"),
            ("320", "32010"),
            ("HK", "HK0810"),
            ("NK", "NK20/16"),
            ("AXK", "AXK1528"),
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

    def test_no_shared_faces(self):
        """Separate parts touch at most at a point or line (balls on raceways): coincident
        faces flicker in section views, so shields, seals, retainers and cage segments
        keep CONTACT_GAP from their neighbours."""
        for series, name, closure, flanged, shape in (
            ("60", "608", "ZZ", False, "Round"),
            ("60", "608", "2RS", False, "Round"),
            ("68", "688", "Z", True, "Round"),
            ("MR", "MR105", "RS", False, "Round"),
            ("R", "R188", "2RS", False, "Round"),
            ("69", "6920", "ZZ", False, "Round"),
            ("72", "7204", "Open", False, "Round"),
            ("511", "51104", "Open", False, "Round"),
            ("LM", "LM8UU", "Open", False, "Round"),
            ("LM", "LM8UU", "Open", True, "Square"),
            ("LM", "LM20LUU", "Open", False, "Round"),
        ):
            with self.subTest(bearing=name, closure=closure, flanged=flanged):
                row = BD.get_row(series, name)
                solids = BG.build(row, closure, flanged, "Detailed", shape)[0].Solids
                shared = 0.0
                for i in range(len(solids)):
                    for j in range(i + 1, len(solids)):
                        a, b = solids[i], solids[j]
                        if not a.BoundBox.intersect(b.BoundBox) or a.distToShape(b)[0] > 1e-7:
                            continue
                        shared += sum(
                            fa.common(fb).Area
                            for fa in a.Faces
                            for fb in b.Faces
                            if fa.BoundBox.intersect(fb.BoundBox)
                        )
                self.assertLess(shared, 1e-6, "parts share %.3f mm² of faces" % shared)
