import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';

DateTime? _dt(Object? v) => v == null ? null : DateTime.tryParse(v.toString());
double _d(Object? v) => v == null ? 0 : double.tryParse(v.toString()) ?? 0;
double? _dn(Object? v) => v == null ? null : double.tryParse(v.toString());

String apiDay(DateTime d) => DateFormat('yyyy-MM-dd').format(d);
String dayText(DateTime? d) => d == null ? '' : DateFormat('d MMM yyyy').format(d.toLocal());

/// 5 -> "5", 2.5 -> "2.5"
String qty(double v) => v == v.roundToDouble() ? v.toStringAsFixed(0) : v.toStringAsFixed(2).replaceFirst(RegExp(r'0+$'), '');

/// (api value, label, icon)
const kItemCategories = <(String, String, IconData)>[
  ('cleaning', 'Cleaning', Icons.cleaning_services_rounded),
  ('housekeeping', 'Housekeeping', Icons.sanitizer_rounded),
  ('electrical', 'Electrical', Icons.bolt_rounded),
  ('plumbing', 'Plumbing', Icons.plumbing_rounded),
  ('safety', 'Safety', Icons.health_and_safety_rounded),
  ('tools', 'Tools', Icons.hardware_rounded),
  ('uniforms', 'Uniforms', Icons.checkroom_rounded),
  ('stationery', 'Stationery', Icons.edit_note_rounded),
  ('gardening', 'Gardening', Icons.yard_rounded),
  ('other', 'Other', Icons.category_rounded),
];
String itemCategoryLabel(String c) => kItemCategories.where((e) => e.$1 == c).firstOrNull?.$2 ?? c;
IconData itemCategoryIcon(String c) => kItemCategories.where((e) => e.$1 == c).firstOrNull?.$3 ?? Icons.category_rounded;

const kUnits = <(String, String)>[
  ('piece', 'piece'), ('kg', 'kg'), ('litre', 'litre'), ('meter', 'metre'), ('box', 'box'),
  ('pack', 'pack'), ('roll', 'roll'), ('set', 'set'), ('pair', 'pair'),
];
String unitLabel(String u) => kUnits.where((e) => e.$1 == u).firstOrNull?.$2 ?? u;

String txnLabel(String t) => switch (t) {
      'stock_in' => 'Stock in',
      'stock_out' => 'Issued',
      'return' => 'Returned',
      'adjustment' => 'Count corrected',
      'consumption' => 'Used up',
      'transfer' => 'Transferred',
      _ => t,
    };
IconData txnIcon(String t) => switch (t) {
      'stock_in' => Icons.add_box_rounded,
      'return' => Icons.undo_rounded,
      'adjustment' => Icons.fact_check_outlined,
      _ => Icons.outbox_rounded,
    };
bool txnAdds(String t) => t == 'stock_in' || t == 'return';

class StoreItem {
  final String id;
  final String code;
  final String name;
  final String category;
  final String unit;
  final String? description;
  final String? location;
  final double minimum;
  final double? unitCost;
  final String? vendor;
  final String? vendorContact;
  final double stock;
  final bool low;

  const StoreItem({
    required this.id,
    required this.code,
    required this.name,
    required this.category,
    required this.unit,
    this.description,
    this.location,
    this.minimum = 0,
    this.unitCost,
    this.vendor,
    this.vendorContact,
    this.stock = 0,
    this.low = false,
  });

  factory StoreItem.fromJson(Map<String, dynamic> j) => StoreItem(
        id: j['id'] as String,
        code: j['item_code'] as String? ?? '',
        name: j['name'] as String? ?? '',
        category: j['category'] as String? ?? 'other',
        unit: j['unit_type'] as String? ?? 'piece',
        description: j['description'] as String?,
        location: j['storage_location'] as String?,
        minimum: _d(j['minimum_stock']),
        unitCost: _dn(j['unit_cost']),
        vendor: j['vendor_name'] as String?,
        vendorContact: j['vendor_contact'] as String?,
        stock: _d(j['current_stock']),
        low: j['is_low_stock'] as bool? ?? false,
      );

  bool get out => stock <= 0;
  String get stockText => '${qty(stock)} ${unitLabel(unit)}';
}

class StoresSummary {
  final int items;
  final int low;
  final int outOfStock;
  final double value;
  final int withPeople;
  final int overdue;
  const StoresSummary({this.items = 0, this.low = 0, this.outOfStock = 0, this.value = 0, this.withPeople = 0, this.overdue = 0});

  factory StoresSummary.fromJson(Map<String, dynamic> j) => StoresSummary(
        items: j['items'] as int? ?? 0,
        low: j['low_stock'] as int? ?? 0,
        outOfStock: j['out_of_stock'] as int? ?? 0,
        value: _d(j['stock_value']),
        withPeople: j['out_with_people'] as int? ?? 0,
        overdue: j['overdue_returns'] as int? ?? 0,
      );
}

class IssueItem {
  final String id;
  final String itemId;
  final String itemName;
  final String? itemCode;
  final String unit;
  final String status;
  final double issued;
  final double returned;
  final double outstanding;
  final String? toName;
  final String? byName;
  final String? purpose;
  final DateTime? expectedReturn;
  final DateTime? actualReturn;
  final DateTime? at;
  final bool overdue;

  const IssueItem({
    required this.id,
    required this.itemId,
    required this.itemName,
    this.itemCode,
    required this.unit,
    required this.status,
    required this.issued,
    required this.returned,
    required this.outstanding,
    this.toName,
    this.byName,
    this.purpose,
    this.expectedReturn,
    this.actualReturn,
    this.at,
    this.overdue = false,
  });

