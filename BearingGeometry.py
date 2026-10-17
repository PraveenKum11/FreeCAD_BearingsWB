# SPDX-License-Identifier: GPL-3.0-or-later
"""Computed internals and Part shapes for rolling bearings.

Local frame: bearing axis is +Z, the bearing occupies z in [-B, 0] and the flange
(if any) sits at z in [-C1, 0]. Rings are made by revolving 2D profiles that already
contain the raceway grooves, so only the cage needs a boolean.

Linear ball bushings use the same frame (length B along Z, flange at the top end). Their
sleeve is a revolved profile too; only a square flange and the flange bolt holes need
booleans.
"""

import math

import FreeCAD
import Part

V = FreeCAD.Vector

DETAIL_LEVELS = ["Envelope", "Standard", "Detailed"]

# ISO 3290 metric balls plus common inch fractions, mm
STANDARD_BALLS = sorted(
    {
        0.3,
        0.4,
        0.5,
        0.6,
        0.635,
        0.7,
        0.8,
        1.0,
        1.2,
        1.5,
        1.588,
        2.0,
        2.381,
        2.5,
        3.0,
        3.175,
        3.5,
        3.969,
        4.0,
        4.5,
        4.762,
        5.0,
        5.556,
        6.0,
        6.35,
        7.0,
        7.144,
        7.938,
        8.0,
        8.731,
        9.0,
        9.525,
        10.0,
        11.112,
        11.906,
        12.0,
        12.7,
        13.494,
        14.0,
        14.288,
        15.081,
        15.875,
        16.0,
        16.669,
        17.462,
        18.0,
        19.05,
        20.0,
        20.638,
        22.225,
        23.812,
        25.4,
        26.988,
        28.575,
        30.0,
        31.75,
    }
)

COLOR_STEEL = (0.76, 0.77, 0.80)
COLOR_BALL = (0.86, 0.87, 0.90)
COLOR_CAGE = (0.80, 0.62, 0.25)
COLOR_SHIELD = (0.60, 0.61, 0.64)
COLOR_SEAL = (0.12, 0.12, 0.12)
COLOR_RETAINER = (0.22, 0.23, 0.26)  # plastic ball retainer of a linear bushing

# Gap left between parts that would otherwise share a face (a shield in its seat, a seal
# against the sleeve, neighbouring cage segments). Coincident faces of separate solids
# flicker in section and clipping views; 0.01 mm is invisible but keeps them apart.
CONTACT_GAP = 0.01


class Internals:
    """Computed internal geometry of a deep groove ball bearing."""

    def __init__(self, d, D, B):
        wall = (D - d) / 2.0
        self.dm = (d + D) / 2.0
        target = min(0.6 * wall, 0.7 * B)
        fitting = [b for b in STANDARD_BALLS if b <= target + 1e-9]
        self.Dw = fitting[-1] if fitting else round(target, 3)
        # adjacent balls must not touch: chord dm*sin(pi/Z) > Dw (with 2% margin)
        z_max = int(math.floor(math.pi / math.asin(min(1.0, 1.02 * self.Dw / self.dm))))
        self.Z = max(3, min(z_max, max(5, int(round(0.6 * math.pi * self.dm / self.Dw)))))
        self.r_groove_in = 0.515 * self.Dw
        self.r_groove_out = 0.525 * self.Dw
        self.x_shoulder = self.dm / 2 - 0.3 * self.Dw  # inner ring outer surface
        self.x_land = self.dm / 2 + 0.3 * self.Dw  # outer ring inner surface
        self.recess = 0.15 * self.Dw  # shield seat in the outer ring


def _closure_dims(closure, B):
    """Return (thickness, inset) for a shield/seal, or None if open."""
    if closure in ("Z", "ZZ"):
        return min(max(0.04 * B, 0.1), 1.0), max(0.03 * B, 0.03)
    if closure in ("RS", "2RS"):
        return min(max(0.1 * B, 0.2), 2.0), max(0.02 * B, 0.02)
    return None


def _closure_sides(closure):
    """(top, bottom) flags. A single closure sits on the top face (z = 0)."""
    if closure in ("Z", "RS"):
        return True, False
    if closure in ("ZZ", "2RS"):
        return True, True
    return False, False


def _cage_segment(face, x0, n):
    """One of n cage segments: the profile face revolved over its pitch, centred on the
    x axis, a CONTACT_GAP short of its neighbours at the inner radius x0."""
    gap = math.degrees(CONTACT_GAP / x0)
    face.rotate(V(0, 0, 0), V(0, 0, 1), -180.0 / n + gap / 2)
    return Part.Solid(face.revolve(V(0, 0, 0), V(0, 0, 1), 360.0 / n - gap))


def _xz(x, z):
    return V(x, 0, z)


