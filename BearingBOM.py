# SPDX-License-Identifier: GPL-3.0-or-later
"""Bill of materials: every bearing in a document, grouped and counted.

Counts standard bearings and linear bushings (by full designation, including App::Link
copies and link arrays), printable bearings (one per BearingParameters datum, so grooved
bodies count too) and the balls the printable bearings need. The list can be saved as CSV
or written to a spreadsheet in the document. No FreeCADGui, so it can be used from scripts
and tested headless.
"""

import csv

import BearingData as BD
import PrintableBearing as PB

SHEET_NAME = "BearingBOM"  # object name of the BOM spreadsheet; its label is free to change
SHEET_LABEL = "Bearing BOM"
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
            counted = [(obj, 1)] + list(_links_to(obj, doc))
            counted = [(o, n) for o, n in counted if _visible(o) or not skip_hidden]
            for o, n in counted:
                add(key, values, n, o.Label)
            if getattr(obj, "Variant", "") == "AXK + 2 AS":
                # an AXK assembly with an AS washer on each side: the washers are bought too
                washer = "AS" + obj.FullDesignation[3:]
                washer_values = dict(
                    values,
                    Item=washer,
                    Description="Thrust washer AS, %g mm" % BD.AS_WASHER,
                    **{"Width (mm)": BD.AS_WASHER},
                )
                for o, n in counted:
                    add((0, washer), washer_values, 2 * n, o.Label)
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


def bom_sheet(doc):
    """The document's BOM spreadsheet, or None."""
    obj = doc.getObject(SHEET_NAME)
    return obj if obj is not None and obj.TypeId == "Spreadsheet::Sheet" else None


def _column(i):
    return chr(ord("A") + i)


def write_sheet(doc, items):
    """Write the BOM to the document's "Bearing BOM" spreadsheet, creating it the first time
    and replacing its contents after that. A total row sums the quantities. Returns the
    sheet."""
    sheet = bom_sheet(doc)
    if sheet is None:
        sheet = doc.addObject("Spreadsheet::Sheet", SHEET_NAME)
        sheet.Label = SHEET_LABEL
    sheet.clearAll()
    last = _column(len(COLUMNS) - 1)
    for j, name in enumerate(COLUMNS):
        sheet.set(_column(j) + "1", "'" + name)
    sheet.setStyle("A1:%s1" % last, "bold")
    for i, row in enumerate(items, 2):
        for j, name in enumerate(COLUMNS):
            value = row[name]
            if value == "":
                continue
            # "'" keeps text such as "608" from becoming a number
            text = ("%g" % value) if isinstance(value, (int, float)) else "'" + str(value)
            sheet.set("%s%d" % (_column(j), i), text)
    qty = _column(COLUMNS.index("Quantity"))
    total = len(items) + 3  # one empty row between the items and the total
    sheet.set("A%d" % total, "'Total parts")
    sheet.set("%s%d" % (qty, total), "=sum(%s2:%s%d)" % (qty, qty, max(2, len(items) + 1)))
    sheet.setStyle("A%d:%s%d" % (total, qty, total), "bold")
    widths = {"Item": 260, "Description": 330, "Objects": 260}
    for j, name in enumerate(COLUMNS):
        sheet.setColumnWidth(_column(j), widths.get(name, 95))
    doc.recompute()
    return sheet
