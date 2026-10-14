# SPDX-License-Identifier: GPL-3.0-or-later
"""GUI commands: one insert command per bearing series, grouped by family.

The toolbar shows one drop-down button per group (GROUPS); the menu has a submenu per
group with every series.
"""

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


class GroupCommand:
    """A toolbar drop-down holding the insert commands of one group of series."""

    def __init__(self, title, commands):
        self.title, self.commands = title, commands

    def GetCommands(self):
        return tuple(self.commands)

    def GetDefaultCommand(self):
        return 0

    def GetResources(self):
        return {"MenuText": self.title, "ToolTip": self.title}

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None


# (command name, title, series): one drop-down per group
GROUPS = [
    ("Bearings_DeepGroove", "Deep groove ball bearings", ["60", "62", "63", "68", "69", "MR", "R"]),
    ("Bearings_AngularContact", "Angular contact ball bearings", ["72", "73"]),
    ("Bearings_SelfAligning", "Self-aligning ball bearings", ["12", "13", "22", "23"]),
    ("Bearings_Cylindrical", "Cylindrical roller bearings", ["NU2", "NU3", "NU22", "NU23"]),
    ("Bearings_Tapered", "Tapered roller bearings", ["302", "303", "320"]),
    ("Bearings_Needle", "Needle roller bearings", ["HK", "NK"]),
    ("Bearings_Thrust", "Thrust bearings", ["511", "AXK"]),
    ("Bearings_Linear", "Linear bushings", ["LM"]),
]

COMMANDS = []  # every insert command, in series order
for _series in BD.SERIES:
    _name = "Bearings_Insert_" + _series
    FreeCADGui.addCommand(_name, InsertBearingCommand(_series))
    COMMANDS.append(_name)

GROUP_COMMANDS = []  # the drop-downs, for the toolbar
MENUS = []  # (submenu title, insert commands)
for _name, _title, _series_list in GROUPS:
    _cmds = ["Bearings_Insert_" + s for s in _series_list]
    FreeCADGui.addCommand(_name, GroupCommand(_title, _cmds))
    GROUP_COMMANDS.append(_name)
    MENUS.append((_title, _cmds))
