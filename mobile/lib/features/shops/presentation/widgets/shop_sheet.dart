import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/widgets/billing_sheet_frame.dart';
import 'package:ar_society_app/features/shops/data/shops_api.dart';
import 'package:ar_society_app/features/shops/presentation/providers/shops_providers.dart';
import 'package:ar_society_app/features/vendor/presentation/widgets/procurement_widgets.dart' show DateField;
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// Add a shop, or change one: its number and place, who owns it, who runs it, when the owner took possession, and
/// its electricity meter. Closes with `true` when something was saved or deleted.
class ShopSheet extends ConsumerStatefulWidget {
  final Shop? existing;
  const ShopSheet({super.key, this.existing});

  @override
  ConsumerState<ShopSheet> createState() => _ShopSheetState();
}

class _ShopSheetState extends ConsumerState<ShopSheet> {
  final _form = GlobalKey<FormState>();
  late final Shop? e = widget.existing;
  late final _number = TextEditingController(text: e?.shopNumber);
  late final _floor = TextEditingController(text: e?.floor?.toString());
  late final _location = TextEditingController(text: e?.location);
  late final _area = TextEditingController(
      text: e?.areaSqft == null ? '' : e!.areaSqft!.toStringAsFixed(e!.areaSqft! % 1 == 0 ? 0 : 2));
  late final _business = TextEditingController(text: e?.businessName);
  late final _owner = TextEditingController(text: e?.ownerName);
  late final _phone = TextEditingController(text: e?.ownerPhone);
  late final _email = TextEditingController(text: e?.ownerEmail);
  late final _tenant = TextEditingController(text: e?.tenantName);
  late final _tenantPhone = TextEditingController(text: e?.tenantPhone);
  late final _meter = TextEditingController(text: e?.electricMeterNo);
  late final _consumer = TextEditingController(text: e?.electricConsumerNo);
  late final _remarks = TextEditingController(text: e?.remarks);
  late String _occupancy = e?.occupancy ?? 'vacant';
  late DateTime? _possession = e?.possessionDate;
  bool _saving = false;

  List<TextEditingController> get _all =>
      [_number, _floor, _location, _area, _business, _owner, _phone, _email, _tenant, _tenantPhone, _meter, _consumer, _remarks];

  @override
  void dispose() {
    for (final c in _all) {
      c.dispose();
    }
    super.dispose();
  }

  String? _t(TextEditingController c) => c.text.trim().isEmpty ? null : c.text.trim();

  String? _phoneCheck(String? v) {
    final d = (v ?? '').trim().replaceAll(RegExp(r'[\s\-()]'), '');
    if (d.isEmpty) return null;
    return RegExp(r'^\+?\d{7,15}$').hasMatch(d) ? null : 'Enter a valid phone number';
  }

  Future<void> _save() async {
    if (!_form.currentState!.validate()) return;
    setState(() => _saving = true);
    final body = <String, dynamic>{
      'shop_number': _number.text.trim(),
      'owner_name': _owner.text.trim(),
      'floor': _t(_floor) == null ? null : int.parse(_floor.text.trim()),
      'location': _t(_location),
      'area_sqft': _t(_area) == null ? null : double.parse(_area.text.trim()),
      'business_name': _t(_business),
      'owner_phone': _t(_phone),
      'owner_email': _t(_email),
      'occupancy': _occupancy,
      // Tenant details only matter when the shop is rented out
      'tenant_name': _occupancy == 'rented' ? _t(_tenant) : null,
      'tenant_phone': _occupancy == 'rented' ? _t(_tenantPhone) : null,
      'possession_date': _possession == null ? null : apiDate(_possession!),
      'electric_meter_no': _t(_meter),
      'electric_consumer_no': _t(_consumer),
      'remarks': _t(_remarks),
    };
    try {
      final api = ref.read(shopsApiProvider);
      if (e == null) {
        body.removeWhere((_, v) => v == null);
        final societyId = ref.read(currentUserProvider)?.societyId;
        await api.create({...body, if (societyId != null) 'society_id': societyId});
      } else {
        await api.update(e!.id, body);
      }
      ref.invalidate(shopsProvider);
      if (mounted) {
        AppToast.success(context, e == null ? 'Shop added' : 'Saved');
        Navigator.pop(context, true);
      }
    } catch (err) {
      if (mounted) {
        setState(() => _saving = false);
        showErrorToast(context, err);
      }
    }
  }

