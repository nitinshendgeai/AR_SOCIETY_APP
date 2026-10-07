import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';

double? _numOrNull(Object? v) => v == null ? null : double.tryParse(v.toString());
DateTime? _dateOrNull(Object? v) => v == null ? null : DateTime.tryParse(v.toString());
String _apiDate(DateTime d) =>
    '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

// ── What a society owns ──────────────────────────────────────────────────────

/// (api value, label, icon) — the order they are offered in.
const kAssetCategories = <(String, String, IconData)>[
  ('air_conditioner', 'Air conditioner', Icons.ac_unit_rounded),
  ('pump', 'Water pump', Icons.water_rounded),
  ('water_tank', 'Water tank', Icons.water_damage_outlined),
  ('water_treatment', 'STP / WTP / RO plant', Icons.opacity_rounded),
  ('lift', 'Lift', Icons.elevator_rounded),
  ('generator', 'Generator (DG set)', Icons.bolt_rounded),
  ('electrical', 'Electrical', Icons.electrical_services_rounded),
  ('solar', 'Solar', Icons.wb_sunny_outlined),
  ('cctv', 'CCTV', Icons.videocam_outlined),
  ('intercom', 'Intercom', Icons.phone_in_talk_outlined),
  ('biometric', 'Biometric', Icons.fingerprint_rounded),
  ('fire_safety', 'Fire safety', Icons.local_fire_department_outlined),
  ('hvac', 'Ventilation / HVAC', Icons.air_rounded),
  ('gym_equipment', 'Gym equipment', Icons.fitness_center_rounded),
  ('garden_equipment', 'Garden equipment', Icons.yard_outlined),
  ('furniture', 'Furniture', Icons.chair_outlined),
  ('it_equipment', 'IT equipment', Icons.computer_outlined),
  ('vehicle', 'Vehicle', Icons.directions_car_outlined),
  ('other', 'Other', Icons.category_outlined),
];

String assetCategoryLabel(String c) => kAssetCategories.where((e) => e.$1 == c).firstOrNull?.$2 ?? c;
IconData assetCategoryIcon(String c) => kAssetCategories.where((e) => e.$1 == c).firstOrNull?.$3 ?? Icons.category_outlined;

const kAssetStatuses = <(String, String)>[
  ('active', 'In use'),
  ('under_maintenance', 'Under maintenance'),
  ('retired', 'Retired'),
  ('disposed', 'Disposed'),
  ('lost', 'Lost'),
];
String assetStatusLabel(String s) => kAssetStatuses.where((e) => e.$1 == s).firstOrNull?.$2 ?? s;

const kMaintenanceTypes = <(String, String)>[
  ('preventive', 'Routine service'),
  ('corrective', 'Repair'),
  ('emergency', 'Emergency repair'),
  ('amc_service', 'AMC visit'),
];
String maintenanceTypeLabel(String t) => kMaintenanceTypes.where((e) => e.$1 == t).firstOrNull?.$2 ?? t;

/// Colour for a service status ("overdue", "due_soon", "ok", "none").
Color serviceColor(String s) => switch (s) {
      'overdue' => AppTheme.error,
      'due_soon' => AppTheme.warning,
      'ok' => AppTheme.success,
      _ => AppTheme.textSecondary,
    };

String serviceLabel(String s, int? days) => switch (s) {
      'overdue' => days == null ? 'Service overdue' : 'Overdue by ${-days} day${days == -1 ? '' : 's'}',
      'due_soon' => days == 0 ? 'Service due today' : 'Service in $days day${days == 1 ? '' : 's'}',
      'ok' => 'Service on schedule',
      _ => 'No service schedule',
    };

Color warrantyColor(String s) => switch (s) {
      'expired' => AppTheme.error,
      'expiring' => AppTheme.warning,
      'active' => AppTheme.success,
      _ => AppTheme.textSecondary,
    };

String warrantyLabel(String s) => switch (s) {
      'expired' => 'Warranty ended',
      'expiring' => 'Warranty ends soon',
      'active' => 'Under warranty',
      _ => 'No warranty',
    };

// ── Models ───────────────────────────────────────────────────────────────────

