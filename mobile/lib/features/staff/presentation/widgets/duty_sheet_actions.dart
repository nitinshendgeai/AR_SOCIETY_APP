import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:ar_society_app/features/accounts/presentation/widgets/accounts_widgets.dart' show deliverPdf;
import 'package:ar_society_app/features/staff/data/repositories/staff_repository.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// Downloads the printable sheet [load] returns as [fileName]. When there is
/// nothing to print (or the user may not print it) the server's reason is shown.
Future<void> deliverSheet(
  BuildContext context,
  Future<StaffResult<Uint8List>> load,
  String fileName,
) async {
  final result = await load;
  if (!context.mounted) return;
  switch (result) {
    case StaffSuccess(:final data):
      await deliverPdf(context, () async => data, fileName, share: false);
    case StaffFailure(:final message):
      AppToast.error(context, message);
  }
}

String isoDay(DateTime d) =>
    '${d.year}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';
