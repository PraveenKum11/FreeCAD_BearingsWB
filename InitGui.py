# SPDX-License-Identifier: LGPL-2.1-or-later


class BearingsWorkbench(Workbench):
    import BRutils

    MenuText = BRutils.translate("Workbench", "Bearings")
    ToolTip = BRutils.translate("Workbench", "Parametric rolling bearings")
    Icon = BRutils.icon("BearingsWB.svg")

    def Initialize(self):
        import BearingsCmd

        self.appendToolbar("Bearings", BearingsCmd.COMMANDS)
        self.appendMenu("Bearings", BearingsCmd.COMMANDS)

    def GetClassName(self):
        return "Gui::PythonWorkbench"


Gui.addWorkbench(BearingsWorkbench())
