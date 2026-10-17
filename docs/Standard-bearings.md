# Standard bearings

Deep groove ball bearings, the most common kind: skateboard 608s, the 625s in 3D printer
extruders, miniatures in RC models, inch R sizes in fidget spinners.

| Series | What it is | Example |
|---|---|---|
| **60** | Deep groove, light | 608 (8 × 22 × 7) |
| **62** | Deep groove, medium | 625 (5 × 16 × 5), 6204 |
| **63** | Deep groove, heavy | 6300 |
| **68** (618) | Thin section | 688 (8 × 16 × 4) |
| **69** (619) | Thin section | 695 |
| **MR** | Metric miniature | MR105 (5 × 10 × 3) |
| **R** | Inch miniature | R188 (1/4" × 1/2" × 1/8") |

## Closures and flanges

`Closure`: **Open**, **Z** / **ZZ** (metal shields) and **RS** / **2RS** (rubber seals). A
single closure sits on the top face. Miniature bearings are often wider when shielded
(688 is 4 mm open, 5 mm as 688ZZ); the workbench uses the right width.

Miniature sizes also come **flanged** (`Flanged`): F688, MF105, FR188. In a hole, the
flange rests on the face and only the body goes in.

![608 open, 608ZZ, 608-2RS and F688ZZ](images/closures.png)

## Detail levels

![A 6204-2RS at the three detail levels](images/detail-levels.png)

- **Envelope**: one solid, the fastest in big assemblies.
- **Standard** (default): rings with their raceways, the balls, shields or seals.
- **Detailed**: adds a ribbon cage.

## How the internals are made

The tables hold only the standard boundary dimensions (ISO 15): bore, outside diameter,
width and corner radius. The ball size is the largest standard ball that fits, and the
ball count the most that fit around the pitch circle, so the shapes are representative,
not a copy of one maker's drawing (608: 7 balls of 4 mm; a real 608 has 7 of 3.969 mm).

## Attaching

See [[Attach it to a hole or a shaft|Getting started#attach-it-to-a-hole-or-a-shaft]].
`MatchTo` decides whether an `Auto` designation matches the edge to the bore (Shaft) or
the outside (Housing); it is set from the geometry when you attach (a hole is Housing, a
shaft end Shaft).

`Auto` uses a size whose outside diameter is equal to the hole or up to the **fit
allowance** smaller, or whose bore is equal to the shaft or up to the allowance larger, so a
22.2 mm hole or a 7.98 mm shaft still gets a 608. The closest size wins, and a bearing is
never picked that would be too big for the hole or too small for the shaft. The allowance
is 0.5 mm by default; change it in **Bearing tools → Settings** (0 needs an exact
match). `FitClearance` in the Bearing info group shows the clearance left. If the
series has no size that fits, no bearing is added and a message names the nearest sizes. To use
one anyway, keep the edge selected and insert it from Find bearing. If the edge later changes to a size the series
does not have, the bearing shows an error on recompute.
