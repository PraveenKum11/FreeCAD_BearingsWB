# SPDX-License-Identifier: LGPL-2.1-or-later
"""Bearing tables: CSV loading, series registry, designation strings, auto-match.

Tables hold only boundary dimensions (d, D, B, r) plus optional shielded width and
flange data. Internal geometry is computed in BearingGeometry.
"""

import csv
import os

from BRutils import dataPath, QT_TRANSLATE_NOOP

# key -> (title, csv file, default designation, family)
SERIES = {
    "60": (QT_TRANSLATE_NOOP("Bearings", "Deep groove ball bearing, series 60"), "iso15_60.csv", "608", "deepgroove"),
    "62": (QT_TRANSLATE_NOOP("Bearings", "Deep groove ball bearing, series 62"), "iso15_62.csv", "625", "deepgroove"),
    "63": (QT_TRANSLATE_NOOP("Bearings", "Deep groove ball bearing, series 63"), "iso15_63.csv", "6300", "deepgroove"),
    "68": (QT_TRANSLATE_NOOP("Bearings", "Thin deep groove ball bearing, series 68 (618)"), "iso15_68.csv", "688", "deepgroove"),
    "69": (QT_TRANSLATE_NOOP("Bearings", "Thin deep groove ball bearing, series 69 (619)"), "iso15_69.csv", "695", "deepgroove"),
    "MR": (QT_TRANSLATE_NOOP("Bearings", "Metric miniature ball bearing, MR"), "mr.csv", "MR105", "deepgroove"),
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
