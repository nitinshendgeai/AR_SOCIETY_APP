import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:share_plus/share_plus.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/layout/app_shell.dart' show isDesktopLayout;
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart';
import 'package:ar_society_app/features/accounts/presentation/providers/accounts_providers.dart';
import 'package:ar_society_app/features/accounts/presentation/screens/accounts_screen.dart' show ledgerRoute;
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/shared/utils/file_saver.dart';
import 'package:ar_society_app/shared/widgets/app_data_table.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// One financial statement for a year, as on paper: a two-sided statement
/// (expenditure | income, liabilities | assets, receipts | payments) with
/// this year's and last year's figures, or a table. Ledgers open their
/// ledger account for the year; the PDF is the printed statement.
class FinancialReportScreen extends ConsumerStatefulWidget {
  final String report;
  final String fy;
  const FinancialReportScreen({super.key, required this.report, required this.fy});

  @override
  ConsumerState<FinancialReportScreen> createState() => _FinancialReportScreenState();
}

class _FinancialReportScreenState extends ConsumerState<FinancialReportScreen> {
  bool _busy = false;

  String get _title => kFinancialReports[widget.report]?.$1 ?? 'Statement';

  Future<void> _pdf(String societyId, {required bool share}) async {
    setState(() => _busy = true);
    final fileName = '${_title.replaceAll('&', 'and').replaceAll(' ', '-')}-FY-${widget.fy}.pdf';
    try {
      final Uint8List bytes = await ref.read(accountsApiProvider).reportPdf(societyId, widget.report, widget.fy);
      if (share) {
        await Share.shareXFiles(
          [XFile.fromData(bytes, name: fileName, mimeType: 'application/pdf')],
          fileNameOverrides: [fileName],
          subject: '$_title — FY ${widget.fy}',
        );
      } else if (await saveFileBytes(bytes, fileName, mimeType: 'application/pdf') && mounted) {
        AppToast.success(context, '$fileName downloaded');
      }
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _openLedger(String accountId) {
    final start = DateTime(int.parse(widget.fy.substring(0, 4)), 4, 1);
    final end = DateTime(start.year + 1, 3, 31);
    context.push(Uri(path: ledgerRoute(accountId), queryParameters: {
      'from': apiDate(start),
      'to': apiDate(end),
    }).toString());
  }

  @override
  Widget build(BuildContext context) {
    final societyId = ref.watch(currentUserProvider)?.societyId;
    if (societyId == null) return const Scaffold(body: Center(child: Text('No society context')));
    final key = (societyId: societyId, report: widget.report, fy: widget.fy);
    final async = ref.watch(financialReportProvider(key));
    final desktop = isDesktopLayout(context);

    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(title: Text('$_title · FY ${widget.fy}', overflow: TextOverflow.ellipsis), actions: [
        IconButton(
          tooltip: 'Share PDF',
          onPressed: _busy || async.valueOrNull == null ? null : () => _pdf(societyId, share: true),
          icon: const Icon(Icons.ios_share_rounded),
        ),
        if (desktop)
          HeaderActionButton(
            icon: Icons.download_rounded,
            label: 'Download PDF',
            onPressed: _busy || async.valueOrNull == null ? null : () => _pdf(societyId, share: false),
          )
        else
          IconButton(
            tooltip: 'Download PDF',
            onPressed: _busy || async.valueOrNull == null ? null : () => _pdf(societyId, share: false),
            icon: const Icon(Icons.download_rounded),
          ),
      ]),
      body: RefreshIndicator(
        onRefresh: () async => ref.invalidate(financialReportProvider(key)),
        child: async.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, _) => ListView(children: [
            Padding(
              padding: const EdgeInsets.all(24),
              child: Text(friendlyErrorMessage(e), style: const TextStyle(color: AppTheme.error)),
            ),
          ]),
          data: (r) => ResponsiveBody(
            maxWidth: r.twoSided ? 1280 : 900,
            child: ListView(
              padding: const EdgeInsets.fromLTRB(16, 16, 16, 96),
              children: [
                Text(r.heading, textAlign: TextAlign.center,
                    style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
                if (r.provisional)
                  const Padding(
                    padding: EdgeInsets.only(top: 4),
                    child: Text('Provisional — the financial year is not over yet.',
                        textAlign: TextAlign.center,
                        style: TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                  ),
                const SizedBox(height: 12),
                if (!r.balanced) const _Banner('The statement doesn\'t tally — check the opening balances.',
                    AppTheme.error),
                for (final n in r.notes) _Banner(n, AppTheme.warning),
                if (r.result != null) ...[
                  _ResultCard(r.result!, r.columns),
                  const SizedBox(height: 12),
                ],
                if (r.twoSided)
                  LayoutBuilder(builder: (context, c) {
                    final sideBySide = c.maxWidth >= 980 && r.sides.length == 2;
                    final width = sideBySide ? (c.maxWidth - 12) / 2 : c.maxWidth;
                    final sides = [
                      for (final s in r.sides)
                        _SideCard(side: s, columns: r.columns, onLedger: _openLedger, width: width,
                            stretch: sideBySide),
                    ];
                    if (sideBySide) {
                      return IntrinsicHeight(
                        child: Row(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                          Expanded(child: sides[0]),
                          const SizedBox(width: 12),
                          Expanded(child: sides[1]),
                        ]),
                      );
                    }
                    return Column(children: [
                      for (final s in sides) Padding(padding: const EdgeInsets.only(bottom: 12), child: s),
                    ]);
                  })
                else
                  _TableCard(report: r, onLedger: _openLedger),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

String _orDash(String s) => s.isEmpty ? '—' : s;

const _num = TextStyle(fontSize: 13, fontFeatures: [FontFeature.tabularFigures()]);

class _Banner extends StatelessWidget {
  final String text;
  final Color color;
  const _Banner(this.text, this.color);

  @override
  Widget build(BuildContext context) => Container(
        margin: const EdgeInsets.only(bottom: 10),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: color.withOpacity(0.08),
          borderRadius: BorderRadius.circular(AppTheme.radiusS),
          border: Border.all(color: color.withOpacity(0.3)),
        ),
        child: Row(children: [
          Icon(Icons.info_outline_rounded, size: 18, color: color),
          const SizedBox(width: 8),
          Expanded(child: Text(text, style: const TextStyle(fontSize: 12.5))),
        ]),
      );
}

class _ResultCard extends StatelessWidget {
  final ReportRow result;
  final List<String> columns;
  const _ResultCard(this.result, this.columns);

  @override
  Widget build(BuildContext context) {
    final v = result.values.isEmpty ? null : result.values.first;
    final surplus = (v ?? 0) >= 0;
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: (surplus ? AppTheme.success : AppTheme.error).withOpacity(0.08),
        borderRadius: BorderRadius.circular(AppTheme.radiusM),
      ),
      child: Row(children: [
        Icon(surplus ? Icons.trending_up_rounded : Icons.trending_down_rounded,
            color: surplus ? AppTheme.success : AppTheme.error),
        const SizedBox(width: 10),
        Expanded(
          child: Text(surplus ? 'Surplus for FY ${columns.first}' : 'Deficit for FY ${columns.first}',
              style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
        ),
        Text(formatInr((v ?? 0).abs()),
            style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700,
                fontFeatures: [FontFeature.tabularFigures()])),
      ]),
    );
  }
}

/// One side of a two-sided statement.
class _SideCard extends StatelessWidget {
  final ReportSide side;
  final List<String> columns;
  final ValueChanged<String> onLedger;
  final double width;

  /// Side by side with the other side: fills the shared height, totals at the bottom.
  final bool stretch;
  const _SideCard({required this.side, required this.columns, required this.onLedger, required this.width,
      this.stretch = false});

  @override
  Widget build(BuildContext context) {
    {
      // This year's figure always; last year's beside it when there's room.
      final showPrev = columns.length > 1 && width >= 430;
      final amountW = width >= 430 ? 112.0 : 96.0;
      Widget amounts(List<double?> v, {bool bold = false, Color? color}) => Row(mainAxisSize: MainAxisSize.min, children: [
            if (showPrev)
              SizedBox(
                width: amountW,
                child: Text(formatStatementAmount(v.length > 1 ? v[1] : null), textAlign: TextAlign.right,
                    style: _num.copyWith(color: AppTheme.textSecondary, fontWeight: bold ? FontWeight.w600 : null)),
              ),
            SizedBox(
              width: amountW,
              child: Text(formatStatementAmount(v.isEmpty ? null : v[0]), textAlign: TextAlign.right,
                  style: _num.copyWith(fontWeight: bold ? FontWeight.w700 : FontWeight.w500, color: color)),
            ),
          ]);

      return Container(
        decoration: BoxDecoration(color: AppTheme.cardBg, borderRadius: BorderRadius.circular(AppTheme.radiusM)),
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Container(
            padding: const EdgeInsets.fromLTRB(14, 10, 14, 10),
            decoration: const BoxDecoration(
              color: AppTheme.primarySoft,
              borderRadius: BorderRadius.vertical(top: Radius.circular(AppTheme.radiusM)),
            ),
            child: Row(children: [
              Expanded(
                child: Text(side.title.toUpperCase(),
                    style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.w800, letterSpacing: .4,
                        color: AppTheme.primaryDark)),
              ),
              if (showPrev)
                SizedBox(
                  width: amountW,
                  child: Text('FY ${columns[1]}', textAlign: TextAlign.right,
                      style: const TextStyle(fontSize: 11.5, fontWeight: FontWeight.w700, color: AppTheme.textSecondary)),
                ),
              SizedBox(
                width: amountW,
                child: Text('FY ${columns[0]}', textAlign: TextAlign.right,
                    style: const TextStyle(fontSize: 11.5, fontWeight: FontWeight.w700, color: AppTheme.primaryDark)),
              ),
            ]),
          ),
          for (final s in side.sections) ...[
            if (s.title != null)
              Padding(
                padding: const EdgeInsets.fromLTRB(14, 10, 14, 4),
                child: Row(children: [
                  Expanded(
                    child: Text(s.title!, style: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w700)),
                  ),
                  amounts(s.total, bold: true),
                ]),
              ),
            for (final r in s.rows)
              InkWell(
                onTap: r.accountId == null ? null : () => onLedger(r.accountId!),
                child: Padding(
                  padding: EdgeInsets.fromLTRB(s.title == null ? 14 : 26, 5, 14, 5),
                  child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Expanded(
                      child: Text(r.label,
                          style: TextStyle(
                              fontSize: 12.8,
                              fontWeight: r.bold ? FontWeight.w700 : FontWeight.w400,
                              color: r.accountId != null ? AppTheme.textPrimary : AppTheme.textSecondary)),
                    ),
                    amounts(r.values, bold: r.bold),
                  ]),
                ),
              ),
          ],
          if (stretch) const Spacer() else const SizedBox(height: 6),
          const Divider(height: 1),
          Padding(
            padding: const EdgeInsets.fromLTRB(14, 10, 14, 12),
            child: Row(children: [
              const Expanded(child: Text('TOTAL', style: TextStyle(fontSize: 13.5, fontWeight: FontWeight.w800))),
              amounts(side.total, bold: true),
            ]),
          ),
        ]),
      );
    }
  }
}

