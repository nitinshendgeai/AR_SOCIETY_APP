import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/billing/domain/entities/billing_entities.dart' show kPaymentModes, kScreenshotRequiredModes;
import 'package:ar_society_app/features/maintenance_billing/data/maintenance_billing_api.dart';
import 'package:ar_society_app/features/maintenance_billing/data/payment_claims_api.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart' show AppToast, showErrorToast;

/// A resident tells the society office "I have paid": the amount, when, how, the UPI or bank reference and a screenshot.
/// Nothing is recorded until the office checks it against the bank, and the resident sees where it stands on My Bills.
class ClaimPaymentScreen extends ConsumerStatefulWidget {
  /// The bill being paid, when the resident came from one (amount and flat are filled in).
  final MaintenanceBill? bill;
  const ClaimPaymentScreen({super.key, this.bill});

  @override
  ConsumerState<ClaimPaymentScreen> createState() => _ClaimPaymentScreenState();
}

class _ClaimPaymentScreenState extends ConsumerState<ClaimPaymentScreen> {
  final _formKey = GlobalKey<FormState>();
  final _amount = TextEditingController();
  final _ref = TextEditingController();
  final _bank = TextEditingController();
  final _notes = TextEditingController();

  String _mode = 'upi';
  DateTime _date = DateTime.now();
  Uint8List? _shot;
  String? _shotName;
  bool _saving = false;

  /// What a resident can report: everything the office records except the payment-gateway one.
  static final _modes = [for (final m in kPaymentModes) if (m.$1 != 'online_gateway') m];

  bool get _needsProof => kScreenshotRequiredModes.contains(_mode);

  @override
  void initState() {
    super.initState();
    final b = widget.bill;
    if (b != null) _amount.text = amountOf(b.outstanding).toStringAsFixed(2);
  }

  @override
  void dispose() {
    _amount.dispose();
    _ref.dispose();
    _bank.dispose();
    _notes.dispose();
    super.dispose();
  }

  String _dateStr(DateTime d) => '${d.day.toString().padLeft(2, '0')}/${d.month.toString().padLeft(2, '0')}/${d.year}';

  Future<void> _pickShot(ImageSource source) async {
    final file = await ImagePicker().pickImage(source: source, imageQuality: 85);
    if (file == null) return;
    final bytes = await file.readAsBytes();
    setState(() {
      _shot = bytes;
      _shotName = file.name;
    });
  }

  Future<void> _pickDate() async {
    final now = DateTime.now();
    final picked = await showDatePicker(
      context: context,
      initialDate: _date,
      firstDate: now.subtract(const Duration(days: 365)),
      lastDate: now,
    );
    if (picked != null) setState(() => _date = picked);
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    if (_needsProof && _shot == null) {
      AppToast.error(context, 'Add a screenshot of the payment');
      return;
    }
    setState(() => _saving = true);
    try {
      await ref.read(paymentClaimsApiProvider).create(
            amount: double.parse(_amount.text.trim()),
            paymentDate: _date,
            paymentMode: _mode,
            flatId: widget.bill?.flatId,
            billId: widget.bill?.id,
            transactionRef: _mode == 'cash' ? null : _ref.text.trim(),
            bankName: _bank.text.trim(),
            notes: _notes.text.trim(),
            screenshotBytes: _shot,
            screenshotName: _shotName,
          );
      ref.invalidate(myPaymentClaimsProvider);
      if (!mounted) return;
      AppToast.success(context, 'Sent to the society office. You will see it confirmed here');
      Navigator.of(context).pop(true);
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final bill = widget.bill;
    return AppFormPage(
      title: 'I have paid',
      subtitle: bill == null ? 'Tell the society office about your payment' : 'Bill ${bill.invoiceNumber}',
      formKey: _formKey,
      submitLabel: 'Send to the office',
      submitIcon: Icons.send_rounded,
      saving: _saving,
      onSubmit: _saving ? null : _submit,
      children: [
        FormSection(
          title: bill == null ? 'Payment' : 'Payment for ${bill.invoiceNumber}',
          description: 'The office checks this against the bank, then your bill is marked paid and a receipt is issued.',
          children: [
            FormFieldBox(
              label: 'Amount paid',
              required: true,
              child: TextFormField(
                key: const Key('claim-amount'),
                controller: _amount,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                inputFormatters: [FilteringTextInputFormatter.allow(RegExp(r'^\d{0,9}(\.\d{0,2})?'))],
                decoration: const InputDecoration(prefixText: '₹ '),
                validator: (v) {
                  final n = double.tryParse((v ?? '').trim());
                  if (n == null || n <= 0) return 'Enter the amount you paid';
                  if (bill != null && n > amountOf(bill.outstanding)) {
                    return 'More than the ${formatRupees(bill.outstanding)} due on this bill';
                  }
                  return null;
                },
              ),
            ),
            FormFieldBox(
              label: 'Paid on',
              child: FormDateField(value: _date, hint: 'Date', format: _dateStr, onTap: _pickDate),
            ),
            FormFieldBox(
              label: 'How did you pay?',
              child: DropdownButtonFormField<String>(
                isExpanded: true,
                value: _mode,
                items: [for (final m in _modes) DropdownMenuItem(value: m.$1, child: Text(m.$2))],
                onChanged: (v) => setState(() => _mode = v ?? 'upi'),
              ),
            ),
            if (_mode != 'cash')
              FormFieldBox(
                label: _needsProof ? 'UPI / bank reference (UTR)' : 'Cheque number',
                required: _needsProof,
                child: TextFormField(
                  key: const Key('claim-ref'),
                  controller: _ref,
                  decoration: const InputDecoration(hintText: 'From your payment app or bank'),
                  validator: (v) => _needsProof && (v == null || v.trim().isEmpty) ? 'Enter the reference of the payment' : null,
                ),
              ),
            FormFieldBox(
              label: 'Your bank (optional)',
              child: TextFormField(controller: _bank),
            ),
            FormFieldBox(
              label: 'Note for the office (optional)',
              child: TextFormField(controller: _notes, maxLines: 2),
            ),
          ],
        ),
        FormSection(
          title: _needsProof ? 'Screenshot of the payment' : 'Screenshot (optional)',
          description: 'The success screen of your UPI or banking app.',
          children: [
            if (_shot != null)
              ClipRRect(
                borderRadius: BorderRadius.circular(8),
                child: Image.memory(_shot!, height: 220, fit: BoxFit.cover),
              ),
            Row(children: [
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: () => _pickShot(ImageSource.gallery),
                  icon: const Icon(Icons.photo_library_outlined),
                  label: const Text('Gallery'),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: () => _pickShot(ImageSource.camera),
                  icon: const Icon(Icons.photo_camera_outlined),
                  label: const Text('Camera'),
                ),
              ),
            ]),
            if (_shot != null)
              Align(
                alignment: Alignment.centerLeft,
                child: TextButton(
                  onPressed: () => setState(() {
                    _shot = null;
                    _shotName = null;
                  }),
                  child: const Text('Remove', style: TextStyle(color: AppTheme.error)),
                ),
              ),
          ],
        ),
      ],
    );
  }
}
