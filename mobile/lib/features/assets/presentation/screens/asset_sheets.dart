import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/assets/data/assets_api.dart';
import 'package:ar_society_app/features/assets/presentation/providers/assets_providers.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/widgets/billing_sheet_frame.dart';
import 'package:ar_society_app/features/vendor/presentation/widgets/procurement_widgets.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';

DateTime _day(DateTime d) => DateTime(d.year, d.month, d.day);
String? _trimmed(TextEditingController c) => c.text.trim().isEmpty ? null : c.text.trim();

/// The months an interval adds to a date (month ends are respected: 31 Jan + 1 month = 28/29 Feb).
DateTime addMonths(DateTime d, int months) {
  final m = d.month - 1 + months;
  final year = d.year + m ~/ 12, month = m % 12 + 1;
  final last = DateTime(year, month + 1, 0).day;
  return DateTime(year, month, d.day > last ? last : d.day);
}

// ── Add / edit an asset ──────────────────────────────────────────────────────

/// Register a new asset, or change one. Only what the committee knows needs filling in: a name and
/// a category are enough; the rest can be added later.
class AssetFormSheet extends ConsumerStatefulWidget {
  final Asset? asset;
  const AssetFormSheet({super.key, this.asset});

  @override
  ConsumerState<AssetFormSheet> createState() => _AssetFormSheetState();
}

class _AssetFormSheetState extends ConsumerState<AssetFormSheet> {
  final _form = GlobalKey<FormState>();
  late final _name = TextEditingController(text: a?.name);
  late final _location = TextEditingController(text: a?.location);
  late final _model = TextEditingController(text: a?.modelNumber);
  late final _serial = TextEditingController(text: a?.serialNumber);
  late final _cost = TextEditingController(text: a?.purchaseCost?.toString());
  late final _vendor = TextEditingController(text: a?.vendorName);
  late final _vendorContact = TextEditingController(text: a?.vendorContact);
  late final _invoice = TextEditingController(text: a?.invoiceNumber);
  late final _interval = TextEditingController(text: a?.serviceIntervalMonths?.toString());
  late final _life = TextEditingController(text: a?.expectedLifeYears?.toString());
  late final _notes = TextEditingController(text: a?.description);
  late String? _category = a?.category;
  late DateTime? _purchased = a?.purchaseDate;
  late DateTime? _warranty = a?.warrantyExpiry;
  late DateTime? _lastServiced = a?.lastServicedOn;
  late DateTime? _nextDue = a?.nextServiceDue;
  bool _saving = false;

  Asset? get a => widget.asset;

