import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart' show apiDate, formatInr, formatAccountsDate;
import 'package:ar_society_app/features/accounts/presentation/providers/accounts_providers.dart' show vendorPaymentsProvider;
import 'package:ar_society_app/features/maintenance_billing/presentation/widgets/billing_sheet_frame.dart';
import 'package:ar_society_app/features/vendor/data/vendors_work_api.dart';
import 'package:ar_society_app/features/vendor/presentation/providers/vendor_providers.dart' show vendorsProvider;
import 'package:ar_society_app/features/vendor/presentation/providers/vendors_work_providers.dart';
import 'package:ar_society_app/features/vendor/presentation/widgets/procurement_widgets.dart' show DateField;
import 'package:ar_society_app/shared/widgets/app_widgets.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';

/// The Vendor Master form: the one place a vendor is entered or edited, from Vendors & Work and from every form that
/// asks who was paid. Closes with the saved vendor, so the caller can select it.
class VendorSheet extends ConsumerStatefulWidget {
  final String societyId;
  final VendorRecord? existing;
  const VendorSheet({super.key, required this.societyId, this.existing});

  @override
  ConsumerState<VendorSheet> createState() => _VendorSheetState();
}

class _VendorSheetState extends ConsumerState<VendorSheet> {
  final _form = GlobalKey<FormState>();
  late final VendorRecord? e = widget.existing;
  late final _name = TextEditingController(text: e?.companyName);
  late final _person = TextEditingController(text: e?.contactPerson);
  late final _mobile = TextEditingController(text: e?.mobile);
  late final _email = TextEditingController(text: e?.email);
  late final _address = TextEditingController(text: e?.address);
  late final _city = TextEditingController(text: e?.city);
  late final _pin = TextEditingController(text: e?.pincode);
  late final _gst = TextEditingController(text: e?.gstNumber);
  late final _pan = TextEditingController(text: e?.panNumber);
  late final _account = TextEditingController(text: e?.bankAccount);
  late final _bank = TextEditingController(text: e?.bankName);
  late final _ifsc = TextEditingController(text: e?.bankIfsc);
  late final _notes = TextEditingController(text: e?.notes);
  late final _lowerRate = TextEditingController(text: e?.tdsLowerRate);
  late final _lowerCert = TextEditingController(text: e?.tdsLowerCertNo);
  late DateTime? _lowerFrom = e?.tdsLowerValidFrom == null ? null : DateTime.tryParse(e!.tdsLowerValidFrom!);
  late DateTime? _lowerTo = e?.tdsLowerValidTo == null ? null : DateTime.tryParse(e!.tdsLowerValidTo!);
  late String _category = e?.category ?? 'other';
  late String _status = e?.status ?? 'active';
  late String? _constitution = e?.constitution;
  late String? _tdsSection = e?.tdsSection;
  bool _saving = false;

  List<TextEditingController> get _all =>
      [_name, _person, _mobile, _email, _address, _city, _pin, _gst, _pan, _account, _bank, _ifsc, _notes, _lowerRate, _lowerCert];

  @override
  void dispose() {
    for (final c in _all) {
      c.dispose();
    }
    super.dispose();
  }

  String? _t(TextEditingController c) => c.text.trim().isEmpty ? null : c.text.trim();

