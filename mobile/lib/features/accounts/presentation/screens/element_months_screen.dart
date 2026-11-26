import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart';
import 'package:ar_society_app/features/accounts/presentation/providers/accounts_providers.dart';
import 'package:ar_society_app/features/accounts/presentation/screens/accounts_screen.dart' show ledgerRoute;
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/staff/presentation/widgets/staff_widgets.dart' show AppCard, EmptyState;
import 'package:ar_society_app/shared/widgets/app_form.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

const _mon = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
String _dmy(DateTime d) => '${d.day.toString().padLeft(2, '0')} ${_mon[d.month - 1]} ${d.year}';

/// One maintenance element's spend month by month: every month of the chosen dates (the financial year so far to begin
/// with), its total and the expense ledgers behind it. A ledger opens its statement.
class ElementMonthsScreen extends ConsumerStatefulWidget {
  /// The element's id, or "none" for the expense heads no element covers.
  final String elementId;
  final String name;
  const ElementMonthsScreen({super.key, required this.elementId, required this.name});

  @override
  ConsumerState<ElementMonthsScreen> createState() => _ElementMonthsScreenState();
}

class _ElementMonthsScreenState extends ConsumerState<ElementMonthsScreen> {
  // Whole days only: they form the key the report is cached under.
  static DateTime get _today {
    final n = DateTime.now();
    return DateTime(n.year, n.month, n.day);
  }

  static DateTime _fyStart(DateTime d) => DateTime(d.month >= 4 ? d.year : d.year - 1, 4, 1);

  late DateTime _from = _fyStart(_today);
  DateTime _to = _today;

  Future<void> _pick({required bool from}) async {
    final picked = await showDatePicker(
      context: context,
      initialDate: from ? _from : _to,
      firstDate: DateTime(2000),
      lastDate: _today,
      helpText: from ? 'From date' : 'To date',
    );
    if (picked == null || !mounted) return;
    final day = DateTime(picked.year, picked.month, picked.day);
    setState(() {
      if (from) {
        _from = day;
        if (_to.isBefore(day)) _to = day;
      } else {
        _to = day;
        if (_from.isAfter(day)) _from = day;
      }
    });
  }

  void _thisYear() => setState(() {
        _from = _fyStart(_today);
        _to = _today;
      });

  void _lastYear() => setState(() {
        final start = _fyStart(_today);
        _from = DateTime(start.year - 1, 4, 1);
        _to = DateTime(start.year, 3, 31);
      });

  @override
  Widget build(BuildContext context) {
    final societyId = ref.watch(currentUserProvider)?.societyId;
    if (societyId == null) return const Scaffold(body: Center(child: Text('No society context')));
    final key = (societyId: societyId, elementId: widget.elementId, from: _from, to: _to);
    final async = ref.watch(elementMonthsProvider(key));
    return AppPage(
      title: widget.name,
      subtitle: 'Spend month by month',
      body: ResponsiveBody(
        maxWidth: 900,
        child: RefreshIndicator(
          onRefresh: () async => ref.invalidate(elementMonthsProvider),
          child: ListView(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 60),
            children: [
              Wrap(spacing: 8, runSpacing: 8, children: [
                ActionChip(key: const ValueKey('months-this-year'), label: const Text('This financial year'), onPressed: _thisYear),
                ActionChip(key: const ValueKey('months-last-year'), label: const Text('Last financial year'), onPressed: _lastYear),
              ]),
              const SizedBox(height: 10),
              Row(children: [
                Expanded(
                  child: OutlinedButton.icon(
                    key: const ValueKey('months-from'),
                    onPressed: () => _pick(from: true),
                    icon: const Icon(Icons.calendar_today_rounded, size: 16),
                    label: Text('From ${_dmy(_from)}'),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: OutlinedButton.icon(
                    key: const ValueKey('months-to'),
                    onPressed: () => _pick(from: false),
                    icon: const Icon(Icons.event_rounded, size: 16),
                    label: Text('To ${_dmy(_to)}'),
                  ),
                ),
              ]),
              const SizedBox(height: 12),
              async.when(
                loading: () => const Padding(padding: EdgeInsets.only(top: 60), child: AppLoader()),
                error: (e, _) => AppErrorState(
                    compact: true, message: friendlyErrorMessage(e), onRetry: () => ref.invalidate(elementMonthsProvider(key))),
                data: _body,
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _body(ElementMonths r) {
    final biggest = r.months.fold<double>(0, (m, e) => e.total.abs() > m ? e.total.abs() : m);
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      AppCard(
        child: Row(children: [
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('Total spent, ${_dmy(r.from)} to ${_dmy(r.to)}',
                  style: TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
              Text(formatInr(r.total), key: const ValueKey('months-total'), style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w700)),
            ]),
          ),
          Text('${r.months.length} month${r.months.length == 1 ? '' : 's'}',
              style: TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
        ]),
      ),
      const SizedBox(height: 12),
      if (r.months.isEmpty)
        const EmptyState(icon: Icons.calendar_month_outlined, title: 'No months to show', subtitle: 'Pick the dates again.')
      else
        for (final m in r.months) ...[_MonthCard(month: m, biggest: biggest), const SizedBox(height: 10)],
    ]);
  }
}

class _MonthCard extends StatelessWidget {
  final MonthSpend month;
  final double biggest;
  const _MonthCard({required this.month, required this.biggest});

  @override
  Widget build(BuildContext context) {
    final nothing = month.total == 0;
    return AppCard(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Expanded(
            child: Text(month.label,
                style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: nothing ? AppTheme.textSecondary : AppTheme.textPrimary)),
          ),
          Text(nothing ? 'Nothing recorded' : formatInr(month.total),
              style: TextStyle(
                  fontWeight: FontWeight.w700, color: nothing ? AppTheme.warning : AppTheme.textPrimary, fontSize: nothing ? 12 : 15)),
        ]),
        if (!nothing && biggest > 0) ...[
          const SizedBox(height: 6),
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(value: (month.total.abs() / biggest).clamp(0.0, 1.0), minHeight: 6),
          ),
        ],
        const SizedBox(height: 6),
        for (final l in month.ledgers)
          InkWell(
            onTap: () => context.push(ledgerRoute(l.accountId)),
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 4),
              child: Row(children: [
                Expanded(child: Text(l.name, style: TextStyle(fontSize: 13, color: AppTheme.textSecondary))),
                Text(formatInr(l.amount), style: TextStyle(fontSize: 13, color: AppTheme.textSecondary)),
                Icon(Icons.chevron_right_rounded, size: 16, color: AppTheme.textSecondary),
              ]),
            ),
          ),
      ]),
    );
  }
}
