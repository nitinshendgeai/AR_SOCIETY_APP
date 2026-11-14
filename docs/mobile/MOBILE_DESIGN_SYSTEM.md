# DuxOS Mobile Design System

Status: Phase 2. Tokens and four widgets are added (additive, nothing existing changed); the rest documents what already exists.
Source of truth in code: `mobile/lib/core/theme/app_theme.dart`, `core/theme/design_tokens.dart`, `shared/widgets/*`, `core/motion/*`.
Direction: premium enterprise SaaS for an Indian residential society. Calm, high-contrast, generous whitespace, numbers first.
Light theme now; dark stays possible (see section 10).

## 1. Principles
1. One screen, one job; the primary action is reachable with a thumb.
2. Numbers (dues, collections) are the hero; labels are quiet.
3. Colour never carries meaning alone: a status always has a word, usually an icon.
4. Every list has four states designed: loading, empty, error, success.
5. Reuse before adding. New widgets only for a gap listed here.

## 2. Colour (existing tokens; audited contrast on white / on `surface` #F2F2F7)

| Token | Hex | On white | On surface | Use |
|---|---|---|---|---|
| `primary` | #0066FF | 4.83 | 4.33 | Buttons, links, active nav. **Small text on `surface` is below AA**: put primary text on white cards. |
| `textPrimary` | #1C1C1E | high | high | Body |
| `textSecondary` | #6C6C70 | 5.23 | 4.69 | Secondary text (AA) |
| `textTertiary` | #6E6E73 (was #AEAEB2, 2.21:1) | 5.07 | 4.54 | **Fixed**: now passes AA. A lighter grey cannot be a separate tier and still pass; it sits almost level with `textSecondary`. A test locks every text colour at 4.5:1 on cards, page and fields. |
| `success` / `warning` / `error` | #34C759 / #FF9500 / #FF3B30 | 2.22 / 2.20 / 3.55 | - | **Icons, fills and bars only, never small text.** |

Status text uses the new **tone pairs** (`AppTone`, `kToneColors`), each at least 5.7:1 on its own soft background:
neutral, info, success, warning, danger. Finance screens use neutral surfaces and reserve danger for overdue.

## 3. Typography (existing, Inter + bundled NotoSansDevanagari)
Large title 34, title 28/24/22/20/18, titleLarge 17, titleMedium 16, titleSmall 14, body 17/15, small 13. Hindi and Marathi fall back to
Noto Sans Devanagari, which has taller glyphs: keep line height >= 1.4 and never fix a text container's height.
Money uses tabular figures (to add with the money widget in Phase 3, `FontFeature.tabularFigures()`).
Text must survive 130% system font scale without clipping (test target).

## 4. Spacing, shape, elevation
- Spacing (`AppSpacing`): 4, 8, 12, 16, 24, 32; page gutter 16; minimum touch target 48.
- Radius (`AppTheme`): 10 / 14 / 18 / 24. Cards 14, sheets 24 top, chips full pill.
- Elevation: `AppTheme.cardShadow` (soft two-layer) on cards over `surface`; no hard borders except `border` hairlines for dividers.

## 5. Components

| Component | Status | Where | Notes |
|---|---|---|---|
| Primary button | exists | `AppPrimaryButton`, themed `FilledButton` | 48 dp height; one per screen |
| Text field | exists | `AppTextField`, `app_form.dart` (`AppFormPage`, `FormSection`, `FormFieldBox`) | labels above fields, helper text, inline validation; set `keyboardType` (phone, number, email) |
| Filter pill | exists | `AppFilterPill` | for list filters and More groups |
| KPI card / grid | exists | `KpiCard`, `KpiGrid` | one announcement for screen readers |
| Toast | exists | `AppToast.success/error/warning/info` | transient confirmation |
| Sheet | exists | `showAppSheet` | bottom sheet on phone, side panel on desktop |
| Bottom navigation | exists, to redesign | `PhoneBottomBar` | see implementation plan, Phase 3 |
| Loading | exists | `AppLoader`, `Shimmer`, `SkeletonBox/List` | prefer skeleton over spinner for lists |
| Empty | exists | `AppEmptyState` | icon, title, hint, optional action |
| Error | exists | `AppErrorState` (+ `compact`), `AppErrorBanner` | always with retry |
| **Status chip** | **new** | `AppStatusChip` | label + tone + optional icon |
| **Section header** | **new** | `AppSectionHeader` | semantic header + 48 dp action |
| **Success state** | **new** | `AppSuccessState` | after a completed task, with next step |
| **Connection banner** | **new** | `AppConnectionBanner` | presentation only; detection comes later |
| **Connection banner (wired)** | **new** | `ConnectionBanner` in the shell | shows while no request reaches the server; Retry probes `/health` |
| **Menu hub** | **new** | `MenuHubScreen` | Operations / Finance / People tabs for admin, committee, manager |
| Money text | planned | Phase 3 | single INR formatter; today 6 private `NumberFormat` copies exist |
| Mobile list card | planned | Phase 3 | replaces table rows at phone width |
| App bar | themed | `AppTheme` | back arrow on detail pages, bar hidden there only on tab pages |
| Dialog | themed | `AlertDialog` | required for destructive and financial confirmations |

