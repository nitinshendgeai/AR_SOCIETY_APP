import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/core/l10n/app_locale.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/complaint/presentation/providers/complaint_providers.dart';
import 'package:ar_society_app/features/dashboard/gate_summary.dart';
import 'package:ar_society_app/features/dashboard/role_dashboards.dart';
import 'package:ar_society_app/features/maintenance_billing/data/maintenance_billing_api.dart' show MyBillsSummary;
import 'package:ar_society_app/features/maintenance_billing/presentation/providers/maintenance_billing_providers.dart' show myBillsProvider;
import 'package:ar_society_app/features/staff/data/datasources/staff_remote_datasource.dart';
import 'package:ar_society_app/features/staff/data/repositories/staff_repository.dart';
import 'package:ar_society_app/features/staff/presentation/providers/staff_providers.dart';
import 'package:ar_society_app/features/staff/presentation/screens/staff_home_screen.dart';
import 'package:ar_society_app/features/users/presentation/providers/user_providers.dart';
import 'package:ar_society_app/features/visitor/data/datasources/visitor_remote_datasource.dart';
import 'package:ar_society_app/features/visitor/data/repositories/visitor_repository.dart';
import 'package:ar_society_app/features/visitor/domain/entities/visitor_entities.dart';
import 'package:ar_society_app/features/visitor/presentation/providers/visitor_providers.dart';
import 'package:ar_society_app/features/visitor/presentation/screens/visitor_list_screen.dart';

const _resident = UserEntity(id: 'u', email: 'a@b.c', fullName: 'Asha Kulkarni', roles: ['Resident'], societyId: 's1');
const _guard = UserEntity(id: 'g', email: 'g@b.c', fullName: 'Ramesh Shinde', roles: ['Security Staff'], societyId: 's1', termsAccepted: true);

Widget _app(Widget home, UserEntity user, List<String> codes, {List<Override> extra = const [], String lang = 'mr'}) => ProviderScope(
      overrides: [
        currentUserProvider.overrideWithValue(user),
        myFormCodesProvider.overrideWith((ref) async => codes),
        staffRepositoryProvider.overrideWithValue(StaffRepository(ds: StaffRemoteDataSource(dio: Dio()))),
        myOpenComplaintsCountProvider.overrideWith((ref) async => 2),
        ...extra,
      ],
      child: MaterialApp(
        theme: AppTheme.lightTheme,
        locale: Locale(lang),
        supportedLocales: kSupportedLocales,
        localizationsDelegates: GlobalMaterialLocalizations.delegates,
        home: home,
      ),
    );

void _tall(WidgetTester t, [double h = 3000]) {
  t.view.physicalSize = Size(800, h);
  t.view.devicePixelRatio = 1;
  addTearDown(t.view.resetPhysicalSize);
  addTearDown(t.view.resetDevicePixelRatio);
}

/// Every piece of text on screen.
List<String> _texts(WidgetTester t) => [
      for (final w in t.widgetList<Text>(find.byType(Text, skipOffstage: false)))
        if (w.data != null) w.data! else if (w.textSpan != null) w.textSpan!.toPlainText(),
    ];

void _noRawSlots(WidgetTester t) {
  for (final s in _texts(t)) {
    expect(s.contains(RegExp(r'\{[a-z]+\}')), isFalse, reason: 'an unfilled {slot} on screen: "$s"');
  }
}

class _Repo extends VisitorRepository {
  final List<VisitorEntity> rows;
  _Repo(this.rows) : super(ds: VisitorRemoteDataSource(dio: Dio()));
  @override
  Future<VisitorResult<List<VisitorEntity>>> listSocietyVisitors(String societyId, {int limit = 50}) async => VisitorSuccess(rows);
  @override
  Future<VisitorResult<List<VisitorEntity>>> getPendingApprovals() async => VisitorSuccess(const []);
}

VisitorEntity _v(String id, VisitorStatus s, VisitorType ty, {String? reason, DateTime? inAt, DateTime? outAt}) => VisitorEntity(
    id: id, name: 'Person $id', mobile: '9000000000', visitorType: ty, societyId: 's1', flatNumber: '101', wingName: 'A',
    status: s, rejectionReason: reason, checkedInAt: inAt, checkedOutAt: outAt, logs: const [], createdAt: DateTime(2026, 11, 13, 9));

