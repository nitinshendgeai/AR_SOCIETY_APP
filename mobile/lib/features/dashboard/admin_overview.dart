import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

// ── Data ─────────────────────────────────────────────────────────────────────

double _num(Object? v) => double.tryParse('${v ?? 0}') ?? 0;

final _rupees = NumberFormat.currency(locale: 'en_IN', symbol: '₹', decimalDigits: 0);
String _inr(double v) => _rupees.format(v);

class CollectionTrendPoint {
  final String name;
  final double billed;
  final double collected;
  CollectionTrendPoint(Map<String, dynamic> j)
      : name = j['name'] as String? ?? '',
        billed = _num(j['billed']),
        collected = _num(j['collected']);
}

class CollectionBlock {
  final String cycleName;
  final double billed, collected, outstanding;
  final int percent, bills, paidBills, overdueBills;
  final List<CollectionTrendPoint> trend;
  CollectionBlock(Map<String, dynamic> j)
      : cycleName = j['cycle_name'] as String? ?? '',
        billed = _num(j['billed']),
        collected = _num(j['collected']),
        outstanding = _num(j['outstanding']),
        percent = (j['percent'] as num?)?.toInt() ?? 0,
        bills = (j['bills'] as num?)?.toInt() ?? 0,
        paidBills = (j['paid_bills'] as num?)?.toInt() ?? 0,
        overdueBills = (j['overdue_bills'] as num?)?.toInt() ?? 0,
        trend = [for (final p in (j['trend'] as List? ?? const [])) CollectionTrendPoint(p as Map<String, dynamic>)];
}

class MoneyBlock {
  final double cash, bank, membersDues, fyIncome, fyExpense;
  final String fy;
  MoneyBlock(Map<String, dynamic> j)
      : cash = _num(j['cash']),
        bank = _num(j['bank']),
        membersDues = _num(j['members_dues']),
        fyIncome = _num(j['fy_income']),
        fyExpense = _num(j['fy_expense']),
        fy = j['fy'] as String? ?? '';
}

class AttentionItem {
  final String key;
  final int count;
  final String severity; // high | medium | info
  final double amount;
  AttentionItem(Map<String, dynamic> j)
      : key = j['key'] as String,
        count = (j['count'] as num?)?.toInt() ?? 0,
        severity = j['severity'] as String? ?? 'info',
        amount = _num(j['amount']);
}

class DashboardOverview {
  final CollectionBlock? collection;
  final MoneyBlock? money;
  final int flats, occupied, vacant, residents, visitorsToday, visitorsInside;
  final bool hasOccupancy, hasToday;
  final List<AttentionItem> attention;

  DashboardOverview.fromJson(Map<String, dynamic> j)
      : collection = j['collection'] == null ? null : CollectionBlock(j['collection'] as Map<String, dynamic>),
        money = j['money'] == null ? null : MoneyBlock(j['money'] as Map<String, dynamic>),
        hasOccupancy = j['occupancy'] != null,
        flats = ((j['occupancy'] as Map?)?['flats'] as num?)?.toInt() ?? 0,
        occupied = ((j['occupancy'] as Map?)?['occupied'] as num?)?.toInt() ?? 0,
        vacant = ((j['occupancy'] as Map?)?['vacant'] as num?)?.toInt() ?? 0,
        residents = ((j['occupancy'] as Map?)?['residents'] as num?)?.toInt() ?? 0,
        hasToday = j['today'] != null,
        visitorsToday = ((j['today'] as Map?)?['visitors_today'] as num?)?.toInt() ?? 0,
        visitorsInside = ((j['today'] as Map?)?['visitors_inside'] as num?)?.toInt() ?? 0,
        attention = [for (final a in (j['attention'] as List? ?? const [])) AttentionItem(a as Map<String, dynamic>)];
}

final dashboardOverviewProvider = FutureProvider.autoDispose.family<DashboardOverview, String>((ref, societyId) async {
  final r = await ApiClient.instance.get('/dashboard/society/$societyId');
  return DashboardOverview.fromJson(r.data as Map<String, dynamic>);
});

// ── What each "needs attention" key says and where it goes ───────────────────

class _Attn {
  final IconData icon;
  final String Function(AttentionItem) text;
  final void Function(BuildContext, String societyId) open;
  const _Attn(this.icon, this.text, this.open);
}

String _n(int n, String one, [String? many]) => '$n ${n == 1 ? one : (many ?? '${one}s')}';