def _profile_face(items):
    """Build a closed planar face in the XZ plane.

    items: ('p', x, z, fillet_r) corner points and ('a', x, z) arc mid points. An 'a'
    item makes the segment between its neighbouring points an arc through (x, z).
    A fillet is applied only where both adjacent segments are straight.
    """
    n = len(items)
    entry, exit_, fillet_arc = {}, {}, {}
    for i, it in enumerate(items):
        if it[0] != "p":
            continue
        p = _xz(it[1], it[2])
        entry[i] = exit_[i] = p
        r = it[3]
        prv, nxt = items[i - 1], items[(i + 1) % n]
        if r <= 0 or prv[0] != "p" or nxt[0] != "p":
            continue
        a, c = _xz(prv[1], prv[2]), _xz(nxt[1], nxt[2])
        la, lc = (a - p).Length, (c - p).Length
        u1, u2 = (a - p).normalize(), (c - p).normalize()
        theta = math.acos(max(-1.0, min(1.0, u1.dot(u2))))
        if theta < 1e-6 or theta > math.pi - 1e-6:
            continue
        # keep the trimmed points on the edges (leave room for the neighbour's fillet)
        r = min(r, 0.45 * min(la, lc) * math.tan(theta / 2))
        t = r / math.tan(theta / 2)
        bis = (u1 + u2).normalize()
        center = p + bis * (r / math.sin(theta / 2))
        entry[i] = p + u1 * t
        exit_[i] = p + u2 * t
        fillet_arc[i] = center - bis * r

    edges = []
    for i, it in enumerate(items):
        if it[0] != "p":
            continue
        if i in fillet_arc:
            edges.append(Part.Arc(entry[i], fillet_arc[i], exit_[i]).toShape())
        j = (i + 1) % n
        if items[j][0] == "p":
            if (entry[j] - exit_[i]).Length > 1e-9:
                edges.append(Part.LineSegment(exit_[i], entry[j]).toShape())
        else:
            k = (j + 1) % n
            mid = _xz(items[j][1], items[j][2])
            edges.append(Part.Arc(exit_[i], mid, entry[k]).toShape())
    return Part.Face(Part.Wire(edges))


def revolve(items):
    """Solid of revolution about Z of a _profile_face() profile in the XZ plane."""
    face = _profile_face(items)
    return Part.Solid(face.revolve(V(0, 0, 0), V(0, 0, 1), 360))


def _annulus(x_in, x_out, z0, z1):
    return revolve(
        [("p", x_in, z0, 0), ("p", x_out, z0, 0), ("p", x_out, z1, 0), ("p", x_in, z1, 0)]
    )


def _outer_top(row, flanged, r):
    """Profile points for the OD side going up to z = 0 (with or without flange)."""
    R = row.D / 2
    if flanged:
        rf = min(r, 0.3 * row.C1)
        return [("p", R, -row.C1, 0), ("p", row.D1 / 2, -row.C1, rf), ("p", row.D1 / 2, 0, rf)]
    return [("p", R, 0, r)]


def make_envelope(row, closure, flanged):
    B = row.width(closure)
    r = row.r
    items = [("p", row.d / 2, -B, r), ("p", row.D / 2, -B, r)]
    items += _outer_top(row, flanged, r)
    items += [("p", row.d / 2, 0, r)]
    return [(revolve(items), COLOR_STEEL)]


