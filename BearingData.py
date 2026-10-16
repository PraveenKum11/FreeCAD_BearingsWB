# SPDX-License-Identifier: GPL-3.0-or-later
"""Bearing tables: CSV loading, series registry, designation strings, auto-match.

Tables hold only boundary dimensions (d, D, B, r) plus optional shielded width and
flange data. Internal geometry is computed in BearingGeometry.

Families: "deepgroove" (BearingRow), "angular" contact (AngularRow, same boundary
dimensions as series 62 / 63, so derived from those tables), "thrust" (ThrustRow, B is
the height H) and "linear" ball bushings (LinearRow). All have d (bore / shaft), D
(outside diameter) and B (width, height or length), so search and auto-match treat them
alike.
"""

import csv
import os
import re

from BRutils import dataPath

# key -> (title, csv file, default designation, family)
SERIES = {
    "60": ("Deep groove ball bearing, series 60", "iso15_60.csv", "608", "deepgroove"),
    "62": ("Deep groove ball bearing, series 62", "iso15_62.csv", "625", "deepgroove"),
    "63": ("Deep groove ball bearing, series 63", "iso15_63.csv", "6300", "deepgroove"),
    "68": ("Thin deep groove ball bearing, series 68 (618)", "iso15_68.csv", "688", "deepgroove"),
    "69": ("Thin deep groove ball bearing, series 69 (619)", "iso15_69.csv", "695", "deepgroove"),
    "MR": ("Metric miniature ball bearing, MR", "mr.csv", "MR105", "deepgroove"),
    "R": ("Inch miniature ball bearing, R", "inch_r.csv", "R188", "deepgroove"),
    "72": ("Angular contact ball bearing, series 72 B", "iso15_62.csv", "7204", "angular"),
    "73": ("Angular contact ball bearing, series 73 B", "iso15_63.csv", "7304", "angular"),
    "12": ("Self-aligning ball bearing, series 12", "iso15_62.csv", "1204", "selfaligning"),
    "13": ("Self-aligning ball bearing, series 13", "iso15_63.csv", "1304", "selfaligning"),
    "22": ("Self-aligning ball bearing, series 22", "iso15_22.csv", "2204", "selfaligning"),
    "23": ("Self-aligning ball bearing, series 23", "iso15_23.csv", "2304", "selfaligning"),
    "NU2": ("Cylindrical roller bearing, series NU2 / NJ2", "iso15_62.csv", "NU204", "cylindrical"),
    "NU3": ("Cylindrical roller bearing, series NU3 / NJ3", "iso15_63.csv", "NU304", "cylindrical"),
    "NU22": (
        "Cylindrical roller bearing, series NU22 / NJ22",
        "iso15_22.csv",
        "NU2204",
        "cylindrical",
    ),
    "NU23": (
        "Cylindrical roller bearing, series NU23 / NJ23",
        "iso15_23.csv",
        "NU2304",
        "cylindrical",
    ),
    "302": ("Tapered roller bearing, series 302", "tapered.csv", "30204", "tapered"),
    "303": ("Tapered roller bearing, series 303", "tapered.csv", "30304", "tapered"),
    "320": ("Tapered roller bearing, series 320", "tapered.csv", "32004", "tapered"),
    "511": ("Thrust ball bearing, series 511", "thrust_511.csv", "51104", "thrust"),
    "AXK": ("Axial needle roller and cage assembly, AXK", "axk.csv", "AXK1528", "axk"),
    "HK": ("Drawn cup needle roller bearing, HK", "needle.csv", "HK0810", "needle"),
    "NK": ("Needle roller bearing, NK", "needle.csv", "NK10/16", "needle"),
    "LM": ("Linear ball bushing, LM", "linear_lm.csv", "LM8UU", "linear"),
}

# Series whose rows come from another series' table (ISO 15 shares boundary dimensions
# between them): series -> (prefix of the source rows, new prefix, smallest bore in mm).
# The smallest sizes of some source tables aren't made in the derived types.
DERIVED = {
    "72": ("62", "72", 10),
    "73": ("63", "73", 10),
    "12": ("62", "12", 10),
    "13": ("63", "13", 12),
    "23": ("23", "23", 12),
    "NU2": ("62", "NU2", 15),
    "NU3": ("63", "NU3", 17),
    "NU22": ("22", "NU22", 17),
    "NU23": ("23", "NU23", 20),
}

