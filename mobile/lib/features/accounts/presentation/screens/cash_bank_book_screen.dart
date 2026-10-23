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
import 'package:ar_society_app/features/accounts/presentation/widgets/voucher_hotkeys.dart';
import 'package:ar_society_app/features/accounts/presentation/widgets/register_widgets.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/shared/widgets/app_data_table.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// The cash and bank book: every cash and bank account's receipts and payments in order with the balance after each,
/// and who entered and who approved every line.
class CashBankBookScreen extends ConsumerStatefulWidget {
  const CashBankBookScreen({super.key});

  @override
  ConsumerState<CashBankBookScreen> createState() => _CashBankBookScreenState();
}

class _CashBankBookScreenState extends ConsumerState<CashBankBookScreen> {
  RegisterPeriod _period = RegisterPeriod.thisYear;
  String? _accountId;

  @override
  Widget build(BuildContext context) {
    final societyId = ref.watch(currentUserProvider)?.societyId ?? '';
    final (from, to) = _period.range;
    final key = (societyId: societyId, from: from, to: to, accountId: _accountId);
    final async = ref.watch(cashBankBookProvider(key));
    // The account chips come from the unfiltered book so they stay put while one is chosen.
    final all = ref.watch(cashBankBookProvider((societyId: societyId, from: from, to: to, accountId: null)));
    final desktop = isDesktopLayout(context);

    return VoucherHotkeys(child: AppPage(
      title: 'Cash & Bank Book',
      subtitle: 'Every receipt and payment, with who entered it',
      actions: [
        PdfActions(
          load: async.valueOrNull == null
              ? null
              : () => ref.read(registersApiProvider).cashBankPdf(societyId, from: from, to: to, accountId: _accountId),
          fileName: 'Cash-Bank-Book.pdf',
          subject: 'Cash and bank book',
        ),
      ],
      body: RefreshIndicator(
        onRefresh: () async => ref.invalidate(cashBankBookProvider),
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 96),
          children: [
            RegisterPeriodBar(value: _period, onChanged: (p) => setState(() => _period = p)),
            if (all.valueOrNull case final book? when book.sections.length > 1) ...[
              const SizedBox(height: 10),
              Wrap(spacing: 8, runSpacing: 8, children: [
                ChoiceChip(
                    label: const Text('All accounts'),
                    selected: _accountId == null,
                    onSelected: (_) => setState(() => _accountId = null)),
                for (final s in book.sections)
                  ChoiceChip(
                    avatar: Icon(s.isCash ? Icons.payments_outlined : Icons.account_balance_outlined, size: 16),
                    label: Text(s.accountName),
                    selected: _accountId == s.accountId,
                    onSelected: (_) => setState(() => _accountId = s.accountId),
                  ),
              ]),
            ],
            const SizedBox(height: 14),
            ...async.when(
              loading: () => [const AppLoader()],
              error: (e, _) => [Text(friendlyErrorMessage(e), style: const TextStyle(color: AppTheme.error))],
              data: (book) => [
                RegisterTotals(figures: [
                  ('Opening', drCrOf(book.opening).label),
                  ('Receipts', formatInr(book.receipts)),
                  ('Payments', formatInr(book.payments)),
                  ('Closing', drCrOf(book.closing).label),
                ]),
                if (book.sections.isEmpty)
                  const Padding(
                    padding: EdgeInsets.only(top: 24),
                    child: AppEmptyState(
                        icon: Icons.account_balance_wallet_outlined,
                        title: 'No cash or bank accounts',
                        subtitle: 'Add them in the Chart of Accounts.'),
                  ),
                for (final s in book.sections) ...[
                  const SizedBox(height: 22),
                  _SectionHeader(section: s),
                  const SizedBox(height: 10),
                  if (s.lines.isEmpty)
                    const AppEmptyState(
                        icon: Icons.menu_book_outlined,
                        title: 'No entries in this period',
                        subtitle: 'Approved receipts and payments appear here.')
                  else if (desktop)
                    _SectionTable(section: s)
                  else
                    Container(
                      decoration:
                          BoxDecoration(color: AppTheme.cardBg, borderRadius: BorderRadius.circular(AppTheme.radiusM)),
                      child: Column(children: [
                        for (final (i, l) in s.lines.indexed) ...[
                          if (i > 0) const Divider(height: 1),
                          _LineTile(line: l, onTap: () => showVoucherSheet(context, l.voucherId)),
                        ],
                      ]),
                    ),
                ],
              ],
            ),
          ],
        ),
      ),
    ));
  }
}