def make_deep_groove(row, closure, flanged, detail, angular=False):
    """Return a list of (solid, rgb) for a deep groove ball bearing.

    `angular`: an angular contact bearing (72xx B / 73xx B, 40°) instead: each ring has a
    high shoulder on one side and a low one on the other (outer ring high at the top,
    inner ring high at the bottom), so it carries axial load from the top. No closures.
    """
    if angular:
        closure, flanged = "Open", False
    if detail == "Envelope":
        return make_envelope(row, closure, flanged)

    B = row.width(closure)
    ins = Internals(row.d, row.D, row.B)
    Dw, dm = ins.Dw, ins.dm
    zc = -B / 2
    r = row.r
    xs, xl = ins.x_shoulder, ins.x_land
    top, bottom = _closure_sides(closure)
    cdims = _closure_dims(closure, B)
    sd = (cdims[0] + cdims[1]) if cdims else 0.0  # depth of the shield seat
    rec = ins.recess

    # shoulder radii, bottom and top: equal for a deep groove bearing
    xs_b = xs_t = xs
    xl_b = xl_t = xl
    if angular:
        xs_t = dm / 2 - 0.48 * Dw  # low inner shoulder at the top, almost at the ball
        xl_b = dm / 2 + 0.48 * Dw  # low outer shoulder at the bottom

    # inner ring with raceway
    xc_in = dm / 2 - Dw / 2 + ins.r_groove_in
    h_in_b = math.sqrt(ins.r_groove_in**2 - (xc_in - xs_b) ** 2)
    h_in_t = math.sqrt(ins.r_groove_in**2 - (xc_in - xs_t) ** 2)
    rb = min(r, 0.4 * (xs_t - row.d / 2))
    inner = revolve(
        [
            ("p", row.d / 2, -B, rb),
            ("p", xs_b, -B, 0),
            ("p", xs_b, zc - h_in_b, 0),
            ("a", dm / 2 - Dw / 2, zc),
            ("p", xs_t, zc + h_in_t, 0),
            ("p", xs_t, 0, 0),
            ("p", row.d / 2, 0, rb),
        ]
    )

    # outer ring with raceway and shield seats
    xc_out = dm / 2 + Dw / 2 - ins.r_groove_out
    h_out_t = math.sqrt(ins.r_groove_out**2 - (xl_t - xc_out) ** 2)
    h_out_b = math.sqrt(ins.r_groove_out**2 - (xl_b - xc_out) ** 2)
    ro = min(r, 0.4 * (row.D / 2 - xl_b - rec))
    items = [("p", xl_b + rec if bottom else xl_b, -B, 0), ("p", row.D / 2, -B, ro)]
    items += _outer_top(row, flanged, ro)
    if top:
        items += [("p", xl_t + rec, 0, 0), ("p", xl_t + rec, -sd, 0), ("p", xl_t, -sd, 0)]
    else:
        items += [("p", xl_t, 0, 0)]
    items += [
        ("p", xl_t, zc + h_out_t, 0),
        ("a", dm / 2 + Dw / 2, zc),
        ("p", xl_b, zc - h_out_b, 0),
    ]
    if bottom:
        items += [("p", xl_b, -B + sd, 0), ("p", xl_b + rec, -B + sd, 0)]
    outer = revolve(items)

    parts = [(inner, COLOR_STEEL), (outer, COLOR_STEEL)]

    # balls
    ball = Part.makeSphere(Dw / 2, V(dm / 2, 0, zc))
    for k in range(ins.Z):
        b = ball.copy()
        b.rotate(V(0, 0, 0), V(0, 0, 1), 360.0 * k / ins.Z)
        parts.append((b, COLOR_BALL))

    # shields / seals
    if cdims:
        t, inset = cdims
        seal = closure in ("RS", "2RS")
        x_in = xs + (0.02 if seal else 0.15) * (xl - xs)
        color = COLOR_SEAL if seal else COLOR_SHIELD
        # clear of the seat's wall and shoulder in the outer ring
        x_out, t = xl + rec - CONTACT_GAP, t - CONTACT_GAP
        if top:
            parts.append((_annulus(x_in, x_out, -inset - t, -inset), color))
        if bottom:
            parts.append((_annulus(x_in, x_out, -B + inset, -B + inset + t), color))

    # ribbon cage with spherical pockets: cut one pocket from one pitch segment and
    # pattern it (about 8x faster than cutting all pockets from a full ring)
    if detail == "Detailed":
        wc = min(1.3 * Dw, B - 2 * sd - 0.1 * B)
        x0, x1 = dm / 2 - 0.1 * Dw, dm / 2 + 0.1 * Dw
        face = _profile_face(
            [
                ("p", x0, zc - wc / 2, 0),
                ("p", x1, zc - wc / 2, 0),
                ("p", x1, zc + wc / 2, 0),
                ("p", x0, zc + wc / 2, 0),
            ]
        )
        segment = _cage_segment(face, x0, ins.Z)
        segment = segment.cut(Part.makeSphere(0.52 * Dw, V(dm / 2, 0, zc)))
        for k in range(ins.Z):
            for s in segment.Solids:
                c = s.copy()
                c.rotate(V(0, 0, 0), V(0, 0, 1), 360.0 * k / ins.Z)
                parts.append((c, COLOR_CAGE))

    return parts


# ---------------------------------------------------------------- thrust bearings


class ThrustInternals:
    """Computed internals of a single direction thrust ball bearing (511xx).

    Two washers with a ball groove each: the shaft washer (bottom, bore d, a little under
    D outside) and the housing washer (top, outside D, bore a little over d), with the
    balls on the pitch circle between them. Same attribute names as Internals."""

    def __init__(self, row):
        d, D, H = row.d, row.D, row.B
        self.dm = (d + D) / 2
        target = min(0.55 * H, 0.4 * (D - d))
        fitting = [b for b in STANDARD_BALLS if b <= target + 1e-9]
        self.Dw = fitting[-1] if fitting else round(target, 3)
        z_max = int(math.floor(math.pi / math.asin(min(1.0, 1.15 * self.Dw / self.dm))))
        self.Z = max(6, z_max)
        self.groove = 0.2 * self.Dw  # groove depth in each washer
        self.washer = H / 2 - (self.Dw / 2 - self.groove)  # washer thickness
        self.r_groove = 0.53 * self.Dw
        clearance = max(0.2, 0.02 * D)
        self.shaft_washer_od = D - 2 * clearance
        self.housing_washer_bore = d + 2 * clearance


def _thrust_washer(row, ins, top):
    """Washer profile with its ball groove: housing washer at the top, shaft washer at
    the bottom."""
    H, zc, Dw = row.B, -row.B / 2, ins.Dw
    r_in = (ins.housing_washer_bore if top else row.d) / 2
    r_out = (row.D if top else ins.shaft_washer_od) / 2
    sign = 1 if top else -1
    z_face = zc + sign * (Dw / 2 - ins.groove)  # face toward the balls
    z_back = 0.0 if top else -H
    z_center = zc + sign * (Dw / 2 - ins.r_groove)  # groove arc center
    w = math.sqrt(ins.r_groove**2 - (z_face - z_center) ** 2)
    x = ins.dm / 2
    r = min(row.r, 0.3 * ins.washer)
    return revolve(
        [
            ("p", r_in, z_back, r),
            ("p", r_out, z_back, r),
            ("p", r_out, z_face, 0),
            ("p", x + w, z_face, 0),
            ("a", x, zc + sign * Dw / 2),
            ("p", x - w, z_face, 0),
            ("p", r_in, z_face, 0),
        ]
    )