  Future<void> _delete() async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text('Remove shop ${e!.shopNumber}?'),
        content: const Text('It is taken off the list. Its number can be used again.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Keep it')),
          FilledButton(
              style: FilledButton.styleFrom(backgroundColor: AppTheme.error),
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text('Remove')),
        ],
      ),
    );
    if (ok != true) return;
    setState(() => _saving = true);
    try {
      await ref.read(shopsApiProvider).delete(e!.id);
      ref.invalidate(shopsProvider);
      if (mounted) {
        AppToast.success(context, 'Shop removed');
        Navigator.pop(context, true);
      }
    } catch (err) {
      if (mounted) {
        setState(() => _saving = false);
        showErrorToast(context, err);
      }
    }
  }

  Widget _section(String title, {bool first = false}) => Padding(
        padding: EdgeInsets.only(top: first ? 0 : 6, bottom: 10),
        child: Text(title, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: AppTheme.primary)),
      );

  Widget _field(TextEditingController c, String label,
          {int max = 100, String? Function(String?)? validator, TextInputType? keyboard,
          List<TextInputFormatter>? formatters, String? helper, TextCapitalization caps = TextCapitalization.none}) =>
      Padding(
        padding: const EdgeInsets.only(bottom: 12),
        child: TextFormField(
          controller: c,
          keyboardType: keyboard,
          textCapitalization: caps,
          inputFormatters: [LengthLimitingTextInputFormatter(max), ...?formatters],
          decoration: InputDecoration(labelText: label, helperText: helper, counterText: ''),
          validator: validator,
        ),
      );

  @override
  Widget build(BuildContext context) {
    Widget pair(Widget a, Widget b) => Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Expanded(child: a),
          const SizedBox(width: 12),
          Expanded(child: b),
        ]);
    return BillingSheetFrame(
      title: e == null ? 'Add a shop' : 'Shop ${e!.shopNumber}',
      child: Form(
        key: _form,
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          _section('Shop', first: true),
          pair(
            _field(_number, 'Shop number *', max: 30,
                validator: (v) => (v ?? '').trim().isEmpty ? 'Enter the shop number' : null),
            _field(_floor, 'Floor', max: 3, keyboard: const TextInputType.numberWithOptions(signed: true),
                formatters: [FilteringTextInputFormatter.allow(RegExp(r'^-?\d{0,3}'))], helper: '0 = ground'),
          ),
          _field(_location, 'Location', max: 120, helper: 'e.g. Ground floor, Block C'),
          pair(
            _field(_area, 'Area (sq ft)', max: 9, keyboard: const TextInputType.numberWithOptions(decimal: true),
                formatters: [FilteringTextInputFormatter.allow(RegExp(r'[0-9.]'))],
                validator: (v) {
                  final t = (v ?? '').trim();
                  if (t.isEmpty) return null;
                  final n = double.tryParse(t);
                  return n == null || n <= 0 ? 'Enter the area' : null;
                }),
            _field(_business, 'Business name', max: 150),
          ),
          _section('Owner'),
          _field(_owner, 'Owner name *', max: 255,
              validator: (v) => (v ?? '').trim().isEmpty ? 'Enter the owner\'s name' : null),
          pair(
            _field(_phone, 'Phone', max: 20, keyboard: TextInputType.phone, validator: _phoneCheck),
            _field(_email, 'Email', max: 255, keyboard: TextInputType.emailAddress),
          ),
          _section('Who runs it'),
          Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: DropdownButtonFormField<String>(
              initialValue: _occupancy,
              isExpanded: true,
              decoration: const InputDecoration(labelText: 'Occupancy'),
              items: [for (final o in kShopOccupancy) DropdownMenuItem(value: o.$1, child: Text(o.$2))],
              onChanged: (v) => setState(() => _occupancy = v ?? 'vacant'),
            ),
          ),
          if (_occupancy == 'rented')
            pair(
              _field(_tenant, 'Tenant / occupant', max: 255),
              _field(_tenantPhone, 'Tenant phone', max: 20, keyboard: TextInputType.phone, validator: _phoneCheck),
            ),
          _section('Possession and electricity'),
          Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: DateField(
              label: 'Possession date',
              value: _possession,
              lastDate: DateTime.now().add(const Duration(days: 366)),
              onChanged: (d) => setState(() => _possession = d),
            ),
          ),
          pair(
            _field(_meter, 'Electric meter no.', max: 40),
            _field(_consumer, 'Consumer no.', max: 40, helper: 'Electricity account'),
          ),
          _field(_remarks, 'Remarks', max: 1000),
          const SizedBox(height: 4),
          AppPrimaryButton(
            label: e == null ? 'Add shop' : 'Save',
            isLoading: _saving,
            onPressed: _saving ? null : _save,
          ),
          if (e != null) ...[
            const SizedBox(height: 8),
            TextButton.icon(
              onPressed: _saving ? null : _delete,
              icon: const Icon(Icons.delete_outline_rounded, size: 18, color: AppTheme.error),
              label: const Text('Remove this shop', style: TextStyle(color: AppTheme.error)),
            ),
          ],
        ]),
      ),
    );
  }
}
