import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/amenities/data/amenities_api.dart';
import 'package:ar_society_app/features/amenities/presentation/providers/amenities_providers.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/widgets/billing_sheet_frame.dart';
import 'package:ar_society_app/features/vendor/presentation/widgets/procurement_widgets.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

String? _trimmed(TextEditingController c) => c.text.trim().isEmpty ? null : c.text.trim();

/// A tappable time field.
class TimeField extends StatelessWidget {
  final String label;
  final TimeOfDay? value;
  final ValueChanged<TimeOfDay?> onChanged;
  final bool clearable;
  const TimeField({super.key, required this.label, required this.value, required this.onChanged, this.clearable = false});

  @override
  Widget build(BuildContext context) => InkWell(
        onTap: () async {
          final t = await showTimePicker(context: context, initialTime: value ?? const TimeOfDay(hour: 9, minute: 0));
          if (t != null) onChanged(t);
        },
        child: InputDecorator(
          decoration: InputDecoration(
            labelText: label,
            suffixIcon: clearable && value != null
                ? IconButton(icon: const Icon(Icons.close_rounded, size: 18), onPressed: () => onChanged(null))
                : const Icon(Icons.schedule_rounded, size: 18),
          ),
          child: Text(value == null ? '—' : timeLabel(value)),
        ),
      );
}

double _hours(TimeOfDay a, TimeOfDay b) => (b.hour * 60 + b.minute - a.hour * 60 - a.minute) / 60;

// ── Book an amenity ──────────────────────────────────────────────────────────

class BookingSheet extends ConsumerStatefulWidget {
  final AmenityItem amenity;
  final DateTime date;
  const BookingSheet({super.key, required this.amenity, required this.date});

  @override
  ConsumerState<BookingSheet> createState() => _BookingSheetState();
}

class _BookingSheetState extends ConsumerState<BookingSheet> {
  final _form = GlobalKey<FormState>();
  final _guests = TextEditingController(text: '1');
  final _purpose = TextEditingController();
  late DateTime _date = widget.date;
  late TimeOfDay _start = widget.amenity.open != null && widget.amenity.open!.hour < 17
      ? TimeOfDay(hour: widget.amenity.open!.hour + 4 > 21 ? 9 : widget.amenity.open!.hour + 4, minute: 0)
      : const TimeOfDay(hour: 17, minute: 0);
  late TimeOfDay _end = TimeOfDay(hour: (_start.hour + 1) % 24, minute: _start.minute);
  bool _saving = false;

  @override
  void dispose() {
    _guests.dispose();
    _purpose.dispose();
    super.dispose();
  }

  /// What this will cost, from the amenity's own rate rule, else its default rate. Null when it is free.
  String? _cost() {
    if (!widget.amenity.chargeable) return null;
    final hours = _hours(_start, _end);
    if (hours <= 0) return null;
    final rules = ref.watch(amenityRulesProvider(widget.amenity.id)).valueOrNull ?? const <AmenityRule>[];
    final rates = ref.watch(amenityRatesProvider(widget.amenity.id)).valueOrNull ?? const <AmenityRate>[];
    double? charge, deposit;
    for (final r in rules) {
      if (r.type == 'charge_per_hour') charge = (double.tryParse(r.value ?? '') ?? 0) * hours;
      if (r.type == 'deposit_required') deposit = double.tryParse(r.value ?? '');
    }
    final d = rates.where((r) => r.isDefault).firstOrNull;
    if (d != null) {
      charge ??= d.flat ?? (d.perHour != null ? d.perHour! * hours : null);
      deposit ??= d.deposit;
    }
    if (charge == null && deposit == null) return null;
    return [if (charge != null) 'Charge ${rupees(charge)}', if (deposit != null) 'Deposit ${rupees(deposit)}'].join(' · ');
  }

