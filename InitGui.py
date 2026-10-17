# SPDX-License-Identifier: GPL-3.0-or-later


class BearingsWorkbench(Workbench):
    import BRutils

    MenuText = "Bearings"
    ToolTip = "Parametric rolling bearings"
    Icon = BRutils.icon("BearingsWB.svg")

    def Initialize(self):
        import BearingBOMGui  # noqa: F401  (registers Bearings_BOM)
        import BearingsCmd
        import BearingSearchGui  # noqa: F401  (registers Bearings_Search)
        import BearingSettingsGui  # noqa: F401  (registers Bearings_Settings)
        import PrintableBearingGui  # noqa: F401  (registers Bearings_PrintableBearing)

        tools = [
            "Bearings_Search",
            "Bearings_PrintableBearing",
            "Bearings_BOM",
            "Bearings_Settings",
        ]
        self.appendToolbar("Bearings", BearingsCmd.GROUP_COMMANDS)
        self.appendToolbar("Bearing tools", tools)
        for title, commands in BearingsCmd.MENUS:
            self.appendMenu(["Bearings", title], commands)
        self.appendMenu("Bearings", ["Separator"] + tools)

    def Activated(self):
        from PySide import QtCore

        import BearingsCmd

        # after FreeCAD has built the toolbars
        QtCore.QTimer.singleShot(0, BearingsCmd.fix_group_tooltips)

    def GetClassName(self):
        return "Gui::PythonWorkbench"


Gui.addWorkbench(BearingsWorkbench())
