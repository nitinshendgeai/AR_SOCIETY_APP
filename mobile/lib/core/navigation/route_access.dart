import 'package:flutter/material.dart';

/// Client-side route access, driven by the same server-granted form codes the menu uses
/// (`GET /roles/forms/mine`, see app_menu.dart), so the menu and the address bar agree.
///
/// This is a convenience, not security: the backend refuses every unauthorized request regardless. It only keeps a
/// typed URL, bookmark or browser refresh from opening a management screen the person cannot use.
///
/// Deliberately limited to management screens. Screens that residents, tenants and staff reach from their own
/// dashboards (visitors, complaints, notices, amenities, meetings, polls, documents, certificates, parcels, domestic
/// help, my bills, edit my info and the whole Staff area) are NOT guarded here: the Forms Matrix has known gaps for
/// some of those roles (for example a Tenant is not granted "my_bills" although the dashboard links to it), and
/// bouncing them would remove something they use today. Their access stays with the backend.

/// Longest prefix first. A path matches on a whole segment (`/users` matches `/users/12` but not `/usersx`).
const _prefixToForm = <(String, String?)>[
  ('/residents/me', null),                                  // a member's own profile (edit_my_info): not guarded
  ('/residents/edit-requests', 'pending_resident_changes'),
  ('/residents', 'residents'),
  ('/tenants', 'tenants'),
  ('/shops', 'shops'),
  ('/automation', 'automation'),
  ('/users', 'users_roles'),
  ('/permission-matrix', 'permission_matrix'),
  ('/forms-matrix', 'forms_matrix'),
  ('/society-settings', 'society_settings'),
  ('/wings', 'setup_wizard'),
  ('/flats', 'setup_wizard'),
  ('/structure-wizard', 'setup_wizard'),
  ('/parking/management', 'parking_management'),
  ('/staff/checklist-templates', 'checklist_templates'),
  ('/manager-checklist', 'manager_checklist'),
  ('/billing/online-payments', 'online_payments'),
  ('/billing/bank-reconciliation', 'bank_reconciliation'),
  ('/billing/maintenance-elements', 'maintenance_elements'),
  ('/billing/maintenance', 'maintenance_billing'),
  ('/billing/defaulters', 'defaulters'),
  ('/vendors/bills', 'vendor_bills'),
  ('/vendors/master', 'vendor_master'),
  ('/vendors/import', 'vendor_master'),
  ('/vendors/tds-review', 'vendor_master'),
  ('/vendors', 'vendors'),
  ('/accounts', 'accounts'),
  ('/assets', 'assets'),
  ('/stores', 'inventory'),
];

bool _under(String path, String prefix) => path == prefix || path.startsWith('$prefix/');

/// The form code that gates [path], or null when the path is not guarded here.
String? formCodeForPath(String path) {
  final p = _normalize(path);
  String? best;
  var bestLen = -1;
  for (final (prefix, code) in _prefixToForm) {
    if (_under(p, prefix) && prefix.length > bestLen) {
      best = code;
      bestLen = prefix.length;
    }
  }
  return best;
}

String _normalize(String path) {
  final q = path.indexOf('?');
  var p = q < 0 ? path : path.substring(0, q);
  if (p.length > 1 && p.endsWith('/')) p = p.substring(0, p.length - 1);
  return p;
}

/// The role dashboards. Each person has exactly one (see userRoleHome); the others are not theirs to open.
const dashboardPaths = <String>{'/admin', '/committee', '/resident', '/security', '/manager', '/supervisor'};

class RouteDenial {
  final String location;
  /// Whether to tell the person (a typed URL for a screen they have no grant for), as opposed to quietly landing
  /// someone on their own dashboard.
  final bool notify;
  const RouteDenial(this.location, {required this.notify});
}

/// Where to send the person instead of [path], or null to let it open.
///
/// [granted] is the person's form codes, or null while unknown (not loaded yet, or the request failed): an unknown
/// grant list never blocks anything, since the backend stays authoritative. [home] is their own dashboard.
RouteDenial? routeDenial({
  required String path,
  required String home,
  required bool platformAdmin,
  required Set<String>? granted,
}) {
  final p = _normalize(path);
  if (platformAdmin) return null;                          // the platform console has its own guards
  if (dashboardPaths.contains(p)) {
    return p == home ? null : RouteDenial(home, notify: false);
  }
  final code = formCodeForPath(p);
  if (code == null || granted == null || granted.contains(code)) return null;
  // Never send someone to a place that would send them straight back.
  if (_normalize(home) == p || formCodeForPath(home) != null) return null;
  return RouteDenial(home, notify: true);
}

/// Set when a typed or bookmarked address was turned away; [RouteDeniedListener] tells the person.
final ValueNotifier<int> routeDeniedSignal = ValueNotifier<int>(0);

const routeDeniedMessage = 'You do not have access to that screen.';

/// Shows a one-line message when [routeDeniedSignal] fires. Wrap the signed-in pages with it.
class RouteDeniedListener extends StatefulWidget {
  final Widget child;
  const RouteDeniedListener({super.key, required this.child});

  @override
  State<RouteDeniedListener> createState() => _RouteDeniedListenerState();
}

class _RouteDeniedListenerState extends State<RouteDeniedListener> {
  @override
  void initState() {
    super.initState();
    routeDeniedSignal.addListener(_onDenied);
  }

  @override
  void dispose() {
    routeDeniedSignal.removeListener(_onDenied);
    super.dispose();
  }

  void _onDenied() {
    // The redirect that raised this is still resolving, so show the message after the frame.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      final messenger = ScaffoldMessenger.maybeOf(context);
      messenger?.hideCurrentSnackBar();
      messenger?.showSnackBar(const SnackBar(content: Text(routeDeniedMessage), behavior: SnackBarBehavior.floating));
    });
  }

  @override
  Widget build(BuildContext context) => widget.child;
}