class _SectionHeader extends StatelessWidget {
  final BookSection section;
  const _SectionHeader({required this.section});

  @override
  Widget build(BuildContext context) {
    final detail = [
      if (!section.isCash && (section.bankAccountNumber ?? '').isNotEmpty) 'A/c ${section.bankAccountNumber}',
      'Opening ${drCrOf(section.opening).label}',
      'Closing ${drCrOf(section.closing).label}',
    ].join(' · ');
    return Row(children: [
      Icon(section.isCash ? Icons.payments_rounded : Icons.account_balance_rounded,
          size: 20, color: section.isCash ? AppTheme.success : AppTheme.primary),
      const SizedBox(width: 8),
      Expanded(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(section.accountName, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
          Text(detail, style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary)),
        ]),
      ),
    ]);
  }
}

class _SectionTable extends StatelessWidget {
  final BookSection section;
  const _SectionTable({required this.section});

  @override
  Widget build(BuildContext context) {
    return AppDataTable<BookLine>(
      rows: section.lines,
      pageSize: 100,
      onRowTap: (l) => showVoucherSheet(context, l.voucherId),
      columns: [
        AppDataColumn.text('Date', (l) => formatAccountsDate(l.date), width: 110, sortKey: (l) => l.date),
        AppDataColumn(
          label: 'Voucher',
          width: 170,
          sortKey: (l) => l.voucherNumber,
          cell: (l) => Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisSize: MainAxisSize.min, children: [
            Text(l.voucherNumber, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
            Text(voucherTypeLabel(l.voucherType), style: TextStyle(fontSize: 11.5, color: voucherTypeColor(l.voucherType))),
          ]),
        ),
        AppDataColumn(label: 'Particulars', flex: 4, cell: (l) => TwoLineCell(l.particulars, l.narration)),
        AppDataColumn(label: 'Entered by', width: 150, sortKey: (l) => l.enteredBy ?? '', cell: (l) => EnteredBy(l.enteredBy)),
        AppDataColumn(
            label: 'Approved by',
            width: 150,
            sortKey: (l) => l.approvedLabel,
            cell: (l) => EnteredBy(l.approvedBy ?? (l.isAuto ? 'Auto-posted' : null))),
        AppDataColumn.text('Receipts', (l) => inr(l.receipt), numeric: true, width: 120, sortKey: (l) => l.receipt),
        AppDataColumn.text('Payments', (l) => inr(l.payment), numeric: true, width: 120, sortKey: (l) => l.payment),
        AppDataColumn(
          label: 'Balance',
          numeric: true,
          width: 140,
          cell: (l) => Align(alignment: Alignment.centerRight, child: DrCrText(drCrOf(l.balance))),
        ),
      ],
    );
  }
}

class _LineTile extends StatelessWidget {
  final BookLine line;
  final VoidCallback onTap;
  const _LineTile({required this.line, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final receipt = line.receipt > 0;
    return InkWell(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(14, 10, 14, 10),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(line.particulars,
                  maxLines: 2, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w600)),
              const SizedBox(height: 2),
              Text('${formatAccountsDate(line.date)} · ${line.voucherNumber}',
                  style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
              Text('Entered by ${line.enteredBy ?? '—'}${line.approvedBy != null ? ' · Approved by ${line.approvedBy}' : line.isAuto ? ' · Auto-posted' : ''}',
                  style: const TextStyle(fontSize: 12, color: AppTheme.textTertiary)),
            ]),
          ),
          const SizedBox(width: 10),
          Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
            Text('${formatInr(receipt ? line.receipt : line.payment)} ${receipt ? 'In' : 'Out'}',
                style: TextStyle(
                    fontSize: 13.5,
                    fontWeight: FontWeight.w700,
                    color: receipt ? AppTheme.success : AppTheme.textPrimary,
                    fontFeatures: const [FontFeature.tabularFigures()])),
            const SizedBox(height: 2),
            Text('Bal ${drCrOf(line.balance).label}', style: const TextStyle(fontSize: 11.5, color: AppTheme.textSecondary)),
          ]),
        ]),
      ),
    );
  }
}
