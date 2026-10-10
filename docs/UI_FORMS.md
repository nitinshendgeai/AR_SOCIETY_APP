# Pages, forms and sheets — one layout for every screen

A full-page form (Add Resident, Add Flat, Log Visitor…) is built with `AppFormPage`
(`mobile/lib/shared/widgets/app_form.dart`). It gives every form the same:

- **Header** — back button, title, one line saying what the form is for, optional status chip and links on the right.
  Header, cards and action bar share one content width (1080 px), so they line up on a wide screen.
- **Sections** — fields grouped in titled cards. On a wide screen the title and a line of explanation sit on the
  left and the fields in two columns on the right; on a phone they stack.
- **Action bar** — fixed at the bottom while the page scrolls: *Fields marked \* are required*, **Cancel** and the
  main button (which shows a spinner and locks while saving). On a phone the main button is full width.
- On a phone the standard app bar is kept (its back button is where people expect it).

```dart
AppFormPage(
  title: 'Add Resident',
  subtitle: 'Add a person to a flat in the society',
  formKey: _formKey,
  submitLabel: 'Add Resident',
  submitIcon: Icons.person_add_rounded,
  saving: isLoading,
  onSubmit: _submit,
  children: [
    FormSection(
      title: 'Personal information',
      description: 'Who the person is and how they relate to the flat.',
      children: [
        FormFieldBox(label: 'Full name', required: true, child: TextFormField(...)),
        FormFieldBox(label: 'Date of birth', child: FormDateField(...)),
        FormFull(child: FormSwitchTile(title: 'Primary resident', value: v, onChanged: ...)),
      ],
    ),
  ],
)
```

| Widget | Use |
|---|---|
| `FormSection(title, description, columns, children)` | A card of related fields. `columns: 1` for long fields. |
| `FormFieldBox(label, required, helper, child)` | Label above the field, red star when required, optional help line below. |
| `FormFull(child)` | Makes a field span the whole row (an address, a note, a switch). |
| `FormSwitchTile(title, subtitle, value, onChanged)` | A yes/no setting as a bordered row. |
| `FormDateField(value, hint, format, onTap, onClear)` | A date shown like a text field. |
| `AppFormPage(actions:, extraActions:)` | Links at the right of the header; extra buttons before the main one ("Save and add another"). |

Rules: put the label in `FormFieldBox`, not `InputDecoration.labelText`; keep hints short; give a dropdown
`isExpanded: true`; keep controllers, validation and API calls exactly as they were — only the layout changes.

## Ordinary screens (`AppPage`)

Every list, detail or card page uses `AppPage` (`mobile/lib/shared/widgets/app_form.dart`) instead of `Scaffold` + `AppBar`:

```dart
AppPage(
  title: 'Residents',
  subtitle: 'People who live in the society',   // optional
  actions: [ ...buttons at the right... ],
  bottom: TabBar(...),                          // optional; on a computer the tabs sit at the left
  floatingActionButton: ...,                    // optional
  body: ...,
)
```

On a computer it draws the same header as the forms (back button when there is somewhere to go back to, a 24 px title, a line
under it, buttons at the right) with the body on one centred content width (1280 px), so the header and the page line up. On a
phone it is the normal app bar. `ResponsiveBody` does nothing inside an `AppPage` (the page already sets the width).
Pass `maxWidth:` for a page of cards that reads better narrower.

## Forms in sheets and panels

Forms that open over a list (a bottom sheet on a phone, a side panel on a computer, via `showAppSheet`) use
`AppSheetFrame` (`BillingSheetFrame` is the same thing under its older name): a header with the title and what the
sheet is for, a rule, then the fields. Fields inside use `FormFieldBox` (label above), as on full pages.

## Settings pages and tabs

`AppPageHeader` (title, a line, buttons at the right) and `SettingsColumn` (a scrolling column of `FormSection`s on one
content width, with the save button at the end) give a settings screen with tabs the same look (Society Settings).

## Where it is used

- **Full-page forms (`AppFormPage`)**: Resident, Tenant, Flat, Wing, Floor, Staff add/edit, User create/edit, Visitor,
  Complaint, Expense, Voucher, Assign Duty, Edit My Info.
- **Settings (`SettingsColumn`)**: Society Settings (General, Contact, Subscription, Security).
- **Sheets (`AppSheetFrame`)**: every form sheet (stores, assets, amenities, notices, vendors and work orders, billing,
  platform console, meetings, polls, documents, parcels, domestic help, certificates, parking, vehicle, agreement
  renewal, move in/out, handover item, vendor bill, assign complaint…). About 150 fields now have their label above.

Not changed on purpose: the sign-in, change-password and registration pages (they stand alone, outside the app shell),
the role dashboards (they have their own layout and phone drawer), and pick-from-a-list sheets (account pickers,
bank-statement match candidates).
