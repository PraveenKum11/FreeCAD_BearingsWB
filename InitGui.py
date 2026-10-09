# SPDX-License-Identifier: LGPL-2.1-or-later


class BearingsWorkbench(Workbench):
    import BRutils

    MenuText = BRutils.translate("Workbench", "Bearings")
    ToolTip = BRutils.translate("Workbench", "Parametric rolling bearings")
    Icon = BRutils.icon("BearingsWB.svg")

    def Initialize(self):
        import BearingsCmd
        import BearingSearchGui  # noqa: F401  (registers Bearings_Search)
        import PrintableBearingGui  # noqa: F401  (registers Bearings_PrintableBearing)

        tools = ["Bearings_Search", "Bearings_PrintableBearing"]
        self.appendToolbar("Bearings", BearingsCmd.COMMANDS)
        self.appendToolbar("Bearing tools", tools)
        self.appendMenu("Bearings", BearingsCmd.COMMANDS + ["Separator"] + tools)

    def GetClassName(self):
        return "Gui::PythonWorkbench"


Gui.addWorkbench(BearingsWorkbench())
