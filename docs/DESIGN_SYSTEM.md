# Baaki design system

The foundation for the worker app (`/app`, `/speak`, `/case/*`, `/diary`, `/voice`, `/safety`), the employer page (`/e/[token]`) and the website (`/`). Read this before you restyle a screen.

**Look in one line:** Gnani.ai's glow (orange #FE914B to violet #9F73F4 gradient, soft sky and lavender haze, off-white #FCF7F2, a serif display face), with mobile patterns from Uber and Agoda (clean cards, a bottom nav, one big primary action, bottom sheets, a map-like hero and status pills).

## 1. Files

| What | Where |
|---|---|
| **All colour tokens** (2 palettes × light/dark), plus spacing, radius, motion and font tokens | `web/app/theme.css` |
| Component and screen classes for the app | `web/app/globals.css` |
| Website-only styles (`.s-*`, the phone mockup `.phone`, `.mini-*`) | `web/app/site.css` |
| Primitives (Screen, MicButton, MeterValue, ChipView, PlayButton, Toggle, Sources, ErrorNote, Loading), with the kit re-exported | `web/components/ui/primitives.tsx` |
| Kit (AppBar, BottomNav, BottomSheet, Card, StatusPill, GradientButton, GlowRing, Waveform, Skeleton, SkeletonCard, Confetti, CountUp, HomesMap) | `web/components/ui/kit.tsx` |
| Illustrations | `web/components/ui/Illustration.tsx` |
| Theme toggle, install button, logo | `web/components/ui/ThemeToggle.tsx`, `InstallButton.tsx`, `Logo.tsx` |
| Icons (stroke = currentColor) | `web/components/ui/icons.tsx` |
| Theme runtime (circular reveal, hooks) and the pre-paint script | `web/lib/theme.ts`, `web/lib/theme-config.ts` |
| Website sections and the phone demo | `web/components/site/Site.tsx`, `PhoneDemo.tsx` |
| PWA: manifest, service worker, offline page, icons | `web/app/manifest.ts`, `web/public/sw.js`, `web/app/offline/page.tsx`, `web/public/icons/` (from `web/scripts/make-icons.mjs`) |

Import everything a screen needs from one place:

```tsx
import { Screen, Card, StatusPill, GradientButton, Illustration, BottomSheet, Skeleton } from "@/components/ui/primitives";
```

## 2. Theme and palette

Two attributes on `<html>` control the look. The inline script in `app/layout.tsx` sets both before first paint, so there is no flash of the wrong theme.

- `data-theme="light" | "dark"`: the saved choice (`localStorage["baaki-theme"]`). On a first visit it follows `prefers-color-scheme`.
- `data-palette="gnani" | "warm"`: **`gnani` is the default** (`DEFAULT_PALETTE` in `lib/theme-config.ts`). `warm` (amber to orange to rose, with no blue or violet) is a backup option.

URL overrides, useful for screenshots and demos:
- `?theme=dark` forces the theme for that page load and is not saved.
- `?palette=warm` sets the palette for that tab (sessionStorage).

To switch everyone to the other palette, change `DEFAULT_PALETTE`. Then update the `COLORS` value in `app/manifest.ts` and run `PALETTE=warm node scripts/make-icons.mjs`.

**Theme toggle:** `<ThemeToggle />` calls `switchTheme(next, x, y)`. The new theme grows as a circle from the button through `document.startViewTransition` and a `clip-path` animation on `::view-transition-new(root)` (650 ms). Without View Transitions, or with reduced motion, the theme switches instantly. Every `<Screen>` app bar includes the toggle (opt out with `themeToggle={false}`), and so does the website header. In code, `useTheme()` and `usePalette()` re-render on change.

## 3. Tokens (use these, never hex)

**Surfaces:** `--bg` (page), `--bg-2` (footer, deeper), `--surface` (cards), `--surface-2` / `--raised` (inset areas, chips), `--glass` (translucent bars; pair with `backdrop-filter`), `--line`, `--line-2`.

**Text:** `--text`, `--text-2` (body copy on haze), `--muted` (labels and hints, at least 4.5:1), `--faint` (decoration only, never body text).

