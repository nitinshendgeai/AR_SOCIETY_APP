import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/maintenance_billing/data/maintenance_billing_api.dart' show formatBillDate, formatRupees;
import 'package:ar_society_app/features/maintenance_billing/presentation/widgets/billing_sheet_frame.dart';
import 'package:ar_society_app/features/vendor/data/vendors_work_api.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';

final moneyInput = [FilteringTextInputFormatter.allow(RegExp(r'^\d{0,10}(\.\d{0,2})?'))];

double? parseMoney(String v) => double.tryParse(v.trim());

/// A tappable date field; [onChanged] gets null when cleared.
class DateField extends StatelessWidget {
  final String label;
  final DateTime? value;
  final ValueChanged<DateTime?> onChanged;
  final bool required;
  final DateTime? lastDate;
  const DateField(
      {super.key, required this.label, required this.value, required this.onChanged, this.required = false, this.lastDate});

  @override
  Widget build(BuildContext context) => FormField<DateTime>(
        initialValue: value,
        validator: (_) => required && value == null ? 'Choose the date' : null,
        builder: (state) => InkWell(
          onTap: () async {
            final d = await showDatePicker(
              context: context,
              initialDate: value ?? DateTime.now(),
              firstDate: DateTime(2000),
              lastDate: lastDate ?? DateTime(2100),
            );
            if (d != null) {
              onChanged(d);
              state.didChange(d);
            }
          },
          child: InputDecorator(
            decoration: InputDecoration(
              labelText: label.isEmpty ? null : (required ? '$label *' : label),
              errorText: state.errorText,
              suffixIcon: value != null && !required
                  ? IconButton(
                      icon: const Icon(Icons.close_rounded, size: 18),
                      onPressed: () {
                        onChanged(null);
                        state.didChange(null);
                      })
                  : const Icon(Icons.calendar_today_rounded, size: 18),
            ),
            child: Text(value == null ? '—' : formatBillDate(value!)),
          ),
        ),
      );
}

/// What the bye-laws ask for work of this amount, in plain words.
class RequirementsBanner extends StatelessWidget {
  final Requirements req;
  final String? amount;
  const RequirementsBanner(this.req, {super.key, this.amount});

  @override
  Widget build(BuildContext context) {
    final a = amount ?? req.amount;
    final total = double.tryParse(a ?? '');
    final tenders = total != null && total > (double.tryParse(req.tenderLimit) ?? 0);
    final gb = total != null && (tenders || total > (double.tryParse(req.committeeLimit) ?? 0));
    final lines = <String>[
      if (total == null)
        'The committee can sanction work up to ${formatRupees(req.committeeLimit)} itself; above '
            '${formatRupees(req.tenderLimit)} tenders are needed (bye-law 157).'
      else if (!gb)
        'Work of ${formatRupees(a!)} is within the committee\'s limit of ${formatRupees(req.committeeLimit)}: '
            'a committee resolution is enough.'
      else ...[
        if (tenders)
          'Work of ${formatRupees(a!)} is above the tender limit of ${formatRupees(req.tenderLimit)}: '
              'tenders from at least ${req.minQuotations} vendors, opened in a committee meeting.',
        'The general body must sanction it (above ${formatRupees(gb && !tenders ? req.committeeLimit : req.tenderLimit)}).',
      ],
    ];
    final color = gb ? AppTheme.warning : AppTheme.success;
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: color.withOpacity(0.08),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: color.withOpacity(0.35)),
      ),
      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Icon(gb ? Icons.how_to_vote_rounded : Icons.verified_rounded, color: color, size: 20),
        const SizedBox(width: 10),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            for (final l in lines) Text(l, style: const TextStyle(fontSize: 13, height: 1.35)),
          ]),
        ),
      ]),
    );
  }
}

/// Quotations received, lowest marked; removable while [onRemove] is given.
class QuotationsList extends StatelessWidget {
  final List<Quotation> quotations;
  final ValueChanged<Quotation>? onRemove;
  const QuotationsList({super.key, required this.quotations, this.onRemove});

