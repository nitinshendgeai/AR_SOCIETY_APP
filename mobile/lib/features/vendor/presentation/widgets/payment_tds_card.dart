import 'package:flutter/material.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart' show formatInr;
import 'package:ar_society_app/features/vendor/data/vendors_work_api.dart';

/// Under the amount on the payment form: the TDS this payment will carry, worked out from the vendor's type and
/// section, and what the vendor actually receives. Shows nothing when there is nothing to say.
class PaymentTdsCard extends StatelessWidget {
  final PaymentTdsPreview? preview;
  final bool loading;
  const PaymentTdsCard({super.key, required this.preview, this.loading = false});

  @override
  Widget build(BuildContext context) {
    final p = preview;
    if (p == null) {
      return loading
          ? const Padding(
              padding: EdgeInsets.only(top: 10),
              child: Align(
                alignment: Alignment.centerLeft,
                child: SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2)),
              ),
            )
          : const SizedBox.shrink();
    }
    if (!p.applies) {
      if (p.note.isEmpty) return const SizedBox.shrink();
      return Padding(
        key: const Key('tds-note'),
        padding: const EdgeInsets.only(top: 10),
        child: Text(p.note, style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
      );
    }
    final tds = double.tryParse(p.tdsAmount) ?? 0;
    final net = double.tryParse(p.netPayable) ?? 0;
    return Container(
      key: const Key('tds-card'),
      margin: const EdgeInsets.only(top: 12),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppTheme.warning.withOpacity(0.10),
        borderRadius: BorderRadius.circular(AppTheme.radiusS),
        border: Border.all(color: AppTheme.warning.withOpacity(0.35)),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          const Expanded(child: Text('TDS to deduct', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 13))),
          Text(formatInr(tds), key: const Key('tds-amount'), style: const TextStyle(fontWeight: FontWeight.w700)),
        ]),
        const SizedBox(height: 2),
        Text(p.note, style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
        const Divider(height: 18),
        Row(children: [
          const Expanded(child: Text('Vendor receives', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 13))),
          Text(formatInr(net), key: const Key('tds-net'), style: const TextStyle(fontWeight: FontWeight.w700)),
        ]),
      ]),
    );
  }
}
