import 'package:flutter/material.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';

/// Rounded, keyboard-aware bottom-sheet body used by the maintenance
/// billing forms.
class BillingSheetFrame extends StatelessWidget {
  final String title;
  final Widget child;
  const BillingSheetFrame({super.key, required this.title, required this.child});

  @override
  Widget build(BuildContext context) => Container(
        decoration: const BoxDecoration(
          color: AppTheme.cardBg,
          borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
        ),
        padding: EdgeInsets.only(
          left: 20, right: 20, top: 20,
          bottom: MediaQuery.of(context).viewInsets.bottom + 20,
        ),
        child: SafeArea(
          top: false,
          child: SingleChildScrollView(
            child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, mainAxisSize: MainAxisSize.min, children: [
              Text(title, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
              const SizedBox(height: 16),
              child,
            ]),
          ),
        ),
      );
}