def make_thrust(row, detail):
    """Return a list of (solid, rgb) for a single direction thrust ball bearing.

    Envelope: one ring d x D x H. Standard: both washers and the balls. Detailed: adds a
    flat cage with a pocket for each ball."""
    H = row.B
    if detail == "Envelope":
        return [(_annulus(row.d / 2, row.D / 2, -H, 0), COLOR_STEEL)]
    ins = ThrustInternals(row)
    zc, Dw, dm = -H / 2, ins.Dw, ins.dm
    parts = [
        (_thrust_washer(row, ins, False), COLOR_STEEL),
        (_thrust_washer(row, ins, True), COLOR_STEEL),
    ]
    ball = Part.makeSphere(Dw / 2, V(dm / 2, 0, zc))
    for k in range(ins.Z):
        b = ball.copy()
        b.rotate(V(0, 0, 0), V(0, 0, 1), 360.0 * k / ins.Z)
        parts.append((b, COLOR_BALL))
    if detail == "Detailed":
        # flat cage in the gap between the washers, one pocket per ball (one segment,
        # patterned, as for the radial bearings)
        gap = 2 * (Dw / 2 - ins.groove)
        tc = 0.5 * gap
        # radially within both washers
        x0 = max(dm / 2 - 0.65 * Dw, ins.housing_washer_bore / 2 + 0.05 * Dw)
        x1 = min(dm / 2 + 0.65 * Dw, ins.shaft_washer_od / 2 - 0.05 * Dw)
        face = _profile_face(
            [
                ("p", x0, zc - tc / 2, 0),
                ("p", x1, zc - tc / 2, 0),
                ("p", x1, zc + tc / 2, 0),
                ("p", x0, zc + tc / 2, 0),
            ]
        )
        segment = _cage_segment(face, x0, ins.Z)
        segment = segment.cut(Part.makeSphere(0.52 * Dw, V(dm / 2, 0, zc)))
        for k in range(ins.Z):
            for s_ in segment.Solids:
                c = s_.copy()
                c.rotate(V(0, 0, 0), V(0, 0, 1), 360.0 * k / ins.Z)
                parts.append((c, COLOR_CAGE))
    return parts


# ---------------------------------------------------------------- v0.4 bearing types
# Self-aligning ball, cylindrical roller, tapered roller, needle roller and axial needle
# bearings. Envelope is always one ring d x D x B. Their cages are not modelled:
# Detailed is the same as Standard.

NEEDLES = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0]  # common needle roller diameters


def _largest(sizes, limit, fallback):
    fitting = [x for x in sizes if x <= limit + 1e-9]
    return fitting[-1] if fitting else round(fallback, 3)


def _count(pitch_radius, size, spacing):
    """Most rolling elements of `size` around a circle with the given spacing factor."""
    return max(
        3, int(math.floor(math.pi / math.asin(min(1.0, spacing * size / (2 * pitch_radius)))))
    )


class SelfAligningInternals:
    """Two rows of balls, staggered by half a pitch, on a spherical outer raceway centered
    on the axis at mid-width; two grooves in the inner ring."""

    def __init__(self, row):
        d, D, B = row.d, row.D, row.B
        wall = (D - d) / 2
        self.dm = (d + D) / 2
        self.Dw = _largest(STANDARD_BALLS, min(0.5 * wall, 0.42 * B), 0.42 * B)
        # axial offset of each row from the middle: the rows must not touch, and the balls
        # must stay inside the width
        while True:
            self.a = min(0.56 * self.Dw, B / 2 - self.Dw / 2 - 0.04 * B)
            if self.a >= 0.5 * self.Dw or self.Dw < 0.5:
                break
            self.Dw = _largest(STANDARD_BALLS, self.Dw - 1e-6, self.Dw * 0.9)
        self.per_row = _count(self.dm / 2, self.Dw, 1.08)
        self.Z = 2 * self.per_row
        self.R_outer = math.hypot(self.dm / 2, self.a) + self.Dw / 2  # sphere radius
        self.r_groove = 0.53 * self.Dw
        self.x_shoulder = self.dm / 2 - 0.32 * self.Dw


def make_selfaligning(row, detail):
    B = row.B
    if detail == "Envelope":
        return [(_annulus(row.d / 2, row.D / 2, -B, 0), COLOR_STEEL)]
    ins = SelfAligningInternals(row)
    zc, Dw, rc, xs = -B / 2, ins.Dw, ins.dm / 2, ins.x_shoulder
    xg = rc - Dw / 2 + ins.r_groove  # groove arc centers (radial)
    h = math.sqrt(ins.r_groove**2 - (xg - xs) ** 2)
    rb = min(row.r, 0.4 * (xs - row.d / 2))
    items = [("p", row.d / 2, -B, rb), ("p", xs, -B, 0)]
    for z in (zc - ins.a, zc + ins.a):
        items += [("p", xs, z - h, 0), ("a", rc - Dw / 2, z), ("p", xs, z + h, 0)]
    items += [("p", xs, 0, 0), ("p", row.d / 2, 0, rb)]
    inner = revolve(items)
    Ro = ins.R_outer
    x_end = math.sqrt(Ro**2 - (B / 2) ** 2)  # sphere radius at the faces
    ro = min(row.r, 0.4 * (row.D / 2 - Ro))
    outer = revolve(
        [
            ("p", x_end, -B, 0),
            ("p", row.D / 2, -B, ro),
            ("p", row.D / 2, 0, ro),
            ("p", x_end, 0, 0),
            ("a", Ro, zc),
        ]
    )
    parts = [(inner, COLOR_STEEL), (outer, COLOR_STEEL)]
    for z, offset in ((zc - ins.a, 0.0), (zc + ins.a, 180.0 / ins.per_row)):
        ball = Part.makeSphere(Dw / 2, V(rc, 0, z))
        for k in range(ins.per_row):
            b = ball.copy()
            b.rotate(V(0, 0, 0), V(0, 0, 1), offset + 360.0 * k / ins.per_row)
            parts.append((b, COLOR_BALL))
    return parts


