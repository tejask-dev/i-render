# I, Render

**One-line pitch**

Sketch a robot, show Rendi your junk drawer, and get a dimensioned 3D model plus a list of parts you could reuse.

## Inspiration

A maker can draw a small rover in ten seconds. The harder question is whether an old toy car and a flashlight contain anything that would help build it. We wanted to make that first design decision easier, before someone buys parts or spends hours printing a chassis.

## What it does

Rendi asks three questions about the robot’s size, personality and job. Our recording is an automated run of the real interface. It asks for *Snack Scout*, a 20 cm desk robot that rolls and lights up, and uploads an original test drawing. Rendi produced a seven-part model that can be rotated, inspected in millimetres and downloaded as an STL.

Next, the run uploaded a collage of reference photographs of an RC car and an AA flashlight. The workbench drew a box around each object and matched four of ten required component units to potential donors. The car could supply one motor and two wheels. The flashlight could supply one LED. The plan listed the remaining motor, driver, power supply, LED and two resistors. The run saved the plan and reopened it by searching for Snack Scout in Rendi’s notebook. The saved project on the demo Mac was created by replaying the same files through the real API.

## How we built it

The recorded workflow runs on a Mac. Qwen3-VL reads the images through Ollama. A FastAPI backend validates the proposed shapes, scales them to the brief and builds solids using Manifold. Trimesh exports the STL and a GLB with independently selectable parts. Three.js displays the GLB in the browser. A component table allocates donor quantities, and SQLite stores each saved plan. The interview also supports push-to-talk through local Whisper and spoken prompts through browser speech synthesis. An optional browser speech service and an optional Gemini adapter can send data off the Mac. The interface labels both.

## The challenge

A drawing shows a front view. It gives few clues about depth, hidden joints or axle diameters. We kept those assumptions visible and made each part inspectable. A similar problem appeared in the drawer scan. Recognizing a toy car tells us where to look for wheels. Only a physical inspection can establish that the wheels fit or the motor works.

## What we’re proud of and what’s next

One drawing made it all the way to a selectable model, a downloadable STL and a saved parts plan. For the next check, we’ll photograph our own donors, measure a wheel and axle against the model, then print and dry-fit the mount. The recorded 40% measures candidate coverage by quantity. Fabrication and physical operation remain to be verified.

## Credits

Zlata prepared the product and feature specifications. Brian planned the physical companion and voice setup and investigated printing. Tejass coordinated the software build. Codex and Claude Fable assisted with implementation, debugging, design and review. OpenAI image generation supplied the workshop and starter illustrations. The recording uses an original test drawing, a CC0 RC car photo by Editor abcdef and a public-domain flashlight photo by Evan-Amos. [RC car photograph](https://commons.wikimedia.org/wiki/File:Radio_controlled_car_on_ground.JPG) · [Flashlight photograph](https://commons.wikimedia.org/wiki/File:Led-flashlight.jpg)

## Zlata’s submission checks

- [ ] Confirm the final roster, each person’s contributions and any on-site test results with Brian and Tejass.
- [ ] Review the 79-second recording. It is an automated run of the real interface, uses fresh on-device recognition with shortened waits and shows a saved, planned build. Use the actual uploaded video URL if adding it to Devpost. [Local walkthrough](demo/I-Render-walkthrough.mp4)
- [ ] Use the working demo for overall judging. Consider Most Adventurous for helping people discover a use for old hardware. Select a sponsor track only after the team can demonstrate its actual requirements. Match the final roster and track selections on the live site and Devpost. [Prize descriptions](https://hack-western-13.devpost.com/#prizes)
- [ ] Finish the Devpost entry and stop coding by **Sunday, November 22, 2026 at 9:00 a.m. Toronto time**. Check that the submission is final and retain its confirmation. [Organizer rules](https://hack-western-13.devpost.com/rules) · [Live portal](https://www.hackwestern.com/live)
