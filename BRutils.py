# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared paths and small helpers for the Bearings workbench."""

import os

wbPath = os.path.dirname(os.path.abspath(__file__))
iconPath = os.path.join(wbPath, "Icons")
dataPath = os.path.join(wbPath, "BRData")


def icon(name):
    return os.path.join(iconPath, name)


def free_label(obj, base):
    """`base` if no other object in the document has that label, else the first free
    "base_001", "base_002", ...

    Setting a taken label instead makes FreeCAD bump its trailing number, so a second 608
    would become "609"."""
    taken = {o.Label for o in obj.Document.Objects if o is not obj}
    label, n = base, 0
    while label in taken:
        n += 1
        label = "%s_%03d" % (base, n)
    return label
