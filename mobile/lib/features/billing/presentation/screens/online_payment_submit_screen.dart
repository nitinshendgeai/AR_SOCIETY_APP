import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/billing/domain/entities/billing_entities.dart';
import 'package:ar_society_app/features/billing/presentation/providers/billing_providers.dart';
import 'package:ar_society_app/features/society_structure/presentation/providers/structure_providers.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// FMC Manager (or Admin/Committee) records a resident's payment: select
/// Wing → Flat, choose On Bill (applied immediately to an existing
/// outstanding bill) or On Account (no bill yet), capture the payment
/// details, and optionally attach a screenshot — required only for the
/// online payment modes (UPI/bank transfer/NEFT/RTGS/online gateway).
/// A receipt is issued immediately either way; bank reconciliation for
/// non-cash payments happens later from the payment's detail screen.
class OnlinePaymentSubmitScreen extends ConsumerStatefulWidget {
  /// Opens pre-filled "On Bill" for one bill (from a maintenance bill's
  /// Record Payment button); all null opens the blank form.
  final String? presetWingId;
  final String? presetFlatId;
  final String? presetBillId;
  final String? presetAmount;

  const OnlinePaymentSubmitScreen({
    super.key,
    this.presetWingId,
    this.presetFlatId,
    this.presetBillId,
    this.presetAmount,
  });

  @override
  ConsumerState<OnlinePaymentSubmitScreen> createState() => _OnlinePaymentSubmitScreenState();
}

enum _PaymentTarget { onAccount, onBill }

class _OnlinePaymentSubmitScreenState extends ConsumerState<OnlinePaymentSubmitScreen> {
  final _amountCtrl = TextEditingController();
  final _refCtrl = TextEditingController();
  final _bankCtrl = TextEditingController();
  final _notesCtrl = TextEditingController();

  String? _wingId;
  String? _flatId;
  _PaymentTarget _target = _PaymentTarget.onAccount;
  String? _billId;
  String _paymentMode = kPaymentModes.first.$1;
  String _purpose = kOnlinePaymentPurposes.first.$1;
  DateTime _paymentDate = DateTime.now();

  XFile? _pickedFile;
  Uint8List? _pickedBytes;
  bool _saving = false;

  bool get _screenshotRequired => kScreenshotRequiredModes.contains(_paymentMode);

  @override
  void initState() {
    super.initState();
    _wingId = widget.presetWingId;
    _flatId = widget.presetFlatId;
    if (widget.presetBillId != null) {
      _target = _PaymentTarget.onBill;
      _billId = widget.presetBillId;
    }
    if (widget.presetAmount != null) _amountCtrl.text = widget.presetAmount!;
  }

  @override
  void dispose() {
    _amountCtrl.dispose();
    _refCtrl.dispose();
    _bankCtrl.dispose();
    _notesCtrl.dispose();
    super.dispose();
  }

  Future<void> _pickScreenshot(ImageSource source) async {
    final picker = ImagePicker();
    final file = await picker.pickImage(source: source, imageQuality: 85);
    if (file == null) return;
    final bytes = await file.readAsBytes();
    setState(() {
      _pickedFile = file;
      _pickedBytes = bytes;
    });
  }