  Future<void> _book() async {
    if (!_form.currentState!.validate()) return;
    if (_hours(_start, _end) <= 0) {
      AppToast.warning(context, 'It must end after it starts');
      return;
    }
    setState(() => _saving = true);
    try {
      final b = await ref.read(amenitiesApiProvider).book({
        'amenity_id': widget.amenity.id,
        'booking_date': apiDate(_date),
        'start_time': apiTime(_start),
        'end_time': apiTime(_end),
        'guest_count': int.parse(_guests.text.trim()),
        if (_trimmed(_purpose) != null) 'purpose': _trimmed(_purpose),
      });
      invalidateAmenities(ref);
      if (!mounted) return;
      AppToast.success(context, b.status == 'pending' ? 'Requested. The committee will confirm it.' : 'Booked');
      Navigator.of(context).pop(b);
    } catch (e) {
      if (mounted) {
        setState(() => _saving = false);
        showErrorToast(context, e);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final a = widget.amenity;
    final cost = _cost();
    return BillingSheetFrame(
      title: 'Book ${a.name}',
      child: Form(
        key: _form,
        autovalidateMode: AutovalidateMode.onUserInteraction,
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Text('${a.hours}${a.capacity != null ? ' · up to ${a.capacity} people' : ''}',
              style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary)),
          const SizedBox(height: 12),
          DateField(
            label: 'Date',
            value: _date,
            required: true,
            onChanged: (v) => setState(() => _date = v ?? _date),
          ),
          const SizedBox(height: 12),
          Row(children: [
            Expanded(child: TimeField(label: 'From', value: _start, onChanged: (v) => setState(() => _start = v ?? _start))),
            const SizedBox(width: 12),
            Expanded(child: TimeField(label: 'To', value: _end, onChanged: (v) => setState(() => _end = v ?? _end))),
          ]),
          const SizedBox(height: 12),
          TextFormField(
            controller: _guests,
            keyboardType: TextInputType.number,
            inputFormatters: [FilteringTextInputFormatter.digitsOnly],
            decoration: const InputDecoration(labelText: 'How many people', helperText: 'Including you'),
            validator: (v) => (int.tryParse((v ?? '').trim()) ?? 0) < 1 ? 'At least one person' : null,
          ),
          const SizedBox(height: 12),
          TextFormField(
            controller: _purpose,
            maxLength: 200,
            textCapitalization: TextCapitalization.sentences,
            decoration: const InputDecoration(labelText: 'What for (optional)', hintText: 'e.g. Birthday party', counterText: ''),
          ),
          if (cost != null) ...[
            const SizedBox(height: 8),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(color: AppTheme.warningSoft, borderRadius: BorderRadius.circular(AppTheme.radiusM)),
              child: Row(children: [
                const Icon(Icons.currency_rupee_rounded, size: 18, color: AppTheme.warning),
                const SizedBox(width: 8),
                Expanded(child: Text('$cost. The committee collects it from you; it is not added to your maintenance bill.',
                    style: const TextStyle(fontSize: 12.5, height: 1.35))),
              ]),
            ),
          ],
          if (a.approvalRequired) ...[
            const SizedBox(height: 8),
            const Text('The committee confirms each booking of this amenity. You will be told when it is decided.',
                style: TextStyle(fontSize: 12.5, color: AppTheme.textSecondary)),
          ],
          const SizedBox(height: 16),
          AppPrimaryButton(label: a.approvalRequired ? 'Request booking' : 'Book', isLoading: _saving, onPressed: _saving ? null : _book),
        ]),
      ),
    );
  }
}

// ── Set up or change an amenity ──────────────────────────────────────────────

class AmenityFormSheet extends ConsumerStatefulWidget {
  final AmenityItem? amenity;
  const AmenityFormSheet({super.key, this.amenity});

  @override
  ConsumerState<AmenityFormSheet> createState() => _AmenityFormSheetState();
}

class _AmenityFormSheetState extends ConsumerState<AmenityFormSheet> {
  final _form = GlobalKey<FormState>();
  late final _name = TextEditingController(text: a?.name);
  late final _location = TextEditingController(text: a?.location);
  late final _description = TextEditingController(text: a?.description);
  late final _capacity = TextEditingController(text: a?.capacity?.toString() ?? '');
  late String _type = a?.type ?? 'clubhouse';
  late TimeOfDay? _open = a?.open ?? const TimeOfDay(hour: 6, minute: 0);
  late TimeOfDay? _close = a?.close ?? const TimeOfDay(hour: 22, minute: 0);
  late bool _booking = a?.bookingRequired ?? true;
  late bool _approval = a?.approvalRequired ?? false;
  late bool _chargeable = a?.chargeable ?? false;
  bool _saving = false;

  AmenityItem? get a => widget.amenity;

  @override
  void dispose() {
    _name.dispose();
    _location.dispose();
    _description.dispose();
    _capacity.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (!_form.currentState!.validate()) return;
    if ((_open == null) != (_close == null)) {
      AppToast.warning(context, 'Give both the opening and closing time, or neither');
      return;
    }
    setState(() => _saving = true);
    try {
      final body = {
        'name': _name.text.trim(),
        'amenity_type': _type,
        'location': _trimmed(_location),
        'description': _trimmed(_description),
        'capacity': int.tryParse(_capacity.text.trim()),
        'open_time': _open == null ? null : apiTime(_open!),
        'close_time': _close == null ? null : apiTime(_close!),
        'booking_required': _booking,
        'approval_required': _approval,
        'is_chargeable': _chargeable,
      };
      final api = ref.read(amenitiesApiProvider);
      final saved = a == null ? await api.create(body..removeWhere((_, v) => v == null)) : await api.update(a!.id, body);
      invalidateAmenities(ref);
      if (!mounted) return;
      AppToast.success(context, a == null ? '${saved.name} added' : 'Saved');
      Navigator.of(context).pop(saved);
    } catch (e) {
      if (mounted) {
        setState(() => _saving = false);
        showErrorToast(context, e);
      }
    }
  }