  @override
  Widget build(BuildContext context) {
    if (quotations.isEmpty) {
      return const Padding(
        padding: EdgeInsets.symmetric(vertical: 12),
        child: Text('No quotations yet. Collect them from vendors and enter each one.',
            style: TextStyle(color: AppTheme.textSecondary)),
      );
    }
    return Column(children: [
      for (final q in quotations)
        ListTile(
          contentPadding: EdgeInsets.zero,
          leading: Icon(q.isSelected ? Icons.check_circle_rounded : Icons.description_outlined,
              color: q.isSelected ? AppTheme.success : AppTheme.textSecondary),
          title: Row(children: [
            Flexible(child: Text(q.vendorName, overflow: TextOverflow.ellipsis)),
            if (q.isLowest) ...[
              const SizedBox(width: 6),
              const _Tag('Lowest', AppTheme.success),
            ],
            if (q.isSelected) ...[
              const SizedBox(width: 6),
              const _Tag('Chosen', AppTheme.primary),
            ],
          ]),
          subtitle: Text([
            if (q.quotationRef != null) 'Ref ${q.quotationRef}',
            formatBillDate(q.quotationDate),
            if (q.validUntil != null) 'valid till ${formatBillDate(q.validUntil!)}',
            if (q.remarks != null) q.remarks!,
          ].join(' · ')),
          trailing: Row(mainAxisSize: MainAxisSize.min, children: [
            Text(formatRupees(q.totalAmount), style: const TextStyle(fontWeight: FontWeight.w600)),
            if (onRemove != null)
              IconButton(
                  tooltip: 'Remove', icon: const Icon(Icons.delete_outline_rounded), onPressed: () => onRemove!(q)),
          ]),
        ),
    ]);
  }
}

class _Tag extends StatelessWidget {
  final String text;
  final Color color;
  const _Tag(this.text, this.color);

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
        decoration: BoxDecoration(color: color.withOpacity(0.12), borderRadius: BorderRadius.circular(4)),
        child: Text(text, style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: color)),
      );
}

/// The recorded sanction: amount, by whom, resolutions.
class SanctionSummary extends StatelessWidget {
  final Sanction s;
  const SanctionSummary(this.s, {super.key});

  @override
  Widget build(BuildContext context) {
    String d(DateTime? v) => v == null ? '' : formatBillDate(v);
    final rows = <(String, String)>[
      ('Sanctioned', '${formatRupees(s.amount!)} by the ${s.byGeneralBody ? 'general body' : 'managing committee'}'),
      ('Committee resolution', '${s.committeeResolutionNo} of ${d(s.committeeMeetingDate)}'),
      if (s.tendersOpenedOn != null) ('Tenders opened', d(s.tendersOpenedOn)),
      if (s.gbResolutionNo != null) ('General body resolution', '${s.gbResolutionNo} of ${d(s.gbMeetingDate)}'),
      if (s.selectionReason != null) ('Why not the lowest', s.selectionReason!),
      ('No committee member interested', 'Declared${s.sanctionedByName != null ? ' · recorded by ${s.sanctionedByName}' : ''}'),
    ];
    return Column(children: [for (final r in rows) InfoLine(r.$1, r.$2)]);
  }
}

class InfoLine extends StatelessWidget {
  final String label;
  final String value;
  const InfoLine(this.label, this.value, {super.key});

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 4),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          SizedBox(
              width: MediaQuery.sizeOf(context).width < 500 ? 120 : 170,
              child: Text(label, style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary))),
          Expanded(child: Text(value, style: const TextStyle(fontSize: 13.5))),
        ]),
      );
}

/// Enter a vendor's quotation.
class QuotationSheet extends StatefulWidget {
  final List<VendorRecord> vendors;
  final Set<String> alreadyQuoted;
  final Future<void> Function(QuotationInput) onSave;
  const QuotationSheet({super.key, required this.vendors, required this.alreadyQuoted, required this.onSave});

  @override
  State<QuotationSheet> createState() => _QuotationSheetState();
}

class _QuotationSheetState extends State<QuotationSheet> {
  final _form = GlobalKey<FormState>();
  final _ref = TextEditingController();
  final _amount = TextEditingController();
  final _gst = TextEditingController(text: '0');
  final _remarks = TextEditingController();
  String? _vendor;
  DateTime? _date = DateTime.now();
  DateTime? _valid;
  bool _saving = false;

