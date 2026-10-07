import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/notices/data/notices_api.dart';

final noticesApiProvider = Provider<NoticesApi>((_) => NoticesApi());

/// The notices meant for the signed-in person, urgent first.
final noticeBoardProvider = FutureProvider.autoDispose.family<List<NoticeItem>, String>(
  (ref, societyId) => ref.watch(noticesApiProvider).board(societyId),
);

typedef ManageKey = ({String societyId, String? status});

/// Every notice of the society (committee only), optionally of one status.
final noticeManageProvider = FutureProvider.autoDispose.family<List<NoticeItem>, ManageKey>(
  (ref, k) => ref.watch(noticesApiProvider).manage(k.societyId, status: k.status),
);

final noticeProvider = FutureProvider.autoDispose.family<NoticeItem, String>(
  (ref, id) => ref.watch(noticesApiProvider).get(id),
);

final ackReportProvider = FutureProvider.autoDispose.family<AckReport, String>(
  (ref, id) => ref.watch(noticesApiProvider).ackReport(id),
);

/// Emergencies in force, checked again every minute for as long as something is watching.
final activeAlertsProvider = StreamProvider.autoDispose<List<EmergencyAlertItem>>((ref) async* {
  final societyId = ref.watch(currentUserProvider)?.societyId;
  if (societyId == null) {
    yield const [];
    return;
  }
  final api = ref.watch(noticesApiProvider);
  while (true) {
    try {
      yield await api.activeAlerts(societyId);
    } catch (_) {
      // Keep what is on screen; try again next minute.
    }
    await Future<void>.delayed(const Duration(seconds: 60));
  }
});

final alertHistoryProvider = FutureProvider.autoDispose.family<List<EmergencyAlertItem>, String>(
  (ref, societyId) => ref.watch(noticesApiProvider).alertHistory(societyId),
);

/// After anything on a notice or alert changes.
void invalidateNotices(WidgetRef ref) {
  ref.invalidate(noticeBoardProvider);
  ref.invalidate(noticeManageProvider);
  ref.invalidate(noticeProvider);
  ref.invalidate(ackReportProvider);
  ref.invalidate(activeAlertsProvider);
  ref.invalidate(alertHistoryProvider);
}
