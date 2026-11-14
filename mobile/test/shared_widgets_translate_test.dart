import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/core/l10n/app_locale.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

Widget _app(Widget body, {Locale? locale}) => ProviderScope(
      child: MaterialApp(
        theme: AppTheme.lightTheme,
        locale: locale,
        supportedLocales: kSupportedLocales,
        localizationsDelegates: GlobalMaterialLocalizations.delegates,
        home: Scaffold(body: body),
      ),
    );

void main() {
  testWidgets('the shared empty state, button, filter pill and error state follow the language', (t) async {
    await t.pumpWidget(_app(
      Column(children: [
        const AppEmptyState(icon: Icons.inbox_rounded, title: 'No visits recorded yet.', subtitle: 'Pay now'),
        AppPrimaryButton(label: 'Pay now', onPressed: () {}),
        AppFilterPill(label: 'Last 30 days', selected: false, onTap: () {}),
        AppErrorState(message: 'Could not load. Try again', onRetry: () {}),
      ]),
      locale: const Locale('mr'),
    ));
    await t.pumpAndSettle();
    expect(find.text('अजून कोणतीही भेट नोंदलेली नाही.'), findsOneWidget);
    expect(find.text('आता भरणा करा'), findsNWidgets(2));        // the empty state's subtitle and the button
    expect(find.text('गेले 30 दिवस'), findsOneWidget);
    expect(find.text('No visits recorded yet.'), findsNothing);
  });

  testWidgets('the same widgets stay in English when English is chosen', (t) async {
    await t.pumpWidget(_app(
      Column(children: [
        const AppEmptyState(icon: Icons.inbox_rounded, title: 'No visits recorded yet.'),
        AppPrimaryButton(label: 'Pay now', onPressed: () {}),
      ]),
    ));
    await t.pumpAndSettle();
    expect(find.text('No visits recorded yet.'), findsOneWidget);
    expect(find.text('Pay now'), findsOneWidget);
  });

  testWidgets('a toast message is translated; one with no translation (a server message) is left as it is', (t) async {
    late BuildContext ctx;
    await t.pumpWidget(_app(Builder(builder: (c) {
      ctx = c;
      return const SizedBox();
    }), locale: const Locale('hi')));
    AppToast.success(ctx, 'Complaint raised successfully');
    await t.pump();
    expect(find.text('शिकायत दर्ज हो गई'), findsOneWidget);
    AppToast.error(ctx, 'Flat 101 already has a tenant');
    await t.pump(const Duration(milliseconds: 400));
    expect(find.text('Flat 101 already has a tenant'), findsOneWidget);
  });
}
