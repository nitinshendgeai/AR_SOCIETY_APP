import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/features/society_settings/data/models/society_settings_model.dart';
import 'package:ar_society_app/features/society_settings/data/repositories/society_settings_repository.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:dio/dio.dart';

final societySettingsRepoProvider = Provider<SocietySettingsRepository>(
  (_) => SocietySettingsRepository(),
);

// ── Current society (loaded from GET /societies/ - first result) ──────────────

final currentSocietyProvider =
    AsyncNotifierProvider<CurrentSocietyNotifier, SocietySettingsModel>(
        CurrentSocietyNotifier.new);

class CurrentSocietyNotifier
    extends AsyncNotifier<SocietySettingsModel> {
  @override
  Future<SocietySettingsModel> build() async {
    // Fetch all societies visible to current user and return the first one.
    final dio = ApiClient.instance;
    final r   = await dio.get('/societies/');
    final list = r.data as List;
    if (list.isEmpty) {
      throw Exception('No society found for your account');
    }
    return SocietySettingsModel.fromJson(list.first as Map<String, dynamic>);
  }

  Future<void> refresh() async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(() => build());
  }

  Future<void> updateSettings(Map<String, dynamic> data) async {
    final current = state.valueOrNull;
    if (current == null) return;
    final updated = await ref
        .read(societySettingsRepoProvider)
        .updateSociety(current.id, data);
    state = AsyncData(updated);
  }
}
