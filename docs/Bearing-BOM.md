# Bearing BOM

**Bearing tools → Bearing BOM** lists every bearing in the document with its quantity:

- standard bearings and bushings by full designation, with
  App::Link copies and link arrays counted;
- the AS washers of AXK assemblies that have them;
- printable bearings by size, and the balls they need, so you know what to buy.

![The Bearing BOM panel](images/bom-panel.png)

Hidden objects (for example a standard bearing you replaced with a printable one) are
skipped unless you untick **Skip hidden objects**. **Save CSV…** writes the list for a
spreadsheet, with the columns Item, Description, Bore d, OD D, Width, Quantity and the
objects it came from.

From Python:

```python
import BearingBOM

items = BearingBOM.bom_items(App.ActiveDocument)
BearingBOM.write_csv("/path/to/bearings.csv", items)
```
