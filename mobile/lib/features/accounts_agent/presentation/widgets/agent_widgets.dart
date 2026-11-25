import 'package:flutter/material.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/core/theme/design_tokens.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart' show formatInr;
import 'package:ar_society_app/features/accounts_agent/presentation/widgets/agent_hud.dart';
import 'package:ar_society_app/features/accounts_agent/data/accounts_agent_api.dart';
import 'package:ar_society_app/features/accounts_agent/data/legal_api.dart';

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
  Widget build(BuildContext context) => HudChip(label: titleCase(severity), tone: severityTone(severity));
}

/// A glass panel of the command deck: translucent navy, a cyan hairline, HUD corner brackets and a soft glow.
/// Tappable panels light up on hover.
class AgentCard extends StatefulWidget {
  final Widget child;
  final EdgeInsets padding;
  final VoidCallback? onTap;

  /// The neon of the border and brackets; cyan unless the panel reports a state (a red alarm, an amber warning).
  final Color accent;
  const AgentCard({super.key, required this.child, this.padding = const EdgeInsets.all(16), this.onTap, this.accent = Hud.cyan});
  @override
  State<AgentCard> createState() => _AgentCardState();
}

class _AgentCardState extends State<AgentCard> {
  bool _hover = false;
  @override
  Widget build(BuildContext context) {
    final a = widget.accent;
    final lit = _hover && widget.onTap != null;
    final radius = BorderRadius.circular(AppTheme.radiusM);
    final box = AnimatedContainer(
      duration: const Duration(milliseconds: 180),
      width: double.infinity,
      decoration: BoxDecoration(
        borderRadius: radius,
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Hud.panelHi.withValues(alpha: lit ? 0.92 : 0.78), Hud.panel.withValues(alpha: lit ? 0.9 : 0.72)],
        ),
        border: Border.all(color: a.withValues(alpha: lit ? 0.6 : 0.2)),
        boxShadow: [BoxShadow(color: a.withValues(alpha: lit ? 0.22 : 0.07), blurRadius: lit ? 28 : 22, spreadRadius: -4)],
      ),
      child: CustomPaint(
        foregroundPainter: HudCorners(color: a.withValues(alpha: lit ? 1 : 0.7), length: 10),
        child: Padding(padding: widget.padding, child: widget.child),
      ),
    );
    if (widget.onTap == null) return box;
    return MouseRegion(
      onEnter: (_) => setState(() => _hover = true),
      onExit: (_) => setState(() => _hover = false),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          borderRadius: radius,
          splashColor: a.withValues(alpha: 0.12),
          highlightColor: a.withValues(alpha: 0.06),
          hoverColor: Colors.transparent,
          onTap: widget.onTap,
          child: box,
        ),
      ),
    );
  }
}

/// A HUD section heading: a lit marker, the title in spaced capitals, and a hairline fading out to the right.
class AgentSectionTitle extends StatelessWidget {
  final String text;
  const AgentSectionTitle(this.text, {super.key});
  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(top: 22, bottom: 10),
        child: Semantics(
          header: true,
          label: text,
          child: ExcludeSemantics(
            child: Row(children: [
              Transform.rotate(
                angle: 0.785398,
                child: Container(
                  width: 7,
                  height: 7,
                  decoration: BoxDecoration(color: Hud.cyan, boxShadow: [BoxShadow(color: Hud.cyan.withValues(alpha: 0.8), blurRadius: 8)]),
                ),
              ),
              const SizedBox(width: 10),
              Flexible(
                flex: 12, // the title takes what it needs; the hairline gets the rest
                child: Text(text.toUpperCase(),
                    style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.w700, letterSpacing: 2.2, color: Hud.cyan)),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Container(
                  height: 1,
                  decoration: BoxDecoration(
                    gradient: LinearGradient(colors: [Hud.cyan.withValues(alpha: 0.45), Hud.cyan.withValues(alpha: 0)]),
                  ),
                ),
              ),
            ]),
          ),
        ),
      );
}

/// A read-out tile: a large glowing figure over its label, with a thin level bar in the same colour.
class AgentStat extends StatelessWidget {
  final String label;
  final int value;
  final Color color;
  final VoidCallback? onTap;
  const AgentStat({super.key, required this.label, required this.value, required this.color, this.onTap});
  @override
  Widget build(BuildContext context) => AgentCard(
        onTap: onTap,
        accent: value > 0 ? color : Hud.cyan,
        child: Semantics(
          label: '$label: $value',
          button: onTap != null,
          child: ExcludeSemantics(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(label.toUpperCase(), maxLines: 1, overflow: TextOverflow.ellipsis, style: Hud.label()),
              const SizedBox(height: 6),
              Text(value.toString().padLeft(2, '0'),
                  style: TextStyle(
                    fontSize: 32,
                    fontWeight: FontWeight.w800,
                    height: 1.05,
                    color: value > 0 ? color : Hud.faint,
                    fontFeatures: Hud.tabular,
                    shadows: value > 0 ? [Shadow(color: color.withValues(alpha: 0.7), blurRadius: 18)] : null,
                  )),
              const SizedBox(height: 10),
              ClipRRect(
                borderRadius: BorderRadius.circular(2),
                child: LinearProgressIndicator(
                  value: value == 0 ? 0 : (0.15 + 0.85 * (1 - 1 / (1 + value / 4))),
                  minHeight: 3,
                  color: color,
                  backgroundColor: Hud.line,
                ),
              ),
            ]),
          ),
        ),
      );
}

