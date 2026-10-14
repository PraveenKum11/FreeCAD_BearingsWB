# Getting started

## The toolbars

![The Bearings and Bearing tools toolbars](images/wiki-toolbars.png)

- **Bearings**: one drop-down per family. Click the arrow to pick a series; the button
  remembers the last one. The **Bearings** menu lists every series by family.
- **Bearing tools**: [[Find bearing]], [[Printable bearings|3D-printable bearing]] and
  [[Bearing BOM]].

## Insert a bearing

With nothing selected, a series button inserts a common size at the origin: 608, 625,
R188, 7204B, NU204, 30204, HK0810, LM8UU, … Select it and change anything in the
property editor; the shape updates on recompute.

![The properties of a 608-2RS](images/wiki-properties.png)

| Property | What it does |
|---|---|
| `Series` | The family member: 60, 62, 63, 68, 69, MR, R, 72, NU2, 302, HK, LM, … |
| `Designation` | The size, or `Auto` to match the attached edge |
| `Closure` | Open, Z, ZZ, RS, 2RS (deep groove bearings) |
| `Flanged`, `FlangeShape` | Flanged variants (F608, MF105, FR188, LMF / LMK) |
| `Variant` | NU / NJ cylindrical roller bearings; AXK with or without AS washers |
| `DetailLevel` | Envelope (one solid), Standard, Detailed (adds the cage) |
| `MatchTo` | With `Auto`: match the edge to the bore (Shaft) or the outside (Housing) |
| `BaseObject` | The circular edge it is attached to |
| `Invert`, `Offset` | Flip it to the other side of the edge, shift it along its axis |

The **Bearing info** group shows what the part is: its full designation (`608-2RS`), bore,
outside diameter, width and, for rolling bearings, the computed ball size and count.

## Attach it to a hole or a shaft

Select one or more circular edges, then pick a series. Each edge gets a bearing:

- the edge of a **hole** gets the bearing whose outside diameter matches, sitting in the
  hole flush with the face (a flanged one rests its flange on the face);
- the end of a **shaft** gets the bearing whose bore matches, sliding onto the shaft.

![A 608 sized to a 22 mm hole, and a 608 sized to an 8 mm shaft](images/edge-snap.png)

The bearing follows the edge when the part changes. `Invert` puts it on the other side
of the edge and `Offset` moves it along the axis.

## Labels

The label follows the designation (`608`, then `608-2RS` after you add seals) until you
rename the bearing. Further bearings of the same size are `608_001`, `608_002`, …