**Brand:**
- `--accent` (solid orange, for fills and borders) and `--accent-text` (for accent-coloured text, at least 4.5:1).
- `--accent-2` (violet), `--accent-3`, `--accent-ink` (dark ink), `--accent-soft` (tint background), `--accent-line` (tint border).
- `--grad` (90° main gradient), `--grad-diag` (135°, for round and square fills), `--grad-text` (a darker or brighter version for gradient text, applied with `.grad-text`), `--grad-soft` (pale tint panels), and `--on-grad` (the ink colour for text on any gradient).

**Glow:** `--haze-1/2/3` (blurred background blobs), `--hero-bg` (the layered Gnani hero gradient), `--glow` (orange shadow), `--glow-2` (violet shadow).

**Status:** `--success`, `--success-soft`, `--success-ink` (text on a success fill), `--warn`, `--warn-soft`, `--error`, `--error-soft`, `--recording` (live mic), `--estimate` (anything labelled "estimate"), `--overlay` (modal scrim).

**Elevation:** `--shadow-1` (resting cards), `--shadow-2` (hover, floating pins, bottom nav), `--shadow-3` (sheets and dialogs), `--ring` (focus halo for inputs).

**Illustration:** `--ill-*` (skin, hair, cloth, paper, coin, leaf, roof, window, phone, screen, blob, shadow). **Phone and maps:** `--phone-body`, `--phone-edge`, `--map-bg`, `--map-road`, `--map-dot`. **Confetti:** `--confetti-1..4`.

**Spacing:** a 4-pt scale, `--s-1` 4 · `--s-2` 8 · `--s-3` 12 · `--s-4` 16 · `--s-5` 20 · `--s-6` 24 · `--s-7` 32 · `--s-8` 40 · `--s-9` 56 · `--s-10` 72. `--space` (16 px) is the side gutter.

**Radius:**

| Token | Size | Use |
|---|---|---|
| `--r-xs` | 8 | tiny elements |
| `--r-sm` | 12 | small buttons |
| `--r-md` | 16 | buttons and inputs |
| `--r-lg` | 20 | cards and big buttons |
| `--r-xl` | 28 | hero cards, sheets, maps |
| `--r-pill` | 999 | pills |

**Sizes:** `--tap` 56 (primary action height), `--tap-min` 44 (every tap target), `--appbar-h` 56, `--nav-h` 68, `--shell` 480 (app column), `--page` 1180 (website).

**Motion:** durations `--dur-1` 120 ms (press, hover), `--dur-2` 200 ms (state changes), `--dur-3` 320 ms (cards entering, sheets), `--dur-4` 560 ms (hero entrances, pops). Easings:
- `--ease-out`, the default for things entering.
- `--ease-std` for colour and opacity.
- `--ease-spring` for pops and toggles, with a small overshoot.

**Fonts:**
- `--font-display` is Instrument Serif, standing in for Gnani's Gambarino. Use it for big headlines, the celebration title and the home greeting, always at weight 400.
- `--font-sans` is Inter, with Noto Sans Telugu and Noto Sans Devanagari as fallbacks for Indic text.
- Money is always `font-variant-numeric: tabular-nums` and weight 700–800.

## 4. Components

