import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'translations.dart';

/// The languages the app can be shown in. English is the source of every text; Hindi and Marathi are looked up
/// in [kTranslations] and fall back to English for anything not translated yet.
const kSupportedLocales = [Locale('en'), Locale('hi'), Locale('mr')];

/// Each language in its own script, as it appears in the picker.
const kLanguageNames = {'en': 'English', 'hi': 'हिन्दी', 'mr': 'मराठी'};

/// Font used for Devanagari text (Hindi, Marathi): bundled so it never depends on a network font.
const kDevanagariFont = 'NotoSansDevanagari';

const _prefsKey = 'app_language';

/// The language chosen on the previous visit, read once at start-up (no flash of English).
final initialLanguageProvider = Provider<String>((ref) => 'en');

Future<String> loadSavedLanguage() async {
  try {
    final code = (await SharedPreferences.getInstance()).getString(_prefsKey);
    return kLanguageNames.containsKey(code) ? code! : 'en';
  } catch (_) {
    return 'en';
  }
}

class LocaleNotifier extends Notifier<Locale> {
  @override
  Locale build() => Locale(ref.watch(initialLanguageProvider));

  Future<void> set(String code) async {
    if (!kLanguageNames.containsKey(code)) return;
    state = Locale(code);
    try {
      await (await SharedPreferences.getInstance()).setString(_prefsKey, code);
    } catch (_) {/* the choice still applies for this visit */}
  }
}

final localeProvider =
    NotifierProvider<LocaleNotifier, Locale>(LocaleNotifier.new);

extension TranslateContext on BuildContext {
  /// [english] in the app's current language; English itself when there is no translation.
  /// Reads the locale from [Localizations], so the widget rebuilds when the language changes.
  String tr(String english) =>
      translate(english, Localizations.localeOf(this).languageCode);
}

String translate(String english, String languageCode) => languageCode == 'en'
    ? english
    : (kTranslations[english]?[languageCode] ?? english);
