# Data sources

The tables in `BRData/` hold only dimensions: bore, outside diameter, width, corner
radius, and the shielded width, flange and groove sizes where they apply. Everything inside a bearing (ball size and count, raceways, cage) is computed.
No load ratings, speeds or other catalogue data are included.

| Table | Dimensions from | Checked against |
|---|---|---|
| Deep groove 60, 62, 63, 68, 69 | ISO 15 | SKF's public table, every size SKF sells |
| MR miniatures | Common miniature listings | SKF (closed widths) |
| Inch R | ABMA inch dimensions × 25.4 | SKF (R144…R12), a miniature vendor's chart (FR flanges) |
| Angular contact 72 / 73 | The 62 / 63 tables (ISO 15) | SKF's angular contact table |
| Thrust 511 | ISO 104 series 11 | SKF's thrust table |
| Series 22 / 23, self-aligning, NU | ISO 15 | SKF's self-aligning and cylindrical tables |
| Tapered 302 / 303 / 320 | ISO 355 | SKF (d, D, T); PTI and BKZ tables (cone and cup widths) |
| Needle HK / NK, AXK | Common needle bearing sizes | SKF's needle tables |
| LM bushings | Samick's catalog | G2k and Tuli tables |

Miniature shielded widths and flanges vary by vendor: check the CSV
against your supplier's sheet before relying on it for tight fits. The tables are plain
CSV, so they are easy to correct. The details of every check are in `PLAN.md` §4.
