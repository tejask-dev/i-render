# Current design reference (original UI/UX)

A complete glossary of the **current** I, Render interface: what every page is called, what's on it, and the exact words it uses for navigation. Source: branch `ui/original` / tag `ui-original`. All copy below is quoted verbatim from [frontend/src.js](../../frontend/src.js).

Jump to: [Features](#0-feature-inventory) · [Navigation vocabulary](#1-web-navigation-vocabulary) · [Site map](#2-site-map-page-names) · [Navigation controls](#3-navigation-language-every-control-that-moves-the-user) · [System messages](#4-system-feedback-language) · [Visual system](#5-visual-design-system) · [Observations](#6-observations-for-the-redesign)

---

## 0. Feature inventory

Everything a user can do today, grouped by where it lives. "Optional" means it only appears when that service is set up on the Mac.

### Global (every page)
| Feature | What it does | Where in code |
| --- | --- | --- |
| Logo → Home | Return to the landing page | `data-action="home"` |
| Workshop / Notebook tabs | Switch between the build wizard and saved projects; Workshop resumes your current step | `workshop`, `notebook` |
| Voice on/off | Rendi reads prompts and questions aloud | `voice` · [voice.js](../../frontend/voice.js) |
| Voice output picker | Choose **Browser voice** or **ElevenLabs** (optional, sends Rendi's text to ElevenLabs) | `#voice-provider` · `POST /api/speak` |
| Rendi companion | Animated droplet mascot: blinks when idle, reacts when listening, thinking or speaking; shows a status line | `companion()` |
| Progress stepper | Shows Brief → Sketch → Model → Drawer → Plan (display only) | `progress()` |
| Busy overlay | Spinner + status text during any slow task; blocks other clicks | `job()` |
| Error notice | Alert bar under the stepper | `#notice` |
| Reset build | Clear the current build and start over (footer) | `reset` |
| Skip link | Keyboard jump to main content | `.skip` |
| Deep link | `/project/<id>` or `#project/<id>` reopens a saved build | `GET /api/projects/{id}` |

### Home
| Feature | What it does |
| --- | --- |
| Start a build | Opens the 3-question interview with a blank brief |
| Project notebook | Opens the Notebook |
| Starter robots (Sketchbook) | 3 example cards, **Wheelbot** (rover, drive), **Armbot** (helping hand, grab), **Blobbot** (glowing companion, light up). Clicking one prefills the interview |

### 1 · Brief (interview + confirm)
| Feature | What it does |
| --- | --- |
| Q1 size | Scale pills: **Handheld** (10 cm), **Desktop** (20), **Floor** (45), **Wearable** (12); exact size in cm (3–150); optional working title |
| Q2 vibe | Free text (1–3 words) + suggestion pills: curious, playful, scrappy, retro, gentle, chaotic (max 3) |
| Q3 adventure | Free-text story + "What should it do?" pills: Drive, Walk, Light up, Make sound, Grab, Spin, Sense distance, Display a face, Move air |
| Dictation | Speak an answer instead of typing. **On-device dictation** (Whisper on the Mac, ~12 s) or **Dictate answer** (browser speech service); tap to start/stop, text stays editable | `dictate` · `POST /api/transcribe` |
| Back | Return to the previous question |
| Memory hint | While answering, Rendi searches past projects and shows "Rendi remembers *Project*" (example vs saved) | `GET /api/memory/search` |
| Confirm brief | Summary of all answers, editable project name, **Edit** button per answer (jumps back, then "Update brief") | `POST /api/brief` |

### 2 · Sketch
| Feature | What it does |
| --- | --- |
| Upload a sketch | JPG, PNG, WebP, HEIC/HEIF up to 10 MB, with preview |
| Use camera instead | Live camera preview → **Take photo** / **Cancel**; camera turns off after capture |
| Recognition provider | Choose **On this Mac** (local Qwen via Ollama) or **Gemini** (optional, sends photo to Google); offline options are disabled and labelled |
| Build from photo | Recognize the drawing and generate a 3D model (`POST /api/sketch`) |
| Retry on this Mac | After a Gemini failure, re-run the same file locally |
| Example sketches | Build a real model from a starter design at your chosen size, with no photo needed |
| Offline fallback | If recognition is unavailable, examples still work |

### 3 · Model
| Feature | What it does |
| --- | --- |
| 3D viewer | three.js: drag to orbit, scroll to zoom, auto-spin with **Pause orbit**, **Fit model** button; keyboard arrows rotate, +/− zoom, Home fits |
| Part inspector | Chips for every part (e.g. Body, Head, Left wheel); selecting one highlights it in 3D and shows type, shape, dimensions (L × W × H mm) and function. Hover also highlights |
| Downloads | **Download STL** (for printing) and **Download GLB** (3D file) |
| Model assumptions | Collapsible list of what the generator guessed |
| Original sketch | Collapsible view of the photo used |
| Warnings | "Still to design" for functions without a placed part; "Low confidence" when confidence < 0.3 |
| Open the drawer | Go to step 4 |

### 4 · Drawer (inventory + review)
| Feature | What it does |
| --- | --- |
| Scan your drawer | Upload or camera-capture a photo of junk parts, pick provider, **Identify items** (`POST /api/junk`) |
| Manual inventory | +/− counters for ~30 known item types (RC car, flashlight, computer fan, old phone, hobby servo, loose motor/LED/wheel, etc.) with a running item count; **Use manual inventory**. An empty drawer is allowed |
| Detection review | Drawer photo with numbered boxes over each detected item; list with condition notes |
| Exclude / Restore item | Remove a wrong detection (or duplicate) before matching; excluded boxes dim on the photo |
| Safety hold | Hazardous items (e.g. batteries in phones) are marked **Do not open or salvage** and can't be used |
| Match my parts / Change inventory | Build the plan (`POST /api/plan`) or go back |

### 5 · Build plan
| Feature | What it does |
| --- | --- |
| Drawer score | % of required components with drawer candidates, plus "N of M required components…" |
| 3D model + inspector | Same viewer as step 3 |
| From your drawer | Expandable rows: part needed × qty, donor item, where it goes on the model, how to salvage it, tools, substitutions. Clicking a box on the drawer photo highlights the matching donor and bill row |
| Still to source | Parts you still need, with buying suggestions, plus **Other parts to consider** (alternatives that need modification) |
| Safety notes | Collected warnings, including "leave X intact" for held items |
| Build steps | Numbered assembly instructions |
| Idea and model assumptions | Collapsible recap of the brief + generator assumptions |
| Rendi remembers | Notes pulled from similar past projects |
| Save to Rendi's memory | Saves the project (`POST /api/projects`), gives it a reopenable link; button becomes "Saved to Rendi's memory" |
| Downloads | STL and GLB again |
| Start a new idea | Begin a fresh build |

### Notebook
| Feature | What it does |
| --- | --- |
| Find a memory | Search past builds by project, part or action (e.g. "wheels", "glow") |
| Search results | Matches marked as seeded example vs saved project |
| Saved on this browser | Links to projects saved from this browser (stored in localStorage) |
| Back to build / Start a build | Return to the build in progress, or start one |

### Behind the scenes (no direct UI, but shapes the experience)
- **Local-first:** vision (Qwen/Ollama), dictation (Whisper) and storage (SQLite in `.var/workbench/`) run on the Mac; Gemini and ElevenLabs are opt-in and labelled before use.
- **Saved recognition:** identical photos can reuse a labelled previous result.
- **Contracts:** ProjectBrief → RobotSpec → Inventory → BuildPlan ([prompts/schemas/](../../prompts/schemas/)).
- **Accessibility:** live regions for status, focus moves to each page's heading, aria-pressed on toggles, keyboard 3D controls.

---

## 1. Web navigation vocabulary

Use these standard terms when discussing or speccing the redesign.

| Term | Meaning | In I, Render today |
| --- | --- | --- |
| **Page / screen / view** | One full layout the user sees | 9 screens, switched by `s.stage` (it's a single-page app, so they're *views*, not separate URLs) |
| **SPA (single-page app)** | One HTML page; JS swaps content instead of loading new pages | Yes — [`render()`](../../frontend/src.js:523) rebuilds `#app` |
| **Route / URL / deep link** | Address that opens a specific view | Only one: `#project/<id>` reopens a saved build. Every other view is at `/` |
| **Header / top bar** | Persistent strip at the top | `.topbar`: logo, main nav, voice controls |
| **Logo / brand mark** | Clickable identity, usually goes home | "I, Render." with droplet icon → Home |
| **Primary (global) navigation** | Top-level sections always available | Two tabs: **Workshop** · **Notebook** |
| **Active state** | Highlight showing where you are | `.nav-btn.active` |
| **Stepper / progress indicator / wizard** | Numbered steps through a linear task | Progress bar: **Brief → Sketch → Model → Drawer → Plan** |
| **Wizard / linear flow** | Steps done in order, one at a time | The whole Workshop is a wizard |
| **Breadcrumb** | Trail of where you came from (Home › A › B) | None |
| **Eyebrow / kicker / overline** | Small label above a heading | e.g. "Project brief · 1 of 3", "Sketch input" |
| **Hero** | Large intro section on a landing page | Home: "Build a robot with Rendi." |
| **CTA (call to action)** | The main button you want clicked | Green primary buttons, e.g. "Start a build" |
| **Primary / secondary / tertiary (text) button** | Visual weight of actions | Classes `primary`, `secondary`, `text-btn` |
| **Back / forward** | Move to previous / next step | "Back" (interview only), plus contextual "Change inventory", "Back to build" |
| **Card** | Boxed content group | `.card` |
| **Panel / inspector / sidebar** | Side area showing details of a selection | "Part inspector" next to the 3D viewer |
| **Dock** | Persistent floating element | Rendi "companion dock" on steps 1–5 |
| **Modal / overlay** | Layer on top of the page | Busy overlay (spinner + status text) |
| **Toast / alert / banner** | Short message about an event | `#notice` alert bar under the progress bar |
| **Loading / empty / error state** | What shows while waiting, with no data, or on failure | Busy overlay; empty drawer copy; notice bar |
| **Disclosure / accordion / details** | Hidden content you expand | "Voice output" settings |
| **Footer** | Bottom strip | Logo + "Reset build" or "Rendi's robot workshop" |
| **Skip link** | Keyboard shortcut to main content | "Skip to workspace" → `#work` |
| **Information architecture (IA)** | How pages are organized and named | See §2 |
| **User flow / journey** | Path a user takes through pages | See §3 |

---

## 2. Site map (page names)

```
I, Render
├── Home ......................... stage: home
├── Workshop (the build wizard)
│   ├── 1 Brief
│   │   ├── Interview (3 questions) stage: interview
│   │   └── Confirm brief .......... stage: confirm
│   ├── 2 Sketch ................... stage: sketch
│   ├── 3 Model .................... stage: model
│   ├── 4 Drawer
│   │   ├── Parts inventory ........ stage: drawer
│   │   └── Drawer inventory review  stage: inventory
│   └── 5 Plan ..................... stage: result
├── Notebook ..................... stage: notebook
└── (Opening saved build) ........ stage: loading   ← via #project/<id>
```

| # | Common name | Code stage | Function | Eyebrow (small label) | Heading (H1/H2) | Subheading |
| --- | --- | --- | --- | --- | --- | --- |
| — | **Home** | `home` | [`home()`](../../frontend/src.js:208) | Robot workshop | Build a robot with *Rendi.* | Turn a sketch and the parts in your junk drawer into a 3D robot and a build plan. |
| 1a | **Interview** | `interview` | [`interview()`](../../frontend/src.js:235) | Project brief · N of 3 | How big is your robot? / What's its vibe? / What adventure does it go on? | Palm-sized or floor-roaming? Let's give it room to move. / Give it a little personality. / Tell me what it does when nobody's watching. |
| 1b | **Confirm brief** | `confirm` | [`confirmBrief()`](../../frontend/src.js:260) | Project brief | Did I get that right? | Change any answer before we move to your sketch. |
| 2 | **Sketch** | `sketch` | [`sketches()`](../../frontend/src.js:349) | Sketch input | Show me your sketch. | Upload a drawing or build from one of these example designs. |
| 3 | **Model** | `model` | [`modelView()`](../../frontend/src.js:369) | *(source, e.g. on-device / example)* | *(robot name)* | Select a part to inspect its estimated dimensions. Measure the physical parts before printing. |
| 4a | **Parts inventory** | `drawer` | [`drawer()`](../../frontend/src.js:429) | Parts inventory | What's in your drawer? | Scan a photo or count items by hand. An empty drawer works too. |
| 4b | **Drawer inventory** | `inventory` | [`inventory()`](../../frontend/src.js:464) | *(source)* | Your drawer inventory | Exclude anything you don't recognize before matching parts. *(empty: "Your drawer is empty. We'll list the components to source.")* |
| 5 | **Build plan** | `result` | [`result()`](../../frontend/src.js:476) | Build plan | *(project name)* | Model · *(source)* |
| — | **Notebook** | `notebook` | [`notebook()`](../../frontend/src.js:519) | Project notebook | Rendi's notebook | Search past builds for parts, ideas or lessons to use again. |
| — | **Opening saved build** | `loading` | inline in `render()` | Notebook | Opening saved build… | — |

### Sections inside pages

| Page | Section headings |
| --- | --- |
| Home | Sketchbook — "Start with a sketch" — "Choose a starter robot to make your own." |
| Interview | Fields: Approximate size (cm), Working title (optional), Adventure — "What should it do?", "One to three words" |
| Confirm brief | Project name + summary list of answers |
| Sketch | Upload card "Use your own sketch" · "Example sketches" |
| Model | 3D viewer · **Part inspector** ("N parts") · model assumptions · low-confidence warning |
| Parts inventory | Upload card "Scan your drawer" · "Manual inventory" |
| Drawer inventory | Detected item rows · "Do not open or salvage" warnings |
| Build plan | Parts list · **From your drawer** · **Still to source** · Other parts to consider · Salvage · **Build steps** · Safety notes · **Rendi remembers** |
| Notebook | **Find a memory** (search) · **Saved on this browser** |

---

## 3. Navigation language (every control that moves the user)

### Global (always visible)
| Control | Location | Label | Goes to |
| --- | --- | --- | --- |
| Logo | Header | I, Render. | Home |
| Nav tab | Header | ✏️ Workshop | Current build step (or Home) |
| Nav tab | Header | 📖 Notebook | Notebook |
| Voice toggle | Header | Voice on / Voice off | — (toggles speech) |
| Disclosure | Header | ⚙️ Voice output → "Rendi's voice output": Browser voice / ElevenLabs | — |
| Text button | Footer (during a build) | ↺ Reset build | Clears build → Home |
| Skip link | Top (keyboard) | Skip to workspace | Main content |

### Step-to-step (wizard) buttons
| From | Label | Style | Goes to |
| --- | --- | --- | --- |
| Home | **Start a build** → | primary | Interview |
| Home | 📖 Project notebook | secondary | Notebook |
| Home | *(example sketch card)* | card | Interview, prefilled |
| Interview | **Continue** → / **Review brief** → (Q3) / **Update brief** (editing) | primary | Next question / Confirm |
| Interview | Back | text | Previous question |
| Confirm brief | **Confirm brief** → | primary | Sketch |
| Confirm brief | Edit (per answer) | quiet | Interview question |
| Sketch | Choose sketch photo | file input | — |
| Sketch | Use camera instead → Take photo ✓ / Cancel | quiet / primary / secondary | — |
| Sketch | 👁 **Build from photo** (or "Send sketch to Gemini") | primary | Model |
| Sketch | Retry on this Mac | secondary | re-runs locally |
| Model | **Open the drawer** → | primary | Parts inventory |
| Model | Download STL | link | file |
| Parts inventory | 👁 **Identify items** (or "Send drawer photo to Gemini") | primary | Drawer inventory |
| Parts inventory | **Use manual inventory** | primary/secondary | Drawer inventory |
| Drawer inventory | **Match my parts** → | primary | Build plan |
| Drawer inventory | Change inventory | secondary | Parts inventory |
| Build plan | **Save to Rendi's memory** | primary | saved → `#project/<id>` |
| Build plan | Start a new idea | secondary | Home / Interview |
| Notebook | Back to build | secondary | Current step |
| Notebook | Start a build | primary | Interview |

### Progress stepper
`1 Brief · 2 Sketch · 3 Model · 4 Drawer · 5 Plan` — completed steps show ✓, current step is highlighted (`aria-current="step"`). **Display only — not clickable.**

---

## 4. System feedback language

**Loading (busy overlay):** Saving your brief… · Saving photo… · Opening camera… · Opening microphone… · Transcribing on this Mac… / Transcribing with your browser… · Reading the sketch and building your model… · Building your dimensioned example… · Identifying items in the photo… · Matching parts and writing your plan… · Saving to Rendi's memory… · Looking through Rendi's notebook… · Opening your saved build…

**Rendi companion status:** Ready when you are · Listening · tap the mic to stop · Speaking… · (thinking while transcribing)
**Rendi lines:** "Hey, I'm Rendi. Let's make a robot!" · "Love it. Show me your sketch!" · reads each interview question aloud.

**Dictation button:** On-device dictation (local Whisper) / Dictate answer (browser) · "Listening… tap to stop"

**Empty states:** No matching memories yet. · Save a completed plan to reopen it here. · No matching parts found. · No component requirements have been mapped. · No model assumptions recorded.

**Warnings / cautions:** Low confidence. Check the shapes and dimensions against your sketch before printing. · Check their fit and electrical ratings before use. · These need changes and a compatibility check. They do not reduce the parts still needed. · Do not open or salvage.

**Success:** Your drawer has candidates for every required component.

---

## 5. Visual design system

| Token | Value | Role |
| --- | --- | --- |
| `--paper` | `#faf8ef` | Background (+ 4px dot-grid texture) |
| `--card` | `#fffcf4` | Card surface |
| `--ink` | `#28281f` | Text |
| `--sub` | `#5d6054` | Secondary text |
| `--line` | `#d6d3c3` | Borders |
| `--green` | `#184f42` | Primary buttons, active nav |
| `--green-soft` | `#dbe9d6` | Selected / soft fill |
| `--orange` | `#bd4e28` | Accent (e.g. *Rendi.* in hero) |

- **Type:** Bricolage Grotesque (display/headings), DM Sans (body), line-height 1.45.
- **Icons:** Lucide — arrow-right, check, book-open, pencil-ruler, upload, focus, eye, box, move-3d, settings-2, rotate-ccw.
- **Imagery:** `rendi-workshop.webp` (hero), `sketches.webp` (example sketches).
- **3D:** three.js viewer — drag to orbit, scroll to zoom, Pause orbit, Fit model.
- **Mascot:** Rendi, an SVG droplet with idle (blink) / listening / thinking / speaking (mouth) states.
- **Tone of voice:** Friendly first person from Rendi ("Show me your sketch.", "Did I get that right?"), cautious and precise about estimates and safety.

---

## 6. Observations for the redesign

- Two naming systems overlap: nav says **Workshop / Notebook**, stepper says **Brief / Sketch / Model / Drawer / Plan**, headings say "Project brief", "Sketch input", "Parts inventory", "Build plan", and the code says `interview`, `result`… Pick one name per page.
- "Notebook", "Project notebook", "Rendi's notebook" and "Rendi's memory" all refer to the same thing.
- "Drawer", "Parts inventory" and "Drawer inventory" are two screens under one step with similar names.
- The stepper isn't clickable and there's no Back button after the interview, so moving backward isn't obvious.
- Only saved projects have a URL; refreshing mid-build or sharing a step isn't possible.