# families without shields or seals (their Closure property is hidden)
NO_CLOSURES = (
    "angular",
    "thrust",
    "linear",
    "selfaligning",
    "cylindrical",
    "tapered",
    "needle",
    "axk",
)

# Family-specific variants (the Variant property): inner ring ribs of a cylindrical roller
# bearing, and thrust washers for an AXK assembly.
VARIANTS = {"cylindrical": ["NU", "NJ"], "axk": ["AXK", "AXK + 2 AS"]}
AS_WASHER = 1.0  # thickness of an AS thrust washer, mm

FLANGE_SHAPES = ["Round", "Square"]  # linear bushings: LMF / LMK

CLOSURES = ["Open", "Z", "ZZ", "RS", "2RS"]
CLOSURE_SUFFIX = {"Open": "", "Z": "Z", "ZZ": "ZZ", "RS": "-RS", "2RS": "-2RS"}

AUTO = "Auto"


class BearingRow:
    __slots__ = ("name", "d", "D", "B", "r", "B_shielded", "D1", "C1")

    def __init__(self, name, d, D, B, r, B_shielded=None, D1=None, C1=None):
        self.name = name
        self.d = d
        self.D = D
        self.B = B
        self.r = r
        self.B_shielded = B_shielded
        self.D1 = D1
        self.C1 = C1

    @property
    def has_flange(self):
        return self.D1 is not None and self.C1 is not None

    def width(self, closure):
        """Width for the given closure (miniature shielded variants are often wider)."""
        if closure != "Open" and self.B_shielded is not None:
            return self.B_shielded
        return self.B

    def __repr__(self):
        return "BearingRow(%s %gx%gx%g)" % (self.name, self.d, self.D, self.B)


class AngularRow(BearingRow):
    """Angular contact ball bearing, 40° (suffix B). ISO 15 gives series 72 / 73 the
    boundary dimensions of 62 / 63; open only, no flanges."""

    is_angular = True


class ThrustRow(BearingRow):
    """Single direction thrust ball bearing: B is the height H."""

    is_thrust = True

    def width(self, closure=None):
        return self.B


class SelfAligningRow(BearingRow):
    """Self-aligning ball bearing: two rows of balls, spherical outer raceway."""

    kind = "selfaligning"


class CylindricalRow(BearingRow):
    """Cylindrical roller bearing NU (ribs on the outer ring) or NJ (plus one inner rib)."""

    kind = "cylindrical"


class TaperedRow(BearingRow):
    """Tapered roller bearing: B is the total width T; cone_B and cup_C the ring widths."""

    kind = "tapered"

    def __init__(self, name, d, D, T, r, cone_B, cup_C):
        BearingRow.__init__(self, name, d, D, T, r)
        self.cone_B, self.cup_C = cone_B, cup_C

    def width(self, closure=None):
        return self.B


class NeedleRow(BearingRow):
    """Needle roller bearing without inner ring: d is the shaft (Fw), B the width C.
    HK = drawn cup (thin shell), NK = machined ring."""

    kind = "needle"

    @property
    def drawn(self):
        return self.name.startswith("HK")


class AxialNeedleRow(BearingRow):
    """AXK axial needle roller and cage assembly: B is the needle diameter (its height)."""

    kind = "axk"


class LinearRow:
    """A linear ball bushing: shaft d, outside diameter D, length B (L in catalogues).

    groove_B / groove_W / groove_D: retaining ring grooves (plain bushings only).
    D1 / C1: flange OD and thickness; K: square flange side; pcd, hole: bolt circle and
    (d1, d2, h) bolt hole with counterbore.
    """

    is_linear = True
    r = 0.0
    B_shielded = None

    def __init__(self, name, d, D, B, groove, rows, flange=None):
        self.name, self.d, self.D, self.B = name, d, D, B
        self.groove_B, self.groove_W, self.groove_D = groove
        self.rows = rows
        D1, C1, pcd, K, hole = flange or (None, None, None, None, None)
        self.D1, self.C1, self.pcd, self.K, self.hole = D1, C1, pcd, K, hole

    @property
    def has_flange(self):
        return self.D1 is not None and self.C1 is not None

    def width(self, closure=None):
        return self.B

    def __repr__(self):
        return "LinearRow(%s %gx%gx%g)" % (self.name, self.d, self.D, self.B)


