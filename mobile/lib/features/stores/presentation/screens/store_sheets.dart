import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/widgets/billing_sheet_frame.dart';
import 'package:ar_society_app/features/stores/data/stores_api.dart';
import 'package:ar_society_app/features/stores/presentation/providers/stores_providers.dart';
import 'package:ar_society_app/features/vendor/presentation/widgets/procurement_widgets.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

String? _t(TextEditingController c) => c.text.trim().isEmpty ? null : c.text.trim();
final _qtyInput = [FilteringTextInputFormatter.allow(RegExp(r'^\d{0,7}(\.\d{0,3})?'))];
String? _qtyValidator(String? v) => (double.tryParse((v ?? '').trim()) ?? 0) <= 0 ? 'Enter a quantity above zero' : null;

/// Runs [action], closes the sheet with [result] and toasts [done]; shows the error and stays open on failure.
Future<void> _submit(BuildContext context, WidgetRef ref, void Function(bool) busy, Future<void> Function() action,
    {required String done, Object? result}) async {
  busy(true);
  try {
    await action();
    invalidateStores(ref);
    if (!context.mounted) return;
    AppToast.success(context, done);
    Navigator.of(context).pop(result ?? true);
  } catch (e) {
    if (context.mounted) {
      busy(false);
      showErrorToast(context, e);
    }
  }
}

// ── Add or change an item ────────────────────────────────────────────────────

class ItemFormSheet extends ConsumerStatefulWidget {
  final StoreItem? item;
  const ItemFormSheet({super.key, this.item});

  @override
  ConsumerState<ItemFormSheet> createState() => _ItemFormSheetState();
}

class _ItemFormSheetState extends ConsumerState<ItemFormSheet> {
  final _form = GlobalKey<FormState>();
  late final _name = TextEditingController(text: i?.name);
  late final _location = TextEditingController(text: i?.location);
  late final _minimum = TextEditingController(text: i == null ? '' : qty(i!.minimum));
  late final _cost = TextEditingController(text: i?.unitCost == null ? '' : qty(i!.unitCost!));
  late final _vendor = TextEditingController(text: i?.vendor);
  late String _category = i?.category ?? 'cleaning';
  late String _unit = i?.unit ?? 'piece';
  bool _saving = false;

  StoreItem? get i => widget.item;

  @override
  void dispose() {
    for (final c in [_name, _location, _minimum, _cost, _vendor]) {
      c.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => BillingSheetFrame(
        title: i == null ? 'Add an item' : 'Edit ${i!.name}',
        child: Form(
          key: _form,
          autovalidateMode: AutovalidateMode.onUserInteraction,
          child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            TextFormField(
              controller: _name,
              maxLength: 255,
              textCapitalization: TextCapitalization.words,
              decoration: const InputDecoration(labelText: 'Name *', hintText: 'e.g. Floor cleaner', counterText: ''),
              validator: (v) => (v ?? '').trim().isEmpty ? 'Give the item a name' : null,
            ),
            const SizedBox(height: 12),
            DropdownButtonFormField<String>(
              initialValue: _category,
              isExpanded: true,
              decoration: const InputDecoration(labelText: 'Kind'),
              items: [
                for (final c in kItemCategories)
                  DropdownMenuItem(value: c.$1, child: Row(children: [Icon(c.$3, size: 18, color: AppTheme.textSecondary), const SizedBox(width: 10), Text(c.$2)])),
              ],
              onChanged: (v) => setState(() => _category = v ?? _category),
            ),
            const SizedBox(height: 12),
            DropdownButtonFormField<String>(
              initialValue: _unit,
              isExpanded: true,
              decoration: InputDecoration(labelText: 'Counted in', helperText: i == null ? null : 'The unit can\'t be changed once the item exists'),
              items: [for (final u in kUnits) DropdownMenuItem(value: u.$1, child: Text(u.$2))],
              onChanged: i == null ? (v) => setState(() => _unit = v ?? _unit) : null,
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _minimum,
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
              inputFormatters: _qtyInput,
              decoration: const InputDecoration(labelText: 'Tell me when it falls to', helperText: 'The level at or below which it shows as low'),
            ),
            const SizedBox(height: 12),
            TextFormField(controller: _location, maxLength: 200, decoration: const InputDecoration(labelText: 'Kept at', hintText: 'e.g. Store room, basement', counterText: '')),
            const SizedBox(height: 12),
            TextFormField(
              controller: _cost,
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
              inputFormatters: moneyInput,
              decoration: const InputDecoration(labelText: 'Cost of one (₹, optional)'),
            ),
            const SizedBox(height: 12),
            TextFormField(controller: _vendor, maxLength: 200, decoration: const InputDecoration(labelText: 'Bought from (optional)', counterText: '')),
            const SizedBox(height: 14),
            AppPrimaryButton(
              label: 'Save',
              isLoading: _saving,
              onPressed: _saving
                  ? null
                  : () {
                      if (!_form.currentState!.validate()) return;
                      final api = ref.read(storesApiProvider);
                      final body = <String, dynamic>{
                        'name': _name.text.trim(),
                        'category': _category,
                        'storage_location': _t(_location),
                        'minimum_stock': double.tryParse(_minimum.text.trim()) ?? 0,
                        'unit_cost': parseMoney(_cost.text),
                        'vendor_name': _t(_vendor),
                      };
                      _submit(context, ref, (b) => setState(() => _saving = b),
                          () async => i == null ? await api.createItem({...body, 'unit_type': _unit}) : await api.updateItem(i!.id, body),
                          done: i == null ? 'Item added' : 'Saved');
                    },
            ),
          ]),
        ),
      );
}

