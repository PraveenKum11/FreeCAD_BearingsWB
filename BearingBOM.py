# SPDX-License-Identifier: GPL-3.0-or-later
"""Bill of materials: every bearing in a document, grouped and counted.

Counts standard bearings and linear bushings (by full designation, including App::Link
copies and link arrays), printable bearings (one per BearingParameters datum, so grooved
bodies count too) and the balls the printable bearings need. No FreeCADGui, so it can be
used from scripts and tested headless.
"""

import csv

import BearingData as BD
import PrintableBearing as PB

COLUMNS = ["Item", "Description", "Bore d (mm)", "OD D (mm)", "Width (mm)", "Quantity", "Objects"]


def is_bearing(obj):
    """A standard bearing or linear bushing made by this workbench (not a link to one:
    links expose the linked object's properties too)."""
    return (
        obj.TypeId == "Part::FeaturePython"
        and hasattr(obj, "FullDesignation")
        and hasattr(obj, "Series")
    )


def is_printable_params(obj):
    """The BearingParameters datum of a printable bearing."""
    return obj.TypeId == "PartDesign::CoordinateSystem" and all(
        hasattr(obj, p) for p in ("ID", "OD", "Height", "BallDiameter", "NumBalls")
    )


def _visible(obj):
    """Shown in the 3D view, as far as the document knows (headless too)."""
    return bool(getattr(obj, "Visibility", True))


def _link_target(link):
    """The object an App::Link shows, through links to links."""
    target, seen = link.LinkedObject, set()
    while target is not None and target.TypeId == "App::Link" and target.Name not in seen:
        seen.add(target.Name)
        target = target.LinkedObject
    return target


def _links_to(obj, doc):
    """(link, count) for every App::Link in `doc` showing `obj`; a link array counts its
    elements (its App::LinkElement children are not counted again)."""
    for link in doc.Objects:
        if link.TypeId != "App::Link":
            continue
        target = _link_target(link)
        if target is None or target.Name != obj.Name:
            continue
        yield link, max(1, getattr(link, "ElementCount", 0) or 1)


def _num(x):
    return float("%.3f" % x)


def ball_name(dia):
    """ "4.5 mm steel BB (.177)" for a preset ball size, else "Ball Ø4.2 mm"."""
    for label, d in PB.BALL_PRESETS:
        if abs(d - dia) < 1e-6:
            return label
    return "Ball Ø%g mm" % _num(dia)


def bom_items(doc, skip_hidden=True):
    """BOM rows as dicts with the keys of COLUMNS, sorted standard bearings first, then
    printable bearings, then balls. `skip_hidden` leaves out hidden objects, e.g. a
    standard bearing replaced by a printable one."""
    rows = {}

    def add(key, values, qty, label):
        row = rows.setdefault(key, dict(values, Quantity=0, Objects=[]))
        row["Quantity"] += qty
        row["Objects"].append(label)

    for obj in doc.Objects:
        if is_bearing(obj):
            values = {
                "Item": obj.FullDesignation,
                "Description": BD.SERIES[obj.Series][0],
                "Bore d (mm)": _num(obj.BoreDiameter.Value),
                "OD D (mm)": _num(obj.OuterDiameter.Value),
                "Width (mm)": _num(obj.Width.Value),
            }
            key = (0, obj.FullDesignation)
            if _visible(obj) or not skip_hidden:
                add(key, values, 1, obj.Label)
            for link, count in _links_to(obj, doc):
                if _visible(link) or not skip_hidden:
                    add(key, values, count, link.Label)
        elif is_printable_params(obj):
            body = obj.getParentGeoFeatureGroup()
            if skip_hidden and body is not None and not _visible(body):
                continue
            v = PB.values_of(obj)
            size = PB.bearing_label(v)[len("Bearing ") :]
            label = (body.getParentGeoFeatureGroup() or body).Label if body else obj.Label
            add(
                (1, size),
                {
                    "Item": "Printable bearing " + size,
                    "Description": "3D-printed races%s"
                    % (" and cage" if _has_cage(obj, doc) else ""),
                    "Bore d (mm)": _num(v["ID"]),
                    "OD D (mm)": _num(v["OD"]),
                    "Width (mm)": _num(v["Height"]),
                },
                1,
                label,
            )
            add(
                (2, _num(v["BallDiameter"])),
                {
                    "Item": ball_name(v["BallDiameter"]),
                    "Description": "Balls for the printable bearings",
                    "Bore d (mm)": "",
                    "OD D (mm)": _num(v["BallDiameter"]),
                    "Width (mm)": "",
                },
                int(v["NumBalls"]),
                label,
            )
    return [dict(rows[k], Objects=", ".join(rows[k]["Objects"])) for k in sorted(rows)]


def _has_cage(params, doc):
    """A Cage body follows this datum (its placement expression names it)."""
    for obj in doc.Objects:
        if obj.TypeId != "PartDesign::Body" or not obj.Label.startswith("Cage"):
            continue
        if any(params.Name in expr for _, expr in obj.ExpressionEngine):
            return True
    return False


def write_csv(path, items):
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(items)
