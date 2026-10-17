# SPDX-License-Identifier: GPL-3.0-or-later
"""Bearing tools → Settings: a dialog for the workbench's settings (the fit allowance)."""

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtGui

import BearingData as BD
from BRutils import icon

TITLE = "Bearings Settings"


class SettingsDialog(QtGui.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(TITLE)
        layout = QtGui.QVBoxLayout(self)

        box = QtGui.QGroupBox("Fitting to a hole or a shaft")
        form = QtGui.QFormLayout(box)
        self.allowance = QtGui.QDoubleSpinBox()
        self.allowance.setRange(0.0, 5.0)
        self.allowance.setDecimals(2)
        self.allowance.setSingleStep(0.05)
        self.allowance.setSuffix(" mm")
        self.allowance.setValue(BD.fit_allowance())
        self.allowance.setToolTip(
            "A bearing whose outside diameter is up to this much smaller than a hole, or "
            "whose bore is up to this much larger than a shaft, still counts as a fit. "
            "The closest size wins."
        )
        form.addRow("Fit allowance:", self.allowance)
        note = QtGui.QLabel(
            "How much clearance a size picked for an edge may leave, so a 22.2 mm hole or a "
            "7.98 mm shaft still gets a 608. Used by Auto sizes and by the catalog sizes of "
            "3D-printable bearings. 0 needs an exact match. Existing bearings use the new "
            "value on their next recompute."
        )
        note.setWordWrap(True)
        form.addRow(note)
        layout.addWidget(box)

        buttons = QtGui.QDialogButtonBox(
            QtGui.QDialogButtonBox.Ok
            | QtGui.QDialogButtonBox.Cancel
            | QtGui.QDialogButtonBox.RestoreDefaults
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons.button(QtGui.QDialogButtonBox.RestoreDefaults).clicked.connect(self.defaults)
        layout.addWidget(buttons)
        self.setMinimumWidth(420)

    def defaults(self):
        self.allowance.setValue(BD.DEFAULT_FIT_ALLOWANCE)

    def save(self):
        App.ParamGet(BD.PREFS).SetFloat("FitAllowance", self.allowance.value())

    def accept(self):
        self.save()
        super().accept()


class SettingsCommand:
    def GetResources(self):
        return {
            "Pixmap": icon("BearingSettings.svg"),
            "MenuText": "Settings",
            "ToolTip": "Settings of the Bearings workbench, such as how much clearance a "
            "bearing may leave in a hole or on a shaft",
        }

    def IsActive(self):
        return True

    def Activated(self):
        SettingsDialog(Gui.getMainWindow()).exec_()


Gui.addCommand("Bearings_Settings", SettingsCommand())
