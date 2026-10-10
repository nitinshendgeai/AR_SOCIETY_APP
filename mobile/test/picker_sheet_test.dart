import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart';
import 'package:ar_society_app/features/accounts/presentation/widgets/accounts_widgets.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';

const _flats = [
  MemberBalance(flatId: 'f1', flatLabel: 'A / 101', memberName: 'Asha Kulkarni', balance: DrCr(1500, 'Dr')),
  MemberBalance(flatId: 'f2', flatLabel: 'A / 102', memberName: 'Rohan Patil', balance: DrCr(0, 'Dr')),
  MemberBalance(flatId: 'f3', flatLabel: 'B / 201', memberName: 'Meera Shah', balance: DrCr(200, 'Cr')),
];

Widget _opener(void Function(MemberBalance?) onPicked) => MaterialApp(
      theme: AppTheme.lightTheme,
      home: Builder(
        builder: (context) => Scaffold(
          body: Center(
            child: ElevatedButton(
              onPressed: () async => onPicked(await pickFlat(context, _flats)),
              child: const Text('open'),
            ),
          ),
        ),
      ),
    );

void main() {
  for (final size in [const Size(390, 844), const Size(1440, 900)]) {
    testWidgets('the flat picker lists flats, filters as you type and returns the one tapped (${size.width.toInt()} wide)',
        (tester) async {
      tester.view.physicalSize = size;
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
      MemberBalance? picked;
      await tester.pumpWidget(_opener((m) => picked = m));
      await tester.tap(find.text('open'));
      await tester.pumpAndSettle();

      expect(find.text('Choose flat'), findsOneWidget);
      expect(find.text('A / 101'), findsOneWidget);
      expect(find.text('B / 201'), findsOneWidget);

      await tester.enterText(find.byType(TextField), 'meera');
      await tester.pumpAndSettle();
      expect(find.text('A / 101'), findsNothing);
      expect(find.text('B / 201'), findsOneWidget);

      await tester.enterText(find.byType(TextField), 'zzz');
      await tester.pumpAndSettle();
      expect(find.text('No flat matches'), findsOneWidget);

      await tester.enterText(find.byType(TextField), 'a / 102');
      await tester.pumpAndSettle();
      await tester.tap(find.text('A / 102'));
      await tester.pumpAndSettle();
      expect(picked?.flatId, 'f2');
    });
  }

  testWidgets('a list sheet with a pinned search keeps the search in view while the rows scroll', (tester) async {
    tester.view.physicalSize = const Size(390, 600);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    await tester.pumpWidget(MaterialApp(
      theme: AppTheme.lightTheme,
      home: Scaffold(
        body: AppSheetFrame(
          title: 'Choose one',
          pinned: SheetSearchField(onChanged: (_) {}),
          scrollBody: false,
          child: ListView(shrinkWrap: true, children: [
            for (var i = 0; i < 40; i++) PickerRow(title: 'Row $i', selected: i == 0, onTap: () {}),
          ]),
        ),
      ),
    ));
    await tester.pumpAndSettle();
    expect(find.byType(TextField), findsOneWidget);
    expect(find.byIcon(Icons.check_rounded), findsOneWidget);
    await tester.drag(find.byType(ListView), const Offset(0, -600));
    await tester.pumpAndSettle();
    expect(find.byType(TextField), findsOneWidget);
    expect(find.text('Row 0'), findsNothing);
  });
}