  @override
  void dispose() {
    for (final c in [_name, _location, _model, _serial, _cost, _vendor, _vendorContact, _invoice, _interval, _life, _notes]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _save() async {
    if (!_form.currentState!.validate()) return;
    setState(() => _saving = true);
    try {
      final api = ref.read(assetsApiProvider);
      final interval = int.tryParse(_interval.text.trim());
      final body = <String, dynamic>{
        'name': _name.text.trim(),
        'asset_category': _category!,
        'location': _trimmed(_location),
        'model_number': _trimmed(_model),
        'serial_number': _trimmed(_serial),
        'purchase_date': _purchased == null ? null : apiDateOnly(_purchased!),
        'purchase_cost': parseMoney(_cost.text),
        'vendor_name': _trimmed(_vendor),
        'vendor_contact': _trimmed(_vendorContact),
        'invoice_number': _trimmed(_invoice),
        'warranty_expiry': _warranty == null ? null : apiDateOnly(_warranty!),
        'service_interval_months': interval,
        'last_serviced_on': _lastServiced == null ? null : apiDateOnly(_lastServiced!),
        'expected_life_years': int.tryParse(_life.text.trim()),
        'description': _trimmed(_notes),
      };
      // A date typed in is kept; otherwise the server works it out from the interval.
      if (_nextDue != null) body['next_service_due'] = apiDateOnly(_nextDue!);
      final Asset saved;
      if (a == null) {
        body.removeWhere((_, v) => v == null);
        saved = await api.create(body);
      } else {
        saved = await api.update(a!.id, body);
      }
      invalidateAssets(ref);
      if (!mounted) return;
      AppToast.success(context, a == null ? '${saved.name} added as ${saved.assetCode}' : 'Changes saved');
      Navigator.of(context).pop(saved);
    } catch (e) {
      if (mounted) {
        setState(() => _saving = false);
        showErrorToast(context, e);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final editing = a != null;
    final interval = int.tryParse(_interval.text.trim());
    final base = _lastServiced ?? _purchased;
    final hint = _nextDue == null && interval != null && base != null
        ? 'First service due ${formatDay(addMonths(base, interval))}'
        : null;
    return BillingSheetFrame(
      title: editing ? 'Edit ${a!.name}' : 'Add an asset',
      child: Form(
        key: _form,
        autovalidateMode: AutovalidateMode.onUserInteraction,
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          FormFieldBox(label: 'Name', required: true, child: TextFormField(
            controller: _name,
            maxLength: 255,
            textCapitalization: TextCapitalization.words,
            decoration: const InputDecoration(
                hintText: 'e.g. Terrace water pump, Clubhouse AC 1', counterText: ''),
            validator: (v) => (v ?? '').trim().isEmpty ? 'Give the asset a name' : null,
          )),
          const SizedBox(height: 12),
          FormFieldBox(label: 'Kind of asset', required: true, child: DropdownButtonFormField<String>(
            initialValue: _category,
            isExpanded: true,
            decoration: const InputDecoration(),
            validator: (v) => v == null ? 'Choose what kind of asset it is' : null,
            items: [
              for (final c in kAssetCategories)
                DropdownMenuItem(value: c.$1, child: Row(children: [
                  Icon(c.$3, size: 18, color: AppTheme.textSecondary),
                  const SizedBox(width: 10),
                  Flexible(child: Text(c.$2, overflow: TextOverflow.ellipsis)),
                ])),
            ],
            onChanged: (v) => setState(() => _category = v),
          )),
          const SizedBox(height: 12),
          FormFieldBox(label: 'Where it is', child: TextFormField(
            controller: _location,
            maxLength: 255,
            decoration: const InputDecoration(
                hintText: 'e.g. Terrace, Wing A · Basement pump room', counterText: ''),
          )),
          const SizedBox(height: 16),
          const Text('Servicing', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 13)),
          const SizedBox(height: 8),
          FormFieldBox(label: 'Serviced every (months)', child: TextFormField(
            controller: _interval,
            keyboardType: TextInputType.number,
            inputFormatters: [FilteringTextInputFormatter.digitsOnly, LengthLimitingTextInputFormatter(3)],
            decoration: InputDecoration(
              helperText: hint ?? 'e.g. 3 for an AC, 6 for a pump. Leave blank if it has no routine service.',
              helperMaxLines: 2,
            ),
            validator: (v) {
              final n = int.tryParse((v ?? '').trim());
              return (v ?? '').trim().isNotEmpty && (n == null || n < 1 || n > 120) ? 'Enter 1 to 120 months' : null;
            },
            onChanged: (_) => setState(() {}),
          )),
          const SizedBox(height: 12),
          Row(children: [
            Expanded(
              child: FormFieldBox(label: 'Last serviced', child: DateField(
                  label: '',value: _lastServiced, lastDate: DateTime.now(),
                  onChanged: (d) => setState(() => _lastServiced = d))),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: FormFieldBox(label: 'Next service due', child: DateField(
                  label: '',value: _nextDue, onChanged: (d) => setState(() => _nextDue = d))),
            ),
          ]),
          const SizedBox(height: 16),
          const Text('Purchase and warranty', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 13)),
          const SizedBox(height: 8),
          Row(children: [
            Expanded(
              child: FormFieldBox(label: 'Bought on', child: DateField(
                  label: '',value: _purchased, lastDate: DateTime.now(),
                  onChanged: (d) => setState(() => _purchased = d))),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: FormFieldBox(label: 'Warranty until', child: DateField(
                  label: '',value: _warranty, onChanged: (d) => setState(() => _warranty = d))),
            ),
          ]),
          const SizedBox(height: 12),
          FormFieldBox(label: 'Cost (₹)', child: TextFormField(
            controller: _cost,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            inputFormatters: moneyInput,
            decoration: const InputDecoration(prefixText: '₹ '),
          )),
          const SizedBox(height: 12),
          FormFieldBox(label: 'Bought from / serviced by', child: TextFormField(
            controller: _vendor,
            maxLength: 255,
            decoration: const InputDecoration(counterText: ''),
          )),
          const SizedBox(height: 12),
          Row(children: [
            Expanded(
              child: FormFieldBox(label: 'Their phone', child: TextFormField(
                  controller: _vendorContact, maxLength: 100, keyboardType: TextInputType.phone,
                  decoration: const InputDecoration(counterText: ''))),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: FormFieldBox(label: "Supplier's invoice no.", child: TextFormField(
                  controller: _invoice, maxLength: 100,
                  decoration: const InputDecoration(counterText: ''))),
            ),
          ]),
          const SizedBox(height: 16),
          const Text('Identification', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 13)),
          const SizedBox(height: 8),
          Row(children: [
            Expanded(
              child: FormFieldBox(label: 'Make / model', child: TextFormField(
                  controller: _model, maxLength: 100,
                  decoration: const InputDecoration(counterText: ''))),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: FormFieldBox(label: 'Serial no.', child: TextFormField(
                  controller: _serial, maxLength: 100,
                  decoration: const InputDecoration(counterText: ''))),
            ),
          ]),
          const SizedBox(height: 12),
          FormFieldBox(label: 'Expected life (years)', child: TextFormField(
            controller: _life,
            keyboardType: TextInputType.number,
            inputFormatters: [FilteringTextInputFormatter.digitsOnly, LengthLimitingTextInputFormatter(3)],
            decoration: const InputDecoration(),
          )),
          const SizedBox(height: 12),
          FormFieldBox(label: 'Notes', child: TextFormField(
            controller: _notes,
            minLines: 2,
            maxLines: 5,
            decoration: const InputDecoration(),
          )),
          const SizedBox(height: 20),
          AppPrimaryButton(label: editing ? 'Save changes' : 'Add asset', isLoading: _saving, onPressed: _saving ? null : _save),
        ]),
      ),
    );
  }
}

