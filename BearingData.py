# SPDX-License-Identifier: GPL-3.0-or-later
"""Bearing tables: CSV loading, series registry, designation strings, auto-match.

Tables hold only boundary dimensions (d, D, B, r) plus optional shielded width and
flange data. Internal geometry is computed in BearingGeometry.
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
}

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


_tables = {}


def _num(text):
    text = text.strip()
    return float(text) if text else None


def load_table(series):
    """Return the list of BearingRow for a series key, sorted by bore."""
    if series in _tables:
        return _tables[series]
    fname = os.path.join(dataPath, SERIES[series][1])
    rows = []
    with open(fname, newline="") as f:
        lines = [ln for ln in f if ln.strip() and not ln.lstrip().startswith("#")]
    reader = csv.reader(lines)
    header = next(reader)
    for rec in reader:
        rec = dict(zip(header, rec))
        rows.append(
            BearingRow(
                rec["Designation"].strip(),
                _num(rec["d"]),
                _num(rec["D"]),
                _num(rec["B"]),
                _num(rec["r"]) or 0.0,
                _num(rec.get("B_shielded", "")),
                _num(rec.get("D1", "")),
                _num(rec.get("C1", "")),
            )
        )
    rows.sort(key=lambda r: (r.d, r.D))
    _tables[series] = rows
    return rows


def designations(series):
    return [r.name for r in load_table(series)]


def get_row(series, name):
    for r in load_table(series):
        if r.name == name:
            return r
    return None


def full_designation(row, closure, flanged):
    name = row.name
    if flanged and row.has_flange:
        name = "MF" + name[2:] if name.startswith("MR") else "F" + name
    return name + CLOSURE_SUFFIX.get(closure, "")


def auto_match(series, diameter, match_to):
    """Pick the row whose bore (match_to='Shaft') or OD ('Housing') is closest to diameter."""
    key = (lambda r: r.d) if match_to == "Shaft" else (lambda r: r.D)
    rows = load_table(series)
    return min(rows, key=lambda r: (abs(key(r) - diameter), r.B))


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


def parse_designation(text):
    """Split a typed designation into (base, closure, flanged).

    "F688-2RS" -> ("688", "2RS", True); "MF105ZZ" -> ("MR105", "ZZ", True);
    "608" -> ("608", None, False). SKF miniature names "618/8" map to "688".
    """
    t = text.strip().upper().replace(" ", "")
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
    m = _SKF_MINI_RE.match(t)
    if m:
        t = "6" + ("8" if m.group(1) == "18" else "9") + m.group(2)
    return t, closure, flanged


def search(name=None, d=None, D=None, B=None, tol=0.0):
    """Catalog rows matching every given criterion, as (series, row) pairs.

    name: designation or its start ("62" finds 62xx and 62x), parsed with
    parse_designation(); it may also be a size "8x22" / "8x22x7" (ID x OD [x height]).
    d, D, B: bore, outside diameter, width in mm, matched within `tol`. B also matches
    the shielded width. Results are sorted by bore, then OD, then designation.
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
    rest = sorted((h for h in hits if h not in exact), key=lambda h: (h[1].d, h[1].D, h[1].name))
    return exact + rest