// ── Stock in ─────────────────────────────────────────────────────────────────

class StockInSheet extends ConsumerStatefulWidget {
  final StoreItem item;
  const StockInSheet({super.key, required this.item});

  @override
  ConsumerState<StockInSheet> createState() => _StockInSheetState();
}

class _StockInSheetState extends ConsumerState<StockInSheet> {
  final _form = GlobalKey<FormState>();
  final _qty = TextEditingController();
  final _cost = TextEditingController();
  final _ref = TextEditingController();
  final _notes = TextEditingController();
  bool _saving = false;

  @override
  void dispose() {
    for (final c in [_qty, _cost, _ref, _notes]) {
      c.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final item = widget.item;
    return BillingSheetFrame(
      title: 'Stock in: ${item.name}',
      child: Form(
        key: _form,
        autovalidateMode: AutovalidateMode.onUserInteraction,
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Text('In stock now: ${item.stockText}', style: const TextStyle(color: AppTheme.textSecondary)),
          const SizedBox(height: 12),
          TextFormField(
            controller: _qty,
            autofocus: true,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            inputFormatters: _qtyInput,
            decoration: InputDecoration(labelText: 'How many ${unitLabel(item.unit)} came in *'),
            validator: _qtyValidator,
          ),
          const SizedBox(height: 12),
          TextFormField(
            controller: _cost,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            inputFormatters: moneyInput,
            decoration: InputDecoration(labelText: 'Cost of one (₹, optional)', helperText: item.unitCost == null ? null : 'Usual: ₹${qty(item.unitCost!)}'),
          ),
          const SizedBox(height: 12),
          TextFormField(controller: _ref, decoration: const InputDecoration(labelText: "Supplier's bill / challan no. (optional)")),
          const SizedBox(height: 12),
          TextFormField(controller: _notes, decoration: const InputDecoration(labelText: 'Note (optional)')),
          const SizedBox(height: 14),
          AppPrimaryButton(
            label: 'Add to stock',
            isLoading: _saving,
            onPressed: _saving
                ? null
                : () {
                    if (!_form.currentState!.validate()) return;
                    _submit(context, ref, (b) => setState(() => _saving = b),
                        () => ref.read(storesApiProvider).stockIn(item.id, double.parse(_qty.text.trim()),
                            unitCost: parseMoney(_cost.text), notes: _t(_notes), reference: _t(_ref)),
                        done: 'Stock added');
                  },
          ),
        ]),
      ),
    );
  }
}

// ── Correct the count ────────────────────────────────────────────────────────

class CountSheet extends ConsumerStatefulWidget {
  final StoreItem item;
  const CountSheet({super.key, required this.item});

