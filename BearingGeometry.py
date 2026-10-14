# SPDX-License-Identifier: GPL-3.0-or-later
"""Computed internals and Part shapes for rolling bearings.

Local frame: bearing axis is +Z, the bearing occupies z in [-B, 0] and the flange
(if any) sits at z in [-C1, 0]. Rings are made by revolving 2D profiles that already
contain the raceway grooves, so only the cage needs a boolean.
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


def make_deep_groove(row, closure, flanged, detail):
    """Return a list of (solid, rgb) for a deep groove ball bearing."""
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

    # inner ring with raceway
    xc_in = dm / 2 - Dw / 2 + ins.r_groove_in
    h_in = math.sqrt(ins.r_groove_in**2 - (xc_in - xs) ** 2)
    rb = min(r, 0.4 * (xs - row.d / 2))
    inner = revolve(
        [
            ("p", row.d / 2, -B, rb),
            ("p", xs, -B, 0),
            ("p", xs, zc - h_in, 0),
            ("a", dm / 2 - Dw / 2, zc),
            ("p", xs, zc + h_in, 0),
            ("p", xs, 0, 0),
            ("p", row.d / 2, 0, rb),
        ]
    )

    # outer ring with raceway and shield seats
    xc_out = dm / 2 + Dw / 2 - ins.r_groove_out
    h_out = math.sqrt(ins.r_groove_out**2 - (xl - xc_out) ** 2)
    ro = min(r, 0.4 * (row.D / 2 - xl - rec))
    items = [("p", xl + rec if bottom else xl, -B, 0), ("p", row.D / 2, -B, ro)]
    items += _outer_top(row, flanged, ro)
    if top:
        items += [("p", xl + rec, 0, 0), ("p", xl + rec, -sd, 0), ("p", xl, -sd, 0)]
    else:
        items += [("p", xl, 0, 0)]
    items += [("p", xl, zc + h_out, 0), ("a", dm / 2 + Dw / 2, zc), ("p", xl, zc - h_out, 0)]
    if bottom:
        items += [("p", xl, -B + sd, 0), ("p", xl + rec, -B + sd, 0)]
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
        if top:
            parts.append((_annulus(x_in, xl + rec, -inset - t, -inset), color))
        if bottom:
            parts.append((_annulus(x_in, xl + rec, -B + inset, -B + inset + t), color))

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
        face.rotate(V(0, 0, 0), V(0, 0, 1), -180.0 / ins.Z)
        segment = Part.Solid(face.revolve(V(0, 0, 0), V(0, 0, 1), 360.0 / ins.Z))
        segment = segment.cut(Part.makeSphere(0.52 * Dw, V(dm / 2, 0, zc)))
        for k in range(ins.Z):
            for s in segment.Solids:
                c = s.copy()
                c.rotate(V(0, 0, 0), V(0, 0, 1), 360.0 * k / ins.Z)
                parts.append((c, COLOR_CAGE))

    return parts


_shape_cache = {}


def build(row, closure, flanged, detail):
    """Return (shape, face_colors) for a table row. Results are cached."""
    flanged = bool(flanged and row.has_flange)
    key = (row.name, row.d, row.D, row.B, row.B_shielded, row.D1, row.C1, closure, flanged, detail)
    if key not in _shape_cache:
        parts = make_deep_groove(row, closure, flanged, detail)
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