class Asset {
  final String id;
  final String assetCode;
  final String name;
  final String category;
  final String status;
  final String? description;
  final String? location;
  final DateTime? purchaseDate;
  final double? purchaseCost;
  final String? vendorName;
  final String? vendorContact;
  final String? invoiceNumber;
  final DateTime? warrantyExpiry;
  final String? serialNumber;
  final String? modelNumber;
  final int? expectedLifeYears;
  final int? serviceIntervalMonths;
  final DateTime? lastServicedOn;
  final DateTime? nextServiceDue;
  final String warrantyStatus;
  final String serviceStatus;
  final int? daysToService;

  const Asset({
    required this.id,
    required this.assetCode,
    required this.name,
    required this.category,
    required this.status,
    this.description,
    this.location,
    this.purchaseDate,
    this.purchaseCost,
    this.vendorName,
    this.vendorContact,
    this.invoiceNumber,
    this.warrantyExpiry,
    this.serialNumber,
    this.modelNumber,
    this.expectedLifeYears,
    this.serviceIntervalMonths,
    this.lastServicedOn,
    this.nextServiceDue,
    this.warrantyStatus = 'none',
    this.serviceStatus = 'none',
    this.daysToService,
  });

  factory Asset.fromJson(Map<String, dynamic> j) => Asset(
        id: j['id'] as String,
        assetCode: j['asset_code'] as String? ?? '',
        name: j['name'] as String? ?? '',
        category: j['asset_category'] as String? ?? 'other',
        status: j['status'] as String? ?? 'active',
        description: j['description'] as String?,
        location: j['location'] as String?,
        purchaseDate: _dateOrNull(j['purchase_date']),
        purchaseCost: _numOrNull(j['purchase_cost']),
        vendorName: j['vendor_name'] as String?,
        vendorContact: j['vendor_contact'] as String?,
        invoiceNumber: j['invoice_number'] as String?,
        warrantyExpiry: _dateOrNull(j['warranty_expiry']),
        serialNumber: j['serial_number'] as String?,
        modelNumber: j['model_number'] as String?,
        expectedLifeYears: j['expected_life_years'] as int?,
        serviceIntervalMonths: j['service_interval_months'] as int?,
        lastServicedOn: _dateOrNull(j['last_serviced_on']),
        nextServiceDue: _dateOrNull(j['next_service_due']),
        warrantyStatus: j['warranty_status'] as String? ?? 'none',
        serviceStatus: j['service_status'] as String? ?? 'none',
        daysToService: j['days_to_service'] as int?,
      );

  /// No longer with the society or out of use: needs no service.
  bool get isRetired => const {'retired', 'disposed', 'lost'}.contains(status);
}

class AssetSummary {
  final int total, active, underMaintenance, retired;
  final double totalPurchaseCost;
  final int warrantyExpiring, warrantyExpired, serviceOverdue, serviceDueSoon, amcExpiring;

  const AssetSummary({
    this.total = 0,
    this.active = 0,
    this.underMaintenance = 0,
    this.retired = 0,
    this.totalPurchaseCost = 0,
    this.warrantyExpiring = 0,
    this.warrantyExpired = 0,
    this.serviceOverdue = 0,
    this.serviceDueSoon = 0,
    this.amcExpiring = 0,
  });

  factory AssetSummary.fromJson(Map<String, dynamic> j) => AssetSummary(
        total: j['total'] as int? ?? 0,
        active: j['active'] as int? ?? 0,
        underMaintenance: j['under_maintenance'] as int? ?? 0,
        retired: j['retired'] as int? ?? 0,
        totalPurchaseCost: _numOrNull(j['total_purchase_cost']) ?? 0,
        warrantyExpiring: j['warranty_expiring'] as int? ?? 0,
        warrantyExpired: j['warranty_expired'] as int? ?? 0,
        serviceOverdue: j['service_overdue'] as int? ?? 0,
        serviceDueSoon: j['service_due_soon'] as int? ?? 0,
        amcExpiring: j['amc_expiring'] as int? ?? 0,
      );

  int get needsService => serviceOverdue + serviceDueSoon;
}

class AssetService {
  final String id;
  final String type;
  final String status; // scheduled | in_progress | completed | cancelled
  final DateTime scheduledDate;
  final DateTime? completedDate;
  final String? vendorName;
  final double? cost;
  final String? description;
  final String? findings;
  final DateTime? nextDueDate;

