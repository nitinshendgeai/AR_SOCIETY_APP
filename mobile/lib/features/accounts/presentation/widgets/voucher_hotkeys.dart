import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/router/app_router.dart';

/// Tally's voucher keys, kept: F4 Contra, F5 Payment, F6 Receipt, F7 Journal.
const kVoucherHotkeys = <(String, LogicalKeyboardKey, String)>[
  ('contra', LogicalKeyboardKey.f4, 'F4'),
  ('payment', LogicalKeyboardKey.f5, 'F5'),
  ('receipt', LogicalKeyboardKey.f6, 'F6'),
  ('journal', LogicalKeyboardKey.f7, 'F7'),
];

/// The key that starts a voucher of [type] ("F6"), or null.
String? voucherHotkeyLabel(String type) => kVoucherHotkeys.where((h) => h.$1 == type).firstOrNull?.$3;

/// The F-key bindings for [onType], to merge into a screen's own shortcuts.
Map<ShortcutActivator, VoidCallback> voucherHotkeyBindings(void Function(String type) onType) => {
      for (final h in kVoucherHotkeys) SingleActivator(h.$2): () => onType(h.$1),
    };

String _newVoucher(String type) =>
    Uri(path: AppRoutes.accountsVoucherNew, queryParameters: {'type': type}).toString();

/// Around an Accounts screen: F4 / F5 / F6 / F7 open a new Contra / Payment / Receipt / Journal voucher from anywhere
/// in it, even while typing in a field. [onType] replaces the default (open the voucher form).
///
/// In a browser the F-keys are the browser's too (F5 reloads); the page keeps them while a screen with these shortcuts
/// is open.
class VoucherHotkeys extends StatelessWidget {
  final Widget child;
  final void Function(BuildContext context, String type)? onType;
  const VoucherHotkeys({super.key, required this.child, this.onType});

  @override
  Widget build(BuildContext context) => CallbackShortcuts(
        bindings: voucherHotkeyBindings((t) => onType != null ? onType!(context, t) : context.push(_newVoucher(t))),
        // Something inside always holds focus, so the keys work before a field is clicked.
        child: Focus(autofocus: true, skipTraversal: true, child: child),
      );
}
