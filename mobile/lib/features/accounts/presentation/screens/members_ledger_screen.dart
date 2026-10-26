import 'package:flutter/material.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/layout/app_shell.dart' show isDesktopLayout;
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart';
import 'package:ar_society_app/features/accounts/presentation/providers/accounts_providers.dart';
import 'package:ar_society_app/features/accounts/presentation/screens/accounts_screen.dart' show ledgerRoute;
import 'package:ar_society_app/features/accounts/presentation/widgets/accounts_widgets.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/shared/widgets/app_data_table.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';

enum _Show { all, dues, advance }

/// Every flat's account with the society: Dr — the member owes (bills
/// not yet paid), Cr — paid in advance. Opens the member's ledger.
class MembersLedgerScreen extends ConsumerStatefulWidget {
  const MembersLedgerScreen({super.key});

  @override
  ConsumerState<MembersLedgerScreen> createState() => _MembersLedgerScreenState();
}

class _MembersLedgerScreenState extends ConsumerState<MembersLedgerScreen> {
  String _q = '';
  _Show _show = _Show.all;

  @override
  Widget build(BuildContext context) {
    final societyId = ref.watch(currentUserProvider)?.societyId;
    if (societyId == null) return const Scaffold(body: Center(child: Text('No society context')));
    final async = ref.watch(membersLedgerProvider(societyId));
    final desktop = isDesktopLayout(context);

    return AppPage(
      title: "Members' Ledger",
      actions: [
        AppBarTextAction(
          onPressed: () => context.push(AppRoutes.defaulters),
          icon: Icons.warning_amber_rounded,
          label: 'Defaulters',
        ),
        PdfActions(
          load: async.valueOrNull == null ? null : () => ref.read(accountsApiProvider).membersLedgerPdf(societyId),
          fileName: 'Members-Ledger-${apiDate(DateTime.now())}.pdf',
          subject: "Members' Ledger",
        ),
        const SizedBox(width: 8),
      ],
      body: RefreshIndicator(
        onRefresh: () async => ref.invalidate(membersLedgerProvider(societyId)),
        child: async.when(
          loading: () => const AppLoader(),
          error: (e, _) => ListView(children: [
            Padding(
              padding: const EdgeInsets.all(24),
              child: Text(friendlyErrorMessage(e), style: const TextStyle(color: AppTheme.error)),
            ),
          ]),
          data: (ledger) {
            final q = _q.toLowerCase();
            final rows = ledger.members.where((m) {
              if (q.isNotEmpty &&
                  !m.flatLabel.toLowerCase().contains(q) &&
                  !m.memberName.toLowerCase().contains(q)) {
                return false;
              }
              return switch (_show) {
                _Show.dues => m.dues > 0,
                _Show.advance => m.advance > 0,
                _Show.all => true,
              };
            }).toList();
            final receivable = ledger.members.fold<double>(0, (s, m) => s + m.dues);
            final advance = ledger.members.fold<double>(0, (s, m) => s + m.advance);
            void open(MemberBalance m) => context.push(Uri(
                  path: ledgerRoute(ledger.accountId),
                  queryParameters: {'flat': m.flatId, 'title': '${m.flatLabel} · ${m.memberName}'},
                ).toString());

            return ResponsiveBody(
              maxWidth: 1000,
              child: ListView(
                padding: const EdgeInsets.fromLTRB(16, 16, 16, 96),
                children: [
                  KpiGrid(cards: [
                    KpiCard(
                      icon: Icons.call_received_rounded,
                      label: 'Dues receivable',
                      value: formatInr(receivable),
                      note: '${ledger.members.where((m) => m.dues > 0).length} flats with dues',
                      color: AppTheme.warning,
                      onTap: () => setState(() => _show = _Show.dues),
                    ),
                    KpiCard(
                      icon: Icons.savings_rounded,
                      label: 'Advance maintenance held',
                      value: formatInr(advance),
                      note: '${ledger.members.where((m) => m.advance > 0).length} flats paid in advance',
                      color: AppTheme.success,
                      onTap: () => setState(() => _show = _Show.advance),
                    ),
                  ]),
                  const SizedBox(height: 14),
                  Wrap(spacing: 8, runSpacing: 8, crossAxisAlignment: WrapCrossAlignment.center, children: [
                    for (final (s, label) in [(_Show.all, 'All flats'), (_Show.dues, 'With dues'), (_Show.advance, 'In advance')])
                      ChoiceChip(label: Text(label), selected: _show == s, onSelected: (_) => setState(() => _show = s)),
                  ]),
                  const SizedBox(height: 10),
                  TableSearchField(hint: 'Search flat or member', onChanged: (v) => setState(() => _q = v)),
                  const SizedBox(height: 12),
                  if (rows.isEmpty)
                    const AppEmptyState(icon: Icons.groups_2_outlined, title: 'No flats to show')
                  else if (desktop)
                    AppDataTable<MemberBalance>(
                      rows: rows,
                      pageSize: 100,
                      onRowTap: open,
                      columns: [
                        AppDataColumn.text('Flat', (m) => m.flatLabel, width: 140, bold: true),
                        AppDataColumn.text('Member', (m) => m.memberName, flex: 3),
                        AppDataColumn(
                          label: 'Dues',
                          numeric: true,
                          width: 120,
                          sortKey: (m) => m.dues,
                          cell: (m) => Align(alignment: Alignment.centerRight, child: Text(m.dues > 0 ? formatInr(m.dues) : '')),
                        ),
                        AppDataColumn(
                          label: 'Advance',
                          numeric: true,
                          width: 120,
                          sortKey: (m) => m.advance,
                          cell: (m) => Align(alignment: Alignment.centerRight, child: Text(m.advance > 0 ? formatInr(m.advance) : '')),
                        ),
                        AppDataColumn(
                          label: 'Balance',
                          numeric: true,
                          width: 180,
                          sortKey: (m) => m.signed,
                          cell: (m) => Align(alignment: Alignment.centerRight, child: DrCrText(m.balance)),
                        ),
                      ],
                    )
                  else
                    Container(
                      decoration:
                          BoxDecoration(color: AppTheme.cardBg, borderRadius: BorderRadius.circular(AppTheme.radiusM)),
                      child: Column(children: [
                        for (final (i, m) in rows.indexed) ...[
                          if (i > 0) const Divider(height: 1),
                          ListTile(
                            title: Text(m.flatLabel, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
                            subtitle: Text(
                              [
                                m.memberName,
                                if (m.dues > 0 && m.advance > 0) 'Dues ${formatInr(m.dues)} · Advance ${formatInr(m.advance)}',
                              ].join('\n'),
                              style: const TextStyle(fontSize: 12.5)),
                            trailing: Row(mainAxisSize: MainAxisSize.min, children: [
                              DrCrText(m.balance),
                              const Icon(Icons.chevron_right_rounded, color: AppTheme.textTertiary),
                            ]),
                            onTap: () => open(m),
                          ),
                        ],
                      ]),
                    ),
                ],
              ),
            );
          },
        ),
      ),
    );
  }
}
