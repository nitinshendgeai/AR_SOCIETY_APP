import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/layout/app_sheet.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart';
import 'package:ar_society_app/features/accounts/presentation/providers/accounts_providers.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/widgets/billing_sheet_frame.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

Color voucherTypeColor(String type) => switch (type) {
      'receipt' => AppTheme.success,
      'payment' => AppTheme.error,
      'contra' => AppTheme.secondary,
      'bill' => AppTheme.primary,
      'purchase' => AppTheme.warning,
      _ => AppTheme.textSecondary,
    };

/// "RV · Receipt" style chip for a voucher type.
class VoucherTypeChip extends StatelessWidget {
  final String type;
  const VoucherTypeChip(this.type, {super.key});

  @override
  Widget build(BuildContext context) {
    final color = voucherTypeColor(type);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(color: color.withOpacity(0.1), borderRadius: BorderRadius.circular(6)),
      child: Text(voucherTypeLabel(type),
          style: TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: color)),
    );
  }
}

/// A Dr/Cr balance, coloured: debit in the primary text colour, credit in
/// the brand colour, nil greyed.
class DrCrText extends StatelessWidget {
  final DrCr value;
  final double fontSize;
  final FontWeight weight;
  const DrCrText(this.value, {super.key, this.fontSize = 13.5, this.weight = FontWeight.w600});

  @override
  Widget build(BuildContext context) => Text(
        value.label,
        textAlign: TextAlign.right,
        style: TextStyle(
          fontSize: fontSize,
          fontWeight: weight,
          color: value.isZero
              ? AppTheme.textTertiary
              : (value.type == 'Cr' ? AppTheme.primaryDark : AppTheme.textPrimary),
          fontFeatures: const [FontFeature.tabularFigures()],
        ),
      );
}

/// Grouped, searchable ledger list; returns the chosen ledger.
Future<LedgerAccount?> pickLedger(
  BuildContext context,
  List<LedgerAccount> ledgers, {
  String title = 'Choose ledger',
}) =>
    showAppSheet<LedgerAccount>(
      context: context,
      builder: (_) => _LedgerPickerSheet(ledgers: ledgers, title: title),
    );

class _LedgerPickerSheet extends StatefulWidget {
  final List<LedgerAccount> ledgers;
  final String title;
  const _LedgerPickerSheet({required this.ledgers, required this.title});

  @override
  State<_LedgerPickerSheet> createState() => _LedgerPickerSheetState();
}

class _LedgerPickerSheetState extends State<_LedgerPickerSheet> {
  String _q = '';

  @override
  Widget build(BuildContext context) {
    final q = _q.toLowerCase();
    final rows = widget.ledgers
        .where((l) => q.isEmpty || l.name.toLowerCase().contains(q) || (l.code ?? '').contains(q) ||
            (l.groupName ?? '').toLowerCase().contains(q))
        .toList();
    final byGroup = <String, List<LedgerAccount>>{};
    for (final l in rows) {
      byGroup.putIfAbsent(l.groupName ?? '', () => []).add(l);
    }
    return _SheetScaffold(
      title: widget.title,
      search: (v) => setState(() => _q = v),
      children: [
        if (rows.isEmpty)
          const Padding(
            padding: EdgeInsets.all(24),
            child: Text('No ledger matches', style: TextStyle(color: AppTheme.textSecondary)),
          ),
        for (final entry in byGroup.entries) ...[
          Padding(
            padding: const EdgeInsets.fromLTRB(4, 12, 4, 4),
            child: Text(entry.key.toUpperCase(),
                style: const TextStyle(
                    fontSize: 11, letterSpacing: .4, fontWeight: FontWeight.w700, color: AppTheme.textSecondary)),
          ),
          for (final l in entry.value)
            ListTile(
              dense: true,
              contentPadding: const EdgeInsets.symmetric(horizontal: 4),
              leading: Icon(
                l.isCash
                    ? Icons.payments_outlined
                    : l.isBank
                        ? Icons.account_balance_outlined
                        : Icons.menu_book_outlined,
                size: 18,
                color: AppTheme.textSecondary,
              ),
              title: Text(l.name, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w500)),
              trailing: l.code == null
                  ? null
                  : Text(l.code!, style: const TextStyle(fontSize: 12, color: AppTheme.textTertiary)),
              onTap: () => Navigator.pop(context, l),
            ),
        ],
      ],
    );
  }
}