/// Trial Balance / Schedule of Funds.
class _TableCard extends StatelessWidget {
  final FinancialReport report;
  final ValueChanged<String> onLedger;
  const _TableCard({required this.report, required this.onLedger});

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(builder: (context, c) {
      final amountW = c.maxWidth < 500 ? 96.0 : 118.0;
      final fits = c.maxWidth >= 150 + amountW * report.columns.length;
      Widget cells(List<double?> v, {bool bold = false}) => Row(mainAxisSize: MainAxisSize.min, children: [
            for (var i = 0; i < report.columns.length; i++)
              SizedBox(
                width: amountW,
                child: Text(formatStatementAmount(i < v.length ? v[i] : null), textAlign: TextAlign.right,
                    style: _num.copyWith(fontWeight: bold ? FontWeight.w700 : FontWeight.w500)),
              ),
          ]);

      Widget row(ReportRow r) {
        final group = r.level == 0 || r.bold;
        final label = Text(r.code == null ? r.label : '${r.code}  ${r.label}',
            style: TextStyle(fontSize: 13, fontWeight: group ? FontWeight.w700 : FontWeight.w400));
        final child = fits
            ? Row(children: [Expanded(child: label), cells(r.values, bold: group)])
            : Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                label,
                const SizedBox(height: 4),
                Wrap(spacing: 14, runSpacing: 2, children: [
                  for (var i = 0; i < report.columns.length; i++)
                    if (i < r.values.length && (r.values[i] ?? 0) != 0)
                      Text('${report.columns[i].replaceAll(' (₹)', '')}: ${formatStatementAmount(r.values[i])}',
                          style: _num.copyWith(fontSize: 12, color: AppTheme.textSecondary)),
                ]),
              ]);
        return InkWell(
          onTap: r.accountId == null ? null : () => onLedger(r.accountId!),
          child: Container(
            color: group ? AppTheme.surface.withOpacity(0.6) : null,
            padding: EdgeInsets.fromLTRB(group ? 14 : 26, 7, 14, 7),
            child: child,
          ),
        );
      }

