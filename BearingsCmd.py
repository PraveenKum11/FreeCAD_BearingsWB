# SPDX-License-Identifier: GPL-3.0-or-later
"""GUI commands: one insert command per bearing series."""

import FreeCAD
import FreeCADGui

import BearingBase
import BearingData as BD
import BRselection
from BRutils import icon


class InsertBearingCommand:
    def __init__(self, series):
        self.series = series

    def GetResources(self):
        title = BD.SERIES[self.series][0]
        return {
            "Pixmap": icon("Bearing_%s.svg" % self.series),
            "MenuText": title,
            "ToolTip": title
            + ".\nSelect circular edges (hole or shaft end) first to attach and auto-size.",
        }

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

    def Activated(self):
        doc = FreeCAD.ActiveDocument
        doc.openTransaction("Add bearing")
        edges = [(obj, [sub]) for obj, sub in BRselection.selected_edges()]
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
