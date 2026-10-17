# SPDX-License-Identifier: GPL-3.0-or-later
"""GUI commands: one insert command per bearing series, grouped by family.

The toolbar shows one drop-down button per group (GROUPS); the menu has a submenu per
group with every series.
"""

import re

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
                except BD.NoFitError as e:
                    skipped.append((BRselection.element_owner(target[0], target[1][0]), e))
        else:
            created.append(BearingBase.make_bearing(self.series, doc=doc))
        if created:
            doc.commitTransaction()
        else:
            doc.abortTransaction()
        if skipped:
            self.report_no_fit(skipped, len(edges))
        if created:
            FreeCADGui.Selection.clearSelection()
            for obj in created:
                FreeCADGui.Selection.addSelection(obj)

    def report_no_fit(self, skipped, n_edges):
        """Say which edges got no bearing, the nearest sizes, and how to use one anyway."""
        from PySide import QtWidgets

        def keep_together(text):  # no line breaks inside "29 mm" or "(26 mm OD)"
            text = re.sub(r"(\d) mm", "\\1\u00a0mm", text)
            return re.sub(r"\([^)]*\)", lambda m: m.group(0).replace(" ", "\u00a0"), text)

        def where(owners):  # "Pocket: Edge10, Edge11; Pad: Edge3"
            by_owner = {}
            for owner, element in owners:
                by_owner.setdefault(owner, []).append(element)
            return "; ".join("{}: {}".format(o, ", ".join(els)) for o, els in by_owner.items())

        groups = {}  # one entry per edge size
        for owner, e in skipped:
            groups.setdefault((e.diameter, e.match_to), (e, []))[1].append(owner)
        name = BD.series_name(self.series)
        if len(groups) == 1:
            e, owners = next(iter(groups.values()))
            edges = (
                "the selected edge"
                if n_edges == 1
                else "{} of the {} selected edges".format(len(owners), n_edges)
            )
            text = "No {} bearing fits {}: {} ({}).".format(
                name, edges, e.what(len(owners)), where(owners)
            )
            details = ["Nearest sizes: {}.".format(e.nearest_text())]
        else:
            text = "No {} bearing fits {} of the {} selected edges.".format(
                name, len(skipped), n_edges
            )
            details = [
                "{} ({})\nNearest: {}.".format(
                    e.what(len(owners)).removeprefix("a ").capitalize(),
                    where(owners),
                    e.nearest_text(),
                )
                for e, owners in groups.values()
            ]
        if len(skipped) < n_edges:
            details.append(
                "A bearing was added to the other edge."
                if n_edges - len(skipped) == 1
                else "Bearings were added to the other edges."
            )
        details.append(
            "To use a nearby size anyway, keep the edge selected and insert it from "
            "Find bearing, or try another series. Auto sizes allow up to {:g} mm of "
            "clearance (Bearing tools → Settings).".format(BD.fit_allowance())
        )
        box = QtWidgets.QMessageBox(FreeCADGui.getMainWindow())
        box.setIcon(QtWidgets.QMessageBox.Warning)
        box.setWindowTitle("No standard bearing")
        box.setText(keep_together(text))
        box.setInformativeText(keep_together("\n\n".join(details)))
        box.exec()


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
