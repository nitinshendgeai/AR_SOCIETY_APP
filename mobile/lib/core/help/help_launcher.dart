import 'package:flutter/foundation.dart';
import 'package:ar_society_app/features/auth/domain/entities/user_entity.dart';

import 'help_open_io.dart' if (dart.library.js_interop) 'help_open_web.dart' as impl;

/// The help guide is a web page served beside the app (web/help/, copied from
/// docs/user-guide/), so it can be opened only where the app runs in a browser.
bool get helpAvailable => kIsWeb;

/// Where the guide is, relative to the app's own address.
const helpGuidePath = '/help/DUX_OS_Help_Guide.html';

/// The part of the guide a person needs first: the guide has one chip per kind
/// of person. [null] shows everything.
String? helpRoleFor(UserEntity? user) {
  if (user == null) return null;
  if (user.isAdminOrCommittee) return 'committee';
  if (user.isManager) return 'manager';
  if (user.isSecurity) return 'guard';
  if (user.isStaff) return 'staff';
  if (user.isResident) return 'resident';
  return null;
}

String helpGuideUrl(UserEntity? user) {
  final role = helpRoleFor(user);
  return role == null ? helpGuidePath : '$helpGuidePath?role=$role';
}

/// Opens the guide in a new browser tab.
void openHelp(UserEntity? user) => impl.openHelpPage(helpGuideUrl(user));