  Future<void> _save() async {
    if (!_form.currentState!.validate()) return;
    setState(() => _saving = true);
    final body = <String, dynamic>{
      'company_name': _name.text.trim(),
      'mobile': _mobile.text.trim(),
      'category': _category,
      'contact_person': _t(_person),
      'email': _t(_email),
      'address': _t(_address),
      'city': _t(_city),
      'gst_number': _t(_gst),
      'pan_number': _t(_pan),
      'bank_account': _t(_account),
      'bank_name': _t(_bank),
      'bank_ifsc': _t(_ifsc),
      'notes': _t(_notes),
      // What kind of vendor this is decides the TDS rate taken when it is paid; null clears it.
      'constitution': _constitution,
      'tds_section': _constitution == null ? null : _tdsSection,
      'tds_lower_rate': _constitution == null ? null : _t(_lowerRate),
      'tds_lower_cert_no': _constitution == null ? null : _t(_lowerCert),
      'tds_lower_valid_from': _constitution == null || _lowerFrom == null ? null : apiDate(_lowerFrom!),
      'tds_lower_valid_to': _constitution == null || _lowerTo == null ? null : apiDate(_lowerTo!),
    };
    final api = ref.read(vendorsWorkApiProvider);
    try {
      body['pincode'] = _t(_pin);
      final VendorRecord saved;
      if (e == null) {
        body.removeWhere((_, v) => v == null);
        saved = await api.createVendor({...body, 'society_id': widget.societyId});
      } else {
        saved = await api.updateVendor(e!.id, {...body, if (_status != e!.status) 'status': _status});
      }
      ref.invalidate(vendorRecordsProvider(widget.societyId));
      ref.invalidate(vendorsProvider(widget.societyId));
      if (mounted) {
        AppToast.success(context, e == null ? 'Vendor added' : 'Saved');
        Navigator.pop(context, saved);
      }
    } catch (err) {
      if (mounted) showErrorToast(context, err);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Widget _field(TextEditingController c, String label,
          {int max = 100, String? Function(String?)? validator, TextCapitalization caps = TextCapitalization.none,
          TextInputType? keyboard}) =>
      Padding(
        padding: const EdgeInsets.only(bottom: 12),
        child: FormFieldBox(label: label, child: TextFormField(
          controller: c,
          maxLength: max,
          textCapitalization: caps,
          keyboardType: keyboard,
          decoration: InputDecoration(counterText: ''),
          validator: validator,
        )),
      );

  Widget _section(String title, {bool first = false}) => Padding(
        padding: EdgeInsets.only(top: first ? 0 : 6, bottom: 10),
        child: Text(title,
            style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: AppTheme.primary)),
      );

  /// The vendor's type and TDS section. The rate we deduct when paying comes from these (and the PAN).
  Widget _tdsSectionUi() {
    final options = ref.watch(tdsOptionsProvider);
    return options.when(
      loading: () => const SizedBox.shrink(),
      error: (_, __) => const SizedBox.shrink(),
      data: (o) => Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        _section('TDS (tax deducted when you pay this vendor)'),
        FormFieldBox(
          label: 'Type of vendor',
          child: DropdownButtonFormField<String?>(
            key: const Key('vendor-constitution'),
            initialValue: _constitution,
            isExpanded: true,
            decoration: const InputDecoration(),
            items: [
              const DropdownMenuItem<String?>(value: null, child: Text('Not set: no TDS will be deducted')),
              for (final c in o.constitutions) DropdownMenuItem<String?>(value: c.$1, child: Text(c.$2)),
            ],
            onChanged: (v) => setState(() {
              _constitution = v;
              if (v != null) _tdsSection ??= o.categoryDefaultSection[_category];
            }),
          ),
        ),
        const SizedBox(height: 12),
        if (_constitution != null) ...[
          FormFieldBox(
            label: 'Usually paid under',
            child: DropdownButtonFormField<String?>(
              key: const Key('vendor-tds-section'),
              initialValue: _tdsSection,
              isExpanded: true,
              decoration: const InputDecoration(),
              items: [
                const DropdownMenuItem<String?>(value: null, child: Text('No TDS on this vendor')),
                for (final s in o.sections) DropdownMenuItem<String?>(value: s.$1, child: Text(s.$2, overflow: TextOverflow.ellipsis)),
              ],
              onChanged: (v) => setState(() => _tdsSection = v),
            ),
          ),
          const SizedBox(height: 8),
          const Text(
            'TDS is worked out when you record a payment, from this type, the section and the PAN above (no PAN means 20%). '
            'The PAN must match the type: P individual, H HUF, F firm or LLP, C company.',
            style: TextStyle(fontSize: 12, color: AppTheme.textSecondary),
          ),
          ExpansionTile(
            tilePadding: EdgeInsets.zero,
            title: const Text('Lower-deduction certificate (optional)', style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
            childrenPadding: const EdgeInsets.only(bottom: 8),
            children: [
              Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Expanded(child: _field(_lowerRate, 'Rate % (0 to 30)', max: 7, keyboard: const TextInputType.numberWithOptions(decimal: true))),
                const SizedBox(width: 12),
                Expanded(child: _field(_lowerCert, 'Certificate no.', max: 50)),
              ]),
              Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Expanded(child: FormFieldBox(label: 'Valid from', child: DateField(label: '', value: _lowerFrom, onChanged: (d) => setState(() => _lowerFrom = d)))),
                const SizedBox(width: 12),
                Expanded(child: FormFieldBox(label: 'Valid to', child: DateField(label: '', value: _lowerTo, onChanged: (d) => setState(() => _lowerTo = d)))),
              ]),
            ],
          ),
        ],
      ]),
    );
  }

  @override
  Widget build(BuildContext context) {
    const upper = TextCapitalization.characters;
    return BillingSheetFrame(
      title: e == null ? 'Add Vendor' : 'Edit ${e!.companyName}',
      child: Form(
        key: _form,
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          _section('Vendor', first: true),
          _field(_name, 'Company / name *', max: 255,
              validator: (v) => (v ?? '').trim().isEmpty ? 'Enter the name' : null),
          Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Expanded(
              child: FormFieldBox(label: 'Kind of work', required: true, child: DropdownButtonFormField<String>(
                initialValue: _category,
                isExpanded: true,
                decoration: const InputDecoration(),
                items: [for (final c in kVendorCategories) DropdownMenuItem(value: c.$1, child: Text(c.$2))],
                onChanged: (v) => setState(() => _category = v!),
              )),
            ),
            if (e != null) ...[
              const SizedBox(width: 12),
              Expanded(
                child: FormFieldBox(label: 'Status', child: DropdownButtonFormField<String>(
                  initialValue: _status,
                  isExpanded: true,
                  decoration: const InputDecoration(),
                  items: [
                    if (e!.status == 'blacklisted') const DropdownMenuItem(value: 'blacklisted', child: Text('Blacklisted')),
                    const DropdownMenuItem(value: 'active', child: Text('Active')),
                    const DropdownMenuItem(value: 'inactive', child: Text('Inactive')),
                    const DropdownMenuItem(value: 'under_review', child: Text('Under review')),
                  ],
                  onChanged: (v) => setState(() => _status = v!),
                )),
              ),
            ],
          ]),
          const SizedBox(height: 12),
          _section('Contact'),
          Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Expanded(child: _field(_person, 'Contact person', max: 255)),
            const SizedBox(width: 12),
            Expanded(
              child: _field(_mobile, 'Mobile *', max: 20, keyboard: TextInputType.phone,
                  validator: (v) =>
                      RegExp(r'^\+?[0-9 \-()]{7,20}$').hasMatch((v ?? '').trim()) ? null : 'Enter a valid phone number'),
            ),
          ]),
          _field(_email, 'Email', max: 255, keyboard: TextInputType.emailAddress),
          _section('Address'),
          _field(_address, 'Address', max: 1000),
          Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Expanded(child: _field(_city, 'City')),
            const SizedBox(width: 12),
            Expanded(
                child: _field(_pin, 'Pincode', max: 6, keyboard: TextInputType.number,
                    validator: (v) => (v ?? '').trim().isEmpty || RegExp(r'^\d{6}$').hasMatch(v!.trim())
                        ? null
                        : '6 digits')),
          ]),
          _section('Tax and bank'),
          Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Expanded(child: _field(_gst, 'GSTIN', max: 15, caps: upper)),
            const SizedBox(width: 12),
            Expanded(child: _field(_pan, 'PAN', max: 10, caps: upper)),
          ]),
          _field(_account, 'Bank account no.', max: 34),
          Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Expanded(child: _field(_bank, 'Bank')),
            const SizedBox(width: 12),
            Expanded(child: _field(_ifsc, 'IFSC', max: 11, caps: upper)),
          ]),
          _tdsSectionUi(),
          _field(_notes, 'Notes (anything to remember about this vendor)', max: 2000),
          if (e != null) _PaidToVendor(societyId: widget.societyId, vendorId: e!.id),
          ElevatedButton(
            onPressed: _saving ? null : _save,
            child: _saving
                ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))
                : Text(e == null ? 'Add Vendor' : 'Save'),
          ),
        ]),
      ),
    );
  }
}