def kind(row):
    """The family of a row: deepgroove, angular, thrust, linear, selfaligning, ..."""
    if getattr(row, "is_linear", False):
        return "linear"
    if getattr(row, "is_angular", False):
        return "angular"
    if getattr(row, "is_thrust", False):
        return "thrust"
    return getattr(row, "kind", "deepgroove")


def family(series):
    return SERIES[series][3]


def is_linear(row):
    return getattr(row, "is_linear", False)


_tables = {}


def _num(text):
    text = text.strip()
    return float(text) if text else None


def _read_csv(fname):
    with open(fname, newline="") as f:
        lines = [ln for ln in f if ln.strip() and not ln.lstrip().startswith("#")]
    reader = csv.reader(lines)
    header = next(reader)
    return [dict(zip(header, rec)) for rec in reader]


def _bearing_args(rec):
    r = _bearing_row(rec)
    return r.name, r.d, r.D, r.B, r.r


def _bearing_row(rec):
    return BearingRow(
        rec["Designation"].strip(),
        _num(rec["d"]),
        _num(rec["D"]),
        _num(rec["B"]),
        _num(rec["r"]) or 0.0,
        _num(rec.get("B_shielded", "")),
        _num(rec.get("D1", "")),
        _num(rec.get("C1", "")),
    )


def _linear_row(rec):
    n = {k: _num(v) for k, v in rec.items() if k != "Designation"}
    flange = None
    if n.get("D1") is not None:
        flange = (n["D1"], n["H"], n["PCD"], n["K"], (n["d1"], n["d2"], n["h"]))
    return LinearRow(
        rec["Designation"].strip(),
        n["d"],
        n["D"],
        n["L"],
        (n["B"], n["W"], n["Dg"]),
        int(n["Rows"]),
        flange,
    )


_ROW_CLASS = {
    "angular": AngularRow,
    "selfaligning": SelfAligningRow,
    "cylindrical": CylindricalRow,
}


def _derived_rows(series, records):
    """Rows of a derived series (DERIVED): the four-digit source sizes, renamed."""
    source, prefix, min_bore = DERIVED[series]
    cls = _ROW_CLASS[family(series)]
    rows = []
    for rec in records:
        name = rec["Designation"].strip()
        if len(name) == 4 and name.startswith(source):
            r = _bearing_row(rec)
            if r.d >= min_bore:
                rows.append(cls(prefix + name[2:], r.d, r.D, r.B, r.r))
    return rows


def _tapered_row(rec):
    n = {k: _num(v) for k, v in rec.items() if k != "Designation"}
    return TaperedRow(rec["Designation"].strip(), n["d"], n["D"], n["T"], n["r"], n["B"], n["C"])


def _needle_row(rec):
    return NeedleRow(
        rec["Designation"].strip(), _num(rec["d"]), _num(rec["D"]), _num(rec["C"]), 0.0
    )


def _axk_row(rec):
    return AxialNeedleRow(
        rec["Designation"].strip(), _num(rec["d"]), _num(rec["D"]), _num(rec["Dw"]), 0.0
    )


def _thrust_row(rec):
    return ThrustRow(
        rec["Designation"].strip(), _num(rec["d"]), _num(rec["D"]), _num(rec["H"]), _num(rec["r"])
    )


def _prefix_of(name, series_keys):
    """The longest series key `name` starts with (UCFL204 is UCFL, not UCF)."""
    keys = [k for k in series_keys if name.startswith(k)]
    return max(keys, key=len) if keys else None


def load_table(series):
    """Return the rows of a series key, sorted by bore (then OD and width)."""
    if series in _tables:
        return _tables[series]
    records = _read_csv(os.path.join(dataPath, SERIES[series][1]))
    fam = family(series)
    if series in DERIVED:
        rows = _derived_rows(series, records)
    elif fam == "selfaligning":  # series 22: the whole table
        rows = [SelfAligningRow(*_bearing_args(rec)) for rec in records]
    else:
        shared = [k for k, v in SERIES.items() if v[1] == SERIES[series][1]]
        if len(shared) > 1:  # one table for several series: rows by designation prefix
            records = [r for r in records if _prefix_of(r["Designation"], shared) == series]
        make = {
            "linear": _linear_row,
            "thrust": _thrust_row,
            "tapered": _tapered_row,
            "needle": _needle_row,
            "axk": _axk_row,
        }.get(fam, _bearing_row)
        rows = [make(rec) for rec in records]
    rows.sort(key=lambda r: (r.d, r.D, r.B))
    _tables[series] = rows
    return rows