  factory IssueItem.fromJson(Map<String, dynamic> j) => IssueItem(
        id: j['id'] as String,
        itemId: j['item_id'] as String,
        itemName: j['item_name'] as String? ?? 'Item',
        itemCode: j['item_code'] as String?,
        unit: j['unit'] as String? ?? 'piece',
        status: j['status'] as String? ?? 'issued',
        issued: _d(j['quantity_issued']),
        returned: _d(j['quantity_returned']),
        outstanding: _d(j['outstanding']),
        toName: j['issued_to_name'] as String?,
        byName: j['issued_by_name'] as String?,
        purpose: j['purpose'] as String?,
        expectedReturn: _dt(j['expected_return_date']),
        actualReturn: _dt(j['actual_return_date']),
        at: _dt(j['created_at']),
        overdue: j['overdue'] as bool? ?? false,
      );

  bool get isOut => status == 'issued' || status == 'partially_returned';
  String get statusLabel => switch (status) {
        'issued' => overdue ? 'Overdue' : 'With them',
        'partially_returned' => overdue ? 'Overdue' : 'Part returned',
        'returned' => 'Returned',
        'consumed' => 'Used up',
        _ => status,
      };
  Color get statusColor => switch (status) {
        'issued' || 'partially_returned' => overdue ? AppTheme.error : AppTheme.warning,
        'returned' => AppTheme.success,
        _ => AppTheme.textSecondary,
      };
}

class StockMove {
  final String type;
  final double quantity;
  final double before;
  final double after;
  final double? totalCost;
  final String? notes;
  final String? ref;
  final String? by;
  final DateTime? at;

  const StockMove({required this.type, required this.quantity, required this.before, required this.after, this.totalCost, this.notes, this.ref, this.by, this.at});

  factory StockMove.fromJson(Map<String, dynamic> j) => StockMove(
        type: j['transaction_type'] as String? ?? '',
        quantity: _d(j['quantity']),
        before: _d(j['quantity_before']),
        after: _d(j['quantity_after']),
        totalCost: _dn(j['total_cost']),
        notes: j['notes'] as String?,
        ref: j['reference_id'] as String?,
        by: j['performed_by_name'] as String?,
        at: _dt(j['created_at']),
      );
}

class Recipient {
  final String id;
  final String name;
  final String? department;
  const Recipient(this.id, this.name, this.department);
}

class StoresApi {
  final Dio _dio;
  StoresApi({Dio? dio}) : _dio = dio ?? ApiClient.instance;

  Future<StoresSummary> summary(String societyId) async =>
      StoresSummary.fromJson((await _dio.get('/inventory/summary/$societyId')).data as Map<String, dynamic>);

  Future<List<StoreItem>> items(String societyId, {String? category}) async =>
      ((await _dio.get('/inventory/items/society/$societyId', queryParameters: {'limit': 200, if (category != null) 'category': category})).data as List)
          .map((e) => StoreItem.fromJson(e as Map<String, dynamic>))
          .toList();

  Future<StoreItem> item(String id) async => StoreItem.fromJson((await _dio.get('/inventory/items/$id')).data as Map<String, dynamic>);

  Future<StoreItem> createItem(Map<String, dynamic> body) async =>
      StoreItem.fromJson((await _dio.post('/inventory/items', data: body)).data as Map<String, dynamic>);

  Future<StoreItem> updateItem(String id, Map<String, dynamic> body) async =>
      StoreItem.fromJson((await _dio.patch('/inventory/items/$id', data: body)).data as Map<String, dynamic>);

  Future<void> stockIn(String itemId, double quantity, {double? unitCost, String? notes, String? reference}) => _dio.post('/inventory/stock/in', data: {
        'item_id': itemId,
        'quantity': quantity,
        if (unitCost != null) 'unit_cost': unitCost,
        if (notes != null && notes.isNotEmpty) 'notes': notes,
        if (reference != null && reference.isNotEmpty) 'reference_id': reference,
      });

  Future<void> adjust(String itemId, double newQuantity, String why) =>
      _dio.post('/inventory/stock/adjust', data: {'item_id': itemId, 'new_quantity': newQuantity, 'notes': why});

  Future<List<StockMove>> history(String itemId) async =>
      ((await _dio.get('/inventory/transactions/$itemId', queryParameters: {'limit': 100})).data as List)
          .map((e) => StockMove.fromJson(e as Map<String, dynamic>))
          .toList();

  Future<List<IssueItem>> issues(String societyId, {String? status, String? itemId}) async =>
      ((await _dio.get('/inventory/issues/society/$societyId', queryParameters: {'limit': 200, if (status != null) 'status': status, if (itemId != null) 'item_id': itemId})).data as List)
          .map((e) => IssueItem.fromJson(e as Map<String, dynamic>))
          .toList();

  Future<void> issue({required String itemId, required double quantity, required String staffId, String? purpose, DateTime? returnBy, bool consumed = false}) =>
      _dio.post('/inventory/issues', data: {
        'item_id': itemId,
        'quantity_issued': quantity,
        'issued_to_staff': staffId,
        if (purpose != null && purpose.isNotEmpty) 'purpose': purpose,
        if (returnBy != null && !consumed) 'expected_return_date': apiDay(returnBy),
        'consumed': consumed,
      });

  Future<void> giveBack(String issueId, double quantity, {String condition = 'good', String? notes}) =>
      _dio.post('/inventory/returns', data: {'issue_id': issueId, 'quantity': quantity, 'condition': condition, if (notes != null && notes.isNotEmpty) 'notes': notes});

  Future<List<Recipient>> recipients(String societyId) async =>
      ((await _dio.get('/staff/society/$societyId', queryParameters: {'limit': 500})).data as List)
          .map((e) => Recipient(e['id'] as String, e['full_name'] as String? ?? '', e['department'] as String?))
          .toList();
}