  const AssetService({
    required this.id,
    required this.type,
    required this.status,
    required this.scheduledDate,
    this.completedDate,
    this.vendorName,
    this.cost,
    this.description,
    this.findings,
    this.nextDueDate,
  });

  factory AssetService.fromJson(Map<String, dynamic> j) => AssetService(
        id: j['id'] as String,
        type: j['maintenance_type'] as String? ?? 'preventive',
        status: j['status'] as String? ?? 'scheduled',
        scheduledDate: DateTime.parse(j['scheduled_date'] as String),
        completedDate: _dateOrNull(j['completed_date']),
        vendorName: j['vendor_name'] as String?,
        cost: _numOrNull(j['cost']),
        description: j['description'] as String?,
        findings: j['findings'] as String?,
        nextDueDate: _dateOrNull(j['next_due_date']),
      );

  bool get isOpen => status == 'scheduled' || status == 'in_progress';
}

class AssetAmc {
  final String id;
  final String vendorName;
  final String? contractNumber;
  final DateTime startDate;
  final DateTime endDate;
  final double? annualCost;
  final String? coverage;
  final bool comprehensive;

  const AssetAmc({
    required this.id,
    required this.vendorName,
    this.contractNumber,
    required this.startDate,
    required this.endDate,
    this.annualCost,
    this.coverage,
    this.comprehensive = false,
  });

  factory AssetAmc.fromJson(Map<String, dynamic> j) => AssetAmc(
        id: j['id'] as String,
        vendorName: j['vendor_name'] as String? ?? '',
        contractNumber: j['contract_number'] as String?,
        startDate: DateTime.parse(j['start_date'] as String),
        endDate: DateTime.parse(j['end_date'] as String),
        annualCost: _numOrNull(j['annual_cost']),
        coverage: j['coverage'] as String?,
        comprehensive: j['is_comprehensive'] as bool? ?? false,
      );

  bool get ended => endDate.isBefore(DateTime.now().subtract(const Duration(days: 1)));
  int get daysLeft => endDate.difference(DateTime.now()).inDays;
}

class LinkedContract {
  final String id, number, name, status;
  final DateTime startDate, endDate;
  final double? annualValue;
  const LinkedContract(this.id, this.number, this.name, this.status, this.startDate, this.endDate, this.annualValue);

  factory LinkedContract.fromJson(Map<String, dynamic> j) => LinkedContract(
        j['id'] as String,
        j['contract_number'] as String? ?? '',
        j['contract_name'] as String? ?? '',
        j['status'] as String? ?? '',
        DateTime.parse(j['start_date'] as String),
        DateTime.parse(j['end_date'] as String),
        _numOrNull(j['annual_value']),
      );
}

class LinkedWorkOrder {
  final String id, number, title, status;
  final double? estimatedCost;
  const LinkedWorkOrder(this.id, this.number, this.title, this.status, this.estimatedCost);

  factory LinkedWorkOrder.fromJson(Map<String, dynamic> j) => LinkedWorkOrder(
        j['id'] as String,
        j['wo_number'] as String? ?? '',
        j['title'] as String? ?? '',
        j['status'] as String? ?? '',
        _numOrNull(j['estimated_cost']),
      );
}

class AssetLogEntry {
  final String action;
  final String? notes;
  final double? cost;
  final DateTime when;
  const AssetLogEntry(this.action, this.notes, this.cost, this.when);

  factory AssetLogEntry.fromJson(Map<String, dynamic> j) => AssetLogEntry(
        j['action'] as String? ?? '',
        j['notes'] as String?,
        _numOrNull(j['cost']),
        DateTime.tryParse(j['created_at'] as String? ?? '') ?? DateTime.now(),
      );
}

class AssetHistory {
  final Asset asset;
  final List<AssetService> services;
  final List<AssetAmc> amc;
  final List<LinkedContract> contracts;
  final List<LinkedWorkOrder> workOrders;
  final List<AssetLogEntry> log;
  final double totalServiceCost;

  const AssetHistory({
    required this.asset,
    required this.services,
    required this.amc,
    required this.contracts,
    required this.workOrders,
    required this.log,
    required this.totalServiceCost,
  });