class CylindricalInternals:
    """Cylindrical rollers between an outer ring with two ribs and an inner ring (NU: no
    ribs; NJ: one rib, at the bottom)."""

    def __init__(self, row):
        wall = (row.D - row.d) / 2
        self.dm = (row.d + row.D) / 2
        self.Dw = _largest(STANDARD_BALLS, 0.5 * wall, 0.5 * wall)  # roller diameter
        self.rib = 0.15 * row.B  # rib width
        self.Lw = row.B - 2 * self.rib - 0.04 * row.B  # roller length
        self.Z = _count(self.dm / 2, self.Dw, 1.12)


def make_cylindrical(row, variant, detail):
    B = row.B
    if detail == "Envelope":
        return [(_annulus(row.d / 2, row.D / 2, -B, 0), COLOR_STEEL)]
    ins = CylindricalInternals(row)
    rp, Dw, t = ins.dm / 2, ins.Dw, ins.rib
    Ro, Ri = rp + Dw / 2, rp - Dw / 2
    r_rib_out, r_rib_in = rp + 0.15 * Dw, rp - 0.15 * Dw
    outer = revolve(
        [
            ("p", r_rib_out, -B, 0),
            ("p", row.D / 2, -B, 0),
            ("p", row.D / 2, 0, 0),
            ("p", r_rib_out, 0, 0),
            ("p", r_rib_out, -t, 0),
            ("p", Ro, -t, 0),
            ("p", Ro, -B + t, 0),
            ("p", r_rib_out, -B + t, 0),
        ]
    )
    if variant == "NJ":
        inner = revolve(
            [
                ("p", row.d / 2, -B, 0),
                ("p", r_rib_in, -B, 0),
                ("p", r_rib_in, -B + t, 0),
                ("p", Ri, -B + t, 0),
                ("p", Ri, 0, 0),
                ("p", row.d / 2, 0, 0),
            ]
        )
    else:
        inner = _annulus(row.d / 2, Ri, -B, 0)
    parts = [(inner, COLOR_STEEL), (outer, COLOR_STEEL)]
    roller = Part.makeCylinder(0.998 * Dw / 2, ins.Lw, V(rp, 0, -B / 2 - ins.Lw / 2))
    for k in range(ins.Z):
        r = roller.copy()
        r.rotate(V(0, 0, 0), V(0, 0, 1), 360.0 * k / ins.Z)
        parts.append((r, COLOR_BALL))
    return parts


class TaperedInternals:
    """Tapered rollers between a cone (inner ring, back rib at the bottom) and a cup
    (outer ring, top). The cone raceway, the cup raceway and every roller are cones with
    one common apex on the bearing axis, above the bearing, as in a real tapered bearing.

    Frame: z in [-T, 0]; the cone occupies [-T, -T + B], the cup [-C, 0]."""

    def __init__(self, row, theta=13.0):
        d, D, T, B, C = row.d, row.D, row.B, row.cone_B, row.cup_C
        self.dm = (d + D) / 2
        self.theta = math.radians(theta)  # roller axis to bearing axis
        overlap_lo, overlap_hi = -C, -T + B  # where both rings are
        self.z_mid = (overlap_lo + overlap_hi) / 2
        self.Lw = 0.8 * (overlap_hi - overlap_lo) / math.cos(self.theta)  # roller length
        self.Dw = 0.2 * (D - d)  # mean roller diameter
        rp = self.dm / 2
        self.s_mid = rp / math.sin(self.theta)  # apex to roller center
        self.z_apex = self.z_mid + rp / math.tan(self.theta)
        self.gamma = math.asin(self.Dw / 2 / self.s_mid)  # roller half angle
        self.alpha = self.theta + self.gamma  # cup raceway to axis
        self.beta = self.theta - self.gamma  # cone raceway to axis
        self.Z = _count(rp, self.Dw, 1.2)
        # back rib: from the cone's back face to just below the rollers' large ends. The
        # end face is square to the tilted roller axis, so its inner edge reaches
        # r_large * sin(theta) below the end's center.
        z_large = self.z_mid - self.Lw / 2 * math.cos(self.theta)
        r_large = (self.s_mid + self.Lw / 2) * math.sin(self.gamma)
        self.rib_top = z_large - r_large * math.sin(self.theta) - 0.03 * T

    def cup_r(self, z):
        return (self.z_apex - z) * math.tan(self.alpha)

    def cone_r(self, z):
        return (self.z_apex - z) * math.tan(self.beta)


