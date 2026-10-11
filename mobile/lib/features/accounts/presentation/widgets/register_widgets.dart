import 'package:flutter/material.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart' show financialYearStart, formatAccountsDate, formatInr;

enum RegisterPeriodKind { thisMonth, thisYear, lastYear, all, custom }

/// The period a register shows: this month, this financial year, last year, everything, or chosen dates.
class RegisterPeriod {
  final RegisterPeriodKind kind;
  final DateTimeRange? custom;
  const RegisterPeriod(this.kind, [this.custom]);

  static const thisYear = RegisterPeriod(RegisterPeriodKind.thisYear);

  /// (from, to); null: no limit on that side.
  (DateTime?, DateTime?) get range {
    final today = DateTime.now();
    final fy = financialYearStart(today);
    return switch (kind) {
      RegisterPeriodKind.thisMonth => (DateTime(today.year, today.month, 1), null),
      RegisterPeriodKind.thisYear => (fy, null),
      RegisterPeriodKind.lastYear => (DateTime(fy.year - 1, 4, 1), DateTime(fy.year, 3, 31)),
      RegisterPeriodKind.all => (null, null),
      RegisterPeriodKind.custom => (custom?.start, custom?.end),
    };
  }

  @override
  bool operator ==(Object other) => other is RegisterPeriod && other.kind == kind && other.custom == custom;

  @override
  int get hashCode => Object.hash(kind, custom);
}

/// The period chips at the top of a register.
class RegisterPeriodBar extends StatelessWidget {
  final RegisterPeriod value;
  final ValueChanged<RegisterPeriod> onChanged;
  const RegisterPeriodBar({super.key, required this.value, required this.onChanged});

  Future<void> _pickCustom(BuildContext context) async {
    final today = DateTime.now();
    final picked = await showDateRangePicker(
      context: context,
      firstDate: DateTime(2000),
      lastDate: DateTime(today.year + 1, 12, 31),
      initialDateRange: value.custom ?? DateTimeRange(start: financialYearStart(today), end: today),
    );
    if (picked != null) onChanged(RegisterPeriod(RegisterPeriodKind.custom, picked));
  }

  @override
  Widget build(BuildContext context) {
    return Wrap(spacing: 8, runSpacing: 8, children: [
      for (final (k, label) in [
        (RegisterPeriodKind.thisMonth, 'This month'),
        (RegisterPeriodKind.thisYear, 'This year'),
        (RegisterPeriodKind.lastYear, 'Last year'),
        (RegisterPeriodKind.all, 'All'),
      ])
        ChoiceChip(label: Text(label), selected: value.kind == k, onSelected: (_) => onChanged(RegisterPeriod(k))),
      ChoiceChip(
        avatar: const Icon(Icons.date_range_rounded, size: 16),
        label: Text(value.kind == RegisterPeriodKind.custom && value.custom != null
            ? '${formatAccountsDate(value.custom!.start)} – ${formatAccountsDate(value.custom!.end)}'
            : 'Dates…'),
        selected: value.kind == RegisterPeriodKind.custom,
        onSelected: (_) => _pickCustom(context),
      ),
    ]);
  }
}

/// A row of labelled figures in a white card: a register's totals.
class RegisterTotals extends StatelessWidget {
  final List<(String, String)> figures;
  const RegisterTotals({super.key, required this.figures});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(color: AppTheme.cardBg, borderRadius: BorderRadius.circular(AppTheme.radiusM)),
      child: Wrap(spacing: 28, runSpacing: 12, children: [
        for (final (label, value) in figures)
          Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(label, style: const TextStyle(fontSize: 11.5, color: AppTheme.textSecondary, fontWeight: FontWeight.w600)),
            const SizedBox(height: 3),
            Text(value,
                style: const TextStyle(
                    fontSize: 15, fontWeight: FontWeight.w700, fontFeatures: [FontFeature.tabularFigures()])),
          ]),
      ]),
    );
  }
}

/// Whoever made an entry, as a small "by Asha Kulkarni" line or cell.
class EnteredBy extends StatelessWidget {
  final String? name;
  final String prefix;
  const EnteredBy(this.name, {super.key, this.prefix = ''});

  @override
  Widget build(BuildContext context) => Text(
        (name == null || name!.isEmpty) ? '—' : '$prefix$name',
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
        style: const TextStyle(fontSize: 13, color: AppTheme.textPrimary),
      );
}

/// How an invoice or bill stands, as the words a register shows.
({String label, Color color}) registerStatus(String status) => switch (status) {
      'paid' => (label: 'Paid', color: AppTheme.success),
      'partially_paid' || 'part_paid' => (label: 'Part paid', color: AppTheme.warning),
      'overdue' => (label: 'Overdue', color: AppTheme.error),
      'cancelled' => (label: 'Cancelled', color: AppTheme.textSecondary),
      'unpaid' => (label: 'Unpaid', color: AppTheme.warning),
      'issued' => (label: 'Issued', color: AppTheme.primary),
      'generated' => (label: 'Generated', color: AppTheme.textSecondary),
      _ => (label: status, color: AppTheme.textSecondary),
    };

String inr(num v) => v == 0 ? '' : formatInr(v);