/// A telemetry row: a small capitalised label and its value.
class KeyValue extends StatelessWidget {
  final String label;
  final String? value;
  const KeyValue(this.label, this.value, {super.key});
  @override
  Widget build(BuildContext context) => (value == null || value!.isEmpty)
      ? const SizedBox.shrink()
      : Padding(
          padding: const EdgeInsets.symmetric(vertical: 4),
          child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            SizedBox(
              width: 168,
              child: Padding(padding: const EdgeInsets.only(top: 2), child: Text(label.toUpperCase(), style: Hud.label(size: 10.5))),
            ),
            Expanded(child: Text(value!, style: const TextStyle(fontSize: 13.5, color: Hud.text, fontFeatures: Hud.tabular))),
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
            Expanded(child: Text(l.account, style: TextStyle(fontSize: 13.5, color: Hud.text, decoration: deco))),
            SizedBox(
              width: 120,
              child: Text(l.debit > 0 ? 'Dr ${formatInr(l.debit)}' : '', textAlign: TextAlign.right, style: TextStyle(fontSize: 13, color: Hud.cyan, fontFeatures: Hud.tabular, decoration: deco)),
            ),
            SizedBox(
              width: 120,
              child: Text(l.credit > 0 ? 'Cr ${formatInr(l.credit)}' : '', textAlign: TextAlign.right, style: TextStyle(fontSize: 13, color: Hud.violetText, fontFeatures: Hud.tabular, decoration: deco)),
            ),
          ]),
        ),
    ]);
  }
}

String agentFindingRoute(String id) => '/accounts-agent/findings/$id';
String agentProposalRoute(String id) => '/accounts-agent/proposals/$id';

AppTone classificationTone(String c) => switch (c) {
      'CONFIRMED_ACCOUNTING_ERROR' || 'CONFIRMED_STATUTORY_VALIDATION_FAILURE' => AppTone.danger,
      'POTENTIAL_NON_COMPLIANCE' || 'SUSPECTED_ACCOUNTING_ANOMALY' || 'LEGAL_SOURCE_CONFLICT' => AppTone.warning,
      'MISSING_DOCUMENTATION' || 'INTERNAL_POLICY_DEVIATION' => AppTone.info,
      _ => AppTone.neutral,
    };

/// The legal basis of a finding or an answer: source, section/clause, effective dates, status and — always — whether
/// it is verified. Society-specific decisions are labelled as such, apart from law.
class LegalSourceCard extends StatelessWidget {
  final LegalSource source;
  const LegalSourceCard({super.key, required this.source});
  @override
  Widget build(BuildContext context) {
    final s = source;
    final period = [if (s.effectiveFrom != null) 'from ${s.effectiveFrom}', if (s.effectiveUntil != null) 'until ${s.effectiveUntil}'].join(' ');
    return AgentCard(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Wrap(spacing: 8, runSpacing: 6, children: [
          HudChip(label: verificationLabel(s.verificationStatus), tone: s.verified ? AppTone.success : AppTone.warning),
          HudChip(label: titleCase(s.legalStatus), tone: AppTone.neutral),
          HudChip(label: s.societySpecific ? 'Society decision / bye-law' : 'Law / jurisdiction', tone: AppTone.info),
        ]),
        const SizedBox(height: 8),
        Text(s.title, style: const TextStyle(fontSize: 14.5, fontWeight: FontWeight.w700)),
        const SizedBox(height: 4),
        KeyValue('Rule', '${s.ruleCode} (version ${s.version})'),
        KeyValue('Source', s.source),
        KeyValue('Level', s.levelName),
        KeyValue('Reference', s.reference),
        KeyValue('In force', period.isEmpty ? null : period),
        if (s.blockedBy.isNotEmpty) KeyValue('Open legal review', s.blockedBy.join('; ')),
        if (s.uncertainty != null) ...[
          const SizedBox(height: 6),
          Text(s.uncertainty!, style: const TextStyle(fontSize: 12.5, color: Hud.amber, height: 1.35)),
        ],
        if (s.note != null) ...[
          const SizedBox(height: 6),
          Text(s.note!, style: const TextStyle(fontSize: 12, color: Hud.dim, height: 1.35)),
        ],
      ]),
    );
  }
}