def make_tapered(row, detail):
    T, B, C = row.B, row.cone_B, row.cup_C
    if detail == "Envelope":
        shape = _annulus(row.d / 2, row.D / 2, -T, 0)
        if B > T:  # some inch tapers have a cone projecting beyond the cup
            ins = TaperedInternals(row)
            shape = shape.fuse(_annulus(row.d / 2, ins.cone_r(B - T), 0, B - T))
        return [(shape, COLOR_STEEL)]
    ins = TaperedInternals(row)
    cup = revolve(
        [
            ("p", ins.cup_r(0), 0, 0),
            ("p", row.D / 2, 0, 0),
            ("p", row.D / 2, -C, 0),
            ("p", ins.cup_r(-C), -C, 0),
        ]
    )
    z_top = -T + B
    rib_r = ins.cone_r(ins.rib_top) + 0.55 * ins.Dw  # the rib holds the rollers' large ends
    cone = revolve(
        [
            ("p", row.d / 2, -T, 0),
            ("p", rib_r, -T, 0),
            ("p", rib_r, ins.rib_top, 0),
            ("p", ins.cone_r(ins.rib_top), ins.rib_top, 0),
            ("p", ins.cone_r(z_top), z_top, 0),
            ("p", row.d / 2, z_top, 0),
        ]
    )
    parts = [(cone, COLOR_STEEL), (cup, COLOR_STEEL)]
    # one roller: a frustum on the roller axis, its radius growing with the distance
    # from the apex (s * sin(gamma)), a little smaller so it doesn't touch the raceways
    axis = V(math.sin(ins.theta), 0, -math.cos(ins.theta))
    apex = V(0, 0, ins.z_apex)
    s1, s2 = ins.s_mid - ins.Lw / 2, ins.s_mid + ins.Lw / 2
    k = 0.98 * math.sin(ins.gamma)
    roller = Part.makeCone(s1 * k, s2 * k, ins.Lw, apex + axis * s1, axis)
    for i in range(ins.Z):
        r = roller.copy()
        r.rotate(V(0, 0, 0), V(0, 0, 1), 360.0 * i / ins.Z)
        parts.append((r, COLOR_BALL))
    return parts


class NeedleInternals:
    """Needle rollers running on the shaft (d = Fw) inside a ring: a thin drawn cup (HK)
    or a machined ring (NK), with a lip / rib at each end holding the needles."""

    def __init__(self, row):
        wall = (row.D - row.d) / 2
        self.Dw = _largest(NEEDLES, 0.75 * wall, 0.6 * wall)
        self.dm = row.d + self.Dw
        self.shell = wall - self.Dw  # radial ring thickness outside the needles
        self.lip = max(0.3, self.shell) if row.drawn else max(0.5, 0.12 * row.B)
        self.Lw = row.B - 2 * self.lip - 0.2  # needle length
        self.Z = _count(self.dm / 2, self.Dw, 1.06)


def make_needle(row, detail):
    C = row.B
    if detail == "Envelope":
        return [(_annulus(row.d / 2, row.D / 2, -C, 0), COLOR_STEEL)]
    ins = NeedleInternals(row)
    r_lip = row.d / 2 + 0.45 * ins.Dw  # the lips come down past the needle centers
    r_race = row.D / 2 - ins.shell
    t = ins.lip
    ring = revolve(
        [
            ("p", r_lip, -C, 0),
            ("p", row.D / 2, -C, 0),
            ("p", row.D / 2, 0, 0),
            ("p", r_lip, 0, 0),
            ("p", r_lip, -t, 0),
            ("p", r_race, -t, 0),
            ("p", r_race, -C + t, 0),
            ("p", r_lip, -C + t, 0),
        ]
    )
    parts = [(ring, COLOR_STEEL)]
    needle = Part.makeCylinder(0.998 * ins.Dw / 2, ins.Lw, V(ins.dm / 2, 0, -C / 2 - ins.Lw / 2))
    for k in range(ins.Z):
        n = needle.copy()
        n.rotate(V(0, 0, 0), V(0, 0, 1), 360.0 * k / ins.Z)
        parts.append((n, COLOR_BALL))
    return parts


class AxialNeedleInternals:
    """AXK: radial needles in a flat cage between the shaft and housing faces (or two AS
    washers). B is the needle diameter."""

    def __init__(self, row):
        self.Dw = row.B
        self.dm = (row.d + row.D) / 2
        self.cage_in = row.d / 2  # an AXK's bore and outside diameter are the cage's
        self.cage_out = row.D / 2
        self.Lw = self.cage_out - self.cage_in - 1.6  # needle length (radial)
        self.Z = _count(self.cage_in + 0.8, self.Dw, 1.3)