      return Container(
        decoration: BoxDecoration(color: AppTheme.cardBg, borderRadius: BorderRadius.circular(AppTheme.radiusM)),
        clipBehavior: Clip.antiAlias,
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          if (fits)
            Container(
              color: AppTheme.primarySoft,
              padding: const EdgeInsets.fromLTRB(14, 10, 14, 10),
              child: Row(children: [
                const Expanded(
                  child: Text('PARTICULARS',
                      style: TextStyle(fontSize: 12, fontWeight: FontWeight.w800, color: AppTheme.primaryDark)),
                ),
                for (final col in report.columns)
                  SizedBox(
                    width: amountW,
                    child: Text(col.toUpperCase(), textAlign: TextAlign.right,
                        style: const TextStyle(fontSize: 11.5, fontWeight: FontWeight.w800, color: AppTheme.primaryDark)),
                  ),
              ]),
            ),
          if (report.rows.isEmpty)
            const Padding(
              padding: EdgeInsets.all(24),
              child: Text('Nothing to show for this year.', style: TextStyle(color: AppTheme.textSecondary)),
            ),
          for (final r in report.rows) row(r),
          const Divider(height: 1),
          Padding(
            padding: const EdgeInsets.fromLTRB(14, 10, 14, 12),
            child: fits
                ? Row(children: [
                    const Expanded(child: Text('TOTAL', style: TextStyle(fontSize: 13.5, fontWeight: FontWeight.w800))),
                    cells(report.totals, bold: true),
                  ])
                : Wrap(spacing: 14, runSpacing: 4, children: [
                    const Text('TOTAL', style: TextStyle(fontSize: 13.5, fontWeight: FontWeight.w800)),
                    for (var i = 0; i < report.columns.length; i++)
                      Text('${report.columns[i].replaceAll(' (₹)', '')}: '
                          '${_orDash(formatStatementAmount(report.totals.length > i ? report.totals[i] : null))}',
                          style: _num.copyWith(fontWeight: FontWeight.w700)),
                  ]),
          ),
        ]),
      );
    });
  }
}