def designations(series):
    return [r.name for r in load_table(series)]


def get_row(series, name):
    for r in load_table(series):
        if r.name == name:
            return r
    return None


def full_designation(row, closure, flanged, flange_shape="Round", variant=None):
    """608ZZ, F688-2RS, MF105ZZ, FR188ZZ; 7204B; 51104; NU204 / NJ204; linear: LM8UU,
    LMF8UU, LMK8LUU. Families without closures get no closure code."""
    name = row.name
    k = kind(row)
    if k == "cylindrical" and variant == "NJ":
        return "NJ" + name[2:]
    if k == "angular":
        return name + "B"
    if k == "linear":
        if flanged and row.has_flange:
            name = "LM" + ("K" if flange_shape == "Square" else "F") + name[2:]
        return name
    if k in NO_CLOSURES:
        return name
    if flanged and row.has_flange:
        name = "MF" + name[2:] if name.startswith("MR") else "F" + name
    return name + CLOSURE_SUFFIX.get(closure, "")


FIT_TOLERANCE = 0.01  # mm: an edge this close to a bore / OD fits it


def _fit_key(match_to):
    return (lambda r: r.d) if match_to == "Shaft" else (lambda r: r.D)


def auto_match(series, diameter, match_to):
    """The row whose bore (match_to='Shaft') or OD ('Housing') equals diameter (the
    narrowest if several do), or None if the series has no such size."""
    key = _fit_key(match_to)
    fits = [r for r in load_table(series) if abs(key(r) - diameter) <= FIT_TOLERANCE]
    return min(fits, key=lambda r: r.B) if fits else None


def series_name(series):
    """Short name for messages: "series 62", "series NU2", "MR", "LM"."""
    return "series " + series if series[0].isdigit() or series.startswith("NU") else series


class NoFitError(ValueError):
    """The series has no standard size for an edge (see auto_match)."""

    def __init__(self, series, diameter, match_to):
        self.series, self.diameter, self.match_to = series, round(diameter, 3), match_to
        key = _fit_key(match_to)
        rows = load_table(series)
        below = max((r for r in rows if key(r) < diameter), key=key, default=None)
        above = min((r for r in rows if key(r) > diameter), key=key, default=None)
        self.nearest = [r for r in (below, above) if r]
        super().__init__(
            "No {} bearing fits {}. Nearest: {}".format(
                series_name(series), self.what(), self.nearest_text()
            )
        )

    def what(self, count=1):
        """ "a 29 mm hole" / "a 13 mm shaft"; "29 mm holes" for count > 1."""
        kind = "shaft" if self.match_to == "Shaft" else "hole"
        if count > 1:
            return "{:g} mm {}s".format(self.diameter, kind)
        return "a {:g} mm {}".format(self.diameter, kind)

    def nearest_text(self):
        """ "629 (26 mm OD) or 6200 (30 mm OD)"."""
        key, dim = (_fit_key(self.match_to), "bore" if self.match_to == "Shaft" else "OD")
        return " or ".join("{} ({:g} mm {})".format(r.name, key(r), dim) for r in self.nearest)


def best_match_kind(series, diameter):
    """Guess whether a circle of this diameter is a shaft (bore match) or a hole (OD match)."""
    rows = load_table(series)
    db = min(abs(r.d - diameter) for r in rows)
    dD = min(abs(r.D - diameter) for r in rows)
    return "Shaft" if db <= dD else "Housing"


# ---------------------------------------------------------------- search

