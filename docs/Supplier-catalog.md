# Tashev-Galving bearing catalog

The offline snapshot in `BRData/tashev_catalog.csv` covers the complete
[bearing category](https://tashev-galving.com/cat/100116/lageri) checked on **2026-10-18**:

| Category | Articles |
|---|---:|
| Ball bearings (including automotive kits and two loose-ball products) | 284 |
| Thrust ball bearings | 22 |
| Roller bearings | 18 |
| Mounted units | 11 |
| Total | 335 |

The live audit also descends through all ten further submenu categories (wheel,
mounted, single-direction thrust, double-row roller, needle, tapered, spherical,
stud, single-row ball and self-aligning ball), deduplicating their articles.

All **335 articles** map to insertable models: 333 assembled-bearing articles plus
`139-FRV-138` (Fervi loose-ball assortment) and `056-PRZ-631` (6 mm loose balls).
The latter are recorded as accessories and modeled as steel rolling elements.
Prices, stock, product descriptions
and photographs are not bundled. The workbench makes no network requests.

## Finding and inserting a bearing

Use **Bearing tools → Find bearing** with a supplier article number (`056 GRP 222`),
a designation (`UCP205`, `NN 3015 SKMSP`, `1306 K/236725`, `VKBA 542`), or dimensions.
Shields and seals survive supplier suffixes such as `ZZC3`, `ZZ/SBB`, `2RSH` and
`2RSL/C3`. Clearance grades and cage/precision suffixes do not change the model's
internal clearances or establish a load rating.

The new toolbar groups contain mounted units, spherical rollers, wheel-kit bearing
components, cam followers and loose balls. Existing groups gain the 160, 161, 64, 6300, 512, 322
and NN30 series. The 62, 511 and NK tables include the additional required sizes.

Every series is available through **Bearings → its family submenu**, its toolbar
drop-down, and Find bearing. Select a size in the object's **Designation** property.

| Supplier subcategory | Workbench menus |
|---|---|
| Ball bearings | Deep groove, Angular contact, Self-aligning, Special/wheel/stud, Loose balls |
| Thrust ball bearings | Thrust bearings |
| Roller bearings | Cylindrical, Tapered, Spherical, Needle |
| Mounted units | Mounted bearing units: UCP, UCF, UCFL, SBLF |

Wheel kits with different bearings have individually selectable components, for
example `VKBA542-1` and `VKBA542-2`. Kit nuts, separate shaft seals, caps, circlips and
spacers are not modeled. A kit containing two equal bearings has one selectable size.
Search its article number or unique kit designation and use **Insert complete set**
to insert every bearing with the correct quantities, or use Python:

```python
import BearingCatalog

bearings = BearingCatalog.make_product("056 SKF 154")  # both VKBA 542 bearings
```

The **Loose bearing balls** menu contains all 11 diameters in the
[Fervi 0116 assortment](https://www.fervi.com/eng/hardware/sets-and-fastenings/sets/metric-chromed-steel-ball-set-pr-6084.htm),
from 2 to 8 mm. Search `139 FRV 138` to select one diameter or insert the complete
450-ball assortment. Search `056 PRZ 631` for a single 6 mm ball. The assortment's
storage box is omitted. Balls have no bore or automatic shaft/housing fit.

These are independent parametric bearing objects at the origin. Position them in your
assembly: a kit does not define the installed spacing between bearings. The BOM counts
each bearing component, not a complete repair kit. Existing closure, detail, placement,
save/restore and BOM features apply. `SourceURL`, `SupplierArticle` and `ModelNotes`
record provenance and qualifications on the inserted objects.

## Mounting dimensions and detail

Mounted units retain the shaft bore, base/flange footprint and bolt-hole spacing.
Their axis is Z; a pillow block's mounting face is at `y = -H`. Flanged housings have
their mounting face at `z = -B`. Their `OuterDiameter` is the insert's diameter, not
the housing length. Auto-sizing uses the shaft bore; an insert OD is not treated as a
mounting hole for the entire housing.

KR19PP has an **8 mm stud**, 19 mm roller, 11 mm roller width and 32 mm overall length.
Its diameter field is the stud diameter, not a hollow bore. It auto-sizes to a mounting
hole, with the stud shoulder on the selected face. Threads are smooth envelopes.

NN30 K and 1306 K include the 1:12 tapered bore. Spherical roller bearings contain two
rows of barrel rollers and a spherical outer raceway. Automotive double-row ball
bearings have opposing rows, a split inner ring, joined outer ring and two seals.
Detailed mode adds ball cages; the new roller bearings use the same geometry as Standard.

Like the existing workbench, these are representative assembly models. Rolling-element
sizes/counts, raceways, casting contours and contact angles are computed. Mounted-unit
locking screws and lubrication fittings are omitted. Automotive cone/cup widths are
representative where only the bearing boundary dimensions are published. Published
wheel-kit dimensions are sometimes rounded; these models are not manufacturing drawings.

## Sources and conflicting dimensions

Every row in `catalog_extra.csv` and `housed.csv` has a dimension source and notes.
The coverage file records the supplier URL and detected title/dimension disagreements
for each article. Sources are the supplier's dimension sheets, manufacturer catalogs,
and SKF's automotive product pages. For example:

- UCP and UCFL mounting dimensions come from the supplier's
  [UCP drawing](https://tashev-galving.com/files/spec/056%20GRP%20222.pdf) and
  [UCFL drawing](https://tashev-galving.com/files/spec/056%20GRP%20352.pdf).
  Housing width, insert width and overall height are separate measurements.
- The 322 taper series uses NTN/NSK standard d/D/T and cone/cup widths, linked from
  each dimension row. A listing's cone
  width is not used as its assembled total width. 32210 is 50 × 90 × 24.75 mm.
- [NSK 51122](https://www.nsk.com/engineering/51122-tb-sd.html) is 110 × 145 × 25 mm;
  51103 is 17 × 30 × 9 mm. The standard
  dimensions take precedence over inconsistent listing titles.
- [SKF's VKBA577 page](https://automotive.skf.com/eur/en/product-catalogue/VKBA577)
  gives 34 × 62 × 37 mm; the supplier title gives 34 × 64 × 37.
- LM11949/910/Q uses SKF's d/D/T = 19.05/45.237/15.494 mm, with cone width
  16.637 mm and cup width 12.065 mm. The cone projects beyond the cup, including
  at Envelope detail.
- **996905 remains a source conflict:** the supplier's attached
  [dimension sheet](https://tashev-galving.com/files/spec/056%20GRP%20123.pdf)
  says 28 × 47 × 9 mm, while its description says 26.222 × 47 × 13.2 mm. The
  model follows the dimension sheet and exposes this qualification in `ModelNotes`.
  Verify the actual supplied part before relying on either set for a tight fit.
- Two unnamed listings are matched by their boundary dimensions: `056-PRZ-217`
  to 6014 (70 × 110 × 20), and `056-PRZ-262` to 689 (9 × 17 × 4).

## Maintaining coverage

Run `python tools/audit_tashev_catalog.py` with ordinary Python to discover the bearing
category's menu, traverse its subcategories and listing pages, and compare article
numbers against the snapshot. It reports added/removed articles and categories as JSON
and exits nonzero on a difference or fetch failure. It does not infer dimensions from
product names or overwrite tables. The snapshot records component mappings as
`series:designation:closure[:quantity]`; an omitted quantity means one.

`test_catalog` checks every article mapping and insertion closure offline.
`test_catalog_geometry` verifies every added size at all detail levels, mounting-hole
clearance, bore clearance, non-overlapping components, real tapered bores/studs, and
document/BOM round trips. The general geometry suite also exercises the new annular
bearing rows with the existing families. `tests/gui/catalog_smoke.py` invokes every
series' menu command, verifies valid geometry, and tests supplier search, closures,
complete-kit insertion and the loose-ball assortment's choices and quantities.
