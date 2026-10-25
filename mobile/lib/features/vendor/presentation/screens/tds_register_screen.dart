import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart' show formatAccountsDate, formatInr;
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/vendor/data/vendor_master_api.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

DateTime _financialYearStart(DateTime d) => DateTime(d.month >= 4 ? d.year : d.year - 1, 4, 1);

/// The TDS deducted from vendor payments over a period, with the date each is due to be deposited with the government
/// (the 7th of the next month; 30 April for March) and the total, for the challan and the quarterly return. It opens on
/// the current financial year.
class TdsRegisterScreen extends ConsumerStatefulWidget {
  /// Today, so tests can fix the period.
  final DateTime? today;
  const TdsRegisterScreen({super.key, this.today});

  @override
  ConsumerState<TdsRegisterScreen> createState() => _TdsRegisterScreenState();
}

class _TdsRegisterScreenState extends ConsumerState<TdsRegisterScreen> {
  late final DateTime _today = widget.today ?? DateTime.now();
  late DateTimeRange _range = DateTimeRange(start: _financialYearStart(_today), end: _today);

  Future<void> _pick() async {
    final r = await showDateRangePicker(
      context: context,
      firstDate: DateTime(_today.year - 6),
      lastDate: DateTime(_today.year + 1, 3, 31),
      initialDateRange: _range,
    );
    if (r != null) setState(() => _range = r);
  }

  void _quarter(int fromMonth) {
    final fy = _financialYearStart(_today).year;
    final start = DateTime(fromMonth >= 4 ? fy : fy + 1, fromMonth, 1);
    final end = DateTime(start.year, start.month + 3, 0);
    setState(() => _range = DateTimeRange(start: start, end: end));
  }

  @override
  Widget build(BuildContext context) {
    final societyId = ref.watch(currentUserProvider)?.societyId;
    if (societyId == null) return const Scaffold(body: Center(child: Text('No society context')));
    final async = ref.watch(tdsRegisterProvider((societyId: societyId, from: _range.start, to: _range.end)));
    return AppPage(
      title: 'TDS Register',
      body: ResponsiveBody(
        maxWidth: 860,
        child: ListView(padding: const EdgeInsets.fromLTRB(16, 16, 16, 96), children: [
          const Text(
              'TDS deducted when vendors were paid, with the date each amount is due to be deposited. Use it for the '
              'challan and the quarterly return.',
              style: TextStyle(fontSize: 12.5, color: AppTheme.textSecondary, height: 1.35)),
          const SizedBox(height: 12),
          OutlinedButton.icon(
            key: const Key('tds-range'),
            onPressed: _pick,
            icon: const Icon(Icons.date_range_rounded, size: 18),
            label: Text('${formatAccountsDate(_range.start)} – ${formatAccountsDate(_range.end)}'),
          ),
          const SizedBox(height: 8),
          Wrap(spacing: 8, runSpacing: 4, children: [
            ActionChip(label: const Text('This financial year'), onPressed: () => setState(() => _range = DateTimeRange(start: _financialYearStart(_today), end: _today))),
            for (final (label, month) in const [('Apr–Jun', 4), ('Jul–Sep', 7), ('Oct–Dec', 10), ('Jan–Mar', 1)])
              ActionChip(key: Key('tds-q-$month'), label: Text(label), onPressed: () => _quarter(month)),
          ]),
          const SizedBox(height: 12),
          async.when(
            loading: () => const Padding(padding: EdgeInsets.all(32), child: AppLoader()),
            error: (e, _) => Text(friendlyErrorMessage(e), style: const TextStyle(color: AppTheme.error)),
            data: (reg) => reg.rows.isEmpty
                ? const Padding(padding: EdgeInsets.all(24), child: Center(child: Text('No TDS deducted in this period')))
                : Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                    Card(
                      color: AppTheme.primary.withValues(alpha: 0.06),
                      child: Padding(
                        padding: const EdgeInsets.all(14),
                        child: Row(children: [
                          Expanded(child: Text('${reg.rows.length} deduction${reg.rows.length == 1 ? '' : 's'}', style: const TextStyle(fontWeight: FontWeight.w600))),
                          Text('Total TDS ${formatInr(double.tryParse(reg.total) ?? 0)}',
                              key: const Key('tds-total'), style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
                        ]),
                      ),
                    ),
                    const SizedBox(height: 8),
                    for (final r in reg.rows) _RegisterTile(row: r),
                  ]),
          ),
        ]),
      ),
    );
  }
}

class _RegisterTile extends StatelessWidget {
  final TdsRegisterRow row;
  const _RegisterTile({required this.row});

  @override
  Widget build(BuildContext context) {
    final r = row;
    String inr(String v) => formatInr(double.tryParse(v) ?? 0);
    final rate = double.tryParse(r.rate) ?? 0;
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Expanded(child: Text(r.vendor, style: const TextStyle(fontWeight: FontWeight.w700))),
            Text(inr(r.tds), style: const TextStyle(fontWeight: FontWeight.w700)),
          ]),
          Text(
              [
                r.paymentNumber,
                formatAccountsDate(r.date),
                if (r.sectionLabel != null) r.sectionLabel!,
                '${rate == rate.roundToDouble() ? rate.toStringAsFixed(0) : rate}% of ${inr(r.base)}',
              ].join(' · '),
              style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary)),
          Text(
              [
                if ((r.pan ?? '').isNotEmpty) 'PAN ${r.pan}' else 'No PAN',
                if (r.constitution != null) r.constitution!,
                'Paid to vendor ${inr(r.netPaid)}',
              ].join(' · '),
              style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary)),
          if (r.depositDue != null)
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Text('Deposit by ${formatAccountsDate(r.depositDue!)}',
                  style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.w600, color: AppTheme.primary)),
            ),
        ]),
      ),
    );
  }
}
