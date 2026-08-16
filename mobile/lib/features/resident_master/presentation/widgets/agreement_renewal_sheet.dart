import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/resident_master/data/models/resident_master_models.dart';
import 'package:ar_society_app/features/resident_master/presentation/providers/resident_master_providers.dart';
import 'package:ar_society_app/features/resident_master/presentation/widgets/resident_master_widgets.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// Agreement renewal — always CREATES a new AgreementTracker row linked via
/// renewal_of_id to the current one (backend: TenantService.renew_agreement /
/// OccupancyService.renew_agreement). This is never an in-place edit of the
/// existing agreement's dates — that would destroy history (Phase M1.3 §13,
/// M1.4 §16).
Future<void> showAgreementRenewalSheet(BuildContext context, WidgetRef ref, {required TenantModel tenant}) {
  return showModalBottomSheet(
    context: context,
    isScrollControlled: true,
    backgroundColor: Colors.transparent,
    builder: (ctx) => _RenewalSheetBody(tenant: tenant),
  );
}

class _RenewalSheetBody extends ConsumerStatefulWidget {
  final TenantModel tenant;
  const _RenewalSheetBody({required this.tenant});

  @override
  ConsumerState<_RenewalSheetBody> createState() => _RenewalSheetBodyState();
}

class _RenewalSheetBodyState extends ConsumerState<_RenewalSheetBody> {
  late DateTime _start;
  late DateTime _end;
  final _rentCtrl = TextEditingController();
  final _depositCtrl = TextEditingController();
  bool _submitting = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    final priorEnd = widget.tenant.agreementEndDate != null
        ? DateTime.tryParse(widget.tenant.agreementEndDate!)
        : null;
    _start = priorEnd ?? DateTime.now();
    _end = _start.add(const Duration(days: 365));
  }

  @override
  void dispose() {
    _rentCtrl.dispose();
    _depositCtrl.dispose();
    super.dispose();
  }

  String _dateStr(DateTime d) =>
      '${d.year}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

  Future<void> _pickDate({required bool isStart}) async {
    final picked = await showDatePicker(
      context: context,
      initialDate: isStart ? _start : _end,
      firstDate: DateTime(2000),
      lastDate: DateTime.now().add(const Duration(days: 365 * 5)),
    );
    if (picked == null) return;
    setState(() {
      if (isStart) {
        _start = picked;
      } else {
        _end = picked;
      }
    });
  }

  Future<void> _submit() async {
    if (!_end.isAfter(_start)) {
      setState(() => _error = 'End date must be after start date');
      return;
    }
    setState(() { _submitting = true; _error = null; });
    final data = <String, dynamic>{
      'start_date': _dateStr(_start),
      'end_date': _dateStr(_end),
      if (_rentCtrl.text.trim().isNotEmpty) 'monthly_rent': _rentCtrl.text.trim(),
      if (_depositCtrl.text.trim().isNotEmpty) 'security_deposit': _depositCtrl.text.trim(),
    };
    await ref.read(tenantFormProvider.notifier).renewAgreement(widget.tenant.id, data);
    if (!mounted) return;
    final state = ref.read(tenantFormProvider);
    if (state is AgreementRenewalSuccess) {
      ref.invalidate(tenantDetailProvider(widget.tenant.id));
      ref.invalidate(tenantAgreementsProvider(widget.tenant.id));
      ref.read(tenantFormProvider.notifier).reset();
      Navigator.of(context).pop();
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
        content: Text('Agreement renewed'), backgroundColor: AppTheme.success,
        behavior: SnackBarBehavior.floating,
      ));
    } else if (state is TenantFormError) {
      setState(() { _submitting = false; _error = rmFriendlyError(state.message); });
    } else {
      setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.of(context).viewInsets.bottom),
      child: Container(
        padding: const EdgeInsets.fromLTRB(20, 20, 20, 28),
        decoration: const BoxDecoration(
          color: AppTheme.cardBg,
          borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
        ),
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Center(
                child: Container(
                  width: 40, height: 4, margin: const EdgeInsets.only(bottom: 16),
                  decoration: BoxDecoration(color: AppTheme.border, borderRadius: BorderRadius.circular(2)),
                ),
              ),
              const Text('Renew Agreement',
                  style: TextStyle(fontSize: 17, fontWeight: FontWeight.w700, color: AppTheme.textPrimary)),
              const SizedBox(height: 4),
              const Text('Creates a new agreement record — the current one is preserved as history.',
                  style: TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
              const SizedBox(height: 16),
              Row(children: [
                Expanded(child: _DateField(label: 'New Start Date', date: _start, onTap: () => _pickDate(isStart: true))),
                const SizedBox(width: 12),
                Expanded(child: _DateField(label: 'New End Date', date: _end, onTap: () => _pickDate(isStart: false))),
              ]),
              const SizedBox(height: 14),
              TextField(
                controller: _rentCtrl,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                decoration: InputDecoration(
                  labelText: 'Monthly Rent',
                  hintText: widget.tenant.monthlyRent != null ? 'Carry over: ${widget.tenant.monthlyRent}' : 'Optional',
                ),
              ),
              const SizedBox(height: 14),
              TextField(
                controller: _depositCtrl,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                decoration: InputDecoration(
                  labelText: 'Security Deposit',
                  hintText: widget.tenant.securityDeposit != null ? 'Carry over: ${widget.tenant.securityDeposit}' : 'Optional',
                ),
              ),
              if (_error != null) ...[
                const SizedBox(height: 12),
                AppErrorBanner(message: _error!),
              ],
              const SizedBox(height: 20),
              AppPrimaryButton(label: 'Renew Agreement', isLoading: _submitting, onPressed: _submit),
            ],
          ),
        ),
      ),
    );
  }
}

class _DateField extends StatelessWidget {
  final String label;
  final DateTime date;
  final VoidCallback onTap;
  const _DateField({required this.label, required this.date, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: AppTheme.textSecondary)),
        const SizedBox(height: 6),
        InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(12),
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 14),
            decoration: BoxDecoration(
              color: AppTheme.surface, borderRadius: BorderRadius.circular(12),
              border: Border.all(color: AppTheme.border),
            ),
            child: Row(children: [
              const Icon(Icons.calendar_today_rounded, size: 16, color: AppTheme.primary),
              const SizedBox(width: 8),
              Text('${date.day}/${date.month}/${date.year}', style: const TextStyle(fontSize: 13)),
            ]),
          ),
        ),
      ],
    );
  }
}
