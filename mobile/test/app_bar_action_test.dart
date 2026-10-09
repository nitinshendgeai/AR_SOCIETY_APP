import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/shared/widgets/app_data_table.dart';

Widget _bar(double width) => MediaQuery(
      data: MediaQueryData(size: Size(width, 800)),
      child: MaterialApp(
        home: Scaffold(
          appBar: AppBar(title: const Text("Members' Ledger"), actions: [
            AppBarTextAction(icon: Icons.warning_amber_rounded, label: 'Defaulters', onPressed: () {}),
          ]),
        ),
      ),
    );

void main() {
  testWidgets('on a phone a secondary header action is icon-only so the title keeps its room', (tester) async {
    await tester.pumpWidget(_bar(390));
    expect(find.text("Members' Ledger"), findsOneWidget);
    expect(find.text('Defaulters'), findsNothing);
    expect(find.byTooltip('Defaulters'), findsOneWidget);
  });

  testWidgets('with room to spare the label is shown', (tester) async {
    await tester.pumpWidget(_bar(1000));
    expect(find.text('Defaulters'), findsOneWidget);
  });
}
