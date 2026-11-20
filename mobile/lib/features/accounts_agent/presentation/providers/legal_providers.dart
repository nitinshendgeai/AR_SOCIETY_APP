import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/features/accounts_agent/data/legal_api.dart';

final legalApiProvider = Provider<LegalApi>((_) => LegalApi());

final complianceOverviewProvider = FutureProvider.autoDispose<ComplianceOverview>((ref) => ref.watch(legalApiProvider).overview());
final legalDocumentsProvider = FutureProvider.autoDispose<List<LegalDocument>>((ref) => ref.watch(legalApiProvider).documents());
final legalRulesProvider = FutureProvider.autoDispose<List<LegalRule>>((ref) => ref.watch(legalApiProvider).rules());
final legalReviewsProvider = FutureProvider.autoDispose<List<LegalReview>>((ref) => ref.watch(legalApiProvider).reviews());
final resolutionsProvider = FutureProvider.autoDispose<List<SocietyResolution>>((ref) => ref.watch(legalApiProvider).resolutions());
final complianceCalendarProvider = FutureProvider.autoDispose<List<ComplianceItem>>((ref) => ref.watch(legalApiProvider).calendar());
final ledgerMapProvider = FutureProvider.autoDispose<LedgerMap>((ref) => ref.watch(legalApiProvider).ledgerMap());
final arrearsProvider = FutureProvider.autoDispose<ArrearsReport>((ref) => ref.watch(legalApiProvider).arrears());

void invalidateLegal(WidgetRef ref) {
  ref.invalidate(complianceOverviewProvider);
  ref.invalidate(legalDocumentsProvider);
  ref.invalidate(legalRulesProvider);
  ref.invalidate(legalReviewsProvider);
  ref.invalidate(resolutionsProvider);
  ref.invalidate(complianceCalendarProvider);
  ref.invalidate(arrearsProvider);
  ref.invalidate(ledgerMapProvider);
}
