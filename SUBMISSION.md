# I, Render

**Saved Devpost draft:** [Edit the team entry](https://devpost.com/submit-to/31536-hack-western-13/manage/submissions/1315044-i-render/project_details/edit). Created November 21 under Tejass's account, `tejas-teaches`. The story, technology tags, public repository link, demo-recording link, Snack Scout screenshot and additional information are saved; the draft is **4/5 steps complete and not submitted**. All three teammates attend Western University, as confirmed by Tejass. The saved AI disclosure distinguishes the local runtime from unactivated cloud adapters. Team membership, remaining hacker ID and prize selections still need final review before submission. The recording is linked from GitHub; an embedded YouTube/Vimeo video is optional.

**One-line pitch**

Sketch a robot, show Rendi your junk drawer, and get a dimensioned 3D model plus a list of parts you could reuse.

## Inspiration

A maker can draw a small rover in ten seconds. The harder question is whether an old toy car and a flashlight contain anything that would help build it. We wanted to make that first design decision easier, before someone buys parts or spends hours printing a chassis.

## What it does

Rendi is the water-drop-shaped companion for I, Render. Its interview currently runs in the laptop browser: it asks three questions about the robot’s size, personality and job, then hands the confirmed idea to the workbench. Our recording is an automated run of the real interface. It asks for *Snack Scout*, a 20 cm desk robot that rolls and lights up, and uploads an original test drawing. Rendi produced a seven-part model that can be rotated, inspected in millimetres and downloaded as an STL.

Next, the run uploaded a collage of reference photographs of an RC car and an AA flashlight. The workbench drew a box around each object and matched four of ten required component units to potential donors. The car could supply one motor and two wheels. The flashlight could supply one LED. The plan listed the remaining motor, driver, power supply, LED and two resistors. The run saved the plan and reopened it by searching for Snack Scout in Rendi’s notebook. The saved project on the demo Mac was created by replaying the same files through the real API.

For missing components, the workbench can suggest related unused parts and explain the adaptations they need. These suggestions do not change the count of matched parts.

## How we built it

The recorded workflow runs on a Mac. Qwen3-VL reads the images through Ollama. A FastAPI backend validates the proposed shapes, scales them to the brief and builds solids using Manifold. Trimesh exports the STL and a GLB with independently selectable parts. Three.js displays the GLB in the browser. A component table allocates donor quantities, and SQLite stores each saved plan. The interview also supports push-to-talk through local Whisper and spoken prompts through browser speech synthesis. Optional Gemini image recognition and ElevenLabs speech adapters are implemented and tested with mocked provider responses; neither is active in the demonstrated local workflow. Their controls disclose when data would be sent to a provider.

## The challenge

A single drawing gives few clues about depth, hidden joints or axle diameters. We kept those assumptions visible and made each part inspectable. A similar problem appeared in the drawer scan. Recognizing a toy car tells us where to look for wheels. Only a physical inspection can establish that the wheels fit or the motor works.

## What we’re proud of and what’s next

One drawing made it all the way to a selectable model, a downloadable STL and a saved parts plan. For the next check, we’ll photograph our own donors, measure a wheel and axle against the model, then print and dry-fit the mount. The recorded 40% measures candidate coverage by quantity. Fabrication and physical operation remain to be verified.

## Credits

Zlata prepared the product and feature specifications. Brian planned the voice setup, supplied six STL files for Rendi’s four-pin enclosure and reported starting the enclosure print. Tejass coordinated the software build. Codex and Claude Fable assisted with implementation, debugging, design and review. OpenAI image generation supplied the workshop and starter illustrations. The recording uses an original test drawing, a CC0 RC car photo by Editor abcdef and a public-domain flashlight photo by Evan-Amos. [RC car photograph](https://commons.wikimedia.org/wiki/File:Radio_controlled_car_on_ground.JPG) · [Flashlight photograph](https://commons.wikimedia.org/wiki/File:Led-flashlight.jpg)

## Zlata’s submission checks

- [ ] Join the existing team entry rather than creating another. Collect each teammate's three-word hacker ID and school. Keep the secret team invite link private.
- [x] Publish the source repository with Tejass's approval. [The public repository](https://github.com/tejask-dev/i-render) was verified without authentication. A private URL or uploaded ZIP would not satisfy Devpost's requirement.
- [x] Save the required AI-tool selections and implementation disclosure: OpenAI, Anthropic and Other (local Qwen through Ollama). The saved text describes the local runtime and distinguishes mocked adapters from live provider use.
- [ ] Confirm the final roster, each person’s contributions and any on-site test results with Brian and Tejass.
- [ ] Review the 79-second recording. It is an automated run of the real interface, uses fresh on-device recognition with shortened waits and shows a saved, planned build. Use the actual uploaded video URL if adding it to Devpost. [Local walkthrough](demo/I-Render-walkthrough.mp4)
- [ ] Use the working demo for overall judging. Consider Most Adventurous for helping people discover a use for old hardware. Select a sponsor track only after the team can demonstrate its actual requirements. Match the final roster and track selections on the live site and Devpost. [Prize descriptions](https://hack-western-13.devpost.com/#prizes)
- [ ] Finish the Devpost entry and stop coding by **Sunday, November 22, 2026 at 9:00 a.m. Toronto time**. Check that the submission is final and retain its confirmation. [Organizer rules](https://hack-western-13.devpost.com/rules) · [Live portal](https://www.hackwestern.com/live)
