import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/shared/widgets/app_data_table.dart' show HeaderActionButton;
import 'package:ar_society_app/shared/widgets/app_form.dart';

Widget _page({required VoidCallback onSubmit, bool saving = false, GlobalKey<FormState>? key}) => MaterialApp(
      theme: AppTheme.lightTheme,
      home: AppFormPage(
        title: 'Add Thing',
        subtitle: 'A thing for the society',
        formKey: key,
        submitLabel: 'Save thing',
        saving: saving,
        onSubmit: onSubmit,
        children: [
          FormSection(title: 'Basics', description: 'The main details.', children: [
            FormFieldBox(
              label: 'Name',
              required: true,
              child: TextFormField(validator: (v) => (v ?? '').isEmpty ? 'Name is required' : null),
            ),
            FormFieldBox(label: 'Code', helper: 'Leave blank for automatic', child: const TextField()),
            const FormFull(child: FormSwitchTile(title: 'Active', subtitle: 'Shown in lists', value: true)),
          ]),
          const FormSection(title: 'Second', children: [Text('second section body')]),
        ],
      ),
    );

void main() {
  appPageEdgeTests();
  testWidgets('a wide screen shows the header, the sections in two columns and the action bar', (tester) async {
    tester.view.physicalSize = const Size(1440, 900);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    var saved = 0;
    await tester.pumpWidget(_page(onSubmit: () => saved++));
    await tester.pumpAndSettle();

    expect(find.text('Add Thing'), findsOneWidget);
    expect(find.text('A thing for the society'), findsOneWidget);
    expect(find.text('Basics'), findsOneWidget);
    expect(find.text('The main details.'), findsOneWidget);
    // Two fields share a row: same top edge, different left edges.
    final name = tester.getTopLeft(find.byType(TextFormField));
    final code = tester.getTopLeft(find.byType(TextField).last);
    expect(code.dy, name.dy);
    expect(code.dx, greaterThan(name.dx));
    // Header, cards and bar share one left edge.
    expect(find.text('Fields marked * are required'), findsOneWidget);

    await tester.tap(find.text('Save thing'));
    await tester.pump();
    expect(saved, 1);
  });

  testWidgets('a narrow screen keeps the app bar, stacks the fields and gives a full-width button', (tester) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    await tester.pumpWidget(_page(onSubmit: () {}));
    await tester.pumpAndSettle();

    expect(find.byType(AppBar), findsOneWidget);
    final name = tester.getTopLeft(find.byType(TextFormField));
    final code = tester.getTopLeft(find.byType(TextField).last);
    expect(code.dx, name.dx);
    expect(code.dy, greaterThan(name.dy));
    expect(find.text('Cancel'), findsNothing);
  });

  testWidgets('the form checks every field, including ones scrolled out of view', (tester) async {
    tester.view.physicalSize = const Size(390, 500);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    final key = GlobalKey<FormState>();
    await tester.pumpWidget(_page(onSubmit: () {}, key: key));
    await tester.pumpAndSettle();
    expect(key.currentState!.validate(), isFalse);
    await tester.pump();
    expect(find.text('Name is required'), findsOneWidget);
  });

  testWidgets('while saving the buttons cannot be pressed twice', (tester) async {
    tester.view.physicalSize = const Size(1440, 900);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    var saved = 0;
    await tester.pumpWidget(_page(onSubmit: () => saved++, saving: true));
    await tester.pump(const Duration(milliseconds: 300));
    await tester.tap(find.byType(ElevatedButton));
    await tester.pump();
    expect(saved, 0);
    expect(tester.widget<OutlinedButton>(find.widgetWithText(OutlinedButton, 'Cancel')).onPressed, isNull);
  });
}

// ── AppPage: header, buttons and body on one set of edges ────────────────────

Widget _appPage() => MaterialApp(
      theme: AppTheme.lightTheme,
      home: AppPage(
        title: 'Cash in Hand',
        showBack: false,
        actions: [
          HeaderActionButton(icon: Icons.download_rounded, label: 'Download PDF', onPressed: () {}),
          // A leftover from a phone app bar: it must not push the button off the edge.
          const SizedBox(width: 8),
        ],
        bottom: const TabBar(tabs: [Tab(text: 'One'), Tab(text: 'Two')], controller: null),
        body: ListView(padding: const EdgeInsets.all(16), children: const [
          Card(child: SizedBox(height: 80, child: Center(child: Text('the card')))),
        ]),
      ),
    );

void _appPageEdgesTest(String name, Size size) {
  testWidgets('AppPage keeps the title, the button and the card on the same edges ($name)', (tester) async {
    tester.view.physicalSize = size;
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    await tester.pumpWidget(DefaultTabController(length: 2, child: _appPage()));
    await tester.pumpAndSettle();

    final title = tester.getTopLeft(find.text('Cash in Hand')).dx;
    final cardRect = tester.getRect(find.byType(Card));
    expect(title, cardRect.left, reason: 'the title lines up with the card at its left');
    final buttonRight = tester.getRect(find.byType(FilledButton)).right;
    expect(buttonRight, cardRect.right, reason: 'the button ends where the card ends');
  });
}

void appPageEdgeTests() {
  _appPageEdgesTest('1280 wide', const Size(1280, 800));
  _appPageEdgesTest('2560 wide, content column centred', const Size(2560, 1300));
}
