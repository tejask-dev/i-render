# I, Render

Rendi helps a maker turn a robot drawing into a dimensioned 3D model and match the design to candidate parts in a junk drawer. The laptop runs the workbench, vision, geometry and project notebook locally.

[Team handoff](STATUS.md) · [79-second rehearsal](demo/I-Render-walkthrough.mp4) · [31-minute wheel fit check](hardware/slicing/Sketch-wheel-fit-P1S.3mf) · [Rendi enclosure](hardware/slicing/Rendi-P1S.3mf)

## Start on Tejass’s Mac

Double-click **Start Demo.command** to open the workshop. The local address is [127.0.0.1:8765](http://127.0.0.1:8765). Keep the Mac plugged in and the server window open during the fair. The launcher serves the notebook in this folder’s `.var/workbench/`. If another server, such as a rehearsal, already holds port 8765, it stops with instructions and leaves that server running.

1. Click **Start a build**. Turn on **Voice** to hear Rendi. Answer the three questions. **On-device dictation** records only after you tap it. Tap again to stop. You can edit the text and confirm the brief.
2. Choose a sketch file or click **Use camera instead**, frame the drawing and click **Take photo**. The camera switches off after capture. **Build from photo** runs recognition, then generates named 3D solids. Drag to orbit, choose a part to inspect it and download the STL. The interview sets the target size. Depths, joints and hidden surfaces are estimates.
3. Photograph the drawer the same way, upload a file or count the items by hand. Click **Identify items** to analyze the photo. Review boxes and conditions. If two boxes point to the same donor, exclude the extra row before matching parts. Select a wheel to highlight its donor and the exact bill row. The percentage counts candidate component units. Inspect the donor and verify compatibility before building.
4. Click **Save to Rendi’s memory**. The saved address reopens the build. The notebook distinguishes seeded examples from projects actually saved on this Mac.

[Practice drawings and drawer photographs](eval/inputs/) · [Team plan](PLAN.md) · [Three-minute demo](DEMO.md) · [Droplet fabrication](hardware/README.md) · [Devpost draft](SUBMISSION.md)

## Fresh machine

On a Mac with uv and Node.js 22.12 or later, double-click **Start Demo.command**. The first launch installs the pinned dependencies and unpacks the curated Snack Scout notebook if the notebook directory is absent. Later launches preserve existing projects. For a manual installation, use Python 3.12, uv, Node.js 22.12 or later and npm. From this directory run:

```sh
uv venv --python 3.12
uv pip install -r requirements.txt
npm --prefix frontend ci
npm --prefix frontend run build
.venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8765
```

For local photo recognition, install Ollama and run `ollama serve`, then `ollama pull qwen3-vl:4b-instruct` in another terminal. Reload the workbench once downloaded. The first photo loads the model into memory. Subsequent identical inputs may use a labelled saved recognition. Every new shape still goes through the geometry builder.

The optional Gemini adapter uses server environment variables `GEMINI_API_KEY` and `GEMINI_MODEL`. Each photo starts with on-device recognition selected. Choosing Gemini for that photo sends it and the relevant prompt to Google. The server lists available models before the request. A failed cloud request can be retried on the Mac with the same file. Missing vision leaves the example and manual paths available. This build’s verified vision path is the local model. Playback uses browser speech synthesis. On this Mac, a 12-second push-to-talk answer uses ffmpeg and Whisper base.en, and the button reads **On-device dictation**. Without local Whisper, the button reads **Dictate answer** and uses the browser’s speech service. That route and Gemini can send audio or images off the Mac. Both are optional and labelled before use. Typing always works.

Use on-device Qwen for the team’s youth-outreach workbench. Google restricts the Gemini API to qualifying developer use and excludes applications directed toward or likely to be accessed by people under 18. The adapter remains unconfigured on the presentation Mac. [Gemini API terms](https://aistudio.google.com/docs/terms)

SQLite stores briefs, plans, recognition results and saved projects under `.var/workbench/`. Normalized sketch and donor photos and generated files are stored there too. Set `RENDI_STATE_DIR` before starting to rehearse with a separate notebook. `/api/config` reports `demo_store: true` only when the server is using this folder’s `.var/workbench/`. Keep this local directory and environment keys private.

## Shared data contracts

| Payload | Where to find it |
| --- | --- |
| [ProjectBrief](prompts/schemas/project_brief.json) | Request body for `POST /api/brief` and the `brief` field in a saved project |
| [RobotSpec](prompts/schemas/robot_spec.json) | `spec` in a sketch response or a saved project. The CAD builder also checks dimensions, parent cycles and part references. |
| [Inventory](prompts/schemas/inventory.json) | `inventory` in a drawer response or a saved project. Manual entries have no photo box. |
| [BuildPlan](prompts/schemas/build_plan.json) | `plan` in a matching response or a saved project. Each allocation identifies a required component unit. |

After changing the Python brief or robot model, regenerate its exported contract with `.venv/bin/python -m eval.check_contracts --write-models`. To check all four contracts against the portable notebook and fresh manual plans, run `uv run --no-project --python .venv/bin/python --with jsonschema python -m eval.check_contracts`. The validator is a development dependency.

To check your own robot, save the `spec` object from the sketch response as `robot.json` and run the command below. You can substitute any contract name from the table using its filename without the `.json` extension. For donor boxes and component joins, the running workbench also checks relationships between values. Raw vision detections are an intermediate format that the backend converts before returning a response.

```sh
uv run --no-project --python .venv/bin/python --with jsonschema python -m eval.check_contracts --validate robot_spec robot.json
```

### Editing the example memories

Open [seed_projects.json](data/seed_projects.json). Each top-level key is a stable example ID. Keep the key when renaming an existing example. Each record needs four nonempty text fields. Use `project_name` for the display name, `note` for what Rendi recalls, `outcome` for the result, and `keywords` for space-separated search terms.

Run `.venv/bin/python -m eval.check_seed_projects` before restarting. It checks your file in a temporary notebook. Invalid JSON or missing fields prevent the server from starting. After the check passes, press Control-C in the terminal running the workbench, then double-click **Start Demo.command**. Opening the launcher while the server is still running reuses that server. Search the notebook for one of your keywords to see the updated example. Removing a key retires that example on the next startup. Your saved builds retain their notes.

## Verification

`python -m backend.check_cad` checks the CAD solids with the project environment active. `python -m backend.salvage` checks the component counts. The end-to-end check writes an Eval Rover into the notebook it runs against, so it defaults to a rehearsal server on port 8768 and exits before writing if the server reports `demo_store: true`. Start the rehearsal server in one terminal:

```sh
RENDI_STATE_DIR="$(mktemp -d)" .venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8768
```

Run the check in another:

```sh
.venv/bin/python eval/eval.py --photos
```

`--photos` sends the included drawings and reference photos through local vision. Omit it to check only examples, matching and the notebook.

## Portable Snack Scout backup

[demo/Snack-Scout-backup.zip](demo/Snack-Scout-backup.zip) is a curated copy of the notebook. It holds `rendi.sqlite3`, `models/` and `photos/` for the Snack Scout reference build and the two seeded examples. Restore it into a new empty directory and serve it on its own port. The notebook in `.var/workbench/` is not touched.

```sh
restore="$(mktemp -d)"
unzip demo/Snack-Scout-backup.zip -d "$restore"
RENDI_STATE_DIR="$restore" .venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8769
```

Then open [127.0.0.1:8769/project/p_d58d57f4214745ed951e4e9fef7d49b0](http://127.0.0.1:8769/project/p_d58d57f4214745ed951e4e9fef7d49b0).

See the [project license](LICENSE) and [third-party notices](THIRD_PARTY_NOTICES.md) for software, fonts and image credits.

## Credits

Zlata prepared the product, feature and team specifications. Brian planned voice and the physical companion and investigated printing. Tejass coordinated the software work. Codex and Claude Fable generated and reviewed implementation and rehearsal materials under Tejass’s direction. The hero and starter artwork are illustrations. Credits for the reference photos are beside the inputs. General judging, AI attribution and sponsor requirements are covered in the [event guide](event-guide.md).