  factory AssetHistory.fromJson(Map<String, dynamic> j) {
    List<T> list<T>(String key, T Function(Map<String, dynamic>) f) =>
        ((j[key] as List?) ?? const []).map((e) => f(e as Map<String, dynamic>)).toList();
    return AssetHistory(
      asset: Asset.fromJson(j['asset'] as Map<String, dynamic>),
      services: list('maintenance', AssetService.fromJson),
      amc: list('amc', AssetAmc.fromJson),
      contracts: list('contracts', LinkedContract.fromJson),
      workOrders: list('work_orders', LinkedWorkOrder.fromJson),
      log: list('log', AssetLogEntry.fromJson),
      totalServiceCost: _numOrNull(j['total_service_cost']) ?? 0,
    );
  }

  /// The AMC in force today, if any.
  AssetAmc? get currentAmc => amc.where((a) => !a.ended && !a.startDate.isAfter(DateTime.now())).firstOrNull;
}

// ── API ──────────────────────────────────────────────────────────────────────

class AssetsApi {
  final Dio _dio;
  AssetsApi({Dio? dio}) : _dio = dio ?? ApiClient.instance;

  Future<AssetSummary> summary(String societyId) async =>
      AssetSummary.fromJson((await _dio.get('/inventory/assets/summary/$societyId')).data as Map<String, dynamic>);

  Future<List<Asset>> list(String societyId, {String? q, String? category, String? status, bool due = false}) async {
    final res = await _dio.get('/inventory/assets/society/$societyId', queryParameters: {
      'limit': 500,
      if (q != null && q.trim().isNotEmpty) 'q': q.trim(),
      if (category != null) 'category': category,
      if (status != null) 'status': status,
      if (due) 'due': true,
    });
    return (res.data as List).map((e) => Asset.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<AssetHistory> history(String assetId) async =>
      AssetHistory.fromJson((await _dio.get('/inventory/assets/$assetId/history')).data as Map<String, dynamic>);

  Future<Asset> create(Map<String, dynamic> body) async =>
      Asset.fromJson((await _dio.post('/inventory/assets', data: body)).data as Map<String, dynamic>);

  /// Only the keys present are changed; a null value clears the field.
  Future<Asset> update(String assetId, Map<String, dynamic> body) async =>
      Asset.fromJson((await _dio.patch('/inventory/assets/$assetId', data: body)).data as Map<String, dynamic>);

  Future<AssetService> scheduleService(
    String assetId, {
    required String type,
    required DateTime date,
    String? vendorName,
    String? description,
    double? cost,
  }) async =>
      AssetService.fromJson((await _dio.post('/inventory/maintenance', data: {
        'asset_id': assetId,
        'maintenance_type': type,
        'scheduled_date': _apiDate(date),
        if (vendorName != null && vendorName.isNotEmpty) 'vendor_name': vendorName,
        if (description != null && description.isNotEmpty) 'description': description,
        if (cost != null) 'cost': cost,
      }))
          .data as Map<String, dynamic>);

  Future<AssetService> completeService(
    String serviceId, {
    required DateTime doneOn,
    double? cost,
    String? findings,
    String? vendorName,
    DateTime? nextDue,
  }) async =>
      AssetService.fromJson((await _dio.post('/inventory/maintenance/$serviceId/complete', data: {
        'completed_date': _apiDate(doneOn),
        if (cost != null) 'cost': cost,
        if (findings != null && findings.isNotEmpty) 'findings': findings,
        if (vendorName != null && vendorName.isNotEmpty) 'vendor_name': vendorName,
        if (nextDue != null) 'next_due_date': _apiDate(nextDue),
      }))
          .data as Map<String, dynamic>);

  Future<void> cancelService(String serviceId) => _dio.post('/inventory/maintenance/$serviceId/cancel');

  Future<AssetAmc> addAmc(
    String assetId, {
    required String vendorName,
    required DateTime start,
    required DateTime end,
    String? contractNumber,
    double? annualCost,
    String? coverage,
    bool comprehensive = false,
  }) async =>
      AssetAmc.fromJson((await _dio.post('/inventory/amc', data: {
        'asset_id': assetId,
        'vendor_name': vendorName,
        'start_date': _apiDate(start),
        'end_date': _apiDate(end),
        if (contractNumber != null && contractNumber.isNotEmpty) 'contract_number': contractNumber,
        if (annualCost != null) 'annual_cost': annualCost,
        if (coverage != null && coverage.isNotEmpty) 'coverage': coverage,
        'is_comprehensive': comprehensive,
      }))
          .data as Map<String, dynamic>);
}