def make_axk(row, washers, detail):
    """`washers`: add an AS washer (1 mm) on each side; the height grows by 2 mm."""
    w = 1.0 if washers else 0.0  # BD.AS_WASHER
    H = row.B + 2 * w
    if detail == "Envelope":
        return [(_annulus(row.d / 2, row.D / 2, -H, 0), COLOR_STEEL)]
    ins = AxialNeedleInternals(row)
    zc, Dw = -H / 2, ins.Dw
    tc = 0.6 * Dw  # cage thickness, thinner than the needles
    cage = _annulus(ins.cage_in, ins.cage_out, zc - tc / 2, zc + tc / 2)
    r0 = ins.cage_in + 0.8
    pockets = []
    for k in range(ins.Z):
        p = Part.makeBox(
            ins.Lw + 0.2, 1.06 * Dw, tc + 0.2, V(r0 - 0.1, -0.53 * Dw, zc - tc / 2 - 0.1)
        )
        p.rotate(V(0, 0, 0), V(0, 0, 1), 360.0 * k / ins.Z)
        pockets.append(p)
    parts = [(cage.cut(Part.makeCompound(pockets)), COLOR_CAGE)]
    needle = Part.makeCylinder(0.998 * Dw / 2, ins.Lw, V(r0, 0, zc), V(1, 0, 0))
    for k in range(ins.Z):
        n = needle.copy()
        n.rotate(V(0, 0, 0), V(0, 0, 1), 360.0 * k / ins.Z)
        parts.append((n, COLOR_BALL))
    if washers:
        parts.append((_annulus(row.d / 2, row.D / 2, -H, -H + w), COLOR_STEEL))
        parts.append((_annulus(row.d / 2, row.D / 2, -w, 0), COLOR_STEEL))
    return parts


# ---------------------------------------------------------------- linear bushings


class LinearInternals:
    """Ball rows of a linear bushing (simplified: one straight row of balls per circuit,
    touching the shaft, between the seals). Same attribute names as Internals.

    The retainer fills the space between the shaft and the sleeve, with one slot per row
    a little wider than a ball, so the balls show through without touching it."""

    def __init__(self, row):
        wall = (row.D - row.d) / 2
        fitting = [b for b in STANDARD_BALLS if b <= 0.45 * wall + 1e-9]
        self.Dw = fitting[-1] if fitting else round(0.45 * wall, 3)
        self.dm = row.d + self.Dw  # diameter through the ball centers
        self.seal = min(max(0.06 * row.B, 0.8), 2.5)  # seal thickness at each end
        self.sleeve_bore = row.d / 2 + 1.05 * self.Dw  # radius
        self.pitch = 1.02 * self.Dw  # balls in a row don't touch
        self.per_row = max(1, int((row.B - 2 * self.seal - 0.2) / self.pitch))
        self.rows = row.rows
        self.Z = self.rows * self.per_row
        self.retainer_bore = row.d / 2 + max(0.05, 0.03 * self.Dw)  # radius, clear of the shaft
        self.slot_width = 1.04 * self.Dw
        self.row_length = self.per_row * self.pitch


_INTERNALS = {
    "selfaligning": SelfAligningInternals,
    "cylindrical": CylindricalInternals,
    "tapered": TaperedInternals,
    "needle": NeedleInternals,
    "axk": AxialNeedleInternals,
}


def internals(row):
    """Internals of any row: ball, roller and needle bearings and linear bushings."""
    if getattr(row, "kind", None) == "looseball":
        from types import SimpleNamespace

        return SimpleNamespace(dm=0, Dw=row.D, Z=1)
    if getattr(row, "is_thrust", False):
        return ThrustInternals(row)
    kind = getattr(row, "kind", None)
    if kind in ("spherical", "doublecylindrical", "doubleangular", "housed", "camfollower"):
        import BearingCatalogGeometry

        return BearingCatalogGeometry.internals(row)
    if kind in _INTERNALS:
        return _INTERNALS[kind](row)
    return (
        LinearInternals(row) if getattr(row, "is_linear", False) else Internals(row.d, row.D, row.B)
    )


def _sleeve_profile(row, flanged, bore):
    """Revolve profile of a linear bushing sleeve: retaining ring grooves on a plain
    bushing, a round flange (D1 x C1, at the top) on a flanged one."""
    L, R = row.B, row.D / 2
    items = [("p", bore, -L, 0), ("p", R, -L, 0)]
    if flanged:
        items += [("p", R, -row.C1, 0), ("p", row.D1 / 2, -row.C1, 0), ("p", row.D1 / 2, 0, 0)]
    else:
        if row.groove_B:
            zc, Rg, W = -L / 2, row.groove_D / 2, row.groove_W
            for z0 in (zc - row.groove_B / 2, zc + row.groove_B / 2 - W):
                items += [
                    ("p", R, z0, 0),
                    ("p", Rg, z0, 0),
                    ("p", Rg, z0 + W, 0),
                    ("p", R, z0 + W, 0),
                ]
        items += [("p", R, 0, 0)]
    items += [("p", bore, 0, 0)]
    return items


def _linear_sleeve(row, flanged, shape, bore):
    sleeve = revolve(_sleeve_profile(row, flanged and shape == "Round", bore))
    if not flanged:
        return sleeve
    if shape == "Square":
        # square flange K x K, corners trimmed to the round flange diameter D1
        K, H = row.K, row.C1
        plate = Part.makeBox(K, K, H, V(-K / 2, -K / 2, -H))
        plate = plate.common(Part.makeCylinder(row.D1 / 2, H, V(0, 0, -H)))
        plate = plate.cut(Part.makeCylinder(bore, H, V(0, 0, -H)))
        sleeve = sleeve.fuse(plate).removeSplitter()
    # four counterbored bolt holes on the bolt circle, on the diagonals
    d1, d2, h = row.hole
    H = row.C1
    holes = []
    for k in range(4):
        a = math.radians(45 + 90 * k)
        c = V(row.pcd / 2 * math.cos(a), row.pcd / 2 * math.sin(a), 0)
        holes.append(Part.makeCylinder(d1 / 2, H + 0.2, c + V(0, 0, -H - 0.1)))
        holes.append(Part.makeCylinder(d2 / 2, h + 0.1, c + V(0, 0, -h)))
    sleeve = sleeve.cut(Part.makeCompound(holes))
    return Part.Solid(sleeve.Solids[0]) if sleeve.Solids else sleeve


