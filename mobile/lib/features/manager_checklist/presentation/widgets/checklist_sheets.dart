import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/manager_checklist/data/checklist_api.dart';
import 'package:ar_society_app/features/manager_checklist/presentation/widgets/checklist_widgets.dart';
import 'package:ar_society_app/features/vendor/presentation/widgets/procurement_widgets.dart' show DateField;
import 'package:ar_society_app/shared/widgets/app_form.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// Record an item as done on a date (with a reference, and for a licence the date it runs to), or mark it as not
/// applicable with a reason. Closes with `true` when it saved.
class RecordSheet extends ConsumerStatefulWidget {
  final ChecklistEntry entry;
  const RecordSheet({super.key, required this.entry});

  @override
  ConsumerState<RecordSheet> createState() => _RecordSheetState();
}

class _RecordSheetState extends ConsumerState<RecordSheet> {
  final _form = GlobalKey<FormState>();
  final _reference = TextEditingController();
  final _note = TextEditingController();
  DateTime _doneOn = DateTime.now();
  DateTime? _validUntil;
  bool _saving = false;

  ChecklistEntry get e => widget.entry;

  @override
  void initState() {
    super.initState();
    _reference.text = e.log?.reference ?? '';
    _note.text = e.log?.note ?? '';
    _validUntil = e.log?.validUntil ?? e.validUntil;
    if (e.log != null) _doneOn = e.log!.doneOn;
  }

  @override
  void dispose() {
    _reference.dispose();
    _note.dispose();
    super.dispose();
  }

  Future<void> _save(String status) async {
    if (status == 'skipped' && _note.text.trim().length < 3) {
      showErrorToast(context, Exception('Say why this does not apply'));
      return;
    }
    if (status == 'done' && !_form.currentState!.validate()) return;
    setState(() => _saving = true);
    try {
      await ref.read(checklistApiProvider).complete(e.id,
          status: status,
          doneOn: _doneOn,
          note: _note.text,
          reference: _reference.text,
          validUntil: status == 'done' ? _validUntil : null);
      invalidateChecklist(ref);
      if (mounted) {
        AppToast.success(context, status == 'done' ? 'Recorded' : 'Marked as not applicable');
        Navigator.pop(context, true);
      }
    } catch (err) {
      if (mounted) {
        setState(() => _saving = false);
        showErrorToast(context, err);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return AppSheetFrame(
      title: e.title,
      subtitle: e.isLicence ? 'Record the licence or certificate and the date it runs to' : e.schedule,
      child: Form(
        key: _form,
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          if (e.legalBasis != null) ...[
            Text('Basis: ${e.legalBasis}', style: const TextStyle(fontSize: 12.5, height: 1.4, color: AppTheme.textSecondary)),
            const SizedBox(height: 14),
          ],
          FormFieldBox(
              label: e.isLicence ? 'Date renewed or issued' : 'Date done',
              child: DateField(label: '', value: _doneOn, lastDate: DateTime.now(), onChanged: (d) => setState(() => _doneOn = d ?? _doneOn))),
          const SizedBox(height: 12),
          if (e.isLicence) ...[
            FormFieldBox(
                label: 'Valid until',
                required: true,
                child: DateField(
                    label: '',
                    value: _validUntil,
                    required: true,
                    lastDate: DateTime.now().add(const Duration(days: 365 * 12)),
                    onChanged: (d) => setState(() => _validUntil = d))),
            const SizedBox(height: 12),
          ],
          FormFieldBox(
              label: 'Reference',
              helper: 'Certificate, receipt, challan or policy number',
              child: TextFormField(controller: _reference, inputFormatters: [LengthLimitingTextInputFormatter(120)])),
          const SizedBox(height: 12),
          FormFieldBox(
              label: 'Note',
              child: TextFormField(controller: _note, maxLines: 2, inputFormatters: [LengthLimitingTextInputFormatter(1000)])),
          const SizedBox(height: 18),
          AppPrimaryButton(label: 'Save', isLoading: _saving, onPressed: _saving ? null : () => _save('done')),
          const SizedBox(height: 8),
          TextButton(
              onPressed: _saving ? null : () => _save('skipped'),
              child: const Text('Does not apply — skip (give the reason in the note)')),
        ]),
      ),
    );
  }
}

/// Close the day: what was done, what was left, and a word for the record.
class SignoffSheet extends ConsumerStatefulWidget {
  final String societyId;
  final TodayChecklist today;
  const SignoffSheet({super.key, required this.societyId, required this.today});

  @override
  ConsumerState<SignoffSheet> createState() => _SignoffSheetState();
}

class _SignoffSheetState extends ConsumerState<SignoffSheet> {
  late final _remarks = TextEditingController(text: widget.today.signoff?.remarks);
  bool _saving = false;

