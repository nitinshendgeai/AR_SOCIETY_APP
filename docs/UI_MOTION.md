# Motion — buttons, waiting, page changes

The app is used mostly in a browser on a computer, so it moves like a web app: things react to the pointer, waiting
is shown rather than hidden, and a page change is a short fade, not a phone-style slide. Everything lives in
`mobile/lib/core/motion/` and `AppTheme`, so a new screen gets it without any code.

| Where | What it does |
|---|---|
| **All buttons** (`AppTheme`) | Colour eases over 200 ms; filled buttons rise a little (shadow) under the pointer and settle when pressed; outlined buttons take the accent border on hover/focus; text buttons tint; the pointer becomes a hand. |
| `AppPrimaryButton` | Presses in (`PressableScale`); label and spinner cross-fade while it works. |
| `PressableScale` | Wrap any card, tile or custom button: lifts 1.5 % on hover, presses to 97 %. Listens to raw pointer events, so taps still reach the child. Already on KPI cards and dashboard quick actions. |
| **Page changes** (`AppPageTransitions`) | New page fades in while rising ~1 %; the old one dims slightly. Set once in `AppTheme`, applies to every route and platform. |
| `AppLoader` | The page/section spinner. Invisible for the first 150 ms (a quick answer shows no flash), then fades in; after 6 s it adds "Still working… the server may be waking up". Use instead of a bare `CircularProgressIndicator`. |
| `SkeletonList` / `SkeletonBox` / `Shimmer` | Grey placeholder rows shaped like the list, shimmering. Used by the list screens' `loading:` and, in their own columns, by `AppDataTable`. |
| `AppReveal(index: i)` | Fades and lifts a child in on first appearance; later items a beat after earlier ones. Used for dashboard sections and table rows. |
| `AppLoadingOverlay` | Scrim fades in and the card eases up; both fade out when done. |
| Spinners / progress bars | One theme (`progressIndicatorTheme`): brand blue, round ends. |
| Dashboard collection chart | Bars grow from the baseline. |

**Reduced motion.** When the device asks for less motion (`MediaQuery.disableAnimations`), every piece above shows
its end state at once (`AppMotion.reduced(context)`).

**Rules for new screens**
- Waiting on data: `loading: () => const SkeletonList()` for lists, `const AppLoader()` for anything else. No bare
  spinners in the middle of a page.
- A button that saves: `AppPrimaryButton(isLoading: …)`.
- A tappable card or tile that is not a Material button: wrap it in `PressableScale`.
- Don't add a `Timer` to drive an animation (tests fail on pending timers); use an `AnimationController`.
- Timings and curves come from `AppMotion` (fast 120 ms, base 200 ms, slow 320 ms, `easeOutCubic`).
