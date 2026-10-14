# Bearing types

Besides [[deep groove ball bearings|Standard bearings]], the workbench has the other
common rolling bearing types. They attach to edges, appear in [[Find bearing]] and the
[[Bearing BOM]], and follow the same labels.

## Angular contact (72xx B, 73xx B)

![6204, 7204B and 51104 cut away](images/angular-thrust.png)

Same boundary dimensions as the 62 / 63 series, 40° contact angle (suffix B). Each ring
has a high shoulder on one side and a low one on the other, so the bearing carries axial
load from the top. Usually mounted in pairs. Open only.

## Thrust ball bearings (511xx)

Two washers with the balls between them, for axial loads (turntables, lazy susans): the
**shaft washer** at the bottom fits the shaft, the **housing washer** on top sits clear of
it. Detailed adds the flat cage.

## Self-aligning, cylindrical, tapered and needle bearings

![2205, NU2205, NJ2205, 30205, HK2520 and AXK2542 cut away](images/more-types.png)

| Type | Series | Notes |
|---|---|---|
| Self-aligning ball | 12, 13, 22, 23 | Two rows of balls on a spherical outer raceway; tolerates a misaligned shaft |
| Cylindrical roller | NU2, NU3, NU22, NU23 | `Variant` NU (ribs on the outer ring only, the shaft can float axially) or NJ (one inner rib too) |
| Tapered roller | 302, 303, 320 | Cone, cup and rollers share one apex on the axis; the cone's back rib holds the rollers |
| Needle roller | HK (drawn cup), NK (machined) | No inner ring: select the shaft, the needles run right on it |
| Thrust needle | AXK | Cage with radial needles; `Variant` "AXK + 2 AS" adds an AS washer on each side |

The 12 / 13 / NU2 / NU3 sizes have the boundary dimensions of the 62 / 63 series
(ISO 15); 22 / 23 are the wide series. The cages of roller and needle bearings aren't
modelled, so Detailed looks like Standard.
