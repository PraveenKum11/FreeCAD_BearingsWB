# SPDX-License-Identifier: GPL-3.0-or-later
"""Representative geometry for mounted, double-row and stud bearings.

As in BearingGeometry, the shaft axis is Z. Mounted units retain their mounting
footprint and bolt spacing; casting contours, screws and rolling internals are
representative. Dimensions and their sources are kept in BRData, not in this module.
"""

import math

import Part

import BearingData as BD
import BearingGeometry as BG

V = BG.V
STEEL, BALL, SEAL = BG.COLOR_STEEL, BG.COLOR_BALL, BG.COLOR_SEAL
CAST = (0.25, 0.29, 0.28)
GAP = BG.CONTACT_GAP


class DoubleRowInternals:
    def __init__(self, row):
        self.dm = (row.d + row.D) / 2
        self.Dw = min(0.22 * (row.D - row.d), 0.3 * row.B)
        self.Lw = 0.34 * row.B
        self.per_row = BG._count(self.dm / 2, self.Dw, 1.15)
        self.Z = 2 * self.per_row


class CamInternals:
    def __init__(self, row):
        self.Dw = (row.D - row.d) * 0.2
        self.dm = row.d + self.Dw + 2 * GAP
        self.Z = BG._count(self.dm / 2, self.Dw, 1.1)


def internals(row):
    if row.kind in ("doublecylindrical", "spherical"):
        return DoubleRowInternals(row)
    if row.kind == "doubleangular":
        ins = BG.Internals(row.d, row.D, row.B / 2)
        ins.Z *= 2
        return ins
    if row.kind == "housed":
        return BG.Internals(row.d, row.D, row.insert_C)
    return CamInternals(row)


def _array(shape, count):
    parts = []
    for i in range(count):
        copy = shape.copy()
        copy.rotate(V(), V(0, 0, 1), i * 360.0 / count)
        parts.append((copy, BALL))
    return parts


def make_double_cylindrical(row, detail):
    B, ri, ro = row.B, row.d / 2, row.D / 2
    if detail == "Envelope":
        return [(BG._annulus(ri, ro, -B, 0), STEEL)]
    ins = DoubleRowInternals(row)
    rp, rw = ins.dm / 2, ins.Dw / 2
    # NN: three ribs on the inner ring, no ribs on the outer ring.
    inner = BG._annulus(ri, rp - rw, -B, 0)
    t = 0.08 * B
    for lo, hi in ((-B, -B + t), (-B / 2 - t / 2, -B / 2 + t / 2), (-t, 0)):
        inner = inner.fuse(BG._annulus(ri, rp - 0.2 * rw, lo, hi))
    parts = [(inner.removeSplitter(), STEEL), (BG._annulus(rp + rw, ro, -B, 0), STEEL)]
    for z in (-0.75 * B, -0.25 * B):
        roller = Part.makeCylinder(rw - GAP, ins.Lw, V(rp, 0, z - ins.Lw / 2))
        parts += _array(roller, ins.per_row)
    return parts


def make_spherical(row, detail):
    B, ri, ro = row.B, row.d / 2, row.D / 2
    if detail == "Envelope":
        return [(BG._annulus(ri, ro, -B, 0), STEEL)]
    ins = DoubleRowInternals(row)
    rp, rw, half = ins.dm / 2, ins.Dw / 2, ins.Lw / 2
    a = 0.24 * B
    rho = math.hypot(rp, a)
    radius = rho + rw
    outer = BG._annulus(ri, ro, -B, 0).cut(Part.makeSphere(radius, V(0, 0, -B / 2)))
    # Barrel cross-section: the rolling surface is an arc of the outer race sphere.
    end = math.sqrt(radius**2 - half**2) - rho
    barrel = BG.revolve(
        [
            ("p", 0, -half, 0),
            ("p", end - GAP, -half, 0),
            ("a", rw - GAP, 0),
            ("p", end - GAP, half, 0),
            ("p", 0, half, 0),
        ]
    )
    profile = [("p", ri, -B, 0), ("p", rp - rw, -B, 0)]
    rollers = []
    for offset in (-a, a):
        theta = math.atan2(offset, rp)
        # Sample the inner flank of the barrel to form its matching inner raceway.
        for i in range(17):
            s = -half + ins.Lw * i / 16
            w = math.sqrt(radius**2 - s**2) - rho
            x = rp - math.cos(theta) * w - math.sin(theta) * s - GAP
            z = -B / 2 + offset - math.sin(theta) * w + math.cos(theta) * s
            profile.append(("p", x, z, 0))
        roller = barrel.copy()
        roller.rotate(V(), V(0, 1, 0), -math.degrees(theta))
        roller.translate(V(rp, 0, -B / 2 + offset))
        rollers += _array(roller, ins.per_row)
    profile += [("p", rp - rw, 0, 0), ("p", ri, 0, 0)]
    return [(BG.revolve(profile), STEEL), (outer, STEEL)] + rollers