def _retainer(row, ins):
    """Plastic retainer between the seals: a tube from just off the shaft to the sleeve,
    with a slot along each ball row."""
    L, t, g = row.B, ins.seal, CONTACT_GAP
    tube = _annulus(ins.retainer_bore, ins.sleeve_bore - g, -L + t + g, -t - g)
    w, length = ins.slot_width, ins.row_length
    slots = []
    for k in range(ins.rows):
        slot = Part.makeBox(ins.sleeve_bore + 1, w, length, V(0, -w / 2, -L / 2 - length / 2))
        slot.rotate(V(0, 0, 0), V(0, 0, 1), 360.0 * k / ins.rows)
        slots.append(slot)
    return tube.cut(Part.makeCompound(slots))


def make_linear(row, flanged, shape, detail):
    """Return a list of (solid, rgb) for a linear ball bushing.

    Envelope: the sleeve alone, bore = shaft. Standard: the sleeve, a rubber seal at each
    end and the slotted ball retainer. Detailed: adds the rows of balls in the slots.
    """
    if detail == "Envelope":
        return [(_linear_sleeve(row, flanged, shape, row.d / 2), COLOR_STEEL)]
    ins = LinearInternals(row)
    L, t = row.B, ins.seal
    parts = [(_linear_sleeve(row, flanged, shape, ins.sleeve_bore), COLOR_STEEL)]
    # seals and retainer just clear of the sleeve and of each other (CONTACT_GAP)
    seal_od = ins.sleeve_bore - CONTACT_GAP
    for z0 in (-L, -t):
        parts.append((_annulus(row.d / 2, seal_od, z0, z0 + t), COLOR_SEAL))
    parts.append((_retainer(row, ins), COLOR_RETAINER))
    if detail != "Detailed":
        return parts
    z_first = -L / 2 - ins.row_length / 2 + ins.pitch / 2
    ball = Part.makeSphere(ins.Dw / 2, V(ins.dm / 2, 0, z_first))
    for k in range(ins.rows):
        for i in range(ins.per_row):
            b = ball.copy()
            b.translate(V(0, 0, i * ins.pitch))
            b.rotate(V(0, 0, 0), V(0, 0, 1), 360.0 * k / ins.rows)
            parts.append((b, COLOR_BALL))
    return parts


_shape_cache = {}


def build(row, closure, flanged, detail, flange_shape="Round", variant=None):
    """Return (shape, face_colors) for a table row. Results are cached.

    `flange_shape` ("Round" or "Square") applies to flanged linear bushings only.
    `variant`: "NU" / "NJ" for cylindrical roller bearings, "AXK + 2 AS" for an AXK with
    its washers."""
    flanged = bool(flanged and row.has_flange)
    linear = getattr(row, "is_linear", False)
    kind = getattr(row, "kind", None)
    if getattr(row, "fixed_name", False):
        closure = row.fixed_closure
    key = (row.name, row.d, row.D, row.B, row.B_shielded, row.D1, row.C1, closure, flanged, detail)
    key += (flange_shape, variant, kind, repr(getattr(row, "parameters", None)))
    if key not in _shape_cache:
        if kind == "looseball":
            parts = [(Part.makeSphere(row.D / 2, V(0, 0, -row.D / 2)), COLOR_BALL)]
        elif kind in ("spherical", "doublecylindrical", "doubleangular", "housed", "camfollower"):
            import BearingCatalogGeometry

            parts = BearingCatalogGeometry.BUILDERS[kind](row, detail)
        elif kind == "selfaligning":
            parts = make_selfaligning(row, detail)
        elif kind == "cylindrical":
            parts = make_cylindrical(row, variant, detail)
        elif kind == "tapered":
            parts = make_tapered(row, detail)
        elif kind == "needle":
            parts = make_needle(row, detail)
        elif kind == "axk":
            parts = make_axk(row, variant == "AXK + 2 AS", detail)
        elif linear:
            parts = make_linear(row, flanged, flange_shape, detail)
        elif getattr(row, "is_thrust", False):
            parts = make_thrust(row, detail)
        else:
            parts = make_deep_groove(
                row, closure, flanged, detail, angular=getattr(row, "is_angular", False)
            )
        if getattr(row, "taper", None):
            # K designations have a 1:12 diameter taper, small end at z=0.
            bore = Part.makeCone(
                row.d / 2 + row.B / (2 * row.taper), row.d / 2, row.B, V(0, 0, -row.B)
            )
            parts = [(shape.cut(bore), color) for shape, color in parts]
        if len(parts) == 1:
            shape = parts[0][0]
        else:
            shape = Part.Compound([p[0] for p in parts])
        colors = []
        for solid, color in parts:
            colors += [color] * len(solid.Faces)
        _shape_cache[key] = (shape, colors)
    shape, colors = _shape_cache[key]
    return shape.copy(), list(colors)
