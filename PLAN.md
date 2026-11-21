# I, Render • weekend build plan

Zlata defined the three-part maker experience. Tejass owns the workbench, and Brian is preparing the physical companion for the live demo. The enclosure is the immediate fabrication dependency.

**Demo first.** A judge answers Rendi, chooses a paper sketch or a labelled example, rotates and selects a real dimensioned CAD part, scans or selects their drawer contents, inspects the matched quantities, downloads their STL, and saves the build. The next interview can recall it. Explicitly identify sample inputs, local speech, manual input, and live vision in the interface.

1. Build a validated RobotSpec and deterministic mesh exports using the attached 03b schema. Produce at least wheelbot, armbot and blobbot examples. Build the shell separately for Brian and verify its digital geometry.
2. Serve a local FastAPI app. SQLite stores briefs, plans and memory across restarts. Use local Qwen3-VL for live photo recognition and configure optional Gemini via server environment. Unavailable service gives an actionable manual/example path. A missing photo service never pretends to recognize an arbitrary upload.
3. Build a responsive local UI with a browser speech/text interview, sketch input, clickable orbit viewer, drawer input, matched build plan, downloads and memory. All assets for the core flow run locally.
4. Rehearse with real HTTP and a browser, test a second project, check exports and review the integrated result with Claude. Gather print/voice/photo evidence at the venue; record known gaps and the three-minute script.
5. Reconcile Slack with the organizer sources. Sunday Nov 22 9 a.m. Toronto is the stop/build and submission deadline. Prepare for 11:30 general judging pending the assigned slot. Keep track claims tied to actual integrations and record AI assistance. Zlata owns external submission.

## API agreement

FastAPI serves frontend/dist at /. Base path /api. JSON response bodies:
- GET /api/config → {vision_available:bool, templates:[{id,label}], salvage_keys:[{id,label}]}
- POST /api/brief with ProjectBrief → {brief_id}; GET /api/brief/latest → brief plus ID.
- POST /api/sketch as multipart: brief_id, and image OR template (wheelbot, armbot, blobbot). Returns {spec_id,spec,glb_url,stl_url,source} with source "example", "local", "gemini", "cached_local" or "cached_gemini". RobotSpec exactly 03b (Z up in source, standard GLB Y up, named meshes, metres).
- POST /api/junk as multipart: image OR items (JSON array of canonical salvage IDs, duplicates permitted). Returns {inventory_id,inventory:{items:[{label,raw_name,box_2d,condition_note}]},source}. Zero items is valid. Boxes normalized 0–1000 YX. Manual sorting uses "manual".
- POST /api/plan JSON {spec_id,inventory_id,brief_id} → {plan_id,plan:{from_your_drawer:[{need,qty,source,how,tools}],to_source:[{need,qty,suggestion}],drawer_score:0..100,steps:[string],memory_notes:[string]}}.
- POST /api/projects JSON {plan_id,outcome:"planned"} → {project_id}. GET /api/projects/{id} returns {brief,spec,plan,glb_url,stl_url}. GET /api/memory/search?q= → array of {project_name,note,outcome,seeded}.