/// Searchable flat list (from the members' ledger); returns the flat.
Future<MemberBalance?> pickFlat(BuildContext context, List<MemberBalance> flats) =>
    showAppSheet<MemberBalance>(context: context, builder: (_) => _FlatPickerSheet(flats: flats));

class _FlatPickerSheet extends StatefulWidget {
  final List<MemberBalance> flats;
  const _FlatPickerSheet({required this.flats});

  @override
  State<_FlatPickerSheet> createState() => _FlatPickerSheetState();
}

class _FlatPickerSheetState extends State<_FlatPickerSheet> {
  String _q = '';

  @override
  Widget build(BuildContext context) {
    final q = _q.toLowerCase();
    final rows = widget.flats
        .where((f) => q.isEmpty || f.flatLabel.toLowerCase().contains(q) || f.memberName.toLowerCase().contains(q))
        .toList();
    return _SheetScaffold(
      title: 'Choose flat',
      search: (v) => setState(() => _q = v),
      children: [
        for (final f in rows)
          ListTile(
            dense: true,
            contentPadding: const EdgeInsets.symmetric(horizontal: 4),
            title: Text(f.flatLabel, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
            subtitle: Text(f.memberName, style: const TextStyle(fontSize: 12)),
            trailing: DrCrText(f.balance, fontSize: 12.5, weight: FontWeight.w500),
            onTap: () => Navigator.pop(context, f),
          ),
      ],
    );
  }
}

class _SheetScaffold extends StatelessWidget {
  final String title;
  final ValueChanged<String> search;
  final List<Widget> children;
  const _SheetScaffold({required this.title, required this.search, required this.children});

  @override
  Widget build(BuildContext context) => Container(
        constraints: BoxConstraints(maxHeight: MediaQuery.of(context).size.height * 0.85),
        decoration: const BoxDecoration(
          color: AppTheme.cardBg,
          borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
        ),
        padding: EdgeInsets.fromLTRB(16, 20, 16, MediaQuery.of(context).viewInsets.bottom + 12),
        child: SafeArea(
          top: false,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(title, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
              const SizedBox(height: 12),
              TextField(
                autofocus: true,
                onChanged: search,
                decoration: const InputDecoration(
                  prefixIcon: Icon(Icons.search_rounded, size: 20),
                  hintText: 'Search',
                  isDense: true,
                ),
              ),
              const SizedBox(height: 4),
              Flexible(child: ListView(shrinkWrap: true, children: children)),
            ],
          ),
        ),
      );
}

/// Voucher detail: its lines, narration, where it came from — and, for a
/// voucher the society entered, Cancel.
Future<void> showVoucherSheet(BuildContext context, String voucherId) =>
    showAppSheet(context: context, panelWidth: 560, builder: (_) => _VoucherSheet(voucherId: voucherId));

class _VoucherSheet extends ConsumerStatefulWidget {
  final String voucherId;
  const _VoucherSheet({required this.voucherId});

  @override
  ConsumerState<_VoucherSheet> createState() => _VoucherSheetState();
}

class _VoucherSheetState extends ConsumerState<_VoucherSheet> {
  bool _busy = false;