_SIZE_RE = re.compile(
    r"^\s*(\d+(?:\.\d+)?)\s*[x×*]\s*(\d+(?:\.\d+)?)(?:\s*[x×*]\s*(\d+(?:\.\d+)?))?\s*$", re.I
)
# closure codes at the end: 2RS / RS (SKF adds a digit: 2RS1), 2Z / ZZ / Z
_CLOSURE_RE = re.compile(r"-?(?:(2RS|RS)\d?|(2Z|ZZ|Z))$", re.I)
_CLOSURE_CODES = {"2RS": "2RS", "RS": "RS", "2Z": "ZZ", "ZZ": "ZZ", "Z": "Z"}
_SKF_MINI_RE = re.compile(r"^6(1[89])/(\d)$")  # SKF 618/8 = 688, 619/5 = 695
_LINEAR_FLANGE_RE = re.compile(r"^LM([FK])(\d.*)$")  # LMF8UU, LMK8LUU
_ANGULAR_RE = re.compile(r"^(7[23]\d\d)(?:B|AC|C)[A-Z0-9/]*$")  # 7204B, 7204 BEP, 7305 BECBP
_TAPERED_RE = re.compile(r"^(3[02][023]\d\d)[A-Z][A-Z0-9/]*$")  # 30204 J2/Q, 32005 X


def parse_designation(text):
    """Split a typed designation into (base, closure, flanged).

    "F688-2RS" -> ("688", "2RS", True); "MF105ZZ" -> ("MR105", "ZZ", True);
    "FR188ZZ" -> ("R188", "ZZ", True); "608" -> ("608", None, False). SKF miniature
    names "618/8" map to "688". Linear bushings: "LMK8UU" -> ("LM8UU", None, "Square"),
    "LMF8LUU" -> ("LM8LUU", None, "Round"); `flanged` is then the flange shape.
    """
    t = text.strip().upper().replace(" ", "")
    m = _ANGULAR_RE.match(t) or _TAPERED_RE.match(t)
    if m:
        return m.group(1), None, False
    # NJ204 is an NU204 variant; SKF suffixes (NU2205 ECP) are dropped
    m = re.match(r"^N[UJ](\d+)(?:[A-Z][A-Z0-9/]*)?$", t)
    if m:
        return "NU" + m.group(1), None, False
    if t.startswith(("NU", "HK", "NK", "AXK")):
        return t, None, False
    m = _LINEAR_FLANGE_RE.match(t)
    if m:
        return "LM" + m.group(2), None, "Square" if m.group(1) == "K" else "Round"
    if t.startswith("LM"):
        return t, None, False
    closure = None
    m = _CLOSURE_RE.search(t)
    if m and m.start() > 0:
        closure = _CLOSURE_CODES[m.group(1) or m.group(2)]
        t = t[: m.start()]
    flanged = False
    if t.startswith("MF"):
        t, flanged = "MR" + t[2:], True
    elif t.startswith("F") and len(t) > 1 and t[1].isdigit():
        t, flanged = t[1:], True
    elif t.startswith("FR") and len(t) > 2 and t[2].isdigit():
        t, flanged = t[1:], True
    m = _SKF_MINI_RE.match(t)
    if m:
        t = "6" + ("8" if m.group(1) == "18" else "9") + m.group(2)
    return t, closure, flanged


def search(name=None, d=None, D=None, B=None, tol=0.0):
    """Catalog rows matching every given criterion, as (series, row) pairs.

    name: designation or its start ("62" finds 62xx and 62x), parsed with
    parse_designation(); it may also be a size "8x22" / "8x22x7" (ID x OD [x height]).
    d, D, B: bore, outside diameter, width in mm, matched within `tol`. B also matches
    the shielded width. Results are sorted by bore, then OD, width and designation.
    """
    flanged = False
    if name:
        size = _SIZE_RE.match(name)
        if size:
            d = float(size.group(1)) if d is None else d
            D = float(size.group(2)) if D is None else D
            if size.group(3) and B is None:
                B = float(size.group(3))
            name = None
        else:
            name, _, flanged = parse_designation(name)

    def near(a, b):
        return b is None or abs(a - b) <= tol + 1e-9

    hits = []
    for series in SERIES:
        for r in load_table(series):
            if name and not r.name.upper().startswith(name):
                continue
            if flanged and not r.has_flange:
                continue
            if not (near(r.d, d) and near(r.D, D)):
                continue
            if B is not None and not (
                near(r.B, B) or (r.B_shielded is not None and near(r.B_shielded, B))
            ):
                continue
            hits.append((series, r))
    exact = [h for h in hits if name and h[1].name.upper() == name]
    rest = sorted(
        (h for h in hits if h not in exact), key=lambda h: (h[1].d, h[1].D, h[1].B, h[1].name)
    )
    return exact + rest
