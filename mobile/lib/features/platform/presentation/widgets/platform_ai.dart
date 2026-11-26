import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/platform/data/platform_api.dart';
import 'package:ar_society_app/features/platform/presentation/providers/platform_providers.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// "300k", "1.5M".
String tokensText(int n) => n >= 1000000
    ? '${(n / 1000000).toStringAsFixed(n % 1000000 == 0 ? 0 : 1)}M'
    : n >= 1000
        ? '${(n / 1000).toStringAsFixed(n % 1000 == 0 || n >= 100000 ? 0 : 1)}k'
        : '$n';

Future<int?> _askTokens(BuildContext context, String title, int current, String help) async {
  final c = TextEditingController(text: '$current');
  final ok = await showDialog<bool>(
    context: context,
    builder: (ctx) => AlertDialog(
      title: Text(title),
      content: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(help, style: TextStyle(color: AppTheme.textSecondary, fontSize: 13)),
        const SizedBox(height: 12),
        TextField(
          controller: c,
          autofocus: true,
          keyboardType: TextInputType.number,
          inputFormatters: [FilteringTextInputFormatter.digitsOnly],
          decoration: const InputDecoration(labelText: 'Tokens', helperText: 'A worded bye-law answer uses about 1,000–2,500'),
        ),
      ]),
      actions: [
        TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
        FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Save')),
      ],
    ),
  );
  final v = int.tryParse(c.text.trim());
  c.dispose();
  return ok == true ? v : null;
}

/// Platform Console → AI plans: which plans include the Accounts Agent's AI wording, and how many tokens.
class AiPlansTab extends ConsumerStatefulWidget {
  const AiPlansTab({super.key});
  @override
  ConsumerState<AiPlansTab> createState() => _AiPlansTabState();
}

class _AiPlansTabState extends ConsumerState<AiPlansTab> {
  String? _busy;

  Future<void> _save(AiPlanRow p, bool included, int tokens) async {
    setState(() => _busy = p.planKey);
    try {
      await ref.read(platformApiProvider).setAiPlan(p.planKey, included, tokens);
      invalidatePlatform(ref);
      if (mounted) AppToast.success(context, '${p.label}: ${included ? '${tokensText(tokens)} tokens' : 'no AI'}');
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _busy = null);
    }
  }

  @override
  Widget build(BuildContext context) {
    final async = ref.watch(platformAiPlansProvider);
    return async.when(
      loading: () => const AppLoader(),
      error: (e, _) => AppErrorState(message: friendlyErrorMessage(e), onRetry: () => ref.invalidate(platformAiPlansProvider)),
      data: (plans) => ListView(padding: const EdgeInsets.fromLTRB(16, 16, 16, 40), children: [
        Text('The Accounts Agent can word bye-law answers and read typed entries with AI (Claude). It is part of the '
            'subscription: choose which plans include it and how many tokens a society may use. A society whose trial '
            'or subscription has ended, or that is suspended, gets no AI; its agent still answers from the bye-laws and '
            'the books. You can override one society on its page.',
            style: TextStyle(color: AppTheme.textSecondary, fontSize: 13, height: 1.4)),
        const SizedBox(height: 12),
        for (final p in plans)
          Card(
            margin: const EdgeInsets.only(bottom: 10),
            child: Padding(
              padding: const EdgeInsets.fromLTRB(16, 8, 8, 8),
              child: Row(children: [
                Expanded(
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text(p.label, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 15)),
                    const SizedBox(height: 2),
                    Text(
                      !p.aiIncluded
                          ? 'No AI'
                          : '${tokensText(p.tokens)} tokens ${p.period == 'trial' ? 'for the whole trial' : 'a month'}',
                      style: TextStyle(color: p.aiIncluded ? AppTheme.success : AppTheme.textSecondary, fontSize: 13),
                    ),
                  ]),
                ),
                if (p.aiIncluded)
                  TextButton(
                    key: Key('ai-plan-tokens-${p.planKey}'),
                    onPressed: _busy != null
                        ? null
                        : () async {
                            final v = await _askTokens(context, '${p.label}: AI tokens', p.tokens,
                                p.period == 'trial' ? 'For the whole free trial.' : 'For each calendar month.');
                            if (v != null) await _save(p, true, v);
                          },
                    child: const Text('Change'),
                  ),
                Switch(
                  key: Key('ai-plan-${p.planKey}'),
                  value: p.aiIncluded,
                  onChanged: _busy != null
                      ? null
                      : (v) => _save(p, v, v && p.tokens == 0 ? (p.period == 'trial' ? 50000 : 300000) : p.tokens),
                ),
              ]),
            ),
          ),
      ]),
    );
  }
}