  Future<void> _cancel(Voucher v) async {
    final reason = TextEditingController();
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text('Cancel ${v.voucherNumber}?'),
        content: Column(mainAxisSize: MainAxisSize.min, children: [
          const Text('The voucher stays on record, marked cancelled, and drops out of every ledger.',
              style: TextStyle(fontSize: 13, color: AppTheme.textSecondary)),
          const SizedBox(height: 12),
          TextField(controller: reason, decoration: const InputDecoration(labelText: 'Reason')),
        ]),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Keep')),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: AppTheme.error),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Cancel voucher'),
          ),
        ],
      ),
    );
    if (ok != true) return;
    if (reason.text.trim().length < 3) {
      if (mounted) showErrorToast(context, Exception('Give a reason for cancelling'));
      return;
    }
    setState(() => _busy = true);
    try {
      await ref.read(accountsApiProvider).cancelVoucher(v.id, reason.text.trim());
      invalidateBooks(ref);
      if (mounted) {
        AppToast.success(context, '${v.voucherNumber} cancelled');
        Navigator.pop(context);
      }
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final async = ref.watch(voucherProvider(widget.voucherId));
    return BillingSheetFrame(
      title: 'Voucher',
      child: async.when(
        loading: () => const Padding(padding: EdgeInsets.all(32), child: Center(child: CircularProgressIndicator())),
        error: (e, _) => Text(friendlyErrorMessage(e), style: const TextStyle(color: AppTheme.error)),
        data: (v) => Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Row(children: [
            VoucherTypeChip(v.voucherType),
            const SizedBox(width: 8),
            Expanded(
              child: Text(v.voucherNumber,
                  style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700)),
            ),
            Text(formatAccountsDate(v.voucherDate),
                style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary)),
          ]),
          if (v.isCancelled) ...[
            const SizedBox(height: 10),
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(color: AppTheme.errorSoft, borderRadius: BorderRadius.circular(10)),
              child: Text('Cancelled${v.cancelReason == null ? '' : ': ${v.cancelReason}'}',
                  style: const TextStyle(fontSize: 13, color: AppTheme.error, fontWeight: FontWeight.w600)),
            ),
          ],
          const SizedBox(height: 14),
          _EntriesTable(v),
          if ((v.narration ?? '').isNotEmpty) ...[
            const SizedBox(height: 14),
            const Text('Narration', style: TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
            const SizedBox(height: 2),
            Text(v.narration!, style: const TextStyle(fontSize: 14)),
          ],
          const SizedBox(height: 12),
          Wrap(spacing: 16, runSpacing: 4, children: [
            if ((v.reference ?? '').isNotEmpty) _meta('Reference', v.reference!),
            _meta('Financial year', v.fiscalYear),
            if (v.createdByName != null) _meta('Entered by', v.createdByName!),
          ]),
          if (v.sourceLabel != null) ...[
            const SizedBox(height: 12),
            Row(children: [
              const Icon(Icons.auto_awesome_rounded, size: 16, color: AppTheme.primary),
              const SizedBox(width: 6),
              Expanded(
                child: Text('${v.sourceLabel} — cancel it from there, not here.',
                    style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary)),
              ),
            ]),
          ],
          if (!v.isAuto && !v.isCancelled) ...[
            const SizedBox(height: 18),
            OutlinedButton.icon(
              style: OutlinedButton.styleFrom(foregroundColor: AppTheme.error),
              onPressed: _busy ? null : () => _cancel(v),
              icon: const Icon(Icons.block_rounded, size: 18),
              label: const Text('Cancel voucher'),
            ),
          ],
        ]),
      ),
    );
  }

  Widget _meta(String label, String value) => Text.rich(TextSpan(children: [
        TextSpan(text: '$label: ', style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary)),
        TextSpan(text: value, style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.w600)),
      ]));
}

class _EntriesTable extends StatelessWidget {
  final Voucher v;
  const _EntriesTable(this.v);

  @override
  Widget build(BuildContext context) {
    const head = TextStyle(fontSize: 11.5, fontWeight: FontWeight.w700, color: AppTheme.textSecondary);
    const num = TextStyle(fontSize: 13.5, fontFeatures: [FontFeature.tabularFigures()]);
    Widget amount(double v) =>
        SizedBox(width: 96, child: Text(v == 0 ? '' : formatInr(v), textAlign: TextAlign.right, style: num));
    return Container(
      decoration: BoxDecoration(
        border: Border.all(color: AppTheme.border),
        borderRadius: BorderRadius.circular(AppTheme.radiusS),
      ),
      child: Column(children: [
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          color: AppTheme.surface,
          child: const Row(children: [
            Expanded(child: Text('PARTICULARS', style: head)),
            SizedBox(width: 96, child: Text('DEBIT', textAlign: TextAlign.right, style: head)),
            SizedBox(width: 96, child: Text('CREDIT', textAlign: TextAlign.right, style: head)),
          ]),
        ),
        for (final e in [...v.debits, ...v.credits])
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 9),
            child: Row(children: [
              Expanded(
                child: Padding(
                  padding: EdgeInsets.only(left: e.credit > 0 ? 16 : 0),
                  child: Text('${e.credit > 0 ? 'To ' : ''}${e.title}',
                      style: const TextStyle(fontSize: 13.5)),
                ),
              ),
              amount(e.debit),
              amount(e.credit),
            ]),
          ),
        const Divider(height: 1),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 9),
          child: Row(children: [
            const Expanded(child: Text('Total', style: TextStyle(fontSize: 13.5, fontWeight: FontWeight.w700))),
            SizedBox(
                width: 96,
                child: Text(formatInr(v.amount),
                    textAlign: TextAlign.right, style: num.copyWith(fontWeight: FontWeight.w700))),
            SizedBox(
                width: 96,
                child: Text(formatInr(v.amount),
                    textAlign: TextAlign.right, style: num.copyWith(fontWeight: FontWeight.w700))),
          ]),
        ),
      ]),
    );
  }
}
