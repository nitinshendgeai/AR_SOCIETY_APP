import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/core/config/edition.dart';
import 'package:ar_society_app/core/navigation/app_menu.dart';
import 'package:ar_society_app/core/navigation/route_access.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';

UserEntity _user(List<String> roles) => UserEntity(
    id: 'u', email: 'a@b.c', fullName: 'A B', roles: roles, societyId: 's1', termsAccepted: true);

// Every form code a society admin is granted, i.e. the full menu.
const _everything = {
  'platform_admin', 'residents', 'tenants', 'pending_resident_changes', 'staff', 'setup_wizard', 'shops',
  'parking_management', 'assets', 'visitors', 'parcels', 'domestic_help', 'complaints', 'notices', 'amenities',
  'meetings', 'polls', 'documents', 'certificates', 'manager_checklist', 'checklist_templates', 'inventory', 'vendors',
  'vendor_master', 'maintenance_billing', 'maintenance_elements', 'online_payments', 'defaulters', 'vendor_bills',
  'bank_reconciliation', 'accounts', 'users_roles', 'permission_matrix', 'forms_matrix', 'society_settings',
  'automation', 'my_bills', 'edit_my_info',
};

Set<String> _codes(Set<String> granted, UserEntity u, {required bool field}) => {
      for (final c in visibleMenuCategories(granted, user: u, fieldEdition: field))
        for (final i in c.items) i.formCode,
    };

void main() {
  group('who may use the field build', () {
    test('residents, tenants, security, technical and gym staff', () {
      for (final role in ['Resident', 'Tenant', 'Security Staff', 'Security Supervisor', 'Technical Staff', 'Technical Supervisor', 'Gym Trainer']) {
        expect(AppEdition.allowsUser(_user([role])), isTrue, reason: role);
      }
    });

    test('society admins, committee members and managers, for Accounts and Stores', () {
      for (final role in ['Society Admin', 'Committee Member', 'Manager']) {
        expect(AppEdition.allowsUser(_user([role])), isTrue, reason: role);
        expect(AppEdition.allowsUser(_user([role, 'Resident'])), isTrue, reason: '$role + Resident');
      }
    });

    test('a platform admin is turned away, even when they also hold a field role', () {
      expect(AppEdition.allowsUser(_user(['Platform Admin'])), isFalse);
      expect(AppEdition.allowsUser(_user(['Platform Admin', 'Resident'])), isFalse);
    });
  });

  group('the field menu', () {
    final u = _user(['Resident']);

    test('keeps only the field screens', () {
      expect(_codes(_everything, u, field: true), _everything.intersection(AppEdition.fieldFormCodes));
    });

    test('has Accounts and Stores', () {
      final codes = _codes(_everything, u, field: true);
      expect(codes.containsAll(['accounts', 'inventory']), isTrue);
    });

    test('has no billing, administration or other management screens', () {
      final codes = _codes(_everything, u, field: true);
      for (final web in ['maintenance_billing', 'vendors', 'users_roles', 'society_settings', 'residents', 'platform_admin']) {
        expect(codes.contains(web), isFalse, reason: web);
      }
    });

    test('the full build is unchanged', () {
      expect(_codes(_everything, u, field: false), _everything);
    });
  });

  group('field route guard', () {
    RouteDenial? deny(String path) =>
        routeDenial(path: path, home: '/resident', platformAdmin: false, granted: _everything, fieldEdition: true);

    test('bounces management screens even when granted', () {
      for (final path in ['/billing/maintenance', '/users', '/vendors/master', '/society-settings']) {
        expect(deny(path)?.location, '/resident', reason: path);
      }
    });

    test('leaves the field screens, Accounts and Stores alone', () {
      expect(deny('/staff'), isNull);
      expect(deny('/residents/me'), isNull);
      expect(deny('/accounts'), isNull);
      expect(deny('/stores'), isNull);
    });

    test('the full build still follows the grants', () {
      expect(
          routeDenial(path: '/accounts', home: '/admin', platformAdmin: false, granted: _everything, fieldEdition: false),
          isNull);
    });
  });
}
