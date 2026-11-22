# Original UI/UX — audit

Snapshot: branch `ui/original`, tag `ui-original` (commit `7602aeb`). This documents what exists so the redesign has a baseline.

## Architecture
A single-page app. [index.html](../../frontend/index.html) mounts `#app`; [`render()`](../../frontend/src.js:523) rebuilds the whole page from template strings on every state change, keyed by `s.stage`.

## Screens (`s.stage`)

| Stage | Render function | Progress step | Purpose |
| --- | --- | --- | --- |
| `home` | [`home()`](../../frontend/src.js:208) | — | Hero: "Build a robot with Rendi." → Start a build / Project notebook |
| `interview` | [`interview()`](../../frontend/src.js:235) | 1 Brief | Three questions (size, vibe, adventure) with Rendi companion + dictation |
| `confirm` | [`confirmBrief()`](../../frontend/src.js:260) | 1 Brief | "Did I get that right?" — editable brief summary |
| `sketch` | [`sketches()`](../../frontend/src.js:349) | 2 Sketch | Upload / camera capture of a drawing, choose vision provider |
| `model` | [`modelView()`](../../frontend/src.js:369) | 3 Model | 3D viewer + part inspector, STL download |
| `drawer` | [`drawer()`](../../frontend/src.js:429) | 4 Drawer | Photograph drawer or count items by hand |
| `inventory` | [`inventory()`](../../frontend/src.js:464) | 4 Drawer | Review detected boxes and conditions |
| `result` | [`result()`](../../frontend/src.js:476) | 5 Plan | Bill of materials, donors, alternatives, save to memory |
| `notebook` | [`notebook()`](../../frontend/src.js:519) | — | Search saved/seeded projects |

Progress bar: [`progress()`](../../frontend/src.js:203) over `["Brief", "Sketch", "Model", "Drawer", "Plan"]`.

## Visual language (from [style.css](../../frontend/style.css:1))

| Token | Value | Use |
| --- | --- | --- |
| `--paper` | `#faf8ef` | Page background (with 4px dot grid) |
| `--card` | `#fffcf4` | Card surfaces |
| `--ink` | `#28281f` | Body text |
| `--sub` | `#5d6054` | Secondary text |
| `--line` | `#d6d3c3` | Borders |
| `--green` | `#184f42` | Primary actions |
| `--green-soft` | `#dbe9d6` | Selected/soft fills |
| `--orange` | `#bd4e28` | Accent |
| `--display` | Bricolage Grotesque | Headings |
| body | DM Sans | Body copy |

Icons: Lucide (static). 3D: three.js. Mascot: inline SVG droplet "Rendi" with idle / listening / thinking / speaking states.

## Pain points to fix
_Fill in during review — screenshot each in [screenshots/](screenshots/) and reference it here._

- [ ] Looks dated/plain — "ugly" per team feedback; low visual hierarchy.
- [ ] Not intuitive — unclear what to do next on each screen.
- [ ] Dense instructional copy (provider notes, caveats) competes with the main action.
- [ ] Sketch and drawer screens pack upload, camera, provider choice and retry into one card.
- [ ] Result screen: bill, donors, alternatives and percentages are hard to scan.
- [ ] Rendi companion feels detached from the task instead of guiding it.
- [ ] _add more…_