  @override
  void dispose() {
    _remarks.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    setState(() => _saving = true);
    try {
      await ref.read(checklistApiProvider).signOff(widget.societyId, _remarks.text.trim().isEmpty ? null : _remarks.text);
      invalidateChecklist(ref);
      if (mounted) {
        AppToast.success(context, 'Day signed off');
        Navigator.pop(context, true);
      }
    } catch (err) {
      if (mounted) {
        setState(() => _saving = false);
        showErrorToast(context, err);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = widget.today.summary;
    final left = s.total - s.done;
    return AppSheetFrame(
      title: 'Close the day',
      subtitle: dayName(widget.today.asOf),
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        ChecklistCard(
          padding: const EdgeInsets.all(14),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('${s.done} of ${s.total} items done${left > 0 ? ' · $left left' : ''}',
                style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700)),
            const SizedBox(height: 4),
            Text(
                s.liveOpen == 0
                    ? 'Nothing is flagged from the records.'
                    : '${s.liveOpen} item(s) are still flagged from the records.',
                style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary)),
          ]),
        ),
        const SizedBox(height: 14),
        FormFieldBox(
            label: 'Remarks',
            helper: 'What was left, and anything to report to the committee',
            child: TextField(controller: _remarks, maxLines: 4, inputFormatters: [LengthLimitingTextInputFormatter(1000)])),
        const SizedBox(height: 18),
        AppPrimaryButton(
            label: widget.today.signoff == null ? 'Sign off' : 'Update sign-off', isLoading: _saving, onPressed: _saving ? null : _save),
      ]),
    );
  }
}

/// Add an item of the society's own, or change one on the list. Closes with `true` when something was saved.
class ItemFormSheet extends ConsumerStatefulWidget {
  final String societyId;
  final ChecklistEntry? existing;
  final ItemList options;
  const ItemFormSheet({super.key, required this.societyId, this.existing, required this.options});

  @override
  ConsumerState<ItemFormSheet> createState() => _ItemFormSheetState();
}

class _ItemFormSheetState extends ConsumerState<ItemFormSheet> {
  final _form = GlobalKey<FormState>();
  late final ChecklistEntry? e = widget.existing;
  late final _title = TextEditingController(text: e?.title);
  late final _detail = TextEditingController(text: e?.detail);
  late final _basis = TextEditingController(text: e?.legalBasis);
  late String _category = e?.category ?? 'housekeeping';
  late String _frequency = e?.frequency ?? 'daily';
  late int _weekday = e?.dueWeekday ?? 0;
  late int _day = e?.dueDay ?? 1;
  late final Set<int> _months = {...?e?.dueMonths};
  late int _lead = e?.leadDays ?? 0;
  late String? _asset = e?.assetCategory;
  late String? _dept = e?.staffDepartment;
  late bool _statutory = e?.statutory ?? false;
  bool _saving = false;

  @override
  void dispose() {
    _title.dispose();
    _detail.dispose();
    _basis.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (!_form.currentState!.validate()) return;
    if (_frequency == 'on_dates' && _months.isEmpty) {
      showErrorToast(context, Exception('Choose at least one month'));
      return;
    }
    setState(() => _saving = true);
    final body = <String, dynamic>{
      'title': _title.text.trim(),
      'detail': _detail.text.trim().isEmpty ? null : _detail.text.trim(),
      'category': _category,
      'frequency': _frequency,
      'due_weekday': _frequency == 'weekly' ? _weekday : null,
      'due_day': _frequency == 'monthly' || _frequency == 'on_dates' ? _day : null,
      'due_months': _frequency == 'on_dates' ? (_months.toList()..sort()) : null,
      'lead_days': _frequency == 'daily' || _frequency == 'weekly' ? 0 : _lead,
      'asset_category': _asset,
      'staff_department': _dept,
      'legal_basis': _basis.text.trim().isEmpty ? null : _basis.text.trim(),
    };
    try {
      final api = ref.read(checklistApiProvider);
      if (e == null) {
        await api.create(widget.societyId, {...body, 'statutory': _statutory});
      } else {
        await api.update(e!.id, body);
      }
      invalidateChecklist(ref);
      if (mounted) {
        AppToast.success(context, e == null ? 'Item added' : 'Saved');
        Navigator.pop(context, true);
      }
    } catch (err) {
      if (mounted) {
        setState(() => _saving = false);
        showErrorToast(context, err);
      }
    }
  }