String apiDateOnly(DateTime d) =>
    '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

const _months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
String formatDay(DateTime d) => '${d.day} ${_months[d.month - 1]} ${d.year}';

// ── Log or finish a service ──────────────────────────────────────────────────

/// Record a service that has been done: today's AC cleaning, the pump overhaul. With [service] given it
/// finishes a service that was scheduled earlier. The asset's "last serviced" and "next due" move on by
/// themselves (the date typed in, else its service interval).
class LogServiceSheet extends ConsumerStatefulWidget {
  final Asset asset;
  final AssetService? service;
  const LogServiceSheet({super.key, required this.asset, this.service});

  @override
  ConsumerState<LogServiceSheet> createState() => _LogServiceSheetState();
}

class _LogServiceSheetState extends ConsumerState<LogServiceSheet> {
  final _form = GlobalKey<FormState>();
  late String _type = widget.service?.type ?? 'preventive';
  late DateTime _doneOn = _day(DateTime.now());
  late final _vendor = TextEditingController(text: widget.service?.vendorName ?? widget.asset.vendorName);
  late final _cost = TextEditingController(text: widget.service?.cost?.toString());
  late final _findings = TextEditingController();
  DateTime? _nextDue;
  bool _saving = false;

  @override
  void dispose() {
    _vendor.dispose();
    _cost.dispose();
    _findings.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (!_form.currentState!.validate()) return;
    setState(() => _saving = true);
    try {
      final api = ref.read(assetsApiProvider);
      final cost = parseMoney(_cost.text);
      var id = widget.service?.id;
      id ??= (await api.scheduleService(widget.asset.id, type: _type, date: _doneOn, vendorName: _trimmed(_vendor))).id;
      await api.completeService(id,
          doneOn: _doneOn, cost: cost, findings: _trimmed(_findings), vendorName: _trimmed(_vendor), nextDue: _nextDue);
      invalidateAssets(ref);
      if (!mounted) return;
      Navigator.of(context).pop(
        (cost != null && cost > 0) ? LoggedService(cost, '${widget.asset.name} — ${maintenanceTypeLabel(_type).toLowerCase()}') : const LoggedService(0, ''),
      );
    } catch (e) {
      if (mounted) {
        setState(() => _saving = false);
        showErrorToast(context, e);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final interval = widget.asset.serviceIntervalMonths;
    final next = _nextDue ?? (interval == null ? null : addMonths(_doneOn, interval));
    return BillingSheetFrame(
      title: widget.service == null ? 'Log a service' : 'Finish this service',
      child: Form(
        key: _form,
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Text(widget.asset.name, style: const TextStyle(color: AppTheme.textSecondary)),
          const SizedBox(height: 12),
          if (widget.service == null) ...[
            FormFieldBox(label: 'What was done', required: true, child: DropdownButtonFormField<String>(
              initialValue: _type,
              decoration: const InputDecoration(),
              items: [for (final t in kMaintenanceTypes) DropdownMenuItem(value: t.$1, child: Text(t.$2))],
              onChanged: (v) => setState(() => _type = v!),
            )),
            const SizedBox(height: 12),
          ],
          FormFieldBox(label: 'Done on', child: DateField(
              label: '',value: _doneOn, required: true, lastDate: DateTime.now(),
              onChanged: (d) => setState(() => _doneOn = _day(d ?? DateTime.now())))),
          const SizedBox(height: 12),
          FormFieldBox(label: 'Done by (agency or person)', child: TextFormField(
            controller: _vendor,
            maxLength: 255,
            decoration: const InputDecoration(counterText: ''),
          )),
          const SizedBox(height: 12),
          FormFieldBox(label: 'Cost (₹)', child: TextFormField(
            controller: _cost,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            inputFormatters: moneyInput,
            decoration: const InputDecoration(prefixText: '₹ ', helperText: 'Leave blank if it was free (under AMC or warranty)'),
          )),
          const SizedBox(height: 12),
          FormFieldBox(label: 'What was found or done', child: TextFormField(
            controller: _findings,
            minLines: 2,
            maxLines: 5,
            decoration: const InputDecoration(hintText: 'e.g. Gas topped up, filters cleaned'),
          )),
          const SizedBox(height: 12),
          FormFieldBox(label: 'Next service due', child: DateField(
            label: '',value: _nextDue,
            onChanged: (d) => setState(() => _nextDue = d == null ? null : _day(d)),
          )),
          Padding(
            padding: const EdgeInsets.only(top: 6, left: 4),
            child: Text(
              _nextDue != null
                  ? 'Next service on ${formatDay(_nextDue!)}'
                  : next != null
                      ? 'Left blank, the next service is set for ${formatDay(next)} (every $interval months)'
                      : 'No next service will be set',
              style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary),
            ),
          ),
          const SizedBox(height: 20),
          AppPrimaryButton(label: 'Save service', isLoading: _saving, onPressed: _saving ? null : _save),
        ]),
      ),
    );
  }
}

