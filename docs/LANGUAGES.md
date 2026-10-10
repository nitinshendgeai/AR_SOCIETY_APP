# Languages — Hindi and Marathi

## In the app
- Languages: `en`, `hi` (हिन्दी), `mr` (मराठी). Phone: **More → Language**; desktop: account menu → Language. Stored on
  the device (`shared_preferences`, key `app_language`), applied at start-up.
- `MaterialApp` gets the locale, `supportedLocales` and the Flutter localization delegates (dates, pickers, dialogs).
- Texts: `context.tr('English text')` looks the text up in `lib/core/l10n/translations.dart` (keyed by the English
  text) and returns English when there is no entry. To translate a screen: wrap its fixed texts in `context.tr(...)`
  and add the entries (both `hi` and `mr`). `test/localization_test.dart` fails if a menu entry lacks a translation or
  an entry misses a language.
- Not translated: text that comes from the data itself (names, notice bodies, bill heads) and any screen not yet
  wrapped in `tr`.
- Font: `assets/fonts/NotoSansDevanagari-*.ttf` (SIL OFL, licence beside it) is the fallback font in `AppTheme`, so
  Devanagari renders offline.

## In PDFs
- English PDFs (bill, receipt, duty sheet, vouchers, pass card) are unchanged (reportlab).
- Certificates and NOCs can be downloaded in Hindi or Marathi: `GET /api/v1/certificates/{id}/pdf?lang=hi|mr`.
  reportlab cannot shape Devanagari (conjuncts and vowel signs break), so these are drawn with **fpdf2** and
  **uharfbuzz** using `backend/app/assets/fonts/NotoSansDevanagari-{Regular,SemiBold}.ttf`. Wording:
  `backend/app/modules/certificates/services/certificate_text.py`.
- Names, addresses and flat numbers print as entered; amounts and dates use Latin digits.

## Next steps (not done)
- Translate the remaining screens (billing, visitors, complaints, dashboards) a few at a time.
- Hindi/Marathi for the maintenance bill and receipt PDFs (the same fpdf2 route; the bill layout needs a port).
- Server-sent notification text in the member's language (needs a language on the user record).
- A native-speaker review of every translation.
