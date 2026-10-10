import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/core/help/help_launcher.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';

UserEntity _user(List<String> roles) =>
    UserEntity(id: '1', email: 'a@b.c', fullName: 'A', roles: roles, societyId: 's');

void main() {
  test('each kind of person opens the part of the guide written for them', () {
    expect(helpRoleFor(_user(['Resident'])), 'resident');
    expect(helpRoleFor(_user(['Security Staff'])), 'guard');
    expect(helpRoleFor(_user(['Housekeeping Supervisor'])), 'staff');
    expect(helpRoleFor(_user(['Manager'])), 'manager');
    expect(helpRoleFor(_user(['Society Admin'])), 'committee');
    expect(helpRoleFor(_user(['Committee Treasurer'])), 'committee');
    expect(helpRoleFor(null), isNull);
    expect(helpGuideUrl(_user(['Resident'])), '/help/DUX_OS_Help_Guide.html?role=resident');
    expect(helpGuideUrl(null), '/help/DUX_OS_Help_Guide.html');
  });

  test('the guide the app serves is the one kept in docs/user-guide', () {
    // The web build can see only mobile/, so web/help/ holds a copy; this fails when only one of them was updated.
    for (final name in ['DUX_OS_Help_Guide.html', 'DUX_OS_Help_Guide.pdf']) {
      final served = File('web/help/$name');
      final source = File('../docs/user-guide/$name');
      expect(served.existsSync(), isTrue, reason: 'web/help/$name is missing');
      if (!source.existsSync()) continue; // a checkout of mobile/ alone
      expect(served.readAsBytesSync(), source.readAsBytesSync(),
          reason: 'copy docs/user-guide/$name to mobile/web/help/');
    }
  });
}
