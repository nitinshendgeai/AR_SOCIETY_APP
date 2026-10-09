import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:ar_society_app/core/l10n/app_locale.dart';
import 'package:ar_society_app/core/l10n/translations.dart';
import 'package:ar_society_app/core/navigation/app_menu.dart';

void main() {
  test('English is returned as it is, and a text with no translation falls back to English', () {
    expect(translate('Visitors', 'en'), 'Visitors');
    expect(translate('Visitors', 'hi'), 'आगंतुक');
    expect(translate('Visitors', 'mr'), 'अभ्यागत');
    expect(translate('Something not translated yet', 'mr'), 'Something not translated yet');
  });

  test('every menu group and item has Hindi and Marathi', () {
    final missing = <String>[];
    for (final c in appMenuCategories) {
      for (final label in [c.label, ...c.items.map((i) => i.label)]) {
        final t = kTranslations[label];
        if (t == null || (t['hi'] ?? '').isEmpty || (t['mr'] ?? '').isEmpty) missing.add(label);
      }
    }
    expect(missing, isEmpty, reason: 'Translate: $missing');
  });

  test('every translation has both languages and no entry is empty', () {
    kTranslations.forEach((en, t) {
      expect(t.keys.toSet(), {'hi', 'mr'}, reason: en);
      expect(t.values.every((v) => v.trim().isNotEmpty), isTrue, reason: en);
    });
  });

  testWidgets('choosing a language changes the text and is remembered for the next visit', (t) async {
    SharedPreferences.setMockInitialValues({});
    late WidgetRef captured;
    await t.pumpWidget(ProviderScope(
      child: Consumer(builder: (context, ref, _) {
        captured = ref;
        return MaterialApp(
          locale: ref.watch(localeProvider),
          supportedLocales: kSupportedLocales,
          localizationsDelegates: const [
            GlobalMaterialLocalizations.delegate,
            GlobalWidgetsLocalizations.delegate,
            GlobalCupertinoLocalizations.delegate,
          ],
          home: Builder(builder: (c) => Scaffold(body: Text(c.tr('Meetings')))),
        );
      }),
    ));
    expect(find.text('Meetings'), findsOneWidget);
    await captured.read(localeProvider.notifier).set('mr');
    await t.pumpAndSettle();
    expect(find.text('सभा'), findsOneWidget);
    await captured.read(localeProvider.notifier).set('hi');
    await t.pumpAndSettle();
    expect(find.text('बैठकें'), findsOneWidget);
    await captured.read(localeProvider.notifier).set('xx');          // unknown: ignored
    await t.pumpAndSettle();
    expect(find.text('बैठकें'), findsOneWidget);
    expect(await loadSavedLanguage(), 'hi');
  });
}
