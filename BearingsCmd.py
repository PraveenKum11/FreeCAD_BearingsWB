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
            "MenuText": "Add " + title[0].lower() + title[1:],
            "ToolTip": title,
        }

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

    def Activated(self):
        doc = FreeCAD.ActiveDocument
        doc.openTransaction("Add bearing")
        edges = [(obj, [sub]) for obj, sub in BRselection.selected_edges()]
        created, skipped = [], []
        if edges:
            for target in edges:
                try:
                    created.append(BearingBase.make_bearing(self.series, attach_to=target, doc=doc))
                except ValueError as e:
                    skipped.append("{}.{}: {}".format(target[0].Label, target[1][0], e))
        else:
            created.append(BearingBase.make_bearing(self.series, doc=doc))
        if created:
            doc.commitTransaction()
        else:
            doc.abortTransaction()
        if skipped:
            from PySide import QtWidgets

            QtWidgets.QMessageBox.warning(
                FreeCADGui.getMainWindow(),
                "No standard bearing",
                "No bearing added for:\n\n" + "\n".join(skipped),
            )
        if created:
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


def fix_group_tooltips():
    """Give each drop-down button the tooltip of its default command.

    FreeCAD wraps a Python group command's first tooltip twice (the group title, then the
    group title again around the default command's tooltip). Once an entry is picked from
    the drop-down it uses that entry's own tooltip; do the same from the start."""
    from PySide import QtWidgets

    groups = {title: name for name, title, _ in GROUPS}
    for bar in FreeCADGui.getMainWindow().findChildren(QtWidgets.QToolBar):
        for action in bar.actions():
            name = groups.get(action.text())
            if name:
                children = FreeCADGui.Command.get(name).getAction()
                if children:
                    action.setToolTip(children[0].toolTip())


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