  @override
  Widget build(BuildContext context) => BillingSheetFrame(
        title: a == null ? 'Add an amenity' : 'Edit ${a!.name}',
        child: Form(
          key: _form,
          autovalidateMode: AutovalidateMode.onUserInteraction,
          child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            TextFormField(
              controller: _name,
              maxLength: 150,
              textCapitalization: TextCapitalization.words,
              decoration: const InputDecoration(labelText: 'Name *', hintText: 'e.g. Clubhouse', counterText: ''),
              validator: (v) => (v ?? '').trim().isEmpty ? 'Give it a name' : null,
            ),
            const SizedBox(height: 12),
            DropdownButtonFormField<String>(
              initialValue: _type,
              isExpanded: true,
              decoration: const InputDecoration(labelText: 'Kind'),
              items: [
                for (final t in kAmenityTypes)
                  DropdownMenuItem(value: t.$1, child: Row(children: [Icon(t.$3, size: 18, color: AppTheme.textSecondary), const SizedBox(width: 10), Text(t.$2)])),
              ],
              onChanged: (v) => setState(() => _type = v ?? _type),
            ),
            const SizedBox(height: 12),
            TextFormField(controller: _location, maxLength: 200, decoration: const InputDecoration(labelText: 'Where', hintText: 'e.g. Ground floor, Wing A', counterText: '')),
            const SizedBox(height: 12),
            TextFormField(
              controller: _capacity,
              keyboardType: TextInputType.number,
              inputFormatters: [FilteringTextInputFormatter.digitsOnly],
              decoration: const InputDecoration(labelText: 'Most people at a time (optional)'),
              validator: (v) => (v ?? '').trim().isNotEmpty && (int.tryParse(v!.trim()) ?? 0) < 1 ? 'At least 1' : null,
            ),
            const SizedBox(height: 12),
            Row(children: [
              Expanded(child: TimeField(label: 'Opens', value: _open, clearable: true, onChanged: (v) => setState(() => _open = v))),
              const SizedBox(width: 12),
              Expanded(child: TimeField(label: 'Closes', value: _close, clearable: true, onChanged: (v) => setState(() => _close = v))),
            ]),
            const SizedBox(height: 12),
            TextFormField(
              controller: _description,
              minLines: 2,
              maxLines: 4,
              textCapitalization: TextCapitalization.sentences,
              decoration: const InputDecoration(labelText: 'About it (optional)', alignLabelWithHint: true),
            ),
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              value: _booking,
              onChanged: (v) => setState(() => _booking = v),
              title: const Text('Residents book a time'),
              subtitle: const Text('Turn off for places anyone can just use'),
            ),
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              value: _approval,
              onChanged: _booking ? (v) => setState(() => _approval = v) : null,
              title: const Text('The committee approves each booking'),
            ),
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              value: _chargeable,
              onChanged: (v) => setState(() => _chargeable = v),
              title: const Text('There is a charge'),
              subtitle: const Text('Set the rates afterwards'),
            ),
            const SizedBox(height: 12),
            AppPrimaryButton(label: 'Save', isLoading: _saving, onPressed: _saving ? null : _save),
          ]),
        ),
      );
}

// ── A rule ───────────────────────────────────────────────────────────────────

class RuleSheet extends ConsumerStatefulWidget {
  final String amenityId;
  const RuleSheet({super.key, required this.amenityId});

  @override
  ConsumerState<RuleSheet> createState() => _RuleSheetState();
}

class _RuleSheetState extends ConsumerState<RuleSheet> {
  final _form = GlobalKey<FormState>();
  final _value = TextEditingController();
  String _type = kRuleKinds.first.$1;
  bool _saving = false;