void main() {
  test('a template keeps its slots in the language\'s own order and fills them', () {
    expect(translate('Across {n} open bills', 'mr'), contains('{n}'));       // the template itself still has the slot
    expect(translate('Across {n} open bills', 'en'), 'Across {n} open bills');
  });

  testWidgets('trf fills the slots in English and in Marathi', (t) async {
    late BuildContext ctx;
    Future<void> pump(String lang) => t.pumpWidget(MaterialApp(
          locale: Locale(lang),
          supportedLocales: kSupportedLocales,
          localizationsDelegates: GlobalMaterialLocalizations.delegates,
          home: Builder(builder: (c) {
            ctx = c;
            return const SizedBox();
          }),
        ));
    await pump('en');
    expect(ctx.trf('Hello, {name}', {'name': 'Ramesh'}), 'Hello, Ramesh');
    await pump('mr');
    expect(ctx.trf('Hello, {name}', {'name': 'Ramesh'}), 'नमस्कार, Ramesh');
  });

  group('the resident Home in Marathi', () {
    Future<void> open(WidgetTester t) async {
      _tall(t);
      await t.pumpWidget(_app(const ResidentDashboardScreen(), _resident,
          ['visitors', 'complaints', 'notices', 'amenities', 'my_bills', 'edit_my_info', 'parcels', 'domestic_help'],
          extra: [
            myBillsProvider.overrideWith((ref) async =>
                const MyBillsSummary(totalOutstanding: '8450.00', openCount: 2, overdueCount: 1, bills: [])),
          ]));
      await t.pump();
      await t.pump();
    }

    testWidgets('speaks Marathi in the title, greeting, dues card, actions, services and summary', (t) async {
      await open(t);
      for (final marathi in [
        'रहिवासी डॅशबोर्ड', 'थकीत देखभाल शुल्क', 'पहा आणि भरा', '1 मुदत उलटली', '2 न भरलेली बिले',
        'पाहुण्याला आमंत्रित करा', 'तक्रार नोंदवा', 'सोसायटी सेवा', 'उघड्या तक्रारी', 'माझे खाते',
      ]) {
        expect(find.text(marathi), findsOneWidget, reason: marathi);
      }
    });

    testWidgets('leaves none of its fixed English on screen', (t) async {
      await open(t);
      for (final english in [
        'Resident Dashboard', 'Outstanding maintenance', 'View and pay', 'Invite guest', 'Raise complaint',
        'Society services', 'Summary', 'My account', 'Open Complaints', 'Visitors Waiting', 'My Flat', 'Edit My Info',
        'Visitors', 'Parcels', 'Daily help', 'Complaints', 'Notices', 'Amenities', 'Need help now? Tell security and the committee.',
      ]) {
        expect(find.text(english), findsNothing, reason: 'still English: $english');
      }
      expect(find.textContaining('Good '), findsNothing);
      _noRawSlots(t);
    });

    testWidgets('the same screen in English is unchanged', (t) async {
      _tall(t);
      await t.pumpWidget(_app(const ResidentDashboardScreen(), _resident, ['complaints', 'my_bills', 'edit_my_info'], lang: 'en', extra: [
        myBillsProvider.overrideWith((ref) async =>
            const MyBillsSummary(totalOutstanding: '4200.00', openCount: 1, overdueCount: 0, bills: [])),
      ]));
      await t.pump();
      await t.pump();
      for (final english in ['Resident Dashboard', 'Outstanding maintenance', 'View and pay', 'Across 1 open bill', 'Payment due', 'Society services']) {
        expect(find.text(english), findsOneWidget, reason: english);
      }
      _noRawSlots(t);
    });
  });

  testWidgets('the guard\'s Staff Portal and Gate panel in Marathi', (t) async {
    _tall(t, 1600);
    await t.pumpWidget(_app(const StaffHomeScreen(), _guard, ['visitors', 'parcels', 'complaints', 'notices', 'staff'], extra: [
      gateSummaryProvider('s1').overrideWith((ref) async => const GateSummary(visitorsToday: 27, checkedInToday: 21, inside: 4)),
      currentStaffProvider.overrideWith((ref) async => null),
    ]));
    await t.pump();
    await t.pump();
    for (final marathi in ['कर्मचारी पोर्टल', 'नमस्कार, Ramesh', 'माझी कामे', 'हजेरी', 'पाहुण्यांची नोंद', 'पाहुणा नोंदवा', 'बाहेर सोडा', 'कोड तपासा']) {
      expect(find.text(marathi), findsOneWidget, reason: marathi);
    }
    for (final english in ['Staff Portal', 'My Operations', 'Attendance', 'Handover', 'Visitor Log', 'No staff profile linked']) {
      expect(find.text(english), findsNothing, reason: 'still English: $english');
    }
    _noRawSlots(t);
  });

  testWidgets('the visitor log in Marathi: tabs, button, statuses, types and the time lines', (t) async {
    _tall(t, 1800);
    final rows = [
      _v('1', VisitorStatus.checkedIn, VisitorType.guest, inAt: DateTime(2026, 11, 13, 9, 30)),
      _v('2', VisitorStatus.pending, VisitorType.delivery),
      _v('3', VisitorStatus.rejected, VisitorType.cab, reason: 'No pass'),
      _v('4', VisitorStatus.checkedOut, VisitorType.vendor, inAt: DateTime(2026, 11, 13, 8), outAt: DateTime(2026, 11, 13, 9)),
    ];
    await t.pumpWidget(_app(const VisitorListScreen(societyId: 's1'), _guard, ['visitors'],
        extra: [visitorRepositoryProvider.overrideWithValue(_Repo(rows))]));
    await t.pumpAndSettle();
    for (final marathi in ['सर्व पाहुणे', 'सध्या आत', 'पाहुणा नोंदवा', 'बाहेर सोडा', 'आत आले', 'प्रलंबित', 'नाकारले', 'बाहेर गेले']) {
      expect(find.text(marathi), findsWidgets, reason: marathi);
    }
    for (final english in ['All Visitors', 'Inside Now', 'Log Visitor', 'Check Out', 'Pending', 'Rejected', 'Checked In']) {
      expect(find.text(english), findsNothing, reason: 'still English: $english');
    }
    expect(find.textContaining('नाकारले: No pass'), findsOneWidget);
    _noRawSlots(t);
  });
}