/// A society's page → AI: what it gets, what it used, and the platform override.
class SocietyAiSection extends ConsumerStatefulWidget {
  final String societyId;
  const SocietyAiSection({super.key, required this.societyId});
  @override
  ConsumerState<SocietyAiSection> createState() => _SocietyAiSectionState();
}

class _SocietyAiSectionState extends ConsumerState<SocietyAiSection> {
  bool _busy = false;

  Future<void> _set(String mode, int? tokens) async {
    setState(() => _busy = true);
    try {
      await ref.read(platformApiProvider).setSocietyAi(widget.societyId, mode, tokens);
      invalidatePlatform(ref);
      if (mounted) AppToast.success(context, 'AI updated');
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final async = ref.watch(platformSocietyAiProvider(widget.societyId));
    return async.when(
      loading: () => const Padding(padding: EdgeInsets.all(12), child: LinearProgressIndicator()),
      error: (e, _) => AppErrorBanner(message: friendlyErrorMessage(e)),
      data: (a) {
        final used = a.budgetTokens == 0 ? 0.0 : (a.spentTokens / a.budgetTokens).clamp(0.0, 1.0);
        return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Icon(a.allowed ? Icons.check_circle_rounded : Icons.block_rounded, size: 18,
                color: a.allowed ? AppTheme.success : AppTheme.textSecondary),
            const SizedBox(width: 6),
            Expanded(
              child: Text(
                a.allowed
                    ? '${tokensText(a.allowance)} tokens ${a.period == 'trial' ? 'for the trial' : 'a month'} · ${a.overrideMode == 'plan' ? '${a.planLabel ?? 'plan'} plan' : 'set for this society'}'
                    : (a.reason ?? 'No AI'),
                style: const TextStyle(fontWeight: FontWeight.w600),
              ),
            ),
          ]),
          if (a.allowed) ...[
            const SizedBox(height: 8),
            LinearProgressIndicator(value: used, minHeight: 6, borderRadius: BorderRadius.circular(3)),
            const SizedBox(height: 4),
            Text('${tokensText(a.spentTokens)} of ${tokensText(a.budgetTokens)} used ${a.period == 'trial' ? 'in the trial' : 'this month'}'
                ' · ${a.aiCalls} AI requests · ${a.answeredWithoutAi} of ${a.requests} answered without AI',
                style: TextStyle(color: AppTheme.textSecondary, fontSize: 12.5)),
          ],
          if (!a.serverHasKey || !a.societySwitchOn) ...[
            const SizedBox(height: 4),
            Text(
              !a.serverHasKey ? 'The server has no Anthropic API key, so no society gets AI yet.' : 'The society has not switched AI wording on (Accounts Agent → Learning & settings).',
              style: TextStyle(color: AppTheme.warning, fontSize: 12.5),
            ),
          ],
          const SizedBox(height: 10),
          SegmentedButton<String>(
            segments: const [
              ButtonSegment(value: 'plan', label: Text('Follow plan')),
              ButtonSegment(value: 'on', label: Text('Always on')),
              ButtonSegment(value: 'off', label: Text('Off')),
            ],
            selected: {a.overrideMode},
            onSelectionChanged: _busy ? null : (v) => _set(v.first, v.first == 'off' ? null : a.overrideTokens),
          ),
          if (a.overrideMode != 'off')
            Align(
              alignment: Alignment.centerLeft,
              child: TextButton(
                onPressed: _busy
                    ? null
                    : () async {
                        if (a.overrideTokens != null) {
                          await _set(a.overrideMode, null);
                          return;
                        }
                        final v = await _askTokens(context, 'Own AI allowance', a.allowance,
                            'Tokens a month for this society only, instead of its plan\'s.');
                        if (v != null) await _set(a.overrideMode, v);
                      },
                child: Text(a.overrideTokens != null
                    ? 'Own allowance ${tokensText(a.overrideTokens!)} · use the plan\'s instead'
                    : 'Give this society its own allowance'),
              ),
            ),
        ]);
      },
    );
  }
}