  @override
  ConsumerState<CountSheet> createState() => _CountSheetState();
}

class _CountSheetState extends ConsumerState<CountSheet> {
  final _form = GlobalKey<FormState>();
  late final _qty = TextEditingController(text: qty(widget.item.stock));
  final _why = TextEditingController();
  bool _saving = false;

  @override
  void dispose() {
    _qty.dispose();
    _why.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final item = widget.item;
    return BillingSheetFrame(
      title: 'Correct the count: ${item.name}',
      child: Form(
        key: _form,
        autovalidateMode: AutovalidateMode.onUserInteraction,
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Text('The app thinks there are ${item.stockText}. Enter what you actually counted.', style: const TextStyle(color: AppTheme.textSecondary, height: 1.35)),
          const SizedBox(height: 12),
          TextFormField(
            controller: _qty,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            inputFormatters: _qtyInput,
            decoration: InputDecoration(labelText: 'Counted (${unitLabel(item.unit)}) *'),
            validator: (v) => double.tryParse((v ?? '').trim()) == null ? 'Enter the number counted' : null,
          ),
          const SizedBox(height: 12),
          TextFormField(
            controller: _why,
            decoration: const InputDecoration(labelText: 'Why it changed *', hintText: 'e.g. Monthly stock count, spilled, miscounted'),
            validator: (v) => (v ?? '').trim().isEmpty ? 'Say why' : null,
          ),
          const SizedBox(height: 14),
          AppPrimaryButton(
            label: 'Save the count',
            isLoading: _saving,
            onPressed: _saving
                ? null
                : () {
                    if (!_form.currentState!.validate()) return;
                    _submit(context, ref, (b) => setState(() => _saving = b),
                        () => ref.read(storesApiProvider).adjust(item.id, double.parse(_qty.text.trim()), _why.text.trim()),
                        done: 'Count saved');
                  },
          ),
        ]),
      ),
    );
  }
}

// ── Issue to staff ───────────────────────────────────────────────────────────

class IssueSheet extends ConsumerStatefulWidget {
  final StoreItem item;
  const IssueSheet({super.key, required this.item});

  @override
  ConsumerState<IssueSheet> createState() => _IssueSheetState();
}

class _IssueSheetState extends ConsumerState<IssueSheet> {
  final _form = GlobalKey<FormState>();
  final _qty = TextEditingController();
  final _purpose = TextEditingController();
  String? _staff;
  bool _consumed = false;
  DateTime? _returnBy;
  bool _saving = false;

  @override
  void dispose() {
    _qty.dispose();
    _purpose.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final item = widget.item;
    final societyId = ref.watch(currentUserProvider)?.societyId ?? '';
    final people = ref.watch(recipientsProvider(societyId));
    return BillingSheetFrame(
      title: 'Issue: ${item.name}',
      child: Form(
        key: _form,
        autovalidateMode: AutovalidateMode.onUserInteraction,
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Text('In stock: ${item.stockText}', style: const TextStyle(color: AppTheme.textSecondary)),
          const SizedBox(height: 12),
          people.when(
            loading: () => const LinearProgressIndicator(),
            error: (e, _) => Text(friendlyErrorMessage(e), style: const TextStyle(color: AppTheme.error)),
            data: (list) => DropdownButtonFormField<String>(
              initialValue: _staff,
              isExpanded: true,
              decoration: const InputDecoration(labelText: 'Give it to *'),
              items: [
                for (final p in list)
                  DropdownMenuItem(value: p.id, child: Text(p.department == null ? p.name : '${p.name} · ${p.department}', overflow: TextOverflow.ellipsis)),
              ],
              onChanged: (v) => setState(() => _staff = v),
              validator: (v) => v == null ? 'Choose who gets it' : null,
            ),
          ),
          const SizedBox(height: 12),
          TextFormField(
            controller: _qty,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            inputFormatters: _qtyInput,
            decoration: InputDecoration(labelText: 'How many ${unitLabel(item.unit)} *'),
            validator: (v) {
              final bad = _qtyValidator(v);
              if (bad != null) return bad;
              return double.parse(v!.trim()) > item.stock ? 'Only ${item.stockText} in stock' : null;
            },
          ),
          const SizedBox(height: 12),
          TextFormField(controller: _purpose, decoration: const InputDecoration(labelText: 'What for (optional)', hintText: 'e.g. Wing B deep clean')),
          SwitchListTile(
            contentPadding: EdgeInsets.zero,
            value: _consumed,
            onChanged: (v) => setState(() => _consumed = v),
            title: const Text('It will be used up'),
            subtitle: const Text('Cleaning supplies and the like. Nothing comes back.'),
          ),
          if (!_consumed) DateField(label: 'Bring it back by (optional)', value: _returnBy, onChanged: (v) => setState(() => _returnBy = v)),
          const SizedBox(height: 14),
          AppPrimaryButton(
            label: 'Issue',
            isLoading: _saving,
            onPressed: _saving
                ? null
                : () {
                    if (!_form.currentState!.validate()) return;
                    _submit(context, ref, (b) => setState(() => _saving = b),
                        () => ref.read(storesApiProvider).issue(
                            itemId: item.id, quantity: double.parse(_qty.text.trim()), staffId: _staff!,
                            purpose: _t(_purpose), returnBy: _returnBy, consumed: _consumed),
                        done: 'Issued');
                  },
          ),
        ]),
      ),
    );
  }
}