final Map<String, _Attn> _attn = {
  'overdue_bills': _Attn(Icons.warning_amber_rounded,
      (a) => '${_n(a.count, 'flat has', 'flats have')} overdue maintenance (${_inr(a.amount)})',
      (c, _) => c.go(AppRoutes.defaulters)),
  'vendor_bills_overdue': _Attn(Icons.storefront_rounded,
      (a) => '${_n(a.count, 'vendor bill')} overdue (${_inr(a.amount)})', (c, _) => c.go(AppRoutes.vendorBills)),
  'recurring_due': _Attn(Icons.event_repeat_rounded,
      (a) => '${_n(a.count, 'monthly expense')} to record', (c, _) => c.push(AppRoutes.accountsRecurring)),
  'agreements_expired': _Attn(Icons.event_busy_rounded,
      (a) => '${_n(a.count, 'tenant agreement has', 'tenant agreements have')} expired', (c, _) => c.go(AppRoutes.tenantsList)),
  'agreements_expiring': _Attn(Icons.event_available_rounded,
      (a) => '${_n(a.count, 'agreement expires', 'agreements expire')} within 30 days', (c, _) => c.go(AppRoutes.tenantsList)),
  'resident_changes': _Attn(Icons.fact_check_outlined,
      (a) => '${_n(a.count, 'resident profile change')} to review', (c, _) => c.go(AppRoutes.pendingResidentChanges)),
  'password_resets': _Attn(Icons.lock_reset_rounded,
      (a) => '${_n(a.count, 'password reset request')}', (c, _) => c.push(AppRoutes.passwordResetRequests)),
  'complaints_old': _Attn(Icons.report_problem_rounded,
      (a) => '${_n(a.count, 'complaint')} open for over a week',
      (c, s) => c.go(AppRoutes.complaintsSociety.replaceFirst(':societyId', s))),
  'complaints_open': _Attn(Icons.report_gmailerrorred_rounded,
      (a) => '${_n(a.count, 'open complaint')}',
      (c, s) => c.go(AppRoutes.complaintsSociety.replaceFirst(':societyId', s))),
  'amenity_requests': _Attn(Icons.pool_rounded,
      (a) => '${_n(a.count, 'amenity booking request')}', (c, _) => c.go(AppRoutes.amenities)),
  'punch_approvals': _Attn(Icons.approval_rounded,
      (a) => '${_n(a.count, 'staff punch')} waiting for approval', (c, s) => c.push(AppRoutes.staffApprovals, extra: s)),
  'leave_requests': _Attn(Icons.beach_access_rounded,
      (a) => '${_n(a.count, 'staff leave request')}', (c, s) => c.push(AppRoutes.staffApprovals, extra: s)),
  'low_stock': _Attn(Icons.inventory_2_outlined,
      (a) => '${_n(a.count, 'store item')} low in stock', (c, _) => c.go(AppRoutes.stores)),
};

Color _severityColor(String s) => switch (s) {
      'high' => AppTheme.error,
      'medium' => AppTheme.warning,
      _ => AppTheme.primary,
    };

// ── Section ──────────────────────────────────────────────────────────────────

/// The admin's overview: collection, money, what is waiting on them, and the
/// society today. One request; each block shows only what the server could work out.
class AdminOverview extends ConsumerWidget {
  final String societyId;
  final String activeStaff;
  const AdminOverview({super.key, required this.societyId, required this.activeStaff});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(dashboardOverviewProvider(societyId));
    return async.when(
      loading: () => const _Frame(child: SizedBox(height: 160, child: Center(child: CircularProgressIndicator()))),
      error: (e, _) => _Frame(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('The overview could not be loaded.', style: TextStyle(fontWeight: FontWeight.w600)),
          const SizedBox(height: 4),
          const Text('Check your connection and try again.',
              style: TextStyle(fontSize: 12.5, color: AppTheme.textSecondary)),
          const SizedBox(height: 10),
          OutlinedButton.icon(
              onPressed: () => ref.invalidate(dashboardOverviewProvider(societyId)),
              icon: const Icon(Icons.refresh_rounded, size: 18),
              label: const Text('Try again')),
        ]),
      ),
      data: (o) => _Body(o: o, societyId: societyId, activeStaff: activeStaff),
    );
  }
}

class _Body extends StatelessWidget {
  final DashboardOverview o;
  final String societyId;
  final String activeStaff;
  const _Body({required this.o, required this.societyId, required this.activeStaff});

