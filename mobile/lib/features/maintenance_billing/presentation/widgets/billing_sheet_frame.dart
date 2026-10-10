import 'package:flutter/material.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';

/// The body of a maintenance-billing form sheet. Kept under this name for the many sheets that use it; it is the
/// shared [AppSheetFrame] (header, rule, scrolling fields).
class BillingSheetFrame extends StatelessWidget {
  final String title;
  final String? subtitle;
  final Widget child;
  const BillingSheetFrame({super.key, required this.title, this.subtitle, required this.child});

  @override
  Widget build(BuildContext context) => AppSheetFrame(title: title, subtitle: subtitle, child: child);
}