  Future<void> _delete() async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Delete this item?'),
        content: const Text('It is taken off the checklist. What was ticked against it stays in the record.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Keep it')),
          FilledButton(
              style: FilledButton.styleFrom(backgroundColor: AppTheme.error),
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text('Delete')),
        ],
      ),
    );
    if (ok != true) return;
    setState(() => _saving = true);
    try {
      await ref.read(checklistApiProvider).delete(e!.id);
      invalidateChecklist(ref);
      if (mounted) Navigator.pop(context, true);
    } catch (err) {
      if (mounted) {
        setState(() => _saving = false);
        showErrorToast(context, err);
      }
    }
  }

  Widget _dropdown<T>(String label, T? value, List<(T?, String)> options, ValueChanged<T?> onChanged, {String? helper}) =>
      Padding(
        padding: const EdgeInsets.only(bottom: 12),
        child: FormFieldBox(
            label: label,
            helper: helper,
            child: DropdownButtonFormField<T>(
              initialValue: value,
              isExpanded: true,
              decoration: const InputDecoration(),
              items: [for (final o in options) DropdownMenuItem<T>(value: o.$1, child: Text(o.$2))],
              onChanged: onChanged,
            )),
      );

  @override
  Widget build(BuildContext context) {
    final o = widget.options;
    final scheduled = _frequency != 'daily' && _frequency != 'weekly';
    return AppSheetFrame(
      title: e == null ? 'Add an item' : 'Change item',
      subtitle: e?.isStandard == true ? 'A built-in item — you can reword it, move its date or switch it off' : null,
      child: Form(
        key: _form,
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: FormFieldBox(
                label: 'What is to be done',
                required: true,
                child: TextFormField(
                    controller: _title,
                    textCapitalization: TextCapitalization.sentences,
                    inputFormatters: [LengthLimitingTextInputFormatter(200)],
                    validator: (v) => (v ?? '').trim().length < 3 ? 'Give the item a title' : null)),
          ),
          Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: FormFieldBox(
                label: 'Details',
                child: TextFormField(controller: _detail, maxLines: 2, inputFormatters: [LengthLimitingTextInputFormatter(2000)])),
          ),
          _dropdown<String>('Group', _category, [for (final c in o.categories) (c.key, c.label)], (v) => setState(() => _category = v ?? _category)),
          _dropdown<String>('How often', _frequency, [for (final f in kFrequencies) (f.$1, f.$2)], (v) => setState(() => _frequency = v ?? _frequency)),
          if (_frequency == 'weekly')
            _dropdown<int>('Day of the week', _weekday, [for (var i = 0; i < 7; i++) (i, kWeekdays[i])], (v) => setState(() => _weekday = v ?? 0)),
          if (_frequency == 'monthly' || _frequency == 'on_dates')
            _dropdown<int>('By which day of the month', _day, [for (var d = 1; d <= 31; d++) (d, d == 31 ? '31 (the last day)' : '$d')],
                (v) => setState(() => _day = v ?? 1)),
          if (_frequency == 'on_dates')
            Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: FormFieldBox(
                  label: 'In which months',
                  required: true,
                  child: Wrap(spacing: 8, runSpacing: 8, children: [
                    for (var m = 1; m <= 12; m++)
                      FilterChip(
                          label: Text(kMonthNames[m - 1]),
                          selected: _months.contains(m),
                          onSelected: (on) => setState(() => on ? _months.add(m) : _months.remove(m))),
                  ])),
            ),
          if (scheduled)
            _dropdown<int>('Show it before it falls due', _lead, [for (final d in const [0, 3, 7, 14, 21, 30, 45, 60, 90, 120]) (d, d == 0 ? 'Only on the day' : '$d days before')],
                (v) => setState(() => _lead = v ?? 0)),
          _dropdown<String?>('Only if the society has this asset', _asset,
              [(null, 'Not tied to an asset'), for (final c in o.assetCategories) (c.key, c.label)], (v) => setState(() => _asset = v),
              helper: 'It shows only while there is such an asset in the register'),
          _dropdown<String?>('Only if the society has this staff', _dept,
              [(null, 'Not tied to staff'), for (final c in o.departments) (c.key, c.label)], (v) => setState(() => _dept = v)),
          Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: FormFieldBox(
                label: 'Legal basis',
                helper: 'The law, rule or bye-law this comes from, if any',
                child: TextFormField(controller: _basis, maxLines: 2, inputFormatters: [LengthLimitingTextInputFormatter(1000)])),
          ),
          if (e == null)
            FormSwitchTile(
                title: 'A statutory or legal requirement',
                subtitle: 'It then appears in the compliance calendar',
                value: _statutory,
                onChanged: (v) => setState(() => _statutory = v)),
          const SizedBox(height: 16),
          AppPrimaryButton(label: e == null ? 'Add item' : 'Save', isLoading: _saving, onPressed: _saving ? null : _save),
          if (e != null && !e!.isStandard) ...[
            const SizedBox(height: 8),
            TextButton(
                onPressed: _saving ? null : _delete,
                style: TextButton.styleFrom(foregroundColor: AppTheme.error),
                child: const Text('Delete this item')),
          ],
        ]),
      ),
    );
  }
}