  @override
  Widget build(BuildContext context) {
    final collection = _CollectionCard(c: o.collection);
    final attention = _AttentionCard(items: o.attention, societyId: societyId);
    return LayoutBuilder(builder: (context, box) {
      final wide = box.maxWidth >= 860;
      return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        if (wide)
          Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Expanded(flex: 5, child: collection),
            const SizedBox(width: 16),
            Expanded(flex: 4, child: attention),
          ])
        else ...[
          collection,
          const SizedBox(height: 16),
          attention,
        ],
        if (o.money != null) ...[
          const SizedBox(height: 20),
          const _Label('Money'),
          const SizedBox(height: 10),
          _MoneyRow(m: o.money!),
        ],
        const SizedBox(height: 20),
        const _Label('Society today'),
        const SizedBox(height: 10),
        _Glance(o: o, activeStaff: activeStaff),
      ]);
    });
  }
}

class _Label extends StatelessWidget {
  final String text;
  const _Label(this.text);
  @override
  Widget build(BuildContext context) => Text(text,
      style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: AppTheme.textSecondary));
}

class _Frame extends StatelessWidget {
  final Widget child;
  final String? title;
  final Widget? trailing;
  const _Frame({required this.child, this.title, this.trailing});

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        color: AppTheme.cardBg,
        borderRadius: BorderRadius.circular(AppTheme.radiusL),
        boxShadow: AppTheme.cardShadow,
      ),
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          if (title != null) ...[
            Row(children: [
              Expanded(
                  child: Text(title!,
                      style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: AppTheme.textPrimary))),
              if (trailing != null) trailing!,
            ]),
            const SizedBox(height: 14),
          ],
          child,
        ]),
      ),
    );
  }
}

// ── Collection ───────────────────────────────────────────────────────────────

class _CollectionCard extends StatelessWidget {
  final CollectionBlock? c;
  const _CollectionCard({required this.c});

  @override
  Widget build(BuildContext context) {
    if (c == null) {
      return _Frame(
        title: 'Maintenance collection',
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('No billing cycle yet.',
              style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: AppTheme.textPrimary)),
          const SizedBox(height: 4),
          const Text('Create the first cycle to see what has been billed and collected.',
              style: TextStyle(fontSize: 12.5, color: AppTheme.textSecondary, height: 1.4)),
          const SizedBox(height: 12),
          OutlinedButton(onPressed: () => context.go(AppRoutes.maintenanceBilling), child: const Text('Open billing')),
        ]),
      );
    }
    final cl = c!;
    final fraction = cl.billed <= 0 ? 0.0 : (cl.collected / cl.billed).clamp(0.0, 1.0);
    return _Frame(
      title: 'Maintenance collection',
      trailing: TextButton(onPressed: () => context.go(AppRoutes.maintenanceBilling), child: const Text('Billing')),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(cl.cycleName, style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary)),
        const SizedBox(height: 6),
        Row(crossAxisAlignment: CrossAxisAlignment.end, children: [
          Expanded(
            // Wraps to a second line on a very narrow screen instead of cutting the amount.
            child: Wrap(crossAxisAlignment: WrapCrossAlignment.end, spacing: 8, children: [
              Text(_inr(cl.collected),
                  style: const TextStyle(fontSize: 26, fontWeight: FontWeight.w800, color: AppTheme.textPrimary)),
              Padding(
                padding: const EdgeInsets.only(bottom: 4),
                child: Text('of ${_inr(cl.billed)} billed',
                    style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary)),
              ),
            ]),
          ),
          const SizedBox(width: 8),
          Text('${cl.percent}%',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: _pctColor(cl.percent))),
        ]),
        const SizedBox(height: 10),
        ClipRRect(
          borderRadius: BorderRadius.circular(6),
          child: LinearProgressIndicator(
              value: fraction, minHeight: 8, backgroundColor: AppTheme.border, color: _pctColor(cl.percent)),
        ),
        const SizedBox(height: 12),
        Wrap(spacing: 18, runSpacing: 6, children: [
          _Fact('Outstanding', _inr(cl.outstanding), cl.outstanding > 0 ? AppTheme.error : AppTheme.textPrimary),
          _Fact('Bills paid', '${cl.paidBills} of ${cl.bills}', AppTheme.textPrimary),
          if (cl.overdueBills > 0) _Fact('Overdue', '${cl.overdueBills}', AppTheme.error),
        ]),
        if (cl.trend.length > 1) ...[
          const SizedBox(height: 18),
          const Text('Last cycles', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: AppTheme.textSecondary)),
          const SizedBox(height: 8),
          _TrendBars(points: cl.trend),
        ],
      ]),
    );
  }

  static Color _pctColor(int p) => p >= 80 ? AppTheme.success : p >= 50 ? AppTheme.warning : AppTheme.error;
}

