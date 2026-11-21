# Five-donor recognition check

These three montages use the same five real photographs. The neutral layout places each object in a separate panel. The dim version changes placement, brightness, colour and in-plane rotation. The staggered version varies panel size, order, rotation and contrast. The photos are cropped and resized. The team's physical-drawer checkpoint still needs separate camera captures at the venue.

| Image | Correct object classes in their panels | Eligible for automatic matching |
| --- | --- | --- |
| [Neutral layout](01-neutral.jpg) | 5 of 5 | 4 of 5 |
| [Dim, warm layout](02-dim-warm.jpg) | 5 of 5 | 4 of 5 |
| [Staggered layout](03-staggered.jpg) | 5 of 5 | 4 of 5 |

The local Qwen model identified the RC car, flashlight, mouse, computer fan and USB wall charger once each in every layout. The check requires the center of each detected box to fall in the panel containing that object. Some boxes include substantial panel background. The fan requires in-hand confirmation before it can count as a candidate. Eligibility refers to donor screening. The selected robot's actual component needs determine which candidates enter its plan.

A separate real e-waste photograph exposed a failure that the montages missed. The first model run treated a grille on a desktop power supply as a standalone fan and also detected an installed optical drive. The corrected run excluded the power supply and four CRTs. The matcher now withholds fans and optical drives identified in photos. A user can manually add an already detached, intact component after verifying its low-voltage rating. Previously saved photo detections used in a new plan receive the same screening. A photo cannot confirm corrosion, electrical condition or suitability for dismantling. [Real e-waste scene, AvWijk, public domain](https://commons.wikimedia.org/wiki/File:Ewaste-pile.jpg)

## Photograph credits

- RC car by Editor abcdef, CC0. [Original](https://commons.wikimedia.org/wiki/File:Radio_controlled_car_on_ground.JPG)
- LED flashlight by Evan-Amos, public domain. [Original](https://commons.wikimedia.org/wiki/File:Led-flashlight.jpg)
- CPU fan by Whityya23, CC0. [Original](https://commons.wikimedia.org/wiki/File:CPU_FAN.jpg)
- AOpen optical mouse by Leon Brooks, public domain. [Original](https://commons.wikimedia.org/wiki/File:Red_aopen_computer_optical_mouse.jpg)
- Pisen USB charger by Imgrenb, CC0. [Original](https://commons.wikimedia.org/wiki/File:Pisen_MF-08EU_12W_USB_charger-0.jpg)