  @override
  void dispose() {
    _value.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (!_form.currentState!.validate()) return;
    setState(() => _saving = true);
    try {
      final kind = ruleKind(_type)!.kind;
      await ref.read(amenitiesApiProvider).setRule(widget.amenityId, _type, kind == 'flag' ? null : _value.text.trim());
      invalidateAmenities(ref);
      if (!mounted) return;
      AppToast.success(context, 'Rule saved');
      Navigator.of(context).pop(true);
    } catch (e) {
      if (mounted) {
        setState(() => _saving = false);
        showErrorToast(context, e);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final k = ruleKind(_type)!;
    return BillingSheetFrame(
      title: 'Add a rule',
      child: Form(
        key: _form,
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          DropdownButtonFormField<String>(
            initialValue: _type,
            isExpanded: true,
            decoration: const InputDecoration(labelText: 'Rule'),
            items: [for (final r in kRuleKinds) DropdownMenuItem(value: r.$1, child: Text(r.$2))],
            onChanged: (v) => setState(() {
              _type = v ?? _type;
              _value.clear();
            }),
          ),
          if (k.kind != 'flag') ...[
            const SizedBox(height: 12),
            TextFormField(
              controller: _value,
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
              inputFormatters: k.kind == 'int' ? [FilteringTextInputFormatter.digitsOnly] : moneyInput,
              decoration: InputDecoration(labelText: 'Value *', helperText: k.hint),
              validator: (v) => (double.tryParse((v ?? '').trim()) ?? 0) <= 0 ? 'Enter a number above zero' : null,
            ),
          ] else
            Padding(padding: const EdgeInsets.only(top: 10), child: Text(k.hint, style: const TextStyle(color: AppTheme.textSecondary))),
          const SizedBox(height: 6),
          const Text('Setting a rule again replaces the earlier one.', style: TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
          const SizedBox(height: 14),
          AppPrimaryButton(label: 'Save rule', isLoading: _saving, onPressed: _saving ? null : _save),
        ]),
      ),
    );
  }
}

// ── A rate ───────────────────────────────────────────────────────────────────

class RateSheet extends ConsumerStatefulWidget {
  final String amenityId;
  const RateSheet({super.key, required this.amenityId});

  @override
  ConsumerState<RateSheet> createState() => _RateSheetState();
}

class _RateSheetState extends ConsumerState<RateSheet> {
  final _form = GlobalKey<FormState>();
  final _label = TextEditingController(text: 'Standard');
  final _flat = TextEditingController();
  final _hour = TextEditingController();
  final _deposit = TextEditingController();
  bool _default = true;
  bool _saving = false;

  @override
  void dispose() {
    _label.dispose();
    _flat.dispose();
    _hour.dispose();
    _deposit.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (!_form.currentState!.validate()) return;
    if (parseMoney(_flat.text) == null && parseMoney(_hour.text) == null && parseMoney(_deposit.text) == null) {
      AppToast.warning(context, 'Give a price per booking, a price per hour or a deposit');
      return;
    }
    setState(() => _saving = true);
    try {
      await ref.read(amenitiesApiProvider).addRate(widget.amenityId, {
        'label': _label.text.trim(),
        'flat_price': parseMoney(_flat.text),
        'price_per_hour': parseMoney(_hour.text),
        'deposit_amount': parseMoney(_deposit.text),
        'is_default': _default,
      });
      invalidateAmenities(ref);
      if (!mounted) return;
      AppToast.success(context, 'Rate saved');
      Navigator.of(context).pop(true);
    } catch (e) {
      if (mounted) {
        setState(() => _saving = false);
        showErrorToast(context, e);
      }
    }
  }

  @override
  Widget build(BuildContext context) => BillingSheetFrame(
        title: 'Add a rate',
        child: Form(
          key: _form,
          child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            TextFormField(
              controller: _label,
              decoration: const InputDecoration(labelText: 'Name *', hintText: 'e.g. Weekend'),
              validator: (v) => (v ?? '').trim().isEmpty ? 'Name this rate' : null,
            ),
            const SizedBox(height: 12),
            TextFormField(controller: _flat, keyboardType: const TextInputType.numberWithOptions(decimal: true), inputFormatters: moneyInput, decoration: const InputDecoration(labelText: 'Price per booking (₹)')),
            const SizedBox(height: 12),
            TextFormField(controller: _hour, keyboardType: const TextInputType.numberWithOptions(decimal: true), inputFormatters: moneyInput, decoration: const InputDecoration(labelText: 'Price per hour (₹)', helperText: 'Used when there is no price per booking')),
            const SizedBox(height: 12),
            TextFormField(controller: _deposit, keyboardType: const TextInputType.numberWithOptions(decimal: true), inputFormatters: moneyInput, decoration: const InputDecoration(labelText: 'Refundable deposit (₹)')),
            SwitchListTile(contentPadding: EdgeInsets.zero, value: _default, onChanged: (v) => setState(() => _default = v), title: const Text('Use this rate for bookings')),
            const SizedBox(height: 10),
            AppPrimaryButton(label: 'Save rate', isLoading: _saving, onPressed: _saving ? null : _save),
          ]),
        ),
      );
}

