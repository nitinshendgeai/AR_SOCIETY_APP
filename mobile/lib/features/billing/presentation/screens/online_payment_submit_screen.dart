import 'dart:typed_data';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/billing/data/payment_setoff_api.dart';
import 'package:ar_society_app/features/billing/domain/entities/billing_entities.dart';
import 'package:ar_society_app/features/billing/presentation/providers/billing_providers.dart';
import 'package:ar_society_app/features/society_structure/presentation/providers/structure_providers.dart';
import 'package:ar_society_app/shared/widgets/app_data_table.dart' show tableMoney;
import 'package:ar_society_app/shared/widgets/app_widgets.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';

/// FMC Manager (or Admin/Committee) records a resident's payment: select
/// Wing → Flat; the payment settles the flat's open bills oldest first
/// (shown as it will be applied), anything over is kept as an advance for
/// the next bill — or it goes against one chosen bill. Capture the payment
/// details, and optionally attach a screenshot — required only for the
/// online payment modes (UPI/bank transfer/NEFT/RTGS/online gateway).
/// A receipt is issued immediately either way; bank reconciliation for
/// non-cash payments happens later from the payment's detail screen.
class OnlinePaymentSubmitScreen extends ConsumerStatefulWidget {
  /// Opens pre-filled against one bill (from a maintenance bill's
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

enum _PaymentTarget { openBills, oneBill }

const _openStatuses = {'issued', 'partially_paid', 'overdue'};

class _OnlinePaymentSubmitScreenState extends ConsumerState<OnlinePaymentSubmitScreen> {
  final _amountCtrl = TextEditingController();
  final _refCtrl = TextEditingController();
  final _bankCtrl = TextEditingController();
  final _notesCtrl = TextEditingController();

  String? _wingId;
  String? _flatId;
  _PaymentTarget _target = _PaymentTarget.openBills;
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
      _target = _PaymentTarget.oneBill;
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
    if (_target == _PaymentTarget.oneBill && _billId == null) {
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
            billId: _target == _PaymentTarget.oneBill ? _billId : null,
            purpose: _purpose,
            transactionRef: _refCtrl.text.trim().isEmpty ? null : _refCtrl.text.trim(),
            bankName: _bankCtrl.text.trim().isEmpty ? null : _bankCtrl.text.trim(),
            notes: _notesCtrl.text.trim().isEmpty ? null : _notesCtrl.text.trim(),
            screenshotBytes: _pickedBytes,
            screenshotFileName: _pickedFile?.name,
            screenshotMimeType: _pickedFile?.mimeType ?? 'image/jpeg',
          );
      ref.invalidate(flatOutstandingBillsProvider(_flatId!));
      ref.invalidate(unappliedPaymentsProvider(societyId));
      if (mounted) {
        final bills = entity.liveSetOffs.length;
        AppToast.success(
            context,
            'Recorded — receipt ${entity.receiptNumber}'
            '${bills > 0 ? ', set off against $bills bill${bills == 1 ? '' : 's'}' : ''}'
            '${entity.unappliedAmount > 0 ? ', ${tableMoney(entity.unappliedAmount)} kept as advance' : ''}');
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
    final billsAsync = _flatId == null ? null : ref.watch(flatOutstandingBillsProvider(_flatId!));
    final openBills = (billsAsync?.valueOrNull ?? const <BillEntity>[])
        .where((b) => _openStatuses.contains(b.billStatus))
        .toList()
      ..sort((a, b) => a.dueDate.compareTo(b.dueDate));
    final amount = double.tryParse(_amountCtrl.text.trim()) ?? 0;
    final allAdvance = _target == _PaymentTarget.openBills && _flatId != null && billsAsync?.hasValue == true &&
        openBills.isEmpty;

    return AppPage(
      title: 'Record Payment',
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          const Text('Flat', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 14)),
          const SizedBox(height: 8),
          wingsAsync.when(
            loading: () => const AppLoader(),
            error: (e, _) => Text(friendlyErrorMessage(e), style: const TextStyle(color: AppTheme.error)),
            data: (wings) => FormFieldBox(label: 'Wing', required: true, child: DropdownButtonFormField<String>(
              value: _wingId,
              decoration: const InputDecoration(),
              items: [for (final w in wings) DropdownMenuItem(value: w.id, child: Text(w.name))],
              onChanged: (v) => setState(() {
                _wingId = v;
                _flatId = null;
                _billId = null;
              }),
            )),
          ),
          const SizedBox(height: 14),
          if (_wingId != null)
            Consumer(builder: (context, ref, _) {
              final flatsAsync = ref.watch(flatsByWingProvider(_wingId!));
              return flatsAsync.when(
                loading: () => const AppLoader(),
                error: (e, _) => Text(friendlyErrorMessage(e), style: const TextStyle(color: AppTheme.error)),
                data: (flats) => FormFieldBox(label: 'Flat', required: true, child: DropdownButtonFormField<String>(
                  value: _flatId,
                  decoration: const InputDecoration(),
                  items: [for (final f in flats) DropdownMenuItem(value: f.id, child: Text(f.flatNumber))],
                  onChanged: (v) => setState(() {
                    _flatId = v;
                    _billId = null;
                  }),
                )),
              );
            }),
          const SizedBox(height: 20),
          const Text('Applied Against', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 14)),
          const SizedBox(height: 8),
          SegmentedButton<_PaymentTarget>(
            segments: const [
              ButtonSegment(value: _PaymentTarget.openBills, label: Text('Open bills, oldest first')),
              ButtonSegment(value: _PaymentTarget.oneBill, label: Text('One bill')),
            ],
            selected: {_target},
            onSelectionChanged: (s) => setState(() {
              _target = s.first;
              if (_target == _PaymentTarget.openBills) _billId = null;
            }),
          ),
          const SizedBox(height: 14),
          if (_flatId == null)
            const Text('Select a flat first to see its outstanding bills',
                style: TextStyle(color: AppTheme.textSecondary, fontSize: 12))
          else if (billsAsync == null || billsAsync.isLoading)
            const AppLoader()
          else if (billsAsync.hasError)
            Text(friendlyErrorMessage(billsAsync.error!), style: const TextStyle(color: AppTheme.error))
          else if (_target == _PaymentTarget.openBills)
            _SetOffPreview(bills: openBills, amount: amount)
          else if (billsAsync.value!.isEmpty)
            const Text('No outstanding bills for this flat',
                style: TextStyle(color: AppTheme.textSecondary, fontSize: 12))
          else
            FormFieldBox(label: 'Bill', required: true, child: DropdownButtonFormField<String>(
              value: _billId,
              decoration: const InputDecoration(),
              items: [
                for (final b in billsAsync.value!)
                  DropdownMenuItem(
                    value: b.id,
                    child: Text('${b.invoiceNumber} — ₹${b.outstanding} due'),
                  ),
              ],
              onChanged: (v) => setState(() => _billId = v),
            )),
          const SizedBox(height: 20),
          const Text('Payment Details', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 14)),
          const SizedBox(height: 8),
          FormFieldBox(label: 'Amount (₹)', required: true, child: TextField(
            controller: _amountCtrl,
            onChanged: (_) => setState(() {}),
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            decoration: const InputDecoration(),
          )),
          const SizedBox(height: 14),
          InkWell(
            onTap: _pickDate,
            child: FormFieldBox(label: 'Payment Date *', child: InputDecorator(
              decoration: const InputDecoration(),
              child: Text('${_paymentDate.day}/${_paymentDate.month}/${_paymentDate.year}'),
            )),
          ),
          const SizedBox(height: 14),
          FormFieldBox(label: 'Payment Mode', required: true, child: DropdownButtonFormField<String>(
            value: _paymentMode,
            decoration: const InputDecoration(),
            items: [for (final m in kPaymentModes) DropdownMenuItem(value: m.$1, child: Text(m.$2))],
            onChanged: (v) => setState(() => _paymentMode = v ?? _paymentMode),
          )),
          if (allAdvance) ...[
            const SizedBox(height: 14),
            FormFieldBox(label: 'Advance On Account Of', required: true, child: DropdownButtonFormField<String>(
              value: _purpose,
              decoration: const InputDecoration(
                  hintText: 'What this payment is for'),
              items: [
                for (final p in kOnlinePaymentPurposes) DropdownMenuItem(value: p.$1, child: Text(p.$2))
              ],
              onChanged: (v) => setState(() => _purpose = v ?? _purpose),
            )),
          ],
          const SizedBox(height: 14),
          FormFieldBox(label: 'Transaction Ref / UTR', child: TextField(
            controller: _refCtrl,
            decoration: const InputDecoration(hintText: 'e.g. UPI reference number'),
          )),
          const SizedBox(height: 14),
          FormFieldBox(label: 'Bank Name (optional)', child: TextField(
            controller: _bankCtrl,
            decoration: const InputDecoration(),
          )),
          const SizedBox(height: 14),
          FormFieldBox(label: 'Notes (optional)', child: TextField(
            controller: _notesCtrl,
            maxLines: 2,
            decoration: const InputDecoration(),
          )),
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

/// How the amount will settle the flat's open bills, oldest first, and the
/// advance left over.
class _SetOffPreview extends StatelessWidget {
  final List<BillEntity> bills;
  final double amount;
  const _SetOffPreview({required this.bills, required this.amount});