| Component | Use | Example |
|---|---|---|
| `Screen` | Every app page. A glass AppBar (back link, title, theme toggle, Help shield), the warm haze backdrop, a 16 px gutter, staggered rise-in of its children. `nav="home|diary|speak|voice"` adds the BottomNav. `right` takes extra bar buttons. | `<Screen title={t("diary.title")} back="/app" t={t} nav="diary">` |
| `AppBar` | The bar on its own, for custom layouts. | `<AppBar title="Pay" back="/app" right={<ThemeToggle/>} />` |
| `BottomNav` | Uber-style floating bar: Home · Diary · **Speak** (raised gradient mic) · Voice · Help. Use it on hub screens only, not inside a flow (Speak, Confirm, Case). | `<BottomNav t={t} active="home" />` |
| `BottomSheet` | Choices, edits, confirmations. Slides up and closes on Esc, scrim tap or the ✕. One primary action per sheet. | `<BottomSheet open={o} onClose={()=>setO(false)} title="Fix amount">…</BottomSheet>` |
| `Card` | Groups one idea. `tone`: `default`, `glow` (gradient border plus halo, **at most one per screen**), `gradient` (solid brand fill, for celebration only), `soft`, `success`, `warn`. Pass `href` to make it a link card. | `<Card tone="glow"><h2>…</h2></Card>` |
| `StatusPill` | State labels. `tone`: neutral, accent, success, warn, error, estimate, live (pulsing dot). Use `toneForState(case.state)` for case states. The old `.tag[data-state]` looks the same. | `<StatusPill tone="live">Listening</StatusPill>` |
| `GradientButton` | **The one primary action on a screen.** Renders a link when given `href`. `size="lg"` is full width and 56 px tall. | `<GradientButton href="/speak" icon={<MicIcon/>}>Tell Baaki</GradientButton>` |
| `.btn` / `.btn-primary` / `.btn-big` / `.btn-small` / `.btn-yes` / `.btn-no` / `.btn-ghost` | Class-based buttons that already exist in screens. `.btn-primary` uses the gradient. | |
| `MicButton` | Press-to-talk. The halo pulses at idle and speeds up while recording. A live `Waveform` follows `level`. API unchanged. | |
| `GlowRing` | Pulsing halos around any round element (the home mic link). `level` 0–1 swells it. | `<GlowRing><span className="mic"/></GlowRing>` |
| `Waveform` | Gradient voice bars. `active` animates them. `level` (0–1) sets the height, so pass the mic level. | `<Waveform active={rec} level={level} bars={20} />` |
| `MeterValue` | The Baaki Meter: gradient digits with a drop-shadow glow, plus a glow pulse on every `tick` step. The count-up comes from `useLiveMeter`. API unchanged. | |
| `CountUp` | Counts to a value when it scrolls into view. The server render shows the final value. | `<CountUp value={13000} />` |
| `PlayButton` | Round gradient play icon, a progress fill and a mini waveform while playing. API unchanged. | |
| `Skeleton`, `SkeletonCard` | Shimmering loading shapes. Match the shape of the content, and keep a `role="status"` label nearby. | `<Skeleton width="60%" height={24} />` |
| `Loading` | Three breathing gradient dots and a label (for short waits). | |
| `ErrorNote` | Tinted error box with an icon and an optional retry. API unchanged. | |
| `Confetti` | Falling pieces over the parent. Use it only for "Paisa aa gaya!" and other real wins. Hidden with reduced motion. | `<Confetti />` |
| `HomesMap` | Map-like hero: a dotted city with one pin per home showing the amount owed. The first pin is gradient. Up to 6 pins. | `<HomesMap homes={[{id, name, amount, tone, href}]} you="Lakshmi" />` |
| `Illustration` | See section 5. | `<Illustration name="speak" animated />` |
| `ThemeToggle` | Circular-reveal light/dark switch (44 px). | |
| `InstallButton` | PWA install. Uses the captured `beforeinstallprompt` event; on iPhone it shows a "Share, then Add to Home Screen" hint. Hidden once installed. `variant`: pill, block, ghost. | `<InstallButton label="Install Baaki" variant="block" />` |
| `Logo`, `LogoMark` | Voice-bubble mark plus the "Baaki బాకీ" wordmark. Follows the palette. | `<Logo size={32} />` |

## 5. Illustrations

The set in `Illustration.tsx` is original inline SVG in one style: flat rounded shapes on a soft blob, one ground shadow, warm skin tones, cloth in brand colours and gradient sparkles. Every fill comes from `--ill-*` and `--accent*`, so each picture works in both palettes and both themes.

| `name` | Shows | Use for |
|---|---|---|
| `speak` | A woman speaking into her phone, with voice bars | language picker, Speak intro, onboarding |
| `home` | A house card with a rupee pin | an employer or home, adding a home |
| `coins` | A note with coin stacks | totals, the Haq Check, money owed |
| `handshake` | Two hands and a heart | agreement (Kaam Patta), the fair employer, paid in parts |
| `shield` | A shield with a check | the safety screen, privacy notes |
| `celebrate` | A phone with a tick, confetti and a coin | "Paisa aa gaya!", success |
| `empty` | A dotted home outline with a mic | empty states |
| `wave` | A voice-note bubble | voice profile, read-back |
| `send` | A sent voice note with a double tick | the ladder step after sending, the employer note |