/// What the Log service sheet hands back: the cost to offer as an expense (0 when none).
class LoggedService {
  final double cost;
  final String note;
  const LoggedService(this.cost, this.note);
}

// ── Schedule a service ───────────────────────────────────────────────────────

class ScheduleServiceSheet extends ConsumerStatefulWidget {
  final Asset asset;
  const ScheduleServiceSheet({super.key, required this.asset});

  @override
  ConsumerState<ScheduleServiceSheet> createState() => _ScheduleServiceSheetState();
}

class _ScheduleServiceSheetState extends ConsumerState<ScheduleServiceSheet> {
  final _form = GlobalKey<FormState>();
  String _type = 'preventive';
  late DateTime _date = _day(widget.asset.nextServiceDue ?? DateTime.now().add(const Duration(days: 7)));
  late final _vendor = TextEditingController(text: widget.asset.vendorName);
  final _what = TextEditingController();
  bool _saving = false;

  @override
  void dispose() {
    _vendor.dispose();
    _what.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (!_form.currentState!.validate()) return;
    setState(() => _saving = true);
    try {
      await ref.read(assetsApiProvider).scheduleService(
            widget.asset.id,
            type: _type,
            date: _date,
            vendorName: _trimmed(_vendor),
            description: _trimmed(_what),
          );
      invalidateAssets(ref);
      if (!mounted) return;
      AppToast.success(context, 'Service planned for ${formatDay(_date)}');
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
        title: 'Plan a service',
        child: Form(
          key: _form,
          child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            Text(widget.asset.name, style: const TextStyle(color: AppTheme.textSecondary)),
            const SizedBox(height: 12),
            FormFieldBox(label: 'Kind of visit', required: true, child: DropdownButtonFormField<String>(
              initialValue: _type,
              decoration: const InputDecoration(),
              items: [for (final t in kMaintenanceTypes) DropdownMenuItem(value: t.$1, child: Text(t.$2))],
              onChanged: (v) => setState(() => _type = v!),
            )),
            const SizedBox(height: 12),
            FormFieldBox(label: 'On', child: DateField(label: '',value: _date, required: true, onChanged: (d) => setState(() => _date = _day(d ?? _date)))),
            const SizedBox(height: 12),
            FormFieldBox(label: 'Who will do it', child: TextFormField(
              controller: _vendor,
              maxLength: 255,
              decoration: const InputDecoration(counterText: ''),
            )),
            const SizedBox(height: 12),
            FormFieldBox(label: 'What needs doing', child: TextFormField(
              controller: _what,
              minLines: 2,
              maxLines: 4,
              decoration: const InputDecoration(),
            )),
            const SizedBox(height: 20),
            AppPrimaryButton(label: 'Plan service', isLoading: _saving, onPressed: _saving ? null : _save),
          ]),
        ),
      );
}