/// What the society has paid this vendor straight from expenses and payments, newest first — so what the
/// Vendor Master holds and what the books show are the same story.
class _PaidToVendor extends ConsumerWidget {
  final String societyId;
  final String vendorId;
  const _PaidToVendor({required this.societyId, required this.vendorId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final paid = ref.watch(vendorPaymentsProvider((societyId, vendorId)));
    return paid.maybeWhen(
      data: (rows) {
        if (rows.isEmpty) return const SizedBox.shrink();
        final total = rows.fold<double>(0, (a, v) => a + v.amount);
        return Container(
          margin: const EdgeInsets.only(bottom: 12),
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
              color: AppTheme.surface, borderRadius: BorderRadius.circular(12), border: Border.all(color: AppTheme.border)),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              const Expanded(child: Text('Paid from expenses', style: TextStyle(fontWeight: FontWeight.w700))),
              Text(formatInr(total), style: const TextStyle(fontWeight: FontWeight.w700)),
            ]),
            const SizedBox(height: 6),
            for (final v in rows.take(5))
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 2),
                child: Row(children: [
                  Expanded(
                    child: Text('${v.voucherNumber} · ${formatAccountsDate(v.voucherDate)}',
                        style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary)),
                  ),
                  Text(formatInr(v.amount), style: const TextStyle(fontSize: 12.5)),
                ]),
              ),
            if (rows.length > 5)
              Text('and ${rows.length - 5} more in the Day Book',
                  style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
          ]),
        );
      },
      orElse: () => const SizedBox.shrink(),
    );
  }
}
