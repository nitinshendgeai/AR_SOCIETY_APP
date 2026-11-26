import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/accounts_agent/data/accounts_agent_api.dart';
import 'package:ar_society_app/features/platform/data/platform_api.dart';
import 'package:ar_society_app/features/platform/presentation/providers/platform_providers.dart';
import 'package:ar_society_app/features/platform/presentation/widgets/platform_ai.dart';

Dio _server(List<RequestOptions> seen, Object Function(RequestOptions) reply) {
  final dio = Dio();
  dio.interceptors.add(InterceptorsWrapper(onRequest: (o, h) {
    seen.add(o);
    h.resolve(Response(requestOptions: o, statusCode: 200, data: reply(o)));
  }));
  return dio;
}

const _plans = {
  'plans': [
    {'plan_key': 'trial', 'label': 'Free trial', 'ai_included': true, 'tokens': 50000, 'period': 'trial'},
    {'plan_key': 'starter', 'label': 'Starter', 'ai_included': false, 'tokens': 0, 'period': 'month'},
    {'plan_key': 'growth', 'label': 'Growth', 'ai_included': true, 'tokens': 300000, 'period': 'month'},
  ],
};

void main() {
  test('a society\'s AI: entitlement, override and use', () {
    final a = SocietyAi.fromJson({
      'entitlement': {'allowed': true, 'tokens': 25000, 'period': 'month', 'plan_label': 'Starter', 'reason': null},
      'override': {'mode': 'on', 'tokens': 25000},
      'budget_tokens': 25000, 'spent_tokens': 1200, 'requests': 4, 'ai_calls': 1, 'answered_without_ai': 3,
      'society_switch_on': true, 'server_has_key': true,
    });
    expect(a.allowed, isTrue);
    expect(a.overrideMode, 'on');
    expect(a.overrideTokens, 25000);
    expect(a.answeredWithoutAi, 3);
    final off = SocietyAi.fromJson({'entitlement': {'allowed': false, 'reason': 'The subscription has expired: AI is off.'}});
    expect(off.allowed, isFalse);
    expect(off.overrideMode, 'plan');
    expect(off.reason, contains('expired'));
  });

  test('society settings carry what the plan includes', () {
    final s = AgentSettings.fromJson({
      'learning_window_months': 3, 'ai_included': false, 'ai_plan_label': 'Starter',
      'ai_plan_reason': 'The Starter plan does not include AI.', 'ai_plan_tokens': 0,
    });
    expect(s.aiIncluded, isFalse);
    expect(s.aiPlanReason, contains('Starter'));
    expect(AgentSettings.fromJson({'learning_window_months': 3}).aiIncluded, isTrue); // an older server
  });

  testWidgets('AI plans: each plan shows what it includes; switching a plan on saves it', (t) async {
    final seen = <RequestOptions>[];
    final api = PlatformApi(dio: _server(seen, (o) => _plans));
    await t.pumpWidget(ProviderScope(
      overrides: [platformApiProvider.overrideWithValue(api)],
      child: MaterialApp(theme: AppTheme.lightTheme, home: const Scaffold(body: AiPlansTab())),
    ));
    await t.pumpAndSettle();
    expect(find.text('50k tokens for the whole trial'), findsOneWidget);
    expect(find.text('No AI'), findsOneWidget);
    expect(find.text('300k tokens a month'), findsOneWidget);
    await t.tap(find.byKey(const Key('ai-plan-starter')));
    await t.pumpAndSettle();
    final put = seen.firstWhere((o) => o.method == 'PUT');
    expect(put.path, '/platform-admin/ai-plans/starter');
    expect(put.data, {'ai_included': true, 'tokens': 300000});
  });
}