class _Fact extends StatelessWidget {
  final String label, value;
  final Color color;
  const _Fact(this.label, this.value, this.color);
  @override
  Widget build(BuildContext context) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(label, style: const TextStyle(fontSize: 11.5, color: AppTheme.textSecondary)),
        Text(value, style: TextStyle(fontSize: 14, fontWeight: FontWeight.w700, color: color)),
      ]);
}

/// "October 2026" -> "Oct 26", so six labels fit across a phone. Other names stay as they are.
String _shortCycle(String name) {
  final m = RegExp(r'^([A-Za-z]{3})[A-Za-z]*\s+(\d{2})(\d{2})$').firstMatch(name.trim());
  return m == null ? name : '${m.group(1)} ${m.group(3)}';
}

/// Billed (light) and collected (solid) for each recent cycle.
class _TrendBars extends StatelessWidget {
  final List<CollectionTrendPoint> points;
  const _TrendBars({required this.points});

  @override
  Widget build(BuildContext context) {
    final maxV = points.fold<double>(0, (m, p) => p.billed > m ? p.billed : m);
    const chartHeight = 84.0;
    return Column(children: [
      SizedBox(
        height: chartHeight,
        child: Row(crossAxisAlignment: CrossAxisAlignment.end, children: [
          for (final p in points)
            Expanded(
              child: Tooltip(
                message: '${p.name}\nBilled ${_inr(p.billed)}\nCollected ${_inr(p.collected)}',
                child: Row(mainAxisAlignment: MainAxisAlignment.center, crossAxisAlignment: CrossAxisAlignment.end, children: [
                  _Bar(height: maxV <= 0 ? 0 : chartHeight * p.billed / maxV, color: AppTheme.primary.withOpacity(0.25)),
                  const SizedBox(width: 3),
                  _Bar(height: maxV <= 0 ? 0 : chartHeight * p.collected / maxV, color: AppTheme.primary),
                ]),
              ),
            ),
        ]),
      ),
      const SizedBox(height: 6),
      Row(children: [
        for (final p in points)
          Expanded(
            child: Text(_shortCycle(p.name),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                textAlign: TextAlign.center,
                style: const TextStyle(fontSize: 10, color: AppTheme.textSecondary)),
          ),
      ]),
      const SizedBox(height: 8),
      Row(mainAxisAlignment: MainAxisAlignment.center, children: [
        _Key(color: AppTheme.primary.withOpacity(0.25), label: 'Billed'),
        const SizedBox(width: 14),
        const _Key(color: AppTheme.primary, label: 'Collected'),
      ]),
    ]);
  }
}

class _Bar extends StatelessWidget {
  final double height;
  final Color color;
  const _Bar({required this.height, required this.color});
  @override
  Widget build(BuildContext context) => Container(
      width: 12,
      height: height < 2 && height > 0 ? 2 : height,
      decoration: BoxDecoration(color: color, borderRadius: const BorderRadius.vertical(top: Radius.circular(3))));
}

class _Key extends StatelessWidget {
  final Color color;
  final String label;
  const _Key({required this.color, required this.label});
  @override
  Widget build(BuildContext context) => Row(children: [
        Container(width: 10, height: 10, decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(2))),
        const SizedBox(width: 5),
        Text(label, style: const TextStyle(fontSize: 11, color: AppTheme.textSecondary)),
      ]);
}

// ── Needs attention ──────────────────────────────────────────────────────────

class _AttentionCard extends StatelessWidget {
  final List<AttentionItem> items;
  final String societyId;
  const _AttentionCard({required this.items, required this.societyId});

  @override
  Widget build(BuildContext context) {
    final known = [for (final i in items) if (_attn.containsKey(i.key)) i];
    return _Frame(
      title: 'Needs attention',
      trailing: known.isEmpty
          ? null
          : Text('${known.length}',
              style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: AppTheme.textSecondary)),
      child: known.isEmpty
          ? const Row(children: [
              Icon(Icons.check_circle_rounded, color: AppTheme.success, size: 22),
              SizedBox(width: 10),
              Expanded(
                  child: Text('All clear. Nothing is waiting on the office right now.',
                      style: TextStyle(fontSize: 13.5, color: AppTheme.textSecondary, height: 1.35))),
            ])
          : Column(children: [
              for (var i = 0; i < known.length; i++) ...[
                if (i > 0) const Divider(height: 1),
                _AttentionRow(item: known[i], societyId: societyId),
              ],
            ]),
    );
  }
}

class _AttentionRow extends StatelessWidget {
  final AttentionItem item;
  final String societyId;
  const _AttentionRow({required this.item, required this.societyId});