## 6. Screen patterns
- **Hub tab**: header with greeting/summary, 2 x N grid of destination cards (icon, label, count badge), searchable.
- **List screen**: search field, filter pills, cards with status chip and one key figure, pull to refresh, skeleton while loading.
- **Detail screen**: summary card on top, grouped sections, sticky primary action.
- **Form**: one column, grouped sections, keyboard-aware, confirm dialog before irreversible money actions.
- **Tables at phone width**: never shrink; show as card list with expandable details (full table retained at >= 1024 dp).

## 7. Motion
Existing `core/motion`. Durations 150 to 250 ms, ease-out, no motion that blocks input, honour reduced motion (`MediaQuery.disableAnimations`).

## 8. Localisation and formats
English, Marathi, Hindi through `context.tr`. Rupees as `₹1,23,456.00` (en_IN grouping); dates `dd MMM yyyy`; times 12-hour with server UTC converted via `parseStamp`.
Marathi strings need native review before release.

## 9. Accessibility checklist
Targets >= 48 dp; text AA (see section 2); every icon-only button has a tooltip/semantic label; status not by colour alone; live regions for errors; focus order follows reading order; test at 130% and 200% text scale and on 360 x 640.

## 10. Dark theme path
Blocked today because screens read `AppTheme.x` constants (2,510 uses). Path: add a `ThemeExtension` with the same token names, migrate by module, switch on once the last constant read is gone. Not in scope now.


## Pitfalls found by rendering the screens (keep out of new code)

1. **A card is one outer box.** Put the colour, outline and shadow on a `Container`, and the ink on a transparent `Material` inside it. A shadow drawn above a coloured `Material` tints the whole card grey. Prefer the outline (`AppTheme.border`) like the neighbouring cards; use the shadow only on a card with nothing coloured above it.
2. **Never replace a button's `textStyle`.** `ButtonStyle(textStyle:)` throws away the theme font (and the Marathi fallback). Set the size or weight on the `Text` instead, which merges.
3. **Bright semantic colours are for icons and fills, not words, and not as a fill under white text.** For words use the tone colours (`kToneColors`); for a filled caution button use `kWarningFill`.
4. **Say a figure once per screen.** If a dues card is at the top, no second card, chip and row repeating it.
5. **No placeholder tiles** ("Coming soon") in a shipped screen.
6. **Translate inside shared widgets, not at every call site.** A helper that draws text (`_SectionLabel`, a chip, a tile, a card) calls `context.tr`; then every screen that uses it is translated for free. For text with values, use `context.trf('Across {n} open bills', {'n': count})`: the template is the key, each language keeps the slots in its own order, and a test checks no `{slot}` reaches the screen. Keep English plural forms as two templates (`... bill` / `... bills`).
7. **Action labels are imperative; statuses are descriptive.** "Check Out" (do it) and "Checked Out" (it happened) are different texts and need different translations.
8. **No see-through fill under a shadow.** A box with `color: tint.withOpacity(0.08)` and a `boxShadow` shows the shadow through the fill and turns it a muddy grey on a real phone. Use `solidTint(color)` (a solid colour laid over the card white). Found on a device, not in tests.
9. **Labels in a fixed bar must not wrap.** The bottom bar caps its own text scale at 1.15x and uses one-line label styles; "Complaints" wrapped at a larger text setting before that. Test with the real font (`FontLoader`), not the test placeholder font, whose letters are far wider.
10. **The test renderer cannot show shadows.** It draws them as hard bands (and `Card` and button elevation as rings). Judge layout in rendered tests and shadows on a device.

## Premium building blocks (`shared/widgets/premium.dart`)
| Piece | Use |
|---|---|
| `HeroBanner` | the deep-blue gradient banner (home screens, login) with soft light circles |
| `AccentBadge` + `accentFor(label)` | gradient icon tile; a label always gets the same accent, so a service keeps its colour everywhere |
| `PremiumSurface` | white card with a soft shadow and ink on a transparent Material |
| `SectionHeading` | section title with a short accent bar |
| `solidTint(color)` | a solid light tint for a card background that also has a shadow |

The theme also gives every `Card` a soft shadow and buttons a resting glow in the brand colour; the bottom bar floats on a soft top shadow.