  @override
  void dispose() {
    for (final c in [_ref, _amount, _gst, _remarks]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _save() async {
    if (!_form.currentState!.validate()) return;
    setState(() => _saving = true);
    try {
      await widget.onSave(QuotationInput(
        vendorId: _vendor!,
        ref: _ref.text.trim(),
        date: _date!,
        validUntil: _valid,
        amount: parseMoney(_amount.text)!,
        gst: parseMoney(_gst.text) ?? 0,
        remarks: _remarks.text.trim(),
      ));
      if (mounted) Navigator.pop(context);
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final choices = widget.vendors.where((v) => v.status != 'blacklisted' && !widget.alreadyQuoted.contains(v.id));
    final total = (parseMoney(_amount.text) ?? 0) + (parseMoney(_gst.text) ?? 0);
    return BillingSheetFrame(
      title: 'Add Quotation',
      child: Form(
        key: _form,
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          FormFieldBox(label: 'Vendor', required: true, child: DropdownButtonFormField<String>(
            initialValue: _vendor,
            isExpanded: true,
            decoration: const InputDecoration(),
            items: [
              for (final v in choices)
                DropdownMenuItem(value: v.id, child: Text('${v.companyName} · ${vendorCategoryLabel(v.category)}')),
            ],
            onChanged: (v) => setState(() => _vendor = v),
            validator: (v) => v == null ? 'Choose the vendor (add them under Vendors first)' : null,
          )),
          const SizedBox(height: 12),
          FormFieldBox(label: 'Quotation no. / reference', child: TextFormField(
            controller: _ref,
            maxLength: 50,
            decoration: const InputDecoration(counterText: ''),
          )),
          const SizedBox(height: 12),
          Row(children: [
            Expanded(
                child: FormFieldBox(label: 'Dated', child: DateField(
                    label: '',value: _date, required: true, lastDate: DateTime.now(),
                    onChanged: (d) => setState(() => _date = d)))),
            const SizedBox(width: 12),
            Expanded(child: FormFieldBox(label: 'Valid until', child: DateField(label: '',value: _valid, onChanged: (d) => setState(() => _valid = d)))),
          ]),
          const SizedBox(height: 12),
          Row(children: [
            Expanded(
              child: FormFieldBox(label: 'Amount (₹)', required: true, child: TextFormField(
                controller: _amount,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                inputFormatters: moneyInput,
                decoration: const InputDecoration(),
                onChanged: (_) => setState(() {}),
                validator: (v) => (parseMoney(v ?? '') ?? 0) <= 0 ? 'Enter the amount' : null,
              )),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: FormFieldBox(label: 'GST (₹)', child: TextFormField(
                controller: _gst,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                inputFormatters: moneyInput,
                decoration: const InputDecoration(),
                onChanged: (_) => setState(() {}),
              )),
            ),
          ]),
          const SizedBox(height: 6),
          Text('Total ${formatRupees(total.toStringAsFixed(2))}', style: const TextStyle(fontWeight: FontWeight.w600)),
          const SizedBox(height: 12),
          FormFieldBox(label: 'Remarks', child: TextFormField(
            controller: _remarks,
            maxLength: 2000,
            maxLines: 2,
            decoration: const InputDecoration(hintText: 'e.g. make, warranty, exclusions'),
          )),
          const SizedBox(height: 12),
          ElevatedButton(
            onPressed: _saving ? null : _save,
            child: _saving
                ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))
                : const Text('Save Quotation'),
          ),
        ]),
      ),
    );
  }
}

/// Record the committee's (and general body's) decision to award the work.
class SanctionSheet extends StatefulWidget {
  final String what;
  final List<Quotation> quotations;
  final Requirements requirements;
  final Future<void> Function(SanctionInput) onSave;
  const SanctionSheet(
      {super.key, required this.what, required this.quotations, required this.requirements, required this.onSave});

  @override
  State<SanctionSheet> createState() => _SanctionSheetState();
}

class _SanctionSheetState extends State<SanctionSheet> {
  final _form = GlobalKey<FormState>();
  final _resolution = TextEditingController();
  final _gbResolution = TextEditingController();
  final _reason = TextEditingController();
  late String? _chosen = widget.quotations.where((q) => q.isLowest).map((q) => q.id).firstOrNull;
  DateTime? _meeting;
  DateTime? _gbMeeting;
  DateTime? _opened;
  bool _declared = false;
  bool _saving = false;

  @override
  void dispose() {
    _resolution.dispose();
    _gbResolution.dispose();
    _reason.dispose();
    super.dispose();
  }

  Quotation? get _q => widget.quotations.where((q) => q.id == _chosen).firstOrNull;