// ── Take something back ──────────────────────────────────────────────────────

class ReturnSheet extends ConsumerStatefulWidget {
  final IssueItem issue;
  const ReturnSheet({super.key, required this.issue});

  @override
  ConsumerState<ReturnSheet> createState() => _ReturnSheetState();
}

class _ReturnSheetState extends ConsumerState<ReturnSheet> {
  final _form = GlobalKey<FormState>();
  late final _qty = TextEditingController(text: qty(widget.issue.outstanding));
  final _notes = TextEditingController();
  String _condition = 'good';
  bool _saving = false;

  @override
  void dispose() {
    _qty.dispose();
    _notes.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final i = widget.issue;
    return BillingSheetFrame(
      title: 'Take back: ${i.itemName}',
      child: Form(
        key: _form,
        autovalidateMode: AutovalidateMode.onUserInteraction,
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Text('${i.toName ?? 'Someone'} has ${qty(i.outstanding)} ${unitLabel(i.unit)}.', style: const TextStyle(color: AppTheme.textSecondary)),
          const SizedBox(height: 12),
          TextFormField(
            controller: _qty,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            inputFormatters: _qtyInput,
            decoration: const InputDecoration(labelText: 'How many came back *'),
            validator: (v) {
              final bad = _qtyValidator(v);
              if (bad != null) return bad;
              return double.parse(v!.trim()) > i.outstanding ? 'No more than ${qty(i.outstanding)}' : null;
            },
          ),
          const SizedBox(height: 12),
          const Text('Condition', style: TextStyle(fontSize: 12.5, color: AppTheme.textSecondary)),
          const SizedBox(height: 6),
          Wrap(spacing: 8, children: [
            for (final c in const [('good', 'Good'), ('damaged', 'Damaged'), ('lost', 'Lost')])
              ChoiceChip(label: Text(c.$2), selected: _condition == c.$1, onSelected: (_) => setState(() => _condition = c.$1)),
          ]),
          if (_condition != 'good')
            const Padding(
              padding: EdgeInsets.only(top: 6),
              child: Text('Damaged or lost items are closed off here but do not go back on the shelf.', style: TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
            ),
          const SizedBox(height: 12),
          TextFormField(controller: _notes, decoration: const InputDecoration(labelText: 'Note (optional)')),
          const SizedBox(height: 14),
          AppPrimaryButton(
            label: 'Take back',
            isLoading: _saving,
            onPressed: _saving
                ? null
                : () {
                    if (!_form.currentState!.validate()) return;
                    _submit(context, ref, (b) => setState(() => _saving = b),
                        () => ref.read(storesApiProvider).giveBack(i.id, double.parse(_qty.text.trim()), condition: _condition, notes: _t(_notes)),
                        done: _condition == 'good' ? 'Back on the shelf' : 'Recorded');
                  },
          ),
        ]),
      ),
    );
  }
}