  Future<void> _pickDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _paymentDate,
      firstDate: DateTime.now().subtract(const Duration(days: 365)),
      lastDate: DateTime.now(),
    );
    if (picked != null) setState(() => _paymentDate = picked);
  }

  Future<void> _submit() async {
    final societyId = ref.read(currentUserProvider)?.societyId;
    final amount = double.tryParse(_amountCtrl.text.trim());

    if (societyId == null || _flatId == null || amount == null || amount <= 0) {
      AppToast.error(context, 'Select a Wing, Flat, and a valid amount');
      return;
    }
    if (_target == _PaymentTarget.onBill && _billId == null) {
      AppToast.error(context, 'Select which bill this payment is against');
      return;
    }
    if (_screenshotRequired && _pickedBytes == null) {
      AppToast.error(context, 'A payment screenshot is required for ${paymentModeLabel(_paymentMode)}');
      return;
    }

    setState(() => _saving = true);
    try {
      final entity = await ref.read(onlinePaymentsProvider(societyId).notifier).submit(
            flatId: _flatId!,
            amount: amount,
            paymentDate: _paymentDate,
            paymentMode: _paymentMode,
            billId: _target == _PaymentTarget.onBill ? _billId : null,
            purpose: _purpose,
            transactionRef: _refCtrl.text.trim().isEmpty ? null : _refCtrl.text.trim(),
            bankName: _bankCtrl.text.trim().isEmpty ? null : _bankCtrl.text.trim(),
            notes: _notesCtrl.text.trim().isEmpty ? null : _notesCtrl.text.trim(),
            screenshotBytes: _pickedBytes,
            screenshotFileName: _pickedFile?.name,
            screenshotMimeType: _pickedFile?.mimeType ?? 'image/jpeg',
          );
      if (mounted) {
        AppToast.success(context, 'Recorded — receipt ${entity.receiptNumber}');
        Navigator.pop(context, entity);
      }
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final wingsAsync = ref.watch(wingsProvider);

    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(title: const Text('Record Payment')),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          const Text('Flat', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 14)),
          const SizedBox(height: 8),
          wingsAsync.when(
            loading: () => const Center(child: CircularProgressIndicator()),
            error: (e, _) => Text(friendlyErrorMessage(e), style: const TextStyle(color: AppTheme.error)),
            data: (wings) => DropdownButtonFormField<String>(
              value: _wingId,
              decoration: const InputDecoration(labelText: 'Wing *'),
              items: [for (final w in wings) DropdownMenuItem(value: w.id, child: Text(w.name))],
              onChanged: (v) => setState(() {
                _wingId = v;
                _flatId = null;
                _billId = null;
              }),
            ),
          ),
          const SizedBox(height: 14),
          if (_wingId != null)
            Consumer(builder: (context, ref, _) {
              final flatsAsync = ref.watch(flatsByWingProvider(_wingId!));
              return flatsAsync.when(
                loading: () => const Center(child: CircularProgressIndicator()),
                error: (e, _) => Text(friendlyErrorMessage(e), style: const TextStyle(color: AppTheme.error)),
                data: (flats) => DropdownButtonFormField<String>(
                  value: _flatId,
                  decoration: const InputDecoration(labelText: 'Flat *'),
                  items: [for (final f in flats) DropdownMenuItem(value: f.id, child: Text(f.flatNumber))],
                  onChanged: (v) => setState(() {
                    _flatId = v;
                    _billId = null;
                  }),
                ),
              );
            }),
          const SizedBox(height: 20),
          const Text('Applied Against', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 14)),
          const SizedBox(height: 8),
          SegmentedButton<_PaymentTarget>(
            segments: const [
              ButtonSegment(value: _PaymentTarget.onAccount, label: Text('On Account')),
              ButtonSegment(value: _PaymentTarget.onBill, label: Text('On Bill')),
            ],
            selected: {_target},
            onSelectionChanged: (s) => setState(() {
              _target = s.first;
              if (_target == _PaymentTarget.onAccount) _billId = null;
            }),
          ),
          if (_target == _PaymentTarget.onBill) ...[
            const SizedBox(height: 14),
            if (_flatId == null)
              const Text('Select a flat first to see its outstanding bills',
                  style: TextStyle(color: AppTheme.textSecondary, fontSize: 12))
            else
              Consumer(builder: (context, ref, _) {
                final billsAsync = ref.watch(flatOutstandingBillsProvider(_flatId!));
                return billsAsync.when(
                  loading: () => const Center(child: CircularProgressIndicator()),
                  error: (e, _) => Text(friendlyErrorMessage(e), style: const TextStyle(color: AppTheme.error)),
                  data: (bills) => bills.isEmpty
                      ? const Text('No outstanding bills for this flat',
                          style: TextStyle(color: AppTheme.textSecondary, fontSize: 12))
                      : DropdownButtonFormField<String>(
                          value: _billId,
                          decoration: const InputDecoration(labelText: 'Bill *'),
                          items: [
                            for (final b in bills)
                              DropdownMenuItem(
                                value: b.id,
                                child: Text('${b.invoiceNumber} — ₹${b.outstanding} due'),
                              ),
                          ],
                          onChanged: (v) => setState(() => _billId = v),
                        ),
                );
              }),
          ],
          const SizedBox(height: 20),
          const Text('Payment Details', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 14)),
          const SizedBox(height: 8),
          TextField(
            controller: _amountCtrl,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            decoration: const InputDecoration(labelText: 'Amount (₹) *'),
          ),
          const SizedBox(height: 14),
          InkWell(
            onTap: _pickDate,
            child: InputDecorator(
              decoration: const InputDecoration(labelText: 'Payment Date *'),
              child: Text('${_paymentDate.day}/${_paymentDate.month}/${_paymentDate.year}'),
            ),
          ),
          const SizedBox(height: 14),
          DropdownButtonFormField<String>(
            value: _paymentMode,
            decoration: const InputDecoration(labelText: 'Payment Mode *'),
            items: [for (final m in kPaymentModes) DropdownMenuItem(value: m.$1, child: Text(m.$2))],
            onChanged: (v) => setState(() => _paymentMode = v ?? _paymentMode),
          ),
          if (_target == _PaymentTarget.onAccount) ...[
            const SizedBox(height: 14),
            DropdownButtonFormField<String>(
              value: _purpose,
              decoration: const InputDecoration(
                  labelText: 'On Account Of *', hintText: 'What this payment is for'),
              items: [
                for (final p in kOnlinePaymentPurposes) DropdownMenuItem(value: p.$1, child: Text(p.$2))
              ],
              onChanged: (v) => setState(() => _purpose = v ?? _purpose),
            ),
          ],
          const SizedBox(height: 14),
          TextField(
            controller: _refCtrl,
            decoration: const InputDecoration(labelText: 'Transaction Ref / UTR', hintText: 'e.g. UPI reference number'),
          ),
          const SizedBox(height: 14),
          TextField(
            controller: _bankCtrl,
            decoration: const InputDecoration(labelText: 'Bank Name (optional)'),
          ),
          const SizedBox(height: 14),
          TextField(
            controller: _notesCtrl,
            maxLines: 2,
            decoration: const InputDecoration(labelText: 'Notes (optional)'),
          ),
          const SizedBox(height: 20),
          Text(_screenshotRequired ? 'Payment Screenshot' : 'Payment Screenshot (optional)',
              style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 14)),
          const SizedBox(height: 8),
          if (_pickedBytes != null)
            ClipRRect(
              borderRadius: BorderRadius.circular(8),
              child: Image.memory(_pickedBytes!, height: 200, fit: BoxFit.cover),
            ),
          const SizedBox(height: 8),
          Row(children: [
            Expanded(
              child: OutlinedButton.icon(
                onPressed: () => _pickScreenshot(ImageSource.gallery),
                icon: const Icon(Icons.photo_library_outlined),
                label: const Text('Choose from Gallery'),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: OutlinedButton.icon(
                onPressed: () => _pickScreenshot(ImageSource.camera),
                icon: const Icon(Icons.camera_alt_outlined),
                label: const Text('Take Photo'),
              ),
            ),
          ]),
          const SizedBox(height: 24),
          ElevatedButton(
            onPressed: _saving ? null : _submit,
            child: _saving
                ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))
                : const Text('Save & Generate Receipt'),
          ),
        ],
      ),
    );
  }
}