  @override
  Widget build(BuildContext context) {
    final a = _attn[item.key]!;
    final color = _severityColor(item.severity);
    return InkWell(
      onTap: () => a.open(context, societyId),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 11),
        child: Row(children: [
          Container(
            width: 32,
            height: 32,
            decoration: BoxDecoration(color: color.withOpacity(0.12), borderRadius: BorderRadius.circular(9)),
            child: Icon(a.icon, color: color, size: 17),
          ),
          const SizedBox(width: 12),
          Expanded(
              child: Text(a.text(item),
                  style: const TextStyle(fontSize: 13.5, color: AppTheme.textPrimary, height: 1.3))),
          const Icon(Icons.chevron_right_rounded, size: 18, color: AppTheme.textTertiary),
        ]),
      ),
    );
  }
}

// ── Money ────────────────────────────────────────────────────────────────────

class _MoneyRow extends StatelessWidget {
  final MoneyBlock m;
  const _MoneyRow({required this.m});

  @override
  Widget build(BuildContext context) {
    final surplus = m.fyIncome - m.fyExpense;
    return KpiGrid(cards: [
      KpiCard(
          icon: Icons.account_balance_rounded,
          label: 'Cash and bank',
          value: _inr(m.cash + m.bank),
          note: 'Bank ${_inr(m.bank)}',
          color: AppTheme.primary,
          onTap: () => context.go(AppRoutes.accounts)),
      KpiCard(
          icon: Icons.account_balance_wallet_rounded,
          label: 'Members owe',
          value: _inr(m.membersDues),
          color: m.membersDues > 0 ? AppTheme.error : AppTheme.success,
          onTap: () => context.go(AppRoutes.defaulters)),
      KpiCard(
          icon: Icons.trending_up_rounded,
          label: 'Income ${m.fy}',
          value: _inr(m.fyIncome),
          color: AppTheme.success,
          onTap: () => context.go(AppRoutes.accounts)),
      KpiCard(
          icon: Icons.trending_down_rounded,
          label: 'Spent ${m.fy}',
          value: _inr(m.fyExpense),
          note: surplus >= 0 ? 'Surplus ${_inr(surplus)}' : 'Deficit ${_inr(-surplus)}',
          color: AppTheme.warning,
          onTap: () => context.go(AppRoutes.accounts)),
    ]);
  }
}

// ── Society today ────────────────────────────────────────────────────────────

class _Glance extends StatelessWidget {
  final DashboardOverview o;
  final String activeStaff;
  const _Glance({required this.o, required this.activeStaff});

  @override
  Widget build(BuildContext context) {
    final fraction = o.flats == 0 ? 0.0 : o.occupied / o.flats;
    return _Frame(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        if (o.hasOccupancy) ...[
          Row(children: [
            Expanded(
              child: Text('${o.occupied} of ${o.flats} flats occupied',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700, color: AppTheme.textPrimary)),
            ),
            const SizedBox(width: 8),
            Text('${o.vacant} vacant', style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary)),
          ]),
          const SizedBox(height: 8),
          ClipRRect(
            borderRadius: BorderRadius.circular(6),
            child: LinearProgressIndicator(
                value: fraction, minHeight: 8, backgroundColor: AppTheme.border, color: AppTheme.success),
          ),
          const SizedBox(height: 16),
        ],
        Wrap(spacing: 28, runSpacing: 12, children: [
          if (o.hasOccupancy)
            _Stat(Icons.people_rounded, '${o.residents}', 'Residents', () => context.go(AppRoutes.residentsList)),
          if (o.hasToday) ...[
            _Stat(Icons.meeting_room_rounded, '${o.visitorsToday}', 'Visitors today', null),
            _Stat(Icons.login_rounded, '${o.visitorsInside}', 'Inside now', null),
          ],
          _Stat(Icons.badge_rounded, activeStaff, 'Active staff', () => context.go(AppRoutes.staffList)),
        ]),
      ]),
    );
  }
}

class _Stat extends StatelessWidget {
  final IconData icon;
  final String value, label;
  final VoidCallback? onTap;
  const _Stat(this.icon, this.value, this.label, this.onTap);

  @override
  Widget build(BuildContext context) => InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(8),
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          Icon(icon, size: 18, color: AppTheme.textSecondary),
          const SizedBox(width: 8),
          Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(value, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: AppTheme.textPrimary)),
            Text(label, style: const TextStyle(fontSize: 11.5, color: AppTheme.textSecondary)),
          ]),
        ]),
      );
}
