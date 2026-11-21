# Rendi print queue

Open [Rendi-P1S.3mf](Rendi-P1S.3mf) as a **project** in Bambu Studio. Plate 1 contains the front half, back half, join ring and faceplate. The estimate for all four together is **2 h 49 min and 76.89 g of PLA** (25.78 m). An 8 a.m. start gives an estimated 10:49 a.m. finish before cooldown and removal. The Saturday room 2247 windows announced to Brian are 8–11 a.m. and 3–7 p.m.

1. Confirm a Bambu Lab P1S, **0.4 mm nozzle**, textured PEI plate and plain 1.75 mm PLA with the lab operator. The project uses Generic PLA at 220 °C with a 55 °C bed. Pick the actual spool in Studio. If the hardware, plate or material differs, change the profile and slice again on site.
2. Keep the parts at 100% scale in their saved orientations. The two shell halves sit seam-down. The ring lies flat and the faceplate sits on its exported base. The project prints all four by layer on one plate.
3. Preview the first layer, the two shell crowns and the speaker grille with the operator. The project uses a 0.20 mm first layer, 0.28 mm subsequent layers, three wall loops, 15% grid infill and automatic organic tree supports from the build plate at a 30° threshold. A separate support-free slice flagged floating regions on the back half.
4. After cooling, remove supports from inside the halves and clear the grille and mating edges. Dry-fit the ring and faceplate before installing electronics. The modeled minimum faceplate gap is only 0.06 mm. If it binds, lightly sand the insert rim or increase `FACE_FIT` and reprint just that piece. See the [shell fit notes](../README.md).

**Local verification.** Bambu Studio 2.9.1.70 sliced the four integrated STLs with its P1S machine profile. A fresh local configuration reopened this project and sliced it again using the embedded settings alone. Both slices produced one plate, all four expected parts, the same ETA and material, and an empty plate-warning field. The lab printer, spool, queue, and physical fit still need an on-site check.