def make_double_angular(row, detail):
    if detail == "Envelope":
        return [(BG._annulus(row.d / 2, row.D / 2, -row.B, 0), STEEL)]
    # Two opposing angular-contact rows, joined outer ring and split inner ring.
    half = BD.AngularRow(row.name + "_half", row.d, row.D, (row.B - GAP) / 2, 0)
    top = BG.make_deep_groove(half, "RS", False, detail, angular=True)
    bottom = []
    for shape, color in top:
        s = shape.copy()
        s.rotate(V(), V(1, 0, 0), 180)
        s.translate(V(0, 0, -row.B))
        bottom.append((s, color))
    # Keep the split inner races; a small bridge makes the two outer halves one ring.
    outer_index = 1
    bridge = BG._annulus(
        row.D / 2 - 0.02 * (row.D - row.d), row.D / 2, -row.B / 2 - GAP, -row.B / 2 + GAP
    )
    outer = top[outer_index][0].fuse(bottom[outer_index][0]).fuse(bridge).removeSplitter()
    parts = [p for i, p in enumerate(top + bottom) if i not in (1, len(top) + 1)] + [(outer, STEEL)]
    ins = BG.Internals(row.d, row.D, half.B)
    for z in (-row.B + 0.02 * half.B, -0.04 * half.B):
        parts.append(
            (
                BG._annulus(
                    ins.dm / 2 - 0.48 * ins.Dw + GAP, ins.x_land - GAP, z, z + 0.02 * half.B
                ),
                SEAL,
            )
        )
    return parts


def _slot(x, y, z, diameter, length, depth):
    """Pillow-block mounting slot along X, extruded along Y."""
    delta = (length - diameter) / 2
    a = Part.makeCylinder(diameter / 2, depth, V(x - delta, y, z), V(0, 1, 0))
    b = Part.makeCylinder(diameter / 2, depth, V(x + delta, y, z), V(0, 1, 0))
    if delta <= 0:
        return a
    bridge = Part.makeBox(2 * delta, depth, diameter, V(x - delta, y, z - diameter / 2))
    return a.fuse(b).fuse(bridge)


