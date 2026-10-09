import 'package:flutter/material.dart';
import 'package:ar_society_app/shared/widgets/app_data_table.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart';
import 'package:ar_society_app/features/accounts/presentation/providers/accounts_providers.dart';
import 'package:ar_society_app/features/accounts/presentation/screens/accounts_screen.dart' show ledgerRoute;
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/maintenance_billing/data/maintenance_billing_api.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/providers/maintenance_billing_providers.dart';
import 'package:ar_society_app/features/staff/presentation/widgets/staff_widgets.dart' show AppCard, EmptyState;
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

const _months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/// What the society spent on each maintenance element: for a month, or the financial year so far.
/// An element with nothing recorded shows at ₹0 — the cue that this month's bill has not been entered —
/// and spend on expense heads that count towards no element is listed apart, with a way to link it.
class ExpensesByElementScreen extends ConsumerStatefulWidget {
  const ExpensesByElementScreen({super.key});

  @override
  ConsumerState<ExpensesByElementScreen> createState() => _ExpensesByElementScreenState();
}

class _ExpensesByElementScreenState extends ConsumerState<ExpensesByElementScreen> {
  late DateTime _month = DateTime(DateTime.now().year, DateTime.now().month);
  bool _yearToDate = false;

  // Whole days only: these form the key the report is cached under, so a value that changed on every
  // rebuild (a time of day) would make it reload forever.
  static DateTime get _today {
    final n = DateTime.now();
    return DateTime(n.year, n.month, n.day);
  }

  DateTime get _from => _yearToDate ? _fyStart(_today) : _month;
  DateTime get _to {
    if (_yearToDate) return _today;
    final end = DateTime(_month.year, _month.month + 1, 0);
    return end.isAfter(_today) ? _today : end;
  }

  static DateTime _fyStart(DateTime d) => DateTime(d.month >= 4 ? d.year : d.year - 1, 4, 1);

  bool get _canGoNext {
    final now = DateTime.now();
    return _month.year < now.year || (_month.year == now.year && _month.month < now.month);
  }

  String get _label => _yearToDate
      ? 'Financial year ${_fyStart(_today).year}-${(_fyStart(_today).year + 1) % 100}'
      : '${_months[_month.month - 1]} ${_month.year}';

  Future<void> _link(LedgerSpend ledger, List<MaintenanceElement> elements) async {
    final choice = await showDialog<MaintenanceElement>(
      context: context,
      builder: (ctx) => SimpleDialog(
        title: Text('${ledger.name} counts towards…'),
        children: [
          for (final e in elements)
            SimpleDialogOption(onPressed: () => Navigator.pop(ctx, e), child: Text(e.name)),
        ],
      ),
    );
    if (choice == null || !mounted) return;
    try {
      await ref.read(accountsApiProvider).updateLedger(ledger.accountId, {'maintenance_element_id': choice.id});
      invalidateBooks(ref);
      if (mounted) AppToast.success(context, '${ledger.name} now counts towards ${choice.name}');
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    }
  }

