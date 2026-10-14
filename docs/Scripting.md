# Scripting

Everything the toolbar does is available from Python.

```python
import FreeCAD as App
import BearingBase

doc = App.ActiveDocument

# a 608 with seals, at the origin
b = BearingBase.make_bearing("60", "608", Closure="2RS", DetailLevel="Detailed")

# a 608 sized to and attached to a hole edge (Designation "Auto")
plate = doc.getObject("Plate")
b = BearingBase.make_bearing("60", attach_to=(plate, ["Edge7"]))

# other families: series key, designation, extra properties
BearingBase.make_bearing("LM", "LM8UU", Flanged=True, FlangeShape="Square")  # LMK8UU
BearingBase.make_bearing("NU2", "NU204", Variant="NJ")  # NJ204
BearingBase.make_bearing("AXK", "AXK1528", Variant="AXK + 2 AS")
```

## The tables

```python
import BearingData as BD

BD.SERIES  # series key -> (title, table, default, family)
BD.designations("60")  # ['604', '605', ...]
BD.get_row("60", "608")  # BearingRow(608 8x22x7)
BD.search(D=22)  # [(series, row), ...]
BD.search(name="F688-2RS")
BD.parse_designation("MF105ZZ")  # ('MR105', 'ZZ', True)
```

## Shapes without a document

```python
import BearingGeometry as BG

row = BD.get_row("62", "6204")
shape, face_colors = BG.build(row, "2RS", False, "Detailed")
Part.show(shape)
```

## Printable bearings

```python
import PrintableBearing as PB

values = dict(PB.CAGE_DEFAULTS, ID=8, OD=22, Height=7, BallDiameter=4, NumBalls=7)
params = PB.create_races(doc, App.Placement(), values, reverse=False, cage=True, balls=True)
```
