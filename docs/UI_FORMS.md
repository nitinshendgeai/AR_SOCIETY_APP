# Forms — one layout for every full-page form

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

**Moved so far:** Resident, Tenant, Flat, Wing, Floor, Staff (add/edit), User (create/edit), Visitor, Complaint, Expense.
Still on the old layout: the voucher form, Edit My Profile, Society Settings, duty/attendance screens, and the bottom
sheets and dialogs (they use `AppSheet`).
