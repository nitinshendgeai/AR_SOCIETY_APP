import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/shared/widgets/confirm_remove.dart';

void main() {
  Future<void> open(WidgetTester t, void Function(bool) onResult) async {
    await t.pumpWidget(MaterialApp(
      home: Builder(
        builder: (c) => Scaffold(
          body: RemoveButton(
            label: 'Remove this thing',
            onPressed: () async => onResult(await confirmRemove(c, title: 'Remove it?', message: 'Entered by mistake.')),
          ),
        ),
      ),
    ));
    await t.tap(find.text('Remove this thing'));
    await t.pumpAndSettle();
  }

  testWidgets('Keep it leaves the record alone', (t) async {
    bool? r;
    await open(t, (v) => r = v);
    expect(find.text('Remove it?'), findsOneWidget);
    await t.tap(find.text('Keep it'));
    await t.pumpAndSettle();
    expect(r, false);
  });

  testWidgets('Remove confirms', (t) async {
    bool? r;
    await open(t, (v) => r = v);
    await t.tap(find.widgetWithText(FilledButton, 'Remove').evaluate().isNotEmpty ? find.widgetWithText(FilledButton, 'Remove') : find.text('Remove').last);
    await t.pumpAndSettle();
    expect(r, true);
  });
}
