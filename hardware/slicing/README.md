# Rendi print queue

## Companion enclosure

Open [Rendi-P1S.3mf](Rendi-P1S.3mf) as a **project** in Bambu Studio. Plate 1 contains the front half, back half, join ring and faceplate. The estimate for all four together is **2 h 49 min and 76.89 g of PLA** (25.78 m). An 8 a.m. start gives an estimated 10:49 a.m. finish before cooldown and removal. The Saturday room 2247 windows announced to Brian are 8–11 a.m. and 3–7 p.m.

1. Confirm a Bambu Lab P1S, **0.4 mm nozzle**, textured PEI plate and plain 1.75 mm PLA with the lab operator. The project uses Generic PLA at 220 °C with a 55 °C bed. Pick the actual spool in Studio. If the hardware, plate or material differs, change the profile and slice again on site.
2. Keep the parts at 100% scale in their saved orientations. The two shell halves sit seam-down. The ring lies flat and the faceplate sits on its exported base. The project prints all four by layer on one plate.
3. Preview the first layer, the two shell crowns and the speaker grille with the operator. The project uses a 0.20 mm first layer, 0.28 mm subsequent layers, three wall loops, 15% grid infill and automatic organic tree supports from the build plate at a 30° threshold. A separate support-free slice flagged floating regions on the back half.
4. After cooling, remove supports from inside the halves and clear the grille and mating edges. Dry-fit the ring and faceplate before installing electronics. The modeled minimum faceplate gap is only 0.06 mm. If it binds, lightly sand the insert rim or increase `FACE_FIT` and reprint just that piece. See the [shell fit notes](../README.md).

**Local verification.** Bambu Studio 2.9.1.70 sliced the four integrated STLs with its P1S machine profile. A fresh local configuration reopened this project and sliced it again using the embedded settings alone. Both slices produced one plate, all four expected parts, the same ETA and material, and an empty plate-warning field. The lab printer, spool, queue, and physical fit still need an on-site check.


## Sketch-derived wheel and rover

For the 3–7 p.m. room 2247 window, start with the **single wheel** if the team wants to check a donor axle. The print-time estimates include printer preparation. Allow extra time for the queue, cooling and inspection.

| Plate | What to print | Saved estimate | Fresh re-slice |
| --- | --- | --- | --- |
| [Wheel fit check](Sketch-wheel-fit-P1S.3mf) | One full-size wheel lying flat, axle opening vertical | 30 min 42 s, 16.97 g PLA | 30 min 46 s, 16.97 g |
| [Complete display rover](Sketch-rover-display-P1S.3mf) | Full-size model on its back, front facing up | 3 h 24 min 34 s, 107.83 g PLA | 3 h 23 min 42 s, 107.04 g |

The workbench generated the model from the [wheelbot reference drawing](../../eval/inputs/wheelbot.jpg). The fit plate uses the actual named mesh `wheel_3`. Its GLB vertices were converted from Y-up metres to the workbench’s Z-up millimetres and rotated onto a flat wheel face. The wheel measures **55.4 mm in diameter and 23.8 mm thick**. Its through-hole measures **5.00 mm across opposite vertices and 4.904 mm across opposite flats**. A true 5 mm round shaft can bind even before printer tolerances. Measure the donor shaft with calipers, compare it to the cooled hole, and record fit before committing to a chassis. Keep scale at 100%.

The display plate uses the complete STL from the same build. Its footprint is 158.6 × 201.45 mm and its height on the bed is 58.6 mm. As a shape prototype it demonstrates the exported geometry. Wheel rotation, chassis assembly and donor compatibility require separate mechanical design and testing. The original upright slice reported six unsupported regions and took 7 h 25 min. Laying the rover on its back with snug supports cleared those warnings. An 8% grid trial took 4 h 38 min and 178.92 g. The supplied lightweight display plate uses 12% lightning infill.

Both projects use a Bambu P1S, 0.4 mm nozzle, Generic PLA, textured PEI plate, 220 °C nozzle, 55 °C bed, 0.20 mm first layer, 0.28 mm subsequent layers and two wall loops. The wheel uses 12% grid infill and zero supports. The rover uses snug automatic supports, a 45° threshold and support placement on both the part and plate. Preview the base, antenna and support removal with the lab operator. Bambu Studio 2.9.1.70 reopened and sliced each saved project using a fresh configuration. Both produced one plate with an empty plate-warning field. Physical prints and axle measurements are pending.
