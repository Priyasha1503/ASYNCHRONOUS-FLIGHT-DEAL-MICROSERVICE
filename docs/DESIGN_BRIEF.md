# SkyScout AI — Design Brief

**Status:** visual identity v1, derived from the three references in `design-references/`
(inspected 2026-10-23). Tokens live in `frontend/src/styles/tokens.css`.

## References
| # | File | Inspected? | What it shows | What we adapt | Reproduce vs. adapt |
|---|---|---|---|---|---|
| 1 | `reference1.jpg` | Yes | Wide twilight sea horizon: periwinkle upper sky, pink/coral cloud streaks, lavender horizon line, deep violet sea with a magenta reflection, tiny white boat | Overall palette; the **horizon line** as a layout device; calm negative space; sun/reflection column | Adapt closely (colour + composition) |
| 2 | `reference2.jpg` | Yes | Saturated violet sky with magenta/coral cumulus, sun on a mountain horizon. **Vecteezy watermarks** (licensed stock) | Warmer magenta/coral accents, sun glow | Palette only — image is watermarked stock and **must not be shipped** |
| 3 | `reference3.png` | Yes | Same scene as #2 with a lavender airliner climbing | Aircraft-in-the-sky motif → small stylised plane + contrail in the hero | Motif only; image not shipped (licence unknown) |

**No raster reference image is bundled in the app.** The hero sky is rendered with layered CSS
gradients + an original SVG aircraft (`components/site/sky-backdrop.tsx`), so there are no licensing
issues, no large image payloads and no layout shift.

## Design analysis
- **Mood:** calm, warm, "golden hour" — trustworthy rather than flashy. Suits a product that asks users
  to trust its price labels.
- **Colour:** cool periwinkle/violet dominate; magenta and coral are small, warm highlights. We keep
  that ratio: violet = brand/primary, coral = single accent (CTAs on dark, emphasis), magenta = chart
  & cloud tints only.
- **Composition:** strong horizontal horizon with lots of sky. Used as a hero/CTA device; content pages
  stay light and quiet so dense flight data remains readable.
- **What we deliberately avoid:** generic blue→purple SaaS gradients, glassmorphism everywhere. Glass is
  used only *on top of the sky* (hero cards, glass button) where the reference imagery justifies it.

## Tokens (summary — see `tokens.css` for exact values)
| Role | Light | Dark | Source |
|---|---|---|---|
| Primary | `#6b3fd4` violet | `#a586f5` | sky band between refs 1 & 3 |
| Accent | `#f26b4a` coral (text-safe `#b2462a`) | `#ff8a66` | sun glow, refs 2–3 |
| Night (hero/sea) | `#1c1134` → `#3c2770` | same | sea, ref 1 |
| Page / surface | `#faf8fd` / `#ffffff` | `#110a20` / `#1a1230` | lavender-tinted neutrals |
| Text / muted | `#1a1033` / `#5d5478` | `#f3eeff` / `#b4aacf` | AA on surface |
| Success / warning / danger / info | `#0e7c5a` / `#93560a` / `#c0264a` / `#2f5bd3` | lightened equivalents | chosen for AA, not from refs |
| Charts | violet, coral, periwinkle `#5f7bd8`, magenta | lightened | ref palette order |

- **Type:** Fraunces (display, soft optical serif → evokes the warm dusk mood) + Inter (UI/data,
  tabular numerals for prices & times via the `tabular` utility).
- **Radius:** 6 / 10 / 14 / 20 / 28 px. Cards `xl`, inputs/buttons `md`, pills `full`.
- **Elevation:** violet-tinted shadows `sm/md/lg`; dark mode uses deeper neutral shadows.
- **Motion:** 120 / 200 / 320 ms, `cubic-bezier(.2,.8,.2,1)`. Only the hero aircraft drifts; all
  motion is disabled under `prefers-reduced-motion`.
- **Icons:** Lucide, 16 px in controls, 20 px in feature tiles, 1.5–2 px stroke.

## Component rules
- Buttons: `primary` (violet) on light surfaces; `accent` (coral, dark text) and `glass` only on the sky.
- Every fare carries a `SourceBadge` (icon + text; colour is secondary).
- Forms: label above field, hint below, inline error with icon + `aria-describedby`.
- Skeletons mirror final layout dimensions.
- Images (future destination imagery): 16:9 hero, 4:3 cards, `object-cover`, never stretched.

## Fixed product principles (independent of visual style)
- Results page is the most important screen: cheapest qualifying → best match → alternatives → list.
- Every fare shows its source label (live / cached / observed / demo) with text, never colour alone.
- Unknown data (e.g. baggage) is shown as "Unknown", not hidden.
- Skeletons match final layout; no layout shift when data arrives.
- Reduced motion respected; no artificial delays.

## Visual verification log
| Date | Screens | Viewports | Method | Result |
|---|---|---|---|---|
| 2026-10-29 | Monitor dialog, monitor page (chart + table), monitoring list, alerts, header bell | 1440×900, 390×844 (light) | `scripts/visual-monitoring.mjs` + manual review; chart colours run through the dataviz validator (light + dark) | Fixed duplicate-date axis and pre-existing runs shown; dark mode not yet screenshot-reviewed |
| 2026-10-29 | Hero search, combobox, results, details, filters (sidebar + mobile sheet), no-results, invalid link | 1440×900, 390×844 (light) | `scripts/visual-search.mjs` + manual review | 4 defects fixed (filter snap-back, duplicate ids, overstated relax count, mobile overflow). Dark mode of results not yet reviewed |
| 2026-10-23 | Landing, register, sign-in, account, mobile menu | 1440×900, 390×844; light + dark (landing) | `scripts/visual-smoke.mjs` (Playwright/Chromium in Docker), screenshots reviewed manually | 4 defects fixed (hero contrast, select alignment, mobile plane overlap, sign-out redirect); no overflow. Not yet compared on real devices or Safari/Firefox |
