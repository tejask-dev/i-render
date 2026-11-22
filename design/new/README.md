# New design — brief

**Goal:** a visually appealing, intuitive creative-innovation interface where a first-time maker goes from idea → sketch → 3D model → parts plan without reading instructions.

## Audience
Young makers and fair visitors (youth outreach), plus the team demoing it. Often on a laptop at a booth, sometimes touch.

## Principles
1. **One obvious next step per screen.** One primary action; everything else is secondary or tucked away.
2. **Show, don't tell.** Replace paragraphs of guidance with visuals, previews and inline hints.
3. **Rendi guides.** The companion speaks the current instruction and reacts to progress, not a side decoration.
4. **Make the creation the hero.** The sketch and the 3D model get the most space and polish.
5. **Progressive disclosure.** Provider choices, privacy notes and caveats live behind "details", not in the main path.
6. **Playful but trustworthy.** Workshop warmth, clear states for loading, errors and estimates.

## Open decisions
- [ ] Aesthetic direction (keep paper/workshop vs. new look) — see [tokens.md](tokens.md)
- [ ] Navigation model (stepper vs. canvas/workspace) — see [flow.md](flow.md)
- [ ] Mockup tool (Figma link / HTML prototype) — put in [mockups/](mockups/)

## Done when
- [ ] Every screen in [screens/](screens/) has a spec and is implemented.
- [ ] A new user completes Brief → Plan without help in a hallway test.
- [ ] Existing checks pass: `eval/check_web_shell.py`, `eval/check_companion.mjs`, `eval/check_voice.mjs`, `eval/check_dictation.mjs`.
- [ ] Keyboard and screen-reader paths still work (skip link, live regions, focus on headings).
- [ ] Before/after screenshots added next to [../original/screenshots/](../original/screenshots/).