  Future<void> _save(bool tenders, bool gb) async {
    if (!_form.currentState!.validate()) return;
    if (!_declared) {
      AppToast.error(context, 'Tick the declaration that no committee member has an interest in this work');
      return;
    }
    setState(() => _saving = true);
    try {
      await widget.onSave(SanctionInput(
        quotationId: _chosen!,
        committeeResolutionNo: _resolution.text.trim(),
        committeeMeetingDate: _meeting!,
        gbResolutionNo: gb ? _gbResolution.text.trim() : null,
        gbMeetingDate: gb ? _gbMeeting : null,
        tendersOpenedOn: tenders ? _opened : null,
        selectionReason: _reason.text.trim(),
        noInterestDeclared: _declared,
      ));
      if (mounted) Navigator.pop(context);
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final q = _q;
    final req = widget.requirements;
    final total = double.tryParse(q?.totalAmount ?? '') ?? 0;
    final tenders = total > (double.tryParse(req.tenderLimit) ?? 0);
    final gb = tenders || total > (double.tryParse(req.committeeLimit) ?? 0);
    final notLowest = q != null && !q.isLowest;
    final today = DateTime.now();
    return BillingSheetFrame(
      title: 'Sanction ${widget.what}',
      child: Form(
        key: _form,
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          if (q != null) RequirementsBanner(req, amount: q.totalAmount),
          const SizedBox(height: 12),
          const Text('Quotation accepted', style: TextStyle(fontWeight: FontWeight.w600)),
          RadioGroup<String>(
            groupValue: _chosen,
            onChanged: (v) => setState(() => _chosen = v),
            child: Column(children: [
              for (final x in widget.quotations)
                RadioListTile<String>(
                  contentPadding: EdgeInsets.zero,
                  value: x.id,
                  title: Text('${x.vendorName} · ${formatRupees(x.totalAmount)}'),
                  subtitle: x.isLowest ? const Text('Lowest') : null,
                ),
            ]),
          ),
          if (notLowest) ...[
            FormFieldBox(label: 'Why not the lowest quotation?', required: true, child: TextFormField(
              controller: _reason,
              maxLength: 1000,
              maxLines: 2,
              decoration: const InputDecoration(),
              validator: (v) => (v ?? '').trim().isEmpty ? 'Record the reason' : null,
            )),
            const SizedBox(height: 8),
          ],
          FormFieldBox(label: 'Committee resolution no.', required: true, child: TextFormField(
            controller: _resolution,
            maxLength: 50,
            decoration: const InputDecoration(counterText: ''),
            validator: (v) => (v ?? '').trim().isEmpty ? 'Enter the resolution number' : null,
          )),
          const SizedBox(height: 12),
          FormFieldBox(label: 'Committee meeting date', child: DateField(
              label: '',value: _meeting, required: true, lastDate: today,
              onChanged: (d) => setState(() => _meeting = d))),
          if (tenders) ...[
            const SizedBox(height: 12),
            FormFieldBox(label: 'Tenders opened on (committee meeting)', child: DateField(
                label: '',value: _opened, required: true, lastDate: today,
                onChanged: (d) => setState(() => _opened = d))),
          ],
          if (gb) ...[
            const SizedBox(height: 12),
            FormFieldBox(label: 'General body resolution no.', required: true, child: TextFormField(
              controller: _gbResolution,
              maxLength: 50,
              decoration: const InputDecoration(counterText: ''),
              validator: (v) => (v ?? '').trim().isEmpty ? 'The general body must sanction this work' : null,
            )),
            const SizedBox(height: 12),
            FormFieldBox(label: 'General body meeting date', child: DateField(
                label: '',value: _gbMeeting, required: true, lastDate: today,
                onChanged: (d) => setState(() => _gbMeeting = d))),
          ],
          const SizedBox(height: 8),
          CheckboxListTile(
            contentPadding: EdgeInsets.zero,
            controlAffinity: ListTileControlAffinity.leading,
            value: _declared,
            onChanged: (v) => setState(() => _declared = v ?? false),
            title: const Text('No member of the managing committee, or their relative, has any interest in this '
                'vendor or this work.'),
            subtitle: const Text('A committee member with an interest in a society contract is disqualified.'),
          ),
          const SizedBox(height: 12),
          ElevatedButton(
            onPressed: _saving || _chosen == null ? null : () => _save(tenders, gb),
            child: _saving
                ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))
                : const Text('Record Sanction'),
          ),
        ]),
      ),
    );
  }
}

/// A one-field reason dialog; null when dismissed.
Future<String?> askReason(BuildContext context, {required String title, required String message, required String action}) async {
  final c = TextEditingController();
  final form = GlobalKey<FormState>();
  final ok = await showDialog<bool>(
    context: context,
    builder: (ctx) => AlertDialog(
      title: Text(title),
      content: Form(
        key: form,
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(message),
          const SizedBox(height: 12),
          FormFieldBox(label: 'Reason', required: true, child: TextFormField(
            controller: c,
            maxLength: 1000,
            maxLines: 2,
            decoration: const InputDecoration(),
            validator: (v) => (v ?? '').trim().isEmpty ? 'Enter the reason' : null,
          )),
        ]),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Back')),
        TextButton(
          onPressed: () {
            if (form.currentState!.validate()) Navigator.pop(ctx, true);
          },
          style: TextButton.styleFrom(foregroundColor: AppTheme.error),
          child: Text(action),
        ),
      ],
    ),
  );
  final text = c.text.trim();
  c.dispose();
  return ok == true ? text : null;
}

String errorText(Object e) => friendlyErrorMessage(e);