// ── Annual maintenance contract ──────────────────────────────────────────────

class AmcSheet extends ConsumerStatefulWidget {
  final Asset asset;
  const AmcSheet({super.key, required this.asset});

  @override
  ConsumerState<AmcSheet> createState() => _AmcSheetState();
}

class _AmcSheetState extends ConsumerState<AmcSheet> {
  final _form = GlobalKey<FormState>();
  late final _vendor = TextEditingController(text: widget.asset.vendorName);
  final _number = TextEditingController();
  final _cost = TextEditingController();
  final _coverage = TextEditingController();
  late DateTime _start = _day(DateTime.now());
  late DateTime _end = addMonths(_day(DateTime.now()), 12).subtract(const Duration(days: 1));
  bool _comprehensive = false;
  bool _saving = false;

  @override
  void dispose() {
    for (final c in [_vendor, _number, _cost, _coverage]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _save() async {
    if (!_form.currentState!.validate()) return;
    if (!_end.isAfter(_start)) {
      AppToast.warning(context, 'The contract must end after it starts');
      return;
    }
    setState(() => _saving = true);
    try {
      await ref.read(assetsApiProvider).addAmc(
            widget.asset.id,
            vendorName: _vendor.text.trim(),
            start: _start,
            end: _end,
            contractNumber: _trimmed(_number),
            annualCost: parseMoney(_cost.text),
            coverage: _trimmed(_coverage),
            comprehensive: _comprehensive,
          );
      invalidateAssets(ref);
      if (!mounted) return;
      AppToast.success(context, 'Service contract added');
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
        title: 'Add a service contract',
        child: Form(
          key: _form,
          child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            Text(widget.asset.name, style: const TextStyle(color: AppTheme.textSecondary)),
            const SizedBox(height: 4),
            const Text(
              'For a contract covering just this asset. A yearly contract with sanction and visit schedule '
              'is kept under Vendors & Work.',
              style: TextStyle(fontSize: 12, color: AppTheme.textSecondary, height: 1.35),
            ),
            const SizedBox(height: 12),
            FormFieldBox(label: 'Agency', required: true, child: TextFormField(
              controller: _vendor,
              maxLength: 255,
              decoration: const InputDecoration(counterText: ''),
              validator: (v) => (v ?? '').trim().isEmpty ? 'Who holds the contract?' : null,
            )),
            const SizedBox(height: 12),
            FormFieldBox(label: 'Contract no.', child: TextFormField(
              controller: _number,
              maxLength: 100,
              decoration: const InputDecoration(counterText: ''),
            )),
            const SizedBox(height: 12),
            Row(children: [
              Expanded(child: FormFieldBox(label: 'From', child: DateField(label: '',value: _start, required: true, onChanged: (d) => setState(() => _start = _day(d ?? _start))))),
              const SizedBox(width: 12),
              Expanded(child: FormFieldBox(label: 'Until', child: DateField(label: '',value: _end, required: true, onChanged: (d) => setState(() => _end = _day(d ?? _end))))),
            ]),
            const SizedBox(height: 12),
            FormFieldBox(label: 'Yearly cost (₹)', child: TextFormField(
              controller: _cost,
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
              inputFormatters: moneyInput,
              decoration: const InputDecoration(prefixText: '₹ '),
            )),
            const SizedBox(height: 12),
            FormFieldBox(label: 'What is covered', child: TextFormField(
              controller: _coverage,
              minLines: 2,
              maxLines: 4,
              decoration: const InputDecoration(hintText: 'e.g. 4 visits a year, labour, gas top-up'),
            )),
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              value: _comprehensive,
              onChanged: (v) => setState(() => _comprehensive = v),
              title: const Text('Comprehensive (parts included)'),
            ),
            const SizedBox(height: 12),
            AppPrimaryButton(label: 'Add contract', isLoading: _saving, onPressed: _saving ? null : _save),
          ]),
        ),
      );
}
