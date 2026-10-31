import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/accounts/presentation/widgets/accounts_widgets.dart' show PdfMenuButton;

Widget _app({required Future<Uint8List> Function() load}) => MaterialApp(
      theme: AppTheme.lightTheme,
      home: Scaffold(
        body: Padding(
          padding: const EdgeInsets.all(16),
          child: PdfMenuButton(load: load, fileName: 'Receipt-RCP-1.pdf', subject: 'Payment Receipt RCP-1'),
        ),
      ),
    );

void main() {
  testWidgets('the receipt button opens a menu of Open, Share and Download, and fetches nothing until one is chosen',
      (t) async {
    var loads = 0;
    await t.pumpWidget(_app(load: () async {
      loads++;
      return Uint8List(0);
    }));

    expect(find.text('Receipt'), findsOneWidget);
    expect(find.text('Open'), findsNothing);

    await t.tap(find.text('Receipt'));
    await t.pumpAndSettle();

    expect(find.text('Open'), findsOneWidget);
    expect(find.text('Share'), findsOneWidget);
    expect(find.text('Download'), findsOneWidget);
    expect(loads, 0);
  });
}