  @override
  Widget build(BuildContext context) {
    final societyId = ref.watch(currentUserProvider)?.societyId;
    if (societyId == null) return const Scaffold(body: Center(child: Text('No society context')));
    final key = (societyId: societyId, from: _from, to: _to);
    final async = ref.watch(expensesByElementProvider(key));
    final elements = ref.watch(maintenanceElementsProvider((societyId: societyId, includeInactive: false))).valueOrNull ??
        const <MaintenanceElement>[];

    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(title: const Text('Spend by element'), actions: [
        AppBarTextAction(
          onPressed: () => context.push(AppRoutes.accountsExpenseNew),
          icon: Icons.add_rounded,
          label: 'Add expense',
        ),
      ]),
      body: ResponsiveBody(
        maxWidth: 900,
        child: RefreshIndicator(
          onRefresh: () async => ref.invalidate(expensesByElementProvider),
          child: ListView(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 60),
            children: [
              Row(children: [
                SegmentedButton<bool>(
                  segments: const [
                    ButtonSegment(value: false, label: Text('Month')),
                    ButtonSegment(value: true, label: Text('Year so far')),
                  ],
                  selected: {_yearToDate},
                  showSelectedIcon: false,
                  onSelectionChanged: (s) => setState(() => _yearToDate = s.first),
                ),
                const Spacer(),
                if (!_yearToDate) ...[
                  IconButton(
                    tooltip: 'Previous month',
                    icon: const Icon(Icons.chevron_left_rounded),
                    onPressed: () => setState(() => _month = DateTime(_month.year, _month.month - 1)),
                  ),
                  Text(_label, style: const TextStyle(fontWeight: FontWeight.w600)),
                  IconButton(
                    tooltip: 'Next month',
                    icon: const Icon(Icons.chevron_right_rounded),
                    onPressed: _canGoNext ? () => setState(() => _month = DateTime(_month.year, _month.month + 1)) : null,
                  ),
                ] else
                  Text(_label, style: const TextStyle(fontWeight: FontWeight.w600)),
              ]),
              const SizedBox(height: 10),
              async.when(
                loading: () => const Padding(
                    padding: EdgeInsets.only(top: 80), child: Center(child: CircularProgressIndicator(color: AppTheme.primary))),
                error: (e, _) => AppErrorBanner(message: friendlyErrorMessage(e)),
                data: (r) => _body(r, elements),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _body(ExpensesByElement r, List<MaintenanceElement> elements) {
    if (r.elements.isEmpty && r.unlinked.isEmpty) {
      return const Padding(
        padding: EdgeInsets.only(top: 40),
        child: EmptyState(
          icon: Icons.receipt_long_outlined,
          title: 'No expenses recorded for this period',
          subtitle: 'Use "Add expense" to record one',
        ),
      );
    }
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      AppCard(
        child: Row(children: [
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              const Text('Total spent', style: TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
              Text(formatInr(r.total), style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w700)),
            ]),
          ),
          if (r.unlinkedTotal > 0)
            Text('${formatInr(r.unlinkedTotal)} on heads\nno element covers',
                textAlign: TextAlign.right, style: const TextStyle(fontSize: 12, color: AppTheme.warning)),
        ]),
      ),
      const SizedBox(height: 12),
      for (final e in r.elements) ...[_ElementCard(spend: e), const SizedBox(height: 10)],
      if (r.unlinked.isNotEmpty) ...[
        const SizedBox(height: 6),
        const Text('Not counted towards any element',
            style: TextStyle(fontSize: 14, fontWeight: FontWeight.w700, color: AppTheme.warning)),
        const SizedBox(height: 4),
        const Text(
          'These were spent on expense heads that count towards no maintenance element, so they are in nobody\'s '
          'budget. Link each head to the element it belongs to.',
          style: TextStyle(fontSize: 12.5, color: AppTheme.textSecondary, height: 1.4),
        ),
        const SizedBox(height: 8),
        for (final l in r.unlinked) ...[
          AppCard(
            child: Row(children: [
              Expanded(child: Text(l.name, style: const TextStyle(fontWeight: FontWeight.w600))),
              Text(formatInr(l.amount)),
              TextButton(onPressed: () => _link(l, elements), child: const Text('Link…')),
            ]),
          ),
          const SizedBox(height: 8),
        ],
      ],
    ]);
  }
}

class _ElementCard extends StatelessWidget {
  final ElementSpend spend;
  const _ElementCard({required this.spend});

  @override
  Widget build(BuildContext context) {
    final nothing = spend.total == 0;
    return AppCard(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Expanded(
            child: Text(spend.name,
                style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: nothing ? AppTheme.textSecondary : AppTheme.textPrimary)),
          ),
          Text(nothing ? 'Nothing recorded' : formatInr(spend.total),
              style: TextStyle(
                  fontWeight: FontWeight.w700, color: nothing ? AppTheme.warning : AppTheme.textPrimary, fontSize: nothing ? 12 : 15)),
        ]),
        const SizedBox(height: 6),
        for (final l in spend.ledgers)
          InkWell(
            onTap: () => context.push(ledgerRoute(l.accountId)),
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 4),
              child: Row(children: [
                Expanded(child: Text(l.name, style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary))),
                Text(formatInr(l.amount), style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary)),
                const Icon(Icons.chevron_right_rounded, size: 16, color: AppTheme.textSecondary),
              ]),
            ),
          ),
      ]),
    );
  }
}
