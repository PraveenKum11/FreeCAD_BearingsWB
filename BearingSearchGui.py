# SPDX-License-Identifier: GPL-3.0-or-later
"""Find a bearing by name, bore (ID), outside diameter (OD) or height, then insert it."""

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui

import BearingBase
import BearingCatalog
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
        self.name.setPlaceholderText("608, F688-2RS, UCP205, VKBA 542, 056 GRP 222 ...")
        self.name.setToolTip(
            "Designation or its start (62 lists all 62xx), with optional flange (F, MF, FR; "
            "LMF / LMK for linear bushings) and closure (Z, ZZ, RS, 2RS) codes, which are "
            "used when inserting. A size such as 8x22 or 8x22x7 (ID x OD x height) also works."
            " Supplier article numbers (056 GRP 222) also work; wheel kits list their bearings."
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
        self.product_btn = QtGui.QPushButton("Insert complete set")
        self.product_btn.setToolTip(
            "Insert all bearings or loose balls with their listed quantities. Parts start "
            "at the origin; position them in your assembly. Separate kit hardware is excluded."
        )
        layout.addWidget(self.product_btn)

        self.name.textChanged.connect(self.update)
        for s in (self.d, self.D, self.B, self.tol):
            s.valueChanged.connect(self.update)
        self.table.itemSelectionChanged.connect(self.update_buttons)
        self.table.cellDoubleClicked.connect(lambda *_: self.insert())
        self.insert_btn.clicked.connect(self.insert)
        self.print_btn.clicked.connect(self.printable)
        self.product_btn.clicked.connect(self.insert_product)
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
        self.closure, self.flanged = closure or "Open", bool(flanged)
        # linear bushings: parse_designation returns the flange shape (LMF / LMK)
        self.flange_shape = flanged if flanged in BD.FLANGE_SHAPES else "Round"
        self.table.setRowCount(len(self.results))
        for i, (series, r) in enumerate(self.results):
            options = BD.search_options(c["name"], series, r)
            shown = BD.full_designation(
                r,
                options["Closure"],
                options["Flanged"],
                options["FlangeShape"],
                options.get("Variant"),
            )
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
                item.setToolTip(
                    "\n".join(x for x in (getattr(r, "notes", ""), getattr(r, "source", "")) if x)
                )
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
        hit = self.current()
        ok = hit is not None and App.ActiveDocument is not None
        self.insert_btn.setEnabled(ok)
        # a printable bearing is a deep groove ball bearing, not a linear bushing
        self.print_btn.setEnabled(ok and BD.kind(hit[1]) == "deepgroove")
        products = BearingCatalog.lookup(self.name.text())
        count = len(BearingCatalog.components(products[0])) if len(products) == 1 else 0
        self.product_btn.setVisible(count > 1)
        self.product_btn.setEnabled(count > 1 and App.ActiveDocument is not None)
        self.product_btn.setText("Insert complete set (%d parts)" % count)

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
        options = BD.search_options(self.name.text(), series, row)
        products = BearingCatalog.lookup(self.name.text())
        if len(products) == 1:
            options["SupplierArticle"] = products[0]["SKU"]
        targets = [None] if BD.kind(row) == "looseball" else self.edges or [None]
        for target in targets:
            obj = BearingBase.make_bearing(
                series,
                row.name,
                attach_to=target,
                doc=doc,
                **options,
            )
            created.append(obj)
        doc.commitTransaction()
        Gui.Selection.clearSelection()
        for obj in created:
            Gui.Selection.addSelection(obj)

    def insert_product(self):
        products = BearingCatalog.lookup(self.name.text())
        doc = App.ActiveDocument
        if len(products) != 1 or doc is None:
            return
        doc.openTransaction("Add bearing set")
        try:
            created = BearingCatalog.make_product(products[0]["SKU"], doc=doc)
            doc.recompute()
        except Exception:
            doc.abortTransaction()
            raise
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
            "outer diameter or height, and insert one",
        }

    def IsActive(self):
        return App.ActiveDocument is not None and Gui.Control.activeDialog() is False

    def Activated(self):
        open_panel()


Gui.addCommand("Bearings_Search", SearchCommand())