def make_housed(row, detail):
    B, L, A, ri = row.B, row.L, row.A, row.d / 2
    if row.style == "pillow":
        # The shaft centre is the origin in XY; the mounting face is y=-H.
        base = Part.makeBox(L, row.foot, A, V(-L / 2, -row.H, -B))
        radius = row.H2 - row.H
        boss = Part.makeCylinder(radius, A * 0.75, V(0, 0, -B + A * 0.125))
        web = Part.makeBox(
            2 * radius, row.H - row.foot, A * 0.75, V(-radius, -row.H + row.foot, -B + A * 0.125)
        )
        housing = base.fuse(boss).fuse(web)
        for x in (-row.J / 2, row.J / 2):
            housing = housing.cut(_slot(x, -row.H - 1, -B / 2, row.hole, row.slot, row.foot + 2))
        centre_z = -B / 2
    else:
        if row.style == "square":
            base = Part.makeBox(L, row.H, row.foot, V(-L / 2, -row.H / 2, -B))
            holes = [(x, y) for x in (-row.J / 2, row.J / 2) for y in (-row.J / 2, row.J / 2)]
        else:
            # Polygonal shoulders and circular bolt pads preserve L, H and J.
            pad = (L - row.J) / 2
            points = [
                V(-row.J / 2, -pad, -B),
                V(0, -row.H / 2, -B),
                V(row.J / 2, -pad, -B),
                V(row.J / 2, pad, -B),
                V(0, row.H / 2, -B),
                V(-row.J / 2, pad, -B),
            ]
            face = Part.Face(Part.makePolygon(points + [points[0]]))
            base = face.extrude(V(0, 0, row.foot))
            holes = [(-row.J / 2, 0), (row.J / 2, 0)]
            for x, y in holes:
                base = base.fuse(Part.makeCylinder(pad, row.foot, V(x, y, -B)))
        boss = Part.makeCylinder(
            row.H / 2 if row.style == "oval" else row.D / 2 + 8, A, V(0, 0, -B)
        )
        housing = base.fuse(boss)
        for x, y in holes:
            housing = housing.cut(Part.makeCylinder(row.hole / 2, B + 2, V(x, y, -B - 1)))
        centre_z = -row.insert_B / 2
    # Spherical insert and seat permit alignment. Keep a visible clearance at the seat.
    sphere = Part.makeSphere(row.D / 2 + GAP, V(0, 0, centre_z))
    housing = housing.cut(sphere).cut(Part.makeCylinder(ri + GAP, B + 2, V(0, 0, -B - 1)))
    insert_row = BD.BearingRow(row.name + "_insert", row.d, row.D, row.insert_C, 0)
    if detail == "Envelope":
        insert = Part.makeCylinder(
            row.D / 2, row.insert_C, V(0, 0, centre_z - row.insert_C / 2)
        ).common(Part.makeSphere(row.D / 2, V(0, 0, centre_z)))
        # Fuse a seat-filling envelope so this detail is one solid.
        filling = Part.makeCylinder(
            row.D / 2 + 2 * GAP, row.insert_C, V(0, 0, centre_z - row.insert_C / 2)
        )
        collar = Part.makeCylinder(
            ri + 0.18 * (row.D - row.d), row.insert_B, V(0, 0, centre_z - row.insert_B / 2)
        )
        solid = housing.fuse(insert).fuse(filling).fuse(collar)
        solid = solid.cut(Part.makeCylinder(ri, B + 2, V(0, 0, -B - 1)))
        return [(solid.removeSplitter(), CAST)]
    parts = BG.make_deep_groove(insert_row, "2RS", False, detail)
    shifted = []
    for i, (shape, color) in enumerate(parts):
        shape.translate(V(0, 0, centre_z + row.insert_C / 2))
        if i == 1:  # the outer ring has a spherical outside
            shape = shape.common(Part.makeSphere(row.D / 2, V(0, 0, centre_z)))
        if i == 0:  # extended inner ring
            ins = BG.Internals(row.d, row.D, row.insert_C)
            collar = BG._annulus(
                ri,
                min(ri + 0.12 * (row.D - row.d), ins.dm / 2 - ins.Dw / 2 - GAP),
                centre_z - row.insert_B / 2,
                centre_z + row.insert_B / 2,
            )
            shape = shape.fuse(collar).removeSplitter()
        shifted.append((shape, color))
    return [(housing.removeSplitter(), CAST)] + shifted


def make_cam_follower(row, detail):
    ri, ro, B, h = row.d / 2, row.D / 2, row.B, row.head_width
    stud = Part.makeCylinder(ri, B, V(0, 0, -B))
    if detail == "Envelope":
        return [(stud.fuse(Part.makeCylinder(ro, h, V(0, 0, -h))).removeSplitter(), STEEL)]
    ins = CamInternals(row)
    rp, rw = ins.dm / 2, ins.Dw / 2
    core = stud.fuse(Part.makeCylinder(rp, 0.5, V(0, 0, -0.5)))
    core = core.fuse(Part.makeCylinder(rp, B - row.stud_length - h, V(0, 0, -B + row.stud_length)))
    outer = BG._annulus(rp + rw + GAP, ro, -h, 0)
    parts = [(core.removeSplitter(), STEEL), (outer, STEEL)]
    parts += _array(Part.makeCylinder(rw - GAP, h - 1.2, V(rp, 0, -h + 0.6)), ins.Z)
    for z in (-h + 0.05, -0.45):
        parts.append((BG._annulus(ri + GAP, rp + rw, z, z + 0.4).cut(core), SEAL))
    return parts


BUILDERS = {
    "spherical": make_spherical,
    "doublecylindrical": make_double_cylindrical,
    "doubleangular": make_double_angular,
    "housed": make_housed,
    "camfollower": make_cam_follower,
}
