import 'package:flutter/material.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/core/theme/design_tokens.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart' show formatInr;
import 'package:ar_society_app/features/accounts_agent/data/accounts_agent_api.dart';
import 'package:ar_society_app/shared/widgets/app_status.dart';

AppTone severityTone(String s) => switch (s) {
      'CRITICAL' || 'HIGH' => AppTone.danger,
      'MEDIUM' => AppTone.warning,
      'LOW' => AppTone.info,
      _ => AppTone.neutral,
    };

String titleCase(String s) =>
    s.replaceAll('_', ' ').toLowerCase().split(' ').map((w) => w.isEmpty ? w : '${w[0].toUpperCase()}${w.substring(1)}').join(' ');

class SeverityChip extends StatelessWidget {
  final String severity;
  const SeverityChip(this.severity, {super.key});
  @override
  Widget build(BuildContext context) => AppStatusChip(label: titleCase(severity), tone: severityTone(severity));
}

/// A white rounded block, the card language the Accounts screens use.
class AgentCard extends StatelessWidget {
  final Widget child;
  final EdgeInsets padding;
  final VoidCallback? onTap;
  const AgentCard({super.key, required this.child, this.padding = const EdgeInsets.all(16), this.onTap});
  @override
  Widget build(BuildContext context) {
    final box = Container(
      width: double.infinity,
      padding: padding,
      decoration: BoxDecoration(color: AppTheme.cardBg, borderRadius: BorderRadius.circular(AppTheme.radiusM)),
      child: child,
    );
    return onTap == null
        ? box
        : Material(
            color: Colors.transparent,
            child: InkWell(borderRadius: BorderRadius.circular(AppTheme.radiusM), onTap: onTap, child: box));
  }
}

class AgentSectionTitle extends StatelessWidget {
  final String text;
  const AgentSectionTitle(this.text, {super.key});
  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(top: 18, bottom: 8),
        child: Semantics(
          header: true,
          child: Text(text, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: AppTheme.textPrimary)),
        ),
      );
}

class AgentStat extends StatelessWidget {
  final String label;
  final int value;
  final Color color;
  final VoidCallback? onTap;
  const AgentStat({super.key, required this.label, required this.value, required this.color, this.onTap});
  @override
  Widget build(BuildContext context) => AgentCard(
        onTap: onTap,
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('$value', style: TextStyle(fontSize: 26, fontWeight: FontWeight.w800, color: color)),
          const SizedBox(height: 2),
          Text(label, style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary)),
        ]),
      );
}

class KeyValue extends StatelessWidget {
  final String label;
  final String? value;
  const KeyValue(this.label, this.value, {super.key});
  @override
  Widget build(BuildContext context) => (value == null || value!.isEmpty)
      ? const SizedBox.shrink()
      : Padding(
          padding: const EdgeInsets.symmetric(vertical: 3),
          child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            SizedBox(width: 120, child: Text(label, style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary))),
            Expanded(child: Text(value!, style: const TextStyle(fontSize: 13.5, color: AppTheme.textPrimary))),
          ]),
        );
}

String stamp(DateTime? d) {
  if (d == null) return '—';
  final l = d.toLocal();
  const m = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  final hh = l.hour.toString().padLeft(2, '0'), mm = l.minute.toString().padLeft(2, '0');
  return '${l.day} ${m[l.month - 1]} ${l.year}, $hh:$mm';
}

String day(DateTime d) {
  const m = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  return '${d.day} ${m[d.month - 1]} ${d.year}';
}

/// Debit / credit lines of a voucher or of a proposed correction.
class LinesTable extends StatelessWidget {
  final List<ProposalLine> lines;
  final bool strike;
  const LinesTable({super.key, required this.lines, this.strike = false});
  @override
  Widget build(BuildContext context) {
    final deco = strike ? TextDecoration.lineThrough : null;
    return Column(children: [
      for (final l in lines)
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 4),
          child: Row(children: [
            Expanded(child: Text(l.account, style: TextStyle(fontSize: 13.5, decoration: deco))),
            SizedBox(
              width: 100,
              child: Text(l.debit > 0 ? 'Dr ${formatInr(l.debit)}' : '', textAlign: TextAlign.right, style: TextStyle(fontSize: 13, decoration: deco)),
            ),
            SizedBox(
              width: 100,
              child: Text(l.credit > 0 ? 'Cr ${formatInr(l.credit)}' : '', textAlign: TextAlign.right, style: TextStyle(fontSize: 13, decoration: deco)),
            ),
          ]),
        ),
    ]);
  }
}

String agentFindingRoute(String id) => '/accounts-agent/findings/$id';
String agentProposalRoute(String id) => '/accounts-agent/proposals/$id';