Rules:
- Use one illustration per screen at most, at 160–240 px wide.
- Add `animated` only for the hero or empty state (gentle float and moving bars). The animation respects reduced motion.
- Pass `title` when the picture carries meaning. Otherwise it is decorative and hidden from screen readers.

## 6. Rules for the screen-restyle agents

**Layout**
- Design phone-first, at 360–430 px wide. Use a 16 px side gutter (`--space`), with no horizontal scroll. The app column stops at 480 px.
- Keep a vertical rhythm of 16 px between blocks (the `Screen` gap) and 12 px inside a block (`.stack`).
- Give each screen one hero: a big number, the mic, a map or an illustration. Something should move in the first 10 seconds (a halo, a count-up, pins popping in, a waveform).
- Give each screen **one** `GradientButton` or `.btn-primary`. Make everything else `.btn` (surface) or a ghost button. Put the yes/no pair in the sticky `.yes-no` bar at the bottom.
- Make every tap target at least 44 px, and primary actions 56 px.

**Colour**
- Use tokens only. Never hard-code hex in TSX or CSS. The one exception is the QR code's white background.
- Use the gradient for the primary action, the meter and total digits (`--grad-text`), the active state and at most one glow card. Too much gradient flattens the hierarchy.
- Put text on gradients in `--on-grad`. Put accent-coloured text in `--accent-text`, never `--accent`.
- Mark estimates with `StatusPill tone="estimate"` or `EstimateTag`.

**Elevation:** resting cards use `--shadow-1`. Floating items (pins, nav, hover) use `--shadow-2`. Sheets and dialogs use `--shadow-3`. Don't stack shadows inside shadows.

**Motion**
- Things entering use `--dur-3` with `--ease-out`.
- Presses use a scale of 0.97 over `--dur-1`.
- Pops use `--ease-spring`.
- Ambient loops (halos, haze drift, waveform) stay slow and subtle.
- The global `prefers-reduced-motion` block switches animations off. Keep it working: don't put information only in an animation.

**Type**
- Use the serif (`.display` / `--font-display`, weight 400) for headlines of 1.9 rem and up, and for the celebration title. Don't use it for numbers or UI labels.
- Use Inter weights 600–800 for numbers and buttons.
- Indic text uses Noto automatically, so set `lang="te"` or `lang="hi"` on mixed strings.

**Accessibility:** keep contrast at 4.5:1 or more for text in both themes and both palettes (`--muted` passes; `--faint` does not). Keep visible focus with the `:focus-visible` accent outline. Live values get `aria-live`. Give icon-only buttons an `aria-label`.

**Do**
- Use status pills for state.
- Show skeletons while loading lists.
- Use a bottom sheet for any edit.
- Use big rupee figures.
- Read back before Send.

**Don't**
- Use more than one glow card per screen.
- Use gradient body text.
- Put information in an animation alone.
- Add new hex colours (add a token to all four blocks in `theme.css` instead).
- Put the BottomNav inside a flow.
- Theme the quick-exit page `/r`, which is plain on purpose and uses `--recipe-*`.

## 7. Routes and the PWA

- `/` is the website and `/app` is the worker home. Back links in the app point to `/app`. The other routes are unchanged.
- The manifest is served at `/manifest.webmanifest`, from `app/manifest.ts`. It sets `start_url` `/app` and `display` standalone, with 192/512 icons plus maskable versions.
- The service worker (`public/sw.js`) is registered in production builds only.
  - The app shell and static files are precached and served cache-first.
  - Pages are network-first, with `/offline` as the fallback.
  - `/api/*` is network-first. Voice notes under `/api/media/*` are cached for at most 1 day and 30 files, and audio Range requests bypass the cache.
  - The quick exit clears the API, media and page caches.
  - Bump `VERSION` in `sw.js` to reset every cache.
- Icons are regenerated with `node scripts/make-icons.mjs`, which renders through sharp; the Telugu text is shaped with Nirmala UI or Noto Sans Telugu.
- `BACKEND_URL` is read when `next.config.ts` runs, and the `/api` rewrite is fixed at **build** time. Set it before `npm run build`, not only before `npm start`.
