import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:ar_society_app/core/theme/app_look.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/core/theme/design_tokens.dart';

void main() {
  tearDown(() => AppTheme.look = AppLook.light);

  test('the palette, tones and theme follow the chosen look', () {
    AppTheme.look = AppLook.light;
    expect(AppTheme.cardBg, AppPalette.light.cardBg);
    expect(AppTheme.lightTheme.colorScheme.brightness, Brightness.light);
    final lightInfo = kToneColors[AppTone.info]!.background;

    AppTheme.look = AppLook.deck;
    expect(AppTheme.cardBg, AppPalette.deck.cardBg);
    expect(AppTheme.textPrimary, AppPalette.deck.textPrimary);
    expect(AppTheme.lightTheme.colorScheme.brightness, Brightness.dark);
    expect(AppTheme.lightTheme.scaffoldBackgroundColor, Colors.transparent); // the starfield shows through
    expect(kToneColors[AppTone.info]!.background, isNot(lightInfo));
  });

  test('the saved look is read back at start-up; anything unknown means light', () async {
    SharedPreferences.setMockInitialValues({'app_look': 'deck'});
    await loadSavedLook();
    expect(AppTheme.look, AppLook.deck);
    SharedPreferences.setMockInitialValues({'app_look': 'neon'});
    await loadSavedLook();
    expect(AppTheme.look, AppLook.light);
  });

  testWidgets('choosing Command deck in the picker switches the look and remembers it', (t) async {
    SharedPreferences.setMockInitialValues({});
    await t.pumpWidget(ProviderScope(
      child: MaterialApp(
        home: Consumer(
          builder: (context, ref, _) => Scaffold(
            body: TextButton(onPressed: () => showLookPicker(context, ref), child: const Text('open')),
          ),
        ),
      ),
    ));
    await t.tap(find.text('open'));
    await t.pumpAndSettle();
    expect(find.text('Light'), findsOneWidget);
    await t.tap(find.text('Command deck'));
    await t.pumpAndSettle();
    expect(AppTheme.look, AppLook.deck);
    expect((await SharedPreferences.getInstance()).getString('app_look'), 'deck');
  });
}
