# Three minutes with Rendi

**Bring** a legible front-view robot drawing, a small toy car, a flashlight, the laptop and its charger. Use one fresh sketch and one constrained drawer shot. Avoid telling judges a spare part works until someone inspects the actual donor.

| Clock | Person | Action and words |
| --- | --- | --- |
| 0:00–0:18 | Zlata | Put the sketch beside the objects. “I can draw the robot I want. What I don’t know is what I can build from these two things.” Introduce Rendi. |
| 0:18–0:45 | Brian | Turn on voice. Give Rendi the desk size, two personality words and the job. Confirm the brief. Let the judge choose one of these answers. |
| 0:45–1:35 | Tejass | Click **Use camera instead** and hold up the sketch, or upload its photo. Start recognition. While it runs, show the paper and explain that vision identifies front-view parts. Geometry code sizes real solids in millimetres. Rotate the result and click a wheel, head or arm. |
| 1:35–2:25 | Brian | Photograph the drawer or upload the prepared shot. Show one bounding box, a donor component and the quantity still needed. “The car can contribute wheels. We still need a compatible driver.” Use the actual values on screen. |
| 2:25–2:50 | Zlata | Download the STL. Save the plan, open the notebook and retrieve it. Explain that saved plans carry a “planned” outcome until someone actually builds them. |
| 2:50–3:00 | Zlata | “From one drawing, we have a model we can inspect and a parts list we can check against the drawer.” Stop and take questions. |

**If the room is loud**, type the three answers. **If fresh recognition is slow or offline**, open the [saved Snack Scout project](http://127.0.0.1:8765/project/p_d58d57f4214745ed951e4e9fef7d49b0) and tell the judge it was processed earlier by replaying the recording’s files through the real API. A saved sketch read applies only to the same image with the same brief. A different brief or a new photo needs the vision model. The first photo after about 15 idle minutes waits for the model to reload, so run one sketch shortly before judging. The three starter designs are clearly labelled examples. Manual inventory is a separate input path. **If the shell hasn’t printed**, show its actual CAD and say it is awaiting fabrication. Use the recording, an automated run of the real interface, as an emergency walkthrough if organizers permit it. The judging rules call for a live demo.

## Questions the team can answer

- **Where did the dimensions come from?** The maker chooses a target size. The model estimates the visible parts and their proportions. Deterministic geometry generates the STL and GLB. Show an assumption and physically measure a donor before claiming a fit.
- **What does the percentage measure?** Matched candidate component units divided by required units. The program allocates the available counts and lists the shortfall. Price, verified compatibility and working condition are separate.
- **What is AI here?** In the preferred on-device path, Qwen sees the input, Whisper transcribes speech, and browser synthesis speaks the interview. The optional browser speech service and Gemini routes can send audio or images off the Mac, and the interface labels them. The interview sequence, geometry, matching and SQLite recall are application code. The browser labels saved recognitions and prebuilt examples.
- **What did the humans and tools do?** Credit Zlata's research, specs and demo decisions, Brian’s hardware work, and Tejass’s coordination. Disclose Codex and Claude’s design, implementation and review contributions. Add human work completed after this handoff.

## Track decisions for Zlata

Lead with the overall prizes and Most Adventurous. Prepare PCBWay once a physical prototype can demonstrate the problem it solves. A PCB for the mic, speaker and eyes is a concrete next fabrication step. Demonstrate an actual Gemini request before claiming the Gemini track. Local SQLite is the current memory store. Entire requires evidence captured in Entire itself. Record the same final roster and track choices in both portals. The organizer’s full criteria are in the [event guide](event-guide.md).

Stop coding and finalize Devpost by **Sunday, Nov 22 at 9 a.m. Toronto time**. Watch the live portal for sponsor slots by 9:45 a.m. Be ready at the assigned general table by 11:30 a.m.
