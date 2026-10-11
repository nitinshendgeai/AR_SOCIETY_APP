import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/layout/app_shell.dart' show isDesktopLayout;
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart';
import 'package:ar_society_app/features/accounts/data/registers_api.dart';
import 'package:ar_society_app/features/accounts/presentation/providers/accounts_providers.dart';
import 'package:ar_society_app/features/accounts/presentation/widgets/accounts_widgets.dart';
import 'package:ar_society_app/features/accounts/presentation/widgets/register_widgets.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/shared/widgets/app_data_table.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// The page both registers share: period chips, status chips, a search box, totals, and the rows (a table on a
/// computer, cards on a phone), with a PDF of the same view.
class _RegisterPage<T> extends ConsumerStatefulWidget {
  final String title;
  final String subtitle;
  final String searchHint;
  final String pdfName;
  final List<(String?, String)> statuses;
  final AutoDisposeFutureProviderFamily<Register<T>, RegisterKey> provider;
  final Future<Uint8List> Function(WidgetRef ref, String societyId, DateTime? from, DateTime? to, String? status) pdf;
  final List<(String, String)> Function(Register<T> r) totals;
  final List<AppDataColumn<T>> columns;
  final Widget Function(T row) card;
  final IconData emptyIcon;
  final String emptyTitle;

  const _RegisterPage({
    required this.title,
    required this.subtitle,
    required this.searchHint,
    required this.pdfName,
    required this.statuses,
    required this.provider,
    required this.pdf,
    required this.totals,
    required this.columns,
    required this.card,
    required this.emptyIcon,
    required this.emptyTitle,
  });

  @override
  ConsumerState<_RegisterPage<T>> createState() => _RegisterPageState<T>();
}

class _RegisterPageState<T> extends ConsumerState<_RegisterPage<T>> {
  RegisterPeriod _period = RegisterPeriod.thisYear;
  String? _status;
  String _search = '';

  @override
  Widget build(BuildContext context) {
    final societyId = ref.watch(currentUserProvider)?.societyId ?? '';
    final (from, to) = _period.range;
    final async = ref.watch(widget.provider((societyId: societyId, from: from, to: to, status: _status, search: _search)));
    final desktop = isDesktopLayout(context);

    return AppPage(
      title: widget.title,
      subtitle: widget.subtitle,
      actions: [
        PdfActions(
          load: async.valueOrNull == null
              ? null
              : () => widget.pdf(ref, societyId, from, to, _status),
          fileName: widget.pdfName,
          subject: widget.title,
        ),
      ],
      body: RefreshIndicator(
        onRefresh: () async => ref.invalidate(widget.provider((societyId: societyId, from: from, to: to, status: _status, search: _search))),
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 96),
          children: [
            RegisterPeriodBar(value: _period, onChanged: (p) => setState(() => _period = p)),
            const SizedBox(height: 10),
            Wrap(spacing: 8, runSpacing: 8, children: [
              for (final (value, label) in widget.statuses)
                ChoiceChip(label: Text(label), selected: _status == value, onSelected: (_) => setState(() => _status = value)),
            ]),
            const SizedBox(height: 12),
            TextField(
              onChanged: (v) => setState(() => _search = v.trim()),
              decoration: InputDecoration(prefixIcon: const Icon(Icons.search_rounded), hintText: widget.searchHint),
            ),
            const SizedBox(height: 14),
            ...async.when(
              loading: () => [const AppLoader()],
              error: (e, _) => [Text(friendlyErrorMessage(e), style: const TextStyle(color: AppTheme.error))],
              data: (r) => [
                RegisterTotals(figures: widget.totals(r)),
                const SizedBox(height: 14),
                if (r.rows.isEmpty)
                  AppEmptyState(icon: widget.emptyIcon, title: widget.emptyTitle, subtitle: 'Try another period or filter.')
                else if (desktop)
                  AppDataTable<T>(rows: r.rows, pageSize: 100, columns: widget.columns)
                else
                  Container(
                    decoration: BoxDecoration(color: AppTheme.cardBg, borderRadius: BorderRadius.circular(AppTheme.radiusM)),
                    child: Column(children: [
                      for (final (i, row) in r.rows.indexed) ...[
                        if (i > 0) const Divider(height: 1),
                        Padding(padding: const EdgeInsets.fromLTRB(14, 10, 14, 10), child: widget.card(row)),
                      ],
                    ]),
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

Widget _statusCell(String status) {
  final s = registerStatus(status);
  return Align(alignment: Alignment.centerLeft, child: StatusPill(s.label, s.color));
}

/// A phone card: two lines on the left, an amount and a status at the right, and who entered it underneath.
Widget _card({
  required String title,
  required String line2,
  String? line3,
  required String amount,
  required String status,
  required String? enteredBy,
}) {
  final s = registerStatus(status);
  return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
    Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Expanded(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(title, style: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w700)),
          Text(line2, style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary)),
          if (line3 != null) Text(line3, style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary)),
        ]),
      ),
      const SizedBox(width: 10),
      Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
        Text(amount, style: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w700)),
        const SizedBox(height: 4),
        StatusPill(s.label, s.color),
      ]),
    ]),
    const SizedBox(height: 4),
    Text('Entered by ${enteredBy ?? 'System'}', style: const TextStyle(fontSize: 12, color: AppTheme.textTertiary)),
  ]);
}

/// Maintenance invoices raised on members, with who generated each.
class InvoiceRegisterScreen extends StatelessWidget {
  const InvoiceRegisterScreen({super.key});

