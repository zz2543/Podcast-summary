# Design Mockups · 001-podcast-summary

This directory holds visual mockups for the podcast-summary web UI. The mockups are produced **externally** by the user using image-generation tools per FR-017. The implementer (codex) reads only the files under `selected/` when building the frontend; everything else is iteration history.

## Directory layout

```
design/
├── README.md          # this file — conventions only, no images
├── list-page/         # all candidate mockups for EpisodeListPage
├── detail-page/       # all candidate mockups for EpisodeDetailPage
├── components/        # close-ups of shared components (audio bar, quote chip, etc.)
├── states/            # error, empty, partial-failure, loading mockups
└── selected/          # the chosen final mockups; the implementer follows these
```

## Naming convention

Candidate (in `list-page/`, `detail-page/`, `components/`, `states/`):

```
<scope>-<version>-<note>.<ext>
```

Examples:
- `list-page-v1-light.png`
- `list-page-v2-dense.png`
- `detail-page-v3-three-column.png`
- `quote-chip-v1.png`
- `empty-state-v1-headphones.png`

`<version>` is just `v1`, `v2`, … — increment when iterating. `<note>` is a short tag to disambiguate multiple variants in the same version.

Final picks (in `selected/`) use **canonical names without versions**:

| Required (must have before frontend implementation starts) | File name |
|------------------------------------------------------------|-----------|
| Episode list page (default state) | `selected/list-page.png` |
| Episode list page (empty state) | `selected/empty-state.png` |
| Episode detail page (all stages present) | `selected/detail-page.png` |
| Sticky audio bar close-up | `selected/audio-bar.png` |
| Quote chip close-up | `selected/quote-chip.png` |

| Optional (nice to have) | File name |
|--------------------------|-----------|
| Episode detail with a `MissingStagePlaceholder` | `selected/detail-page-partial.png` |
| Confirm delete dialog | `selected/delete-dialog.png` |
| Submit panel close-up | `selected/submit-panel.png` |
| Mobile / narrow-screen detail page | `selected/detail-page-mobile.png` |

## File format

- **PNG preferred** for raster mockups (lossless, easy to diff visually). JPEG accepted.
- Width ≥ 1440 px for full-page shots so codex can read details.
- For component close-ups, ≥ 800 px on the long edge.
- SVG accepted for icon-style assets only.

## Git handling

- All files under `design/` are **committed to the repo** (not gitignored). They are part of the feature's design record.
- A `.gitattributes` rule marks `*.png` / `*.jpg` as binary (no diff noise). Add it at repo root if it doesn't exist already.

## Workflow for adding a new round

1. Generate candidates with your image-generation tool of choice; save them under the appropriate sub-directory with `<scope>-vN-<note>.<ext>` naming.
2. Iterate until satisfied; old `vN` files are kept for history (do not delete unless storage is an issue).
3. When a final pick is chosen, **copy** (not move) it into `selected/` with the canonical name from the table above.
4. If a previously selected mockup is replaced, overwrite the file in `selected/` — git history preserves the prior version.
5. Notify the implementer (or open a tracking note in `detail.md`) that `selected/` is ready or has been updated.

## Hard constraints from `ui-brief.md` §8 (visual designer must honor)

- HookCard is the most visually prominent block on the detail page (bigger than three-act, bigger than chapter content).
- Sticky audio player at the bottom is always visible while the detail page is open.
- Quote chips visibly afford clicking — they are buttons disguised as quotes.
- Status colors must be distinguishable for red/green color-blindness — keep the text label, never encode status by color alone.
- The list view must fit ≥ 5 episode rows on a 1080 p screen without scroll.

## What NOT to design (out of scope per spec)

Login / signup / settings / sharing / comments / mobile-app shells / speaker waveform / audio-editing UI. See `ui-brief.md` §9.
