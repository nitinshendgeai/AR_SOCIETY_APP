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

/// FMC Manager (or Admin/Committee) records a resident's online payment:
/// select Wing → Flat, upload the transaction screenshot, and capture the
/// payment details for later bank reconciliation.
class OnlinePaymentSubmitScreen extends ConsumerStatefulWidget {
  const OnlinePaymentSubmitScreen({super.key});

  @override
  ConsumerState<OnlinePaymentSubmitScreen> createState() => _OnlinePaymentSubmitScreenState();
}

class _OnlinePaymentSubmitScreenState extends ConsumerState<OnlinePaymentSubmitScreen> {
  final _amountCtrl = TextEditingController();
  final _refCtrl = TextEditingController();
  final _bankCtrl = TextEditingController();
  final _notesCtrl = TextEditingController();

  String? _wingId;
  String? _flatId;
  String _paymentMode = kPaymentModes.first.$1;
  DateTime _paymentDate = DateTime.now();

  XFile? _pickedFile;
  Uint8List? _pickedBytes;
  bool _saving = false;

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

    if (societyId == null || _flatId == null || amount == null || amount <= 0 || _pickedBytes == null) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
        content: Text('Select a Wing, Flat, valid amount, and a payment screenshot'),
        backgroundColor: AppTheme.error,
      ));
      return;
    }

    setState(() => _saving = true);
    try {
      final mimeType = _pickedFile!.mimeType ?? 'image/jpeg';
      final entity = await ref.read(onlinePaymentsProvider(societyId).notifier).submit(
            flatId: _flatId!,
            amount: amount,
            paymentDate: _paymentDate,
            paymentMode: _paymentMode,
            transactionRef: _refCtrl.text.trim().isEmpty ? null : _refCtrl.text.trim(),
            bankName: _bankCtrl.text.trim().isEmpty ? null : _bankCtrl.text.trim(),
            notes: _notesCtrl.text.trim().isEmpty ? null : _notesCtrl.text.trim(),
            screenshotBytes: _pickedBytes!,
            screenshotFileName: _pickedFile!.name,
            screenshotMimeType: mimeType,
          );
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text('Recorded — receipt ${entity.receiptNumber}'),
          backgroundColor: AppTheme.success,
        ));
        Navigator.pop(context, entity);
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text(friendlyErrorMessage(e)), backgroundColor: AppTheme.error));
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final wingsAsync = ref.watch(wingsProvider);

    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(title: const Text('Record Online Payment')),
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
                  onChanged: (v) => setState(() => _flatId = v),
                ),
              );
            }),
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
          const Text('Payment Screenshot', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 14)),
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
