import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/core/navigation/app_menu.dart';
import 'package:ar_society_app/core/router/app_router.dart';

void main() {
  test('no two AppRoutes constants share a path (the first GoRoute would win and the other screen never opens)', () {
    final src = File('lib/core/router/app_router.dart').readAsStringSync();
    final paths = <String, List<String>>{};
    for (final m in RegExp(r"static const (\w+)\s*=\s*'([^']+)'").allMatches(src)) {
      paths.putIfAbsent(m.group(2)!, () => []).add(m.group(1)!);
    }
    final shared = {for (final e in paths.entries) if (e.value.length > 1) e.key: e.value};
    expect(shared, isEmpty);
  });

  test('the Managing Committee menu item opens the committee register, not the committee dashboard', () {
    final item = appMenuCategories.expand((c) => c.items).firstWhere((i) => i.label == 'Managing Committee');
    expect(item.route, AppRoutes.committee);
    expect(item.route, isNot(AppRoutes.committeeHome));
  });
}
