import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/features/accounts/presentation/screens/accounts_screen.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

BookItem _item(String t) => BookItem(Icons.book_rounded, t, 'sub of $t', () {});

Future<void> _pump(WidgetTester t, double width, Widget child) async {
  t.view.physicalSize = Size(width, 1200);
  t.view.devicePixelRatio = 1.0;
  addTearDown(t.view.resetPhysicalSize);
  addTearDown(t.view.resetDevicePixelRatio);
  await t.pumpWidget(MaterialApp(home: Scaffold(body: SingleChildScrollView(child: child))));
}

void main() {
  testWidgets('a short last row shares the full width instead of leaving an empty cell', (t) async {
    await _pump(t, 800, BooksGrid(items: [for (final n in ['A', 'B', 'C', 'D', 'E']) _item(n)]));
    final full = t.getSize(find.text('sub of A').first).width;
    final a = t.getRect(find.ancestor(of: find.text('A'), matching: find.byType(InkWell)).first);
    final e = t.getRect(find.ancestor(of: find.text('E'), matching: find.byType(InkWell)).first);
    expect(full, greaterThan(0));
    expect(e.width, closeTo(a.width * 2 + 10, 1), reason: 'the lone fifth tile spans both columns');
    expect(e.top, greaterThan(a.bottom));
  });

  testWidgets('a single tile fills the row', (t) async {
    await _pump(t, 800, BooksGrid(items: [_item('Only')]));
    final r = t.getRect(find.ancestor(of: find.text('Only'), matching: find.byType(InkWell)).first);
    expect(r.width, greaterThan(700));
  });

  testWidgets('a filter pill is no taller than the strip it sits in', (t) async {
    await _pump(t, 360, Row(children: [AppFilterPill(label: 'Owners', selected: true, onTap: () {})]));
    expect(t.getSize(find.byType(ChoiceChip)).height, lessThanOrEqualTo(34));
  });
}
