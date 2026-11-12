# DuxOS Society Mobile UI/UX Revamp

## Objective

Improve the existing Flutter Android application's usability and visual quality without replacing its architecture or changing business behaviour.

## Guardrails

- Preserve the existing application ID and signing/release configuration.
- Preserve FastAPI contracts, authentication, tenant isolation, RBAC and service entitlements.
- Do not introduce a second mobile app or a separate database.
- Keep the field-edition role restrictions intact. Admin/committee access must only be available in a build edition that already authorizes those roles.
- Keep the web application unchanged.
- Prefer shared components and theme tokens over one-off screen styling.
- Support small Android screens, large text scaling, Marathi/English strings, loading/error/empty states and accessibility semantics.

## Role-specific experience

Use one consistent design system, with dashboards and navigation derived from the authenticated user's existing roles and granted forms/services:

- Resident / Tenant: personal bills, visitor approvals, complaints, notices, amenities and profile.
- Security: gate operations, visitor check-in/out, verification and permitted supervisor actions.
- Technical staff: assigned work, attendance and service tasks.
- Gym trainer: gym-specific attendance and permitted work.
- Admin / Committee / Manager: only in an authorized build edition; operational overview, approvals and management shortcuts according to existing permissions.

Never infer access from the role label alone. Continue using the existing authorization and menu visibility mechanisms.

## Visual direction

- Calm, premium, mobile-first interface.
- DuxOS blue as the primary accent, neutral light surfaces and restrained semantic colors.
- Compact app header and greeting area.
- Clear hierarchy: urgent actions first, key metrics second, secondary information later.
- Consistent 8-point spacing rhythm, readable typography and accessible tap targets.
- Avoid oversized hero cards, oversized charts, redundant labels and large empty chart regions.
- Use compact summaries for zero/empty data; do not represent failed data requests as zero.
- Bottom navigation should expose only the most-used role-specific destinations; remaining destinations stay in the existing More menu.

## Delivery sequence

1. Dashboard header/greeting and navigation shell.
2. Role-specific dashboard information hierarchy and quick actions.
3. Maintenance bills, receipts and payment screens.
4. Notices, complaints, visitors and staff workflows.
5. Remaining feature screens, accessibility and responsive polish.

## First implementation slice

- Reduce the height and visual dominance of the shared role-dashboard greeting card.
- Keep the user's name, role context, society identity and date readable without long society names forcing multiple lines.
- Preserve the existing providers and data sources.
- Review the bottom navigation after the updated dashboard is installed and visually checked on a physical device.

## Validation checklist

- Flutter format and analyze.
- Existing unit/widget tests.
- Verify each authorized role lands on the correct dashboard.
- Verify unauthorized routes remain inaccessible.
- Verify each role sees only its granted services.
- Verify loading, empty, error and long-text states.
- Test on compact and large Android screen sizes and with larger system text.
- Build and install a fresh APK; compare screenshots against the current APK before merging.
