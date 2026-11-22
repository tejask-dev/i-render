# RoomProof status

Updated November 21, 2026, 21:05 Toronto. The goal remains active.

- Branch `codex/roomproof`, based on `7602aeb`; I, Render and `main` preserved.
- Team-scaler run `2530376a-a3b0-4a64-9cfd-93b024ed57dc`: Claude backend integrated; native geometry, visual and contract-review contributions integrated. External review approved with limitations; its four material findings and the PDF/camera fixes were independently rechecked as corrected. Live-provider and physical-device gates remain mandatory.
- Target is the regular iPhone 16. Manual room measurements are primary; optional photos describe style. Pro/LiDAR capture is deferred.
- Implemented: SwiftUI room/brief/plan screens, RealityKit preview, editable floor plan, local constraint and budget solver, explicit repair, project library, atomic persistence and PDF Fit Sheet. Server holds provider keys; the phone stores its pairing token in Keychain.
- Core: 13 focused Swift tests pass. Native: all 8 hosted XCTest checks pass on the iPhone 17e simulator. The initial loader hang was resolved using `/private/tmp` DerivedData and normal simulator ad-hoc signing; no privacy settings changed. The final generic iOS device build compiles unsigned.
- Screen rehearsal: observed 3D and top-down views; CAD 250 → 200 replaces the CAD 248 pair with CAD 178.99; moving into the door reserve blocks export; explicit Fix position restores a valid plan. These observations used labeled saved/sample evidence.
- PDF generation and content checks pass. The final sample was visually reviewed and occupies two pages with qualifications and selected-product evidence intact.
- Review corrections: sourcing jobs survive same-workspace edits, incomplete refreshed evidence preserves the last pose while blocking export, 3D handedness now agrees with the floor plan, and Gemini accepts ordinary qualitative wording while refusing explicit numerical claims. Background saves no longer hide an unchanged PDF share action.
- Backend mocked suite passes after evidence validation and retry corrections. Real localhost HTTP confirms authenticated health, unauthenticated rejection, and an honest missing-Gemini-key error. No live provider request has passed yet.
- Mac now detects the physical iPhone 16; Developer Mode is disabled. Personal Team certificate/device registration approval is pending, and no physical install or phone-to-Mac request is claimed.
- Google AI Studio onboarding and TinyFish sign-in/key creation await the user. Private keys are absent. No billing or purchases have been initiated.
- An authorized group update about RoomProof, target tracks and suggested work split was sent to Zlata and Brian at 20:27 and observed in Messages. No event submission or public post.

Remaining gates: provider setup and genuine Gemini/TinyFish responses; personal development signing and Developer Mode; signed install; private-hotspot connection; full physical rehearsal; independent review; commit/push the new branch. Freeze features by 07:30 Toronto November 22; event cutoff 08:50. TestFlight is optional.
