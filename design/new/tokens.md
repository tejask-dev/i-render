# Design tokens

Implemented as CSS custom properties at the top of [frontend/style.css](../../frontend/style.css). Original values are in [../original/README.md](../original/README.md#visual-language-from-stylecss). Roles and contrast rationale: [SPEC.md §2](SPEC.md#2-design-system).

## Color
| Token | Name | Value | Role |
| --- | --- | --- | --- |
| `--indigo` | Space Indigo | `#1f2041` | Page ground (dark) |
| `--grape` | Vintage Grape | `#4b3f72` | Raised surfaces, glass tint, fog |
| `--gold` | Golden Pollen | `#ffc857` | Primary action fill (indigo label), highlights |
| `--cyan` | Dark Cyan | `#119da4` | Glow, lines, focus ring, links on dark |
| `--slate` | Blue Slate | `#19647e` | Secondary fills, progress, 3D grid |
| `--mist` | derived | `#eceaf5` | Body text |
| `--mist-dim` | derived | `rgb(236 234 245 / .72)` | Secondary text |
| `--line` | derived | `rgb(236 234 245 / .14)` | Hairlines, glass borders |
| `--glass` | derived | `rgb(75 63 114 / .42)` + blur 16px | Glass panels |
| `--success` / `--warning` / `--danger` | _tbd_ | | Must pass 4.5:1 on indigo |

```json
{"Space Indigo":"1f2041","Vintage Grape":"4b3f72","Golden Pollen":"ffc857","Dark Cyan":"119da4","Blue Slate":"19647e"}
```

## Typography
| Role | Font | Weight / style |
| --- | --- | --- |
| Display / headings | Petrona | 500–600 |
| Subheading / emphasis | Karla | 600 italic |
| Body | Karla | 400 |

At most 4 font files, `font-display: swap`, bundled locally.

## Spacing, radius, elevation
- Spacing scale: 4 · 8 · 12 · 16 · 24 · 32 · 48 · 64
- Radius: 10 (controls) · 16 (cards/panels) · 28 (hero glass) · 999 (pills)
- Elevation on dark: lighter surface + glass, not drop shadows

## Motion
- Hover 150ms in / 120ms out · press 90ms · panel 200ms · travel 240ms · view < 400ms
- Ease `cubic-bezier(.2,.8,.2,1)`; enter `cubic-bezier(.22,1,.36,1)`; loops linear
- Respect `prefers-reduced-motion`.
