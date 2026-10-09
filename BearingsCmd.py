# SPDX-License-Identifier: LGPL-2.1-or-later
"""GUI commands: one insert command per bearing series."""

import FreeCAD
import FreeCADGui

import BearingBase
import BearingData as BD
from BRutils import icon, translate


def _selected_circular_edges():
    result = []
    for sel in FreeCADGui.Selection.getSelectionEx():
        for name, sub in zip(sel.SubElementNames, sel.SubObjects):
            if BearingBase._is_circular_edge(sub):
                result.append((sel.Object, [name]))
    return result


class InsertBearingCommand:
    def __init__(self, series):
        self.series = series

    def GetResources(self):
        title = BD.SERIES[self.series][0]
        return {
            "Pixmap": icon("Bearing_%s.svg" % self.series),
            "MenuText": translate("Bearings", title),
            "ToolTip": translate(
                "Bearings",
                "{}.\nSelect circular edges (hole or shaft end) first to attach and auto-size.",
            ).format(translate("Bearings", title)),
        }

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

    def Activated(self):
        doc = FreeCAD.ActiveDocument
        doc.openTransaction("Add bearing")
        edges = _selected_circular_edges()
        created = []
        if edges:
            for target in edges:
                created.append(BearingBase.make_bearing(self.series, attach_to=target, doc=doc))
        else:
            created.append(BearingBase.make_bearing(self.series, doc=doc))
        doc.commitTransaction()
        FreeCADGui.Selection.clearSelection()
        for obj in created:
            FreeCADGui.Selection.addSelection(obj)


COMMANDS = []
for _series in BD.SERIES:
    _name = "Bearings_Insert_" + _series
    FreeCADGui.addCommand(_name, InsertBearingCommand(_series))
    COMMANDS.append(_name)