// ── Close a date ─────────────────────────────────────────────────────────────

class ClosedDateSheet extends ConsumerStatefulWidget {
  final String amenityId;
  const ClosedDateSheet({super.key, required this.amenityId});

  @override
  ConsumerState<ClosedDateSheet> createState() => _ClosedDateSheetState();
}

class _ClosedDateSheetState extends ConsumerState<ClosedDateSheet> {
  final _reason = TextEditingController();
  DateTime _date = DateTime.now().add(const Duration(days: 1));
  bool _saving = false;

  @override
  void dispose() {
    _reason.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    setState(() => _saving = true);
    try {
      await ref.read(amenitiesApiProvider).closeDate(widget.amenityId, _date, _reason.text.trim());
      invalidateAmenities(ref);
      if (!mounted) return;
      AppToast.success(context, 'Closed on ${dayLabel(_date)}');
      Navigator.of(context).pop(true);
    } catch (e) {
      if (mounted) {
        setState(() => _saving = false);
        showErrorToast(context, e);
      }
    }
  }

  @override
  Widget build(BuildContext context) => BillingSheetFrame(
        title: 'Close it on a date',
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          DateField(label: 'Date', value: _date, required: true, onChanged: (v) => setState(() => _date = v ?? _date)),
          const SizedBox(height: 12),
          TextField(controller: _reason, decoration: const InputDecoration(labelText: 'Why (optional)', hintText: 'e.g. Painting')),
          const SizedBox(height: 6),
          const Text('Nobody can book it on that day. Bookings already made are not cancelled.',
              style: TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
          const SizedBox(height: 14),
          AppPrimaryButton(label: 'Close that day', isLoading: _saving, onPressed: _saving ? null : _save),
        ]),
      );
}

// ── Reject / cancel with a reason, and complete ──────────────────────────────

/// Asks for a reason; pops the reason text. For rejecting, a reason is required.
class ReasonSheet extends StatefulWidget {
  final String title;
  final String label;
  final String action;
  final bool required;
  const ReasonSheet({super.key, required this.title, required this.label, required this.action, this.required = true});

  @override
  State<ReasonSheet> createState() => _ReasonSheetState();
}

class _ReasonSheetState extends State<ReasonSheet> {
  final _form = GlobalKey<FormState>();
  final _text = TextEditingController();

  @override
  void dispose() {
    _text.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => BillingSheetFrame(
        title: widget.title,
        child: Form(
          key: _form,
          child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            TextFormField(
              controller: _text,
              minLines: 2,
              maxLines: 4,
              textCapitalization: TextCapitalization.sentences,
              decoration: InputDecoration(labelText: widget.required ? '${widget.label} *' : widget.label, alignLabelWithHint: true),
              validator: (v) => widget.required && (v ?? '').trim().isEmpty ? 'Say why' : null,
            ),
            const SizedBox(height: 14),
            FilledButton(
              onPressed: () {
                if (_form.currentState!.validate()) Navigator.of(context).pop(_text.text.trim());
              },
              child: Text(widget.action),
            ),
          ]),
        ),
      );
}

/// After the booking has been used: note any damage. Pops (damaged, notes).
class CompleteSheet extends StatefulWidget {
  const CompleteSheet({super.key});

  @override
  State<CompleteSheet> createState() => _CompleteSheetState();
}

class _CompleteSheetState extends State<CompleteSheet> {
  final _notes = TextEditingController();
  bool _damage = false;

  @override
  void dispose() {
    _notes.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => BillingSheetFrame(
        title: 'Mark as used',
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          SwitchListTile(contentPadding: EdgeInsets.zero, value: _damage, onChanged: (v) => setState(() => _damage = v), title: const Text('Something was damaged')),
          if (_damage)
            TextField(controller: _notes, minLines: 2, maxLines: 4, decoration: const InputDecoration(labelText: 'What was damaged *', alignLabelWithHint: true)),
          const SizedBox(height: 14),
          FilledButton(
            onPressed: () {
              if (_damage && _notes.text.trim().isEmpty) {
                AppToast.warning(context, 'Say what was damaged');
                return;
              }
              Navigator.of(context).pop((_damage, _notes.text.trim()));
            },
            child: const Text('Mark as used'),
          ),
        ]),
      );
}

/// Used by screens that show the signed-in user's role.
bool canManageBookings(WidgetRef ref) {
  final u = ref.read(currentUserProvider);
  return u != null && (u.isAdminOrCommittee || u.isManager);
}
