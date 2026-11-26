import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/staff/data/attendance_geo_api.dart';
import 'package:ar_society_app/features/staff/data/location_service.dart';
import 'package:ar_society_app/features/staff/domain/entities/attendance_geo.dart';
import 'package:ar_society_app/features/staff/presentation/providers/staff_providers.dart';

/// Check in or out, sending the phone's location when the society checks it.
///
/// If the society does not check location, this is the plain check-in or check-out. If it does, the phone's position is
/// read first (waiting a few seconds for a good reading) and sent along; the server decides. When the location cannot be
/// read: in `flag` mode the punch still goes through (the manager will see "no location"); in `block` mode it stops here
/// with the reason.
Future<void> punchWithLocation(BuildContext context, WidgetRef ref, String staffId, {required bool checkIn}) async {
  final notifier = ref.read(attendanceProvider.notifier);
  GeoStatus? status;
  try {
    status = await ref.read(attendanceGeoApiProvider).status();
  } catch (_) {
    status = null; // cannot tell: carry on, the server applies the rule
  }

  GeoReading? reading;
  if (status != null && status.enabled) {
    if (!context.mounted) return;
    final outcome = await _readPhone(context, ref, status);
    reading = outcome.reading;
    if (reading == null) {
      if (!context.mounted) return;
      final blocked = status.mode == 'block';
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text(blocked ? outcome.problem! : '${outcome.problem} Going ahead without it: your manager will see this.'),
        backgroundColor: blocked ? AppTheme.error : AppTheme.warning,
        behavior: SnackBarBehavior.floating,
        duration: const Duration(seconds: 6),
      ));
      if (blocked) return;
    }
  }

  if (checkIn) {
    await notifier.checkIn(staffId, location: reading);
  } else {
    await notifier.checkOut(staffId, location: reading);
  }
}

class _Outcome {
  final GeoReading? reading;
  final String? problem;
  const _Outcome(this.reading, this.problem);
}

/// Reads the position with a small progress dialog ("Getting your location, accurate to ±12 m").
Future<_Outcome> _readPhone(BuildContext context, WidgetRef ref, GeoStatus status) async {
  final accuracy = ValueNotifier<double?>(null);
  showDialog<void>(
    context: context,
    barrierDismissible: false,
    useRootNavigator: true,
    builder: (_) => PopScope(
      canPop: false,
      child: AlertDialog(
        content: Row(children: [
          const SizedBox(width: 26, height: 26, child: CircularProgressIndicator(strokeWidth: 3)),
          const SizedBox(width: 18),
          Expanded(
            child: ValueListenableBuilder<double?>(
              valueListenable: accuracy,
              builder: (_, a, __) => Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
                const Text('Getting your location…', style: TextStyle(fontWeight: FontWeight.w700)),
                const SizedBox(height: 4),
                Text(
                    a == null
                        ? 'Stay outdoors or near a window.'
                        : 'Accurate to ${a.round()} m (need ${status.maxAccuracyM.round()} m)',
                    style: TextStyle(fontSize: 12.5, color: AppTheme.textSecondary)),
              ]),
            ),
          ),
        ]),
      ),
    ),
  );
  try {
    final reading = await ref.read(locationServiceProvider).read(
          wantAccuracyM: status.maxAccuracyM,
          onAccuracy: (a) => accuracy.value = a,
        );
    return _Outcome(reading, null);
  } on LocationUnavailable catch (e) {
    return _Outcome(null, e.message);
  } catch (_) {
    return const _Outcome(null, "Couldn't read your location.");
  } finally {
    if (context.mounted) Navigator.of(context, rootNavigator: true).pop();
    accuracy.dispose();
  }
}
