# Resources

A living list of useful links (art, icon sets, references, docs, and tools) used while building STL Manager. Prefer adding notes on license and how you intend to use the resource.

## Icon libraries

- Warhammer 40K Icon set (SVG / iconfont)
  - Repo: https://github.com/Certseeds/wh40k-icon
  - Live preview:
    - SVG gallery: https://certseeds.github.io/wh40k-icon/
    - Icon font preview: https://certseeds.github.io/wh40k-icon/fonts.html
  - License notes (per repo):
    - Multi-license; repository declares AGPL-3.0-or-later (for code), CC-BY-NC-SA-4.0-or-later (for docs and non-font assets), and OFL-1.1-RFN (for font files). Symbols and names belong to Games Workshop.
    - Practical implication: non-commercial, share-alike for many assets; ensure attribution and license compatibility for your intended use.
  - Suggested usage here: use individual SVGs for small UI badges or a local icon font; keep an attribution note in `docs/RESOURCES.md` and/or app credits.

- D&D 5e Icon Set (SVG)
  - Repo: https://github.com/intrinsical/tw-dnd/tree/main/icons
  - Preview: Browse `icons/` folders (attributes, combat, damage types, spells, monsters, etc.)
  - License notes:
    - Icons are licensed under CC BY-SA 4.0 (per `icons/README.md`). The root repository is GPL‑3.0 for code; treat icons with CC BY‑SA 4.0 terms (attribution + share‑alike).
  - Suggested usage here: use selected SVGs for generic UI glyphs (e.g., damage types, conditions). Provide attribution in `docs/RESOURCES.md` and in‑app credits; if you modify icons, share under the same license.

---

## How to add new entries

- Add a bullet under the right section with:
  - Name, link(s), and a short description of what it provides.
  - License summary and any usage constraints.
  - A sentence on how/where we plan to use it.

## Related

- Project progress and notes: `docs/PROGRESS.md` (has a “Useful Links” section for development context).
