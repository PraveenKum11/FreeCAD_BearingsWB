# SPDX-License-Identifier: GPL-3.0-or-later
"""Bill of materials panel and command: list the document's bearings, write them to a
spreadsheet or save them as CSV."""

import os

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui

import BearingBOM
from BRutils import icon

TITLE = "Bearing BOM"


class BOMPanel:
    def __init__(self, doc):
        self.doc = doc
        self.items = []
        self.form = QtGui.QWidget()
        self.form.setWindowTitle(TITLE)
        self.form.setWindowIcon(QtGui.QIcon(icon("BearingBOM.svg")))
        layout = QtGui.QVBoxLayout(self.form)

        self.skip_hidden = QtGui.QCheckBox("Skip hidden objects")
        self.skip_hidden.setChecked(True)
        self.skip_hidden.setToolTip(
            "Leave out bearings you have hidden, for example a standard bearing that was "
            "replaced by a printable one."
        )
        layout.addWidget(self.skip_hidden)

        self.count = QtGui.QLabel()
        layout.addWidget(self.count)
        columns = BearingBOM.COLUMNS
        self.table = QtGui.QTableWidget(0, len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        self.table.setEditTriggers(QtGui.QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setMinimumHeight(260)
        layout.addWidget(self.table)

        buttons = QtGui.QHBoxLayout()
        self.sheet_btn = QtGui.QPushButton()
        self.sheet_btn.setToolTip(
            'Write the list to the "Bearing BOM" spreadsheet in this document, creating it '
            "the first time and updating it after that."
        )
        buttons.addWidget(self.sheet_btn)
        self.save_btn = QtGui.QPushButton("Save CSV…")
        self.save_btn.setToolTip("Save the list as a CSV file, e.g. to open in a spreadsheet.")
        buttons.addWidget(self.save_btn)
        layout.addLayout(buttons)

        self.skip_hidden.toggled.connect(self.update)
        self.sheet_btn.clicked.connect(self.write_sheet)
        self.save_btn.clicked.connect(self.save)
        self.update()

    def update(self, *_):
        self.items = BearingBOM.bom_items(self.doc, self.skip_hidden.isChecked())
        self.table.setRowCount(len(self.items))
        for i, row in enumerate(self.items):
            for j, key in enumerate(BearingBOM.COLUMNS):
                value = row[key]
                text = ("%g" % value) if isinstance(value, float) else str(value)
                item = QtGui.QTableWidgetItem(text)
                if 2 <= j <= 5:
                    item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                self.table.setItem(i, j, item)
        self.table.resizeColumnsToContents()
        total = sum(r["Quantity"] for r in self.items)
        self.count.setText("%d items, %d parts in total" % (len(self.items), total))
        self.save_btn.setEnabled(bool(self.items))
        self.sheet_btn.setEnabled(bool(self.items))
        exists = BearingBOM.bom_sheet(self.doc) is not None
        self.sheet_btn.setText("Update spreadsheet" if exists else "Create spreadsheet")

    def write_sheet(self):
        self.doc.openTransaction("Bearing BOM spreadsheet")
        sheet = BearingBOM.write_sheet(self.doc, self.items)
        self.doc.commitTransaction()
        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(sheet)
        self.sheet_btn.setText("Update spreadsheet")
        App.Console.PrintMessage("Bearing BOM written to the spreadsheet %s\n" % sheet.Label)

    def save(self):
        base = os.path.splitext(self.doc.FileName)[0] if self.doc.FileName else self.doc.Name
        path, _ = QtGui.QFileDialog.getSaveFileName(
            self.form, TITLE, base + "_bearings.csv", "CSV files (*.csv)"
        )
        if not path:
            return
        BearingBOM.write_csv(path, self.items)
        App.Console.PrintMessage("Bearing BOM saved to %s\n" % path)

    def getStandardButtons(self):
        return QtGui.QDialogButtonBox.Close  # no int(): PySide6 enums

    def reject(self):
        Gui.Control.closeDialog()
        return True


def open_panel():
    panel = BOMPanel(App.ActiveDocument)
    Gui.Control.showDialog(panel)
    return panel


class BOMCommand:
    def GetResources(self):
        return {
            "Pixmap": icon("BearingBOM.svg"),
            "MenuText": "Bearing BOM",
            "ToolTip": "List every bearing in the document with its quantity (standard "
            "bearings, linear bushings, printable bearings and the balls they need), and "
            "write the list to a spreadsheet or save it as CSV.",
        }

    def IsActive(self):
        return App.ActiveDocument is not None and Gui.Control.activeDialog() is False

    def Activated(self):
        open_panel()


Gui.addCommand("Bearings_BOM", BOMCommand())
