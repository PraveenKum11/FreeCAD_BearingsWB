# SPDX-License-Identifier: GPL-3.0-or-later
"""Find a bearing by name, bore (ID), outside diameter (OD) or height, then insert it."""

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui

import BearingBase
import BearingData as BD
import BRselection as BRS
from BRutils import icon

TITLE = "Find Bearing"
COLUMNS = ["Designation", "Series", "ID", "OD", "Height", "Shielded H", "Flange"]


def _num(x):
    return "" if x is None else ("%g" % x)


class SearchPanel:
    def __init__(self, edges=()):
        self.edges = list(edges)  # selected circular edges to attach inserted bearings to
        self.form = QtGui.QWidget()
        self.form.setWindowTitle(TITLE)
        self.form.setWindowIcon(QtGui.QIcon(icon("BearingSearch.svg")))
        layout = QtGui.QVBoxLayout(self.form)
        form = QtGui.QFormLayout()
        layout.addLayout(form)

        self.name = QtGui.QLineEdit()
        self.name.setPlaceholderText("608, F688-2RS, 62, MR105, 8x22x7 ...")
        self.name.setToolTip(
            "Designation or its start (62 lists all 62xx), with optional flange (F, MF) and "
            "closure (Z, ZZ, RS, 2RS) codes, which are used when inserting. A size such as "
            "8x22 or 8x22x7 (ID x OD x height) also works."
        )
        form.addRow("Name:", self.name)

        def dim(tip):
            s = QtGui.QDoubleSpinBox()
            s.setRange(0, 10000)
            s.setDecimals(3)
            s.setSuffix(" mm")
            s.setSpecialValueText("Any")  # 0 = not a criterion
            s.setToolTip(tip)
            return s

        self.d = dim("Bore diameter (ID), i.e. the shaft size. 'Any' to ignore.")
        self.D = dim("Outside diameter (OD), i.e. the housing bore. 'Any' to ignore.")
        self.B = dim(
            "Width / height B. Also matches the wider shielded "
            "width of miniature bearings. 'Any' to ignore."
        )
        self.tol = QtGui.QDoubleSpinBox()
        self.tol.setRange(0, 100)
        self.tol.setDecimals(2)
        self.tol.setSuffix(" mm")
        self.tol.setPrefix("± ")
        self.tol.setToolTip("How far ID, OD and height may differ from the values entered.")
        form.addRow("Inner diameter:", self.d)
        form.addRow("Outer diameter:", self.D)
        form.addRow("Height:", self.B)
        form.addRow("Tolerance:", self.tol)

        self.count = QtGui.QLabel()
        layout.addWidget(self.count)
        self.table = QtGui.QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtGui.QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QtGui.QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setMinimumHeight(260)
        layout.addWidget(self.table)

        buttons = QtGui.QHBoxLayout()
        self.insert_btn = QtGui.QPushButton(QtGui.QIcon(icon("Bearing_60.svg")), "Insert bearing")
        self.insert_btn.setToolTip(
            "Insert the selected size as a standard bearing (attached to the edges "
            "selected before opening this panel, if any). Double-click a row does the same."
        )
        self.print_btn = QtGui.QPushButton(QtGui.QIcon(icon("PrintableBearing.svg")), "Printable…")
        self.print_btn.setToolTip("Open the 3D-printable bearing panel with this size.")
        buttons.addWidget(self.insert_btn)
        buttons.addWidget(self.print_btn)
        layout.addLayout(buttons)

        self.name.textChanged.connect(self.update)
        for s in (self.d, self.D, self.B, self.tol):
            s.valueChanged.connect(self.update)
        self.table.itemSelectionChanged.connect(self.update_buttons)
        self.table.cellDoubleClicked.connect(lambda *_: self.insert())
        self.insert_btn.clicked.connect(self.insert)
        self.print_btn.clicked.connect(self.printable)
        self.results = []
        self.update()

    def criteria(self):
        val = lambda s: s.value() or None  # noqa: E731 (0 = "Any")
        return dict(
            name=self.name.text().strip() or None,
            d=val(self.d),
            D=val(self.D),
            B=val(self.B),
            tol=self.tol.value(),
        )

    def update(self, *_):
        c = self.criteria()
        self.results = BD.search(**c)  # no criteria: the whole catalog
        _, closure, flanged = BD.parse_designation(c["name"]) if c["name"] else (None, None, False)
        self.closure, self.flanged = closure or "Open", flanged
        self.table.setRowCount(len(self.results))
        for i, (series, r) in enumerate(self.results):
            shown = BD.full_designation(r, self.closure, self.flanged)
            cells = [
                shown,
                series,
                _num(r.d),
                _num(r.D),
                _num(r.B),
                _num(r.B_shielded),
                "%gx%g" % (r.D1, r.C1) if r.has_flange else "",
            ]
            for j, text in enumerate(cells):
                item = QtGui.QTableWidgetItem(text)
                if j >= 2:
                    item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                self.table.setItem(i, j, item)
        self.table.resizeColumnsToContents()
        self.count.setText(
            "%d bearing%s" % (len(self.results), "" if len(self.results) == 1 else "s")
        )
        if self.results:
            self.table.selectRow(0)
        self.update_buttons()

    def update_buttons(self):
        ok = self.current() is not None and App.ActiveDocument is not None
        self.insert_btn.setEnabled(ok)
        self.print_btn.setEnabled(ok)

    def current(self):
        rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        return self.results[rows[0].row()] if rows else None

    def insert(self):
        hit = self.current()
        if hit is None or App.ActiveDocument is None:
            return
        series, row = hit
        doc = App.ActiveDocument
        doc.openTransaction("Add bearing")
        created = []
        for target in self.edges or [None]:
            obj = BearingBase.make_bearing(
                series,
                row.name,
                attach_to=target,
                doc=doc,
                Closure=self.closure,
                Flanged=self.flanged,
            )
            created.append(obj)
        doc.commitTransaction()
        Gui.Selection.clearSelection()
        for obj in created:
            Gui.Selection.addSelection(obj)

    def printable(self):
        hit = self.current()
        if hit is None:
            return
        _, row = hit
        Gui.Control.closeDialog()
        import PrintableBearingGui

        PrintableBearingGui.open_panel(preset=(row.d, row.D, row.B))

    def getStandardButtons(self):
        return QtGui.QDialogButtonBox.Close  # no int(): PySide6 enums

    def reject(self):
        Gui.Control.closeDialog()
        return True


def open_panel():
    edges = [(obj, [sub]) for obj, sub in BRS.selected_edges()]
    panel = SearchPanel(edges)
    Gui.Control.showDialog(panel)
    return panel


class SearchCommand:
    def GetResources(self):
        return {
            "Pixmap": icon("BearingSearch.svg"),
            "MenuText": "Find bearing",
            "ToolTip": "Search bearings by name (608, F688-2RS, 62…), inner diameter, "
            "outer diameter or height, and insert one.\nSelect circular edges first to attach the "
            "inserted bearing to them.",
        }

    def IsActive(self):
        return App.ActiveDocument is not None and Gui.Control.activeDialog() is False

    def Activated(self):
        open_panel()


Gui.addCommand("Bearings_Search", SearchCommand())