  static String _rs(double v) => tableMoney(v);

  @override
  Widget build(BuildContext context) {
    if (bills.isEmpty) {
      return const Text(
          'No open bills for this flat. The payment is kept as an advance and set off against the next bill '
          'when it is issued.',
          style: TextStyle(color: AppTheme.textSecondary, fontSize: 12.5));
    }
    var left = amount;
    final rows = <Widget>[];
    for (final b in bills) {
      final due = double.tryParse(b.outstanding) ?? 0;
      final take = left <= 0 ? 0.0 : (left < due ? left : due);
      left -= take;
      rows.add(Padding(
        padding: const EdgeInsets.symmetric(vertical: 4),
        child: Row(children: [
          Icon(take >= due && due > 0 ? Icons.check_circle_rounded : Icons.radio_button_unchecked_rounded,
              size: 16, color: take > 0 ? AppTheme.success : AppTheme.textTertiary),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
                '${b.invoiceNumber} · due ${b.dueDate.day}/${b.dueDate.month}/${b.dueDate.year} · ${_rs(due)} due',
                style: const TextStyle(fontSize: 12.5)),
          ),
          Text(take > 0 ? _rs(take) : '—',
              style: TextStyle(
                  fontSize: 13, fontWeight: FontWeight.w600, color: take > 0 ? AppTheme.textPrimary : AppTheme.textTertiary)),
        ]),
      ));
    }
    return Container(
      padding: const EdgeInsets.fromLTRB(12, 10, 12, 10),
      decoration: BoxDecoration(color: AppTheme.cardBg, borderRadius: BorderRadius.circular(AppTheme.radiusM)),
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        const Text('Open bills — the payment settles them oldest first',
            style: TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
        const SizedBox(height: 4),
        ...rows,
        if (left > 0) ...[
          const Divider(height: 14),
          Row(children: [
            const Icon(Icons.savings_outlined, size: 16, color: AppTheme.primary),
            const SizedBox(width: 8),
            const Expanded(child: Text('Advance — for the next bill', style: TextStyle(fontSize: 12.5))),
            Text(_rs(left), style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
          ]),
        ],
      ]),
    );
  }
}
