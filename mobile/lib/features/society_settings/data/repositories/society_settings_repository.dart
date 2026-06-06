import 'package:ar_society_app/features/society_settings/data/datasources/society_settings_datasource.dart';
import 'package:ar_society_app/features/society_settings/data/models/society_settings_model.dart';

class SocietySettingsRepository {
  final SocietySettingsDataSource _ds;
  SocietySettingsRepository({SocietySettingsDataSource? ds})
      : _ds = ds ?? SocietySettingsDataSource();

  Future<SocietySettingsModel> getSociety(String id) => _ds.getSociety(id);

  Future<SocietySettingsModel> updateSociety(
          String id, Map<String, dynamic> data) =>
      _ds.updateSociety(id, data);
}