  @override
  Widget build(BuildContext context) => _RegisterPage<InvoiceRow>(
        title: 'Invoice Register',
        subtitle: 'Maintenance invoices raised on members, with who generated them',
        searchHint: 'Search invoice number, flat or member',
        pdfName: 'Invoice-Register.pdf',
        statuses: const [
          (null, 'All'),
          ('issued', 'Issued'),
          ('partially_paid', 'Part paid'),
          ('paid', 'Paid'),
          ('overdue', 'Overdue'),
          ('cancelled', 'Cancelled'),
        ],
        provider: invoiceRegisterProvider,
        pdf: (ref, sid, from, to, status) => ref.read(registersApiProvider).invoicesPdf(sid, from: from, to: to, status: status),
        totals: (r) => [
          ('Invoices', '${r.count}'),
          ('Billed', formatInr(r.total)),
          ('Collected', formatInr(r.paid)),
          ('Due', formatInr(r.outstanding)),
        ],
        columns: [
          AppDataColumn.text('Date', (r) => formatAccountsDate(r.billDate), width: 110, sortKey: (r) => r.billDate),
          AppDataColumn(
              label: 'Invoice',
              width: 160,
              sortKey: (r) => r.invoiceNumber,
              cell: (r) => TwoLineCell(r.invoiceNumber, r.cycle)),
          AppDataColumn(label: 'Flat', width: 120, sortKey: (r) => r.flat, cell: (r) => Text(r.flat)),
          AppDataColumn(label: 'Member', flex: 3, sortKey: (r) => r.member, cell: (r) => Text(r.member, maxLines: 1, overflow: TextOverflow.ellipsis)),
          AppDataColumn.text('Billed', (r) => formatInr(r.total), numeric: true, width: 120, sortKey: (r) => r.total),
          AppDataColumn.text('Paid', (r) => inr(r.paid), numeric: true, width: 120, sortKey: (r) => r.paid),
          AppDataColumn.text('Due', (r) => inr(r.outstanding), numeric: true, width: 120, sortKey: (r) => r.outstanding),
          AppDataColumn(label: 'Status', width: 110, sortKey: (r) => r.status, cell: (r) => _statusCell(r.status)),
          AppDataColumn(
              label: 'Entered by', width: 160, sortKey: (r) => r.enteredBy ?? '', cell: (r) => EnteredBy(r.enteredBy ?? 'System')),
        ],
        card: (r) => _card(
          title: '${r.flat} · ${r.member}',
          line2: '${r.invoiceNumber} · ${formatAccountsDate(r.billDate)}',
          line3: r.outstanding > 0 && !r.isCancelled ? 'Due ${formatInr(r.outstanding)}' : null,
          amount: formatInr(r.total),
          status: r.status,
          enteredBy: r.enteredBy,
        ),
        emptyIcon: Icons.description_outlined,
        emptyTitle: 'No invoices in this period',
      );
}

/// Bills received from vendors, with who entered each.
class BillsRegisterScreen extends StatelessWidget {
  const BillsRegisterScreen({super.key});

  @override
  Widget build(BuildContext context) => _RegisterPage<BillRow>(
        title: 'Bills Register',
        subtitle: 'Bills received from vendors, with who entered them',
        searchHint: 'Search bill number, vendor or note',
        pdfName: 'Bills-Register.pdf',
        statuses: const [(null, 'All'), ('unpaid', 'Unpaid'), ('part_paid', 'Part paid'), ('paid', 'Paid')],
        provider: billsRegisterProvider,
        pdf: (ref, sid, from, to, status) => ref.read(registersApiProvider).billsPdf(sid, from: from, to: to, status: status),
        totals: (r) => [
          ('Bills', '${r.count}'),
          ('Total', formatInr(r.total)),
          ('Paid', formatInr(r.paid)),
          ('To pay', formatInr(r.outstanding)),
        ],
        columns: [
          AppDataColumn.text('Date', (r) => formatAccountsDate(r.invoiceDate), width: 110, sortKey: (r) => r.invoiceDate),
          AppDataColumn(
              label: 'Bill', width: 150, sortKey: (r) => r.invoiceNumber, cell: (r) => TwoLineCell(r.invoiceNumber, r.expenseHead)),
          AppDataColumn(label: 'Vendor', flex: 3, sortKey: (r) => r.vendor ?? '', cell: (r) => TwoLineCell(r.vendor ?? '—', r.description)),
          AppDataColumn.text('Total', (r) => formatInr(r.total), numeric: true, width: 120, sortKey: (r) => r.total),
          AppDataColumn.text('Paid', (r) => inr(r.paid), numeric: true, width: 120, sortKey: (r) => r.paid),
          AppDataColumn.text('To pay', (r) => inr(r.outstanding), numeric: true, width: 120, sortKey: (r) => r.outstanding),
          AppDataColumn(label: 'Status', width: 110, sortKey: (r) => r.status, cell: (r) => _statusCell(r.status)),
          AppDataColumn(label: 'Entered by', width: 160, sortKey: (r) => r.enteredBy ?? '', cell: (r) => EnteredBy(r.enteredBy)),
        ],
        card: (r) => _card(
          title: r.vendor ?? 'Vendor',
          line2: '${r.invoiceNumber} · ${formatAccountsDate(r.invoiceDate)}',
          line3: r.outstanding > 0 ? 'To pay ${formatInr(r.outstanding)}' : null,
          amount: formatInr(r.total),
          status: r.status,
          enteredBy: r.enteredBy,
        ),
        emptyIcon: Icons.receipt_long_outlined,
        emptyTitle: 'No bills in this period',
      );
}
