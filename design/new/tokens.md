# Design tokens — Liquid Cobalt

Implemented as CSS custom properties at the top of [frontend/style.css](../../frontend/style.css). Source: the brand board `I,Render — Brand & UI.html`. Roles and contrast: [SPEC.md §2](SPEC.md#2-design-system). Original values: [../original/README.md](../original/README.md#visual-language-from-stylecss).

## Color
| Token | Value | Role |
| --- | --- | --- |
| `--midnight` | `#03195b` | Dark surfaces |
| `--cobalt` | `#0b2cb1` | Hover/pressed primary, active text |
| `--signal` | `#1951fc` | Primary action, links, kickers, focus |
| `--sky` | `#3781fc` | Gradients, decoration |
| `--frost` | `#eaf0ff` | Selected, soft panels |
| `--ink` | `#0a0f1f` | Headlines, text |
| `--bg` | `#f2f4fa` | App ground |
| `--card` | `#ffffff` | Cards |
| `--body` | `#2a3352` | Body text |
| `--sub` | `#4a5578` | Secondary text |
| `--line` / `--line-strong` | `#dde4f5` / `#b9c6ea` | Borders |
| `--pale` / `--pale-2` | `#bfd6ff` / `#d9e4ff` | Text on dark |
| `--glass` / `--glass-line` | white 12% / white 30% | Glass on dark |
| `--danger` / `--danger-bg` | `#b42318` / `#fef0ee` | Safety |
| `--warn` / `--warn-bg` | `#8a5a00` / `#fff4dc` | Notices |

Mascot drop gradient: `#FFFFFF → #DCE8FF → #7FA9FF` (radial). App-icon square: `#3781FC → #0B2CB1` (linear). Both are defined once in [frontend/index.html](../../frontend/index.html) as `#ir-drop`, `#ir-square`, `#ir-soft`, `#ir-drop-shape`.

## Typography
| Token | Font | Weights |
| --- | --- | --- |
| `--display` | Space Grotesk Variable | 700 (headlines), 600 (eyebrows) |
| `--serif` | Instrument Serif | 400 italic |
| `--text` | Inter Variable | 400–600 |

## Shape
`--r-sm` 14 · `--r` 22 · `--r-lg` 28 · `--r-xl` 32 · pills 999.

## Texture
`--grain`: SVG fractal noise, `mix-blend-mode: overlay`, 30% on dark panels.

## Motion
`--ease` `cubic-bezier(.2,.8,.2,1)`. Hover 150ms · press 90ms · cover-flow travel 420ms · zoom-out to new project 380ms. Everything rests under `prefers-reduced-motion`.
