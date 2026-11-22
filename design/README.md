# I, Render — Design specs

Home for the UI/UX redesign of the Rendi workshop. The software works; this folder is about making it **visually appealing and intuitive** for a first-time maker.

## Where things live

| | Branch / tag | What it is |
| --- | --- | --- |
| Original UI/UX | [`ui/original`](../../../tree/ui/original) branch · `ui-original` tag | Frozen snapshot of the working app before the redesign (commit `7602aeb`). Never commit to it. |
| New design | `design/new-ui` branch (this one) | All redesign work: specs here, implementation in [`frontend/`](../frontend/). |
| Shipping app | `main` | Stays demo-safe. Merge `design/new-ui` in only once the new flow passes the checks in [new/README.md](new/README.md#done-when). |

To compare: `git diff ui-original design/new-ui -- frontend/` · to run the original: `git switch ui/original && npm --prefix frontend run build`.

## Spec index

### Original (as built)
- [original/README.md](original/README.md) — audit of the current UI: screens, flow, tokens, components and the pain points we're fixing.
- [original/screenshots/](original/screenshots/) — captures of each screen from `ui/original`.

### New design
- [new/README.md](new/README.md) — design brief: goals, principles, success criteria.
- [new/tokens.md](new/tokens.md) — color, type, spacing, radius, motion.
- [new/flow.md](new/flow.md) — the intended user journey and navigation model.
- [new/screens/](new/screens/) — one spec per screen (layout, states, copy, interactions).
- [new/components.md](new/components.md) — shared components (buttons, cards, companion, uploader, 3D viewer, progress).
- [new/mockups/](new/mockups/) — wireframes, Figma exports, prototype links.

## Source files the specs map to

| Concern | File |
| --- | --- |
| Page shell | [frontend/index.html](../frontend/index.html) |
| Screens, state & flow | [frontend/src.js](../frontend/src.js) |
| All styling & tokens | [frontend/style.css](../frontend/style.css) |
| Icons / UI helpers | [frontend/ui.js](../frontend/ui.js) |
| 3D model viewer | [frontend/viewer.js](../frontend/viewer.js) |
| Voice & dictation | [frontend/voice.js](../frontend/voice.js), [frontend/dictation.js](../frontend/dictation.js) |
| Images | [frontend/public/](../frontend/public/) |

## Working agreement
1. Spec first: update the screen spec in `new/screens/` before changing its code.
2. Keep behavior intact — the redesign changes presentation and flow, not the backend contracts in [prompts/schemas/](../prompts/schemas/).
3. Run the existing UI checks (`eval/check_web_shell.py`, `eval/check_companion.mjs`, `eval/check_voice.mjs`) after each screen lands.
