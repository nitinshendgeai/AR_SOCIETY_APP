import 'package:flutter/material.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart' show formatInr, formatAccountsDate;
import 'package:ar_society_app/features/accounts/presentation/providers/accounts_providers.dart' show vendorPaymentsProvider;
import 'package:ar_society_app/features/vendor/presentation/providers/vendor_providers.dart' show vendorsProvider;
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/layout/app_shell.dart' show isDesktopLayout;
import 'package:ar_society_app/core/layout/app_sheet.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/accounts/presentation/providers/accounts_providers.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/maintenance_billing/data/maintenance_billing_api.dart' show formatBillDate, formatRupees;
import 'package:ar_society_app/features/maintenance_billing/presentation/widgets/billing_sheet_frame.dart';
import 'package:ar_society_app/features/vendor/data/vendors_work_api.dart';
import 'package:ar_society_app/features/vendor/presentation/providers/vendors_work_providers.dart';
import 'package:ar_society_app/features/vendor/presentation/widgets/procurement_widgets.dart';
import 'package:ar_society_app/shared/widgets/app_data_table.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

String workOrderRoute(String id) => AppRoutes.workOrderDetail.replaceFirst(':id', id);
String contractRoute(String id) => AppRoutes.contractDetail.replaceFirst(':id', id);

Color workOrderColor(String status) => switch (status) {
      'draft' => AppTheme.warning,
      'sanctioned' || 'issued' => AppTheme.primary,
      'completed' || 'closed' => AppTheme.success,
      _ => AppTheme.textSecondary,
    };

/// Vendors and the work given to them, the way the model bye-laws require:
/// quotations collected, the committee's (or general body's) sanction
/// recorded, a written work order issued, completion certified before the
/// final payment. Annual contracts take the same sanction.
class VendorsWorkScreen extends ConsumerStatefulWidget {
  const VendorsWorkScreen({super.key});

  @override
  ConsumerState<VendorsWorkScreen> createState() => _VendorsWorkScreenState();
}

class _VendorsWorkScreenState extends ConsumerState<VendorsWorkScreen> with SingleTickerProviderStateMixin {
  late final TabController _tabs = TabController(length: 4, vsync: this)..addListener(() => setState(() {}));

  @override
  void dispose() {
    _tabs.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final user = ref.watch(currentUserProvider);
    final societyId = user?.societyId;
    if (societyId == null) return const Scaffold(body: Center(child: Text('No society context')));
    final committee = user!.isAdminOrCommittee;
    final desktop = isDesktopLayout(context);
    final (String? label, VoidCallback? add) = switch (_tabs.index) {
      0 => ('New Work Order', () => showAppSheet(context: context, builder: (_) => WorkOrderSheet(societyId: societyId))),
      1 => ('New Contract', () => showAppSheet(context: context, builder: (_) => _ContractSheet(societyId: societyId))),
      2 when committee => ('Add Vendor', () => showAppSheet(context: context, builder: (_) => VendorSheet(societyId: societyId))),
      _ => (null, null),
    };
    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(
        title: const Text('Vendors & Work'),
        actions: [if (desktop && add != null) HeaderActionButton(icon: Icons.add_rounded, label: label!, onPressed: add)],
        bottom: TabBar(
          controller: _tabs,
          isScrollable: !desktop,
          tabAlignment: desktop ? null : TabAlignment.start,
          tabs: const [Tab(text: 'Work Orders'), Tab(text: 'Contracts'), Tab(text: 'Vendors'), Tab(text: 'Limits')],
        ),
      ),
      floatingActionButton: desktop || add == null
          ? null
          : FloatingActionButton.extended(onPressed: add, icon: const Icon(Icons.add_rounded), label: Text(label!)),
      body: TabBarView(controller: _tabs, children: [
        _WorkOrdersTab(societyId: societyId),
        _ContractsTab(societyId: societyId),
        _VendorsTab(societyId: societyId, committee: committee),
        _LimitsTab(societyId: societyId, committee: committee),
      ]),
    );
  }
}

Widget _asyncList<T>(
  WidgetRef ref,
  AsyncValue<List<T>> async,
  VoidCallback refresh, {
  required String intro,
  required String empty,
  required Widget Function(T) item,
}) =>
    RefreshIndicator(
      onRefresh: () async => refresh(),
      child: async.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => ListView(children: [
          Padding(
              padding: const EdgeInsets.all(24),
              child: Text(friendlyErrorMessage(e), style: const TextStyle(color: AppTheme.error))),
        ]),
        data: (rows) => ResponsiveBody(
          maxWidth: 860,
          child: ListView(padding: const EdgeInsets.fromLTRB(16, 16, 16, 96), children: [
            Text(intro, style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary, height: 1.35)),
            const SizedBox(height: 12),
            if (rows.isEmpty)
              Padding(padding: const EdgeInsets.symmetric(vertical: 40), child: Center(child: Text(empty))),
            for (final r in rows) item(r),
          ]),
        ),
      ),
    );

// ── Work orders ──────────────────────────────────────────────────────────────

class _WorkOrdersTab extends ConsumerWidget {
  final String societyId;
  const _WorkOrdersTab({required this.societyId});

  @override
  Widget build(BuildContext context, WidgetRef ref) => _asyncList<WorkOrder>(
        ref,
        ref.watch(workOrdersProvider(societyId)),
        () => ref.invalidate(workOrdersProvider(societyId)),
        intro: 'Any repair or job given to a vendor: collect quotations, get it sanctioned by the committee (the '
            'general body above the committee\'s limit, with tenders above the tender limit), issue the written '
            'work order, and pay bills only up to the sanctioned amount.',
        empty: 'No work orders yet',
        item: (w) => Card(
          margin: const EdgeInsets.only(bottom: 8),
          child: ListTile(
            onTap: () => context.push(workOrderRoute(w.id)),
            title: Text('${w.woNumber} · ${w.title}', style: const TextStyle(fontWeight: FontWeight.w600)),
            subtitle: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text([
                vendorCategoryLabel(w.category),
                if (w.vendorName != null) w.vendorName!,
                if (w.location != null) w.location!,
              ].join(' · ')),
              const SizedBox(height: 4),
              StatusPill(w.statusLabel, workOrderColor(w.status)),
            ]),
            isThreeLine: true,
            trailing: Text(
              w.sanction.amount != null
                  ? formatRupees(w.sanction.amount!)
                  : (w.estimatedCost != null ? 'est. ${formatRupees(w.estimatedCost!)}' : ''),
              style: const TextStyle(fontWeight: FontWeight.w600),
            ),
          ),
        ),
      );
}

/// New work order, or edits to a draft / sanctioned one.
class WorkOrderSheet extends ConsumerStatefulWidget {
  final String societyId;
  final WorkOrder? existing;
  const WorkOrderSheet({super.key, required this.societyId, this.existing});

  @override
  ConsumerState<WorkOrderSheet> createState() => _WorkOrderSheetState();
}

class _WorkOrderSheetState extends ConsumerState<WorkOrderSheet> {
  final _form = GlobalKey<FormState>();
  late final WorkOrder? e = widget.existing;
  late final _title = TextEditingController(text: e?.title);
  late final _location = TextEditingController(text: e?.location);
  late final _scope = TextEditingController(text: e?.scopeOfWork);
  late final _estimate = TextEditingController(text: e?.estimatedCost);
  late final _advance = TextEditingController(text: e == null ? '0' : e!.advanceAmount);
  late final _retention = TextEditingController(text: e == null ? '0' : e!.retentionPct);
  late final _dlp = TextEditingController(text: e == null ? '0' : '${e!.defectLiabilityMonths}');
  late final _terms = TextEditingController(text: e?.paymentTerms);
  late String _category = e?.category ?? 'civil';
  late String? _expense = e?.expenseAccountId;
  late DateTime? _start = e?.startDate;
  late DateTime? _due = e?.dueDate;
  bool _saving = false;

  bool get _termsLocked => e != null && !e!.isDraft;

  @override
  void dispose() {
    for (final c in [_title, _location, _scope, _estimate, _advance, _retention, _dlp, _terms]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _save() async {
    if (!_form.currentState!.validate()) return;
    setState(() => _saving = true);
    final body = <String, dynamic>{
      'title': _title.text.trim(),
      'category': _category,
      'location': _location.text.trim(),
      'estimated_cost': _estimate.text.trim().isEmpty ? null : parseMoney(_estimate.text)!.toStringAsFixed(2),
      'expense_account_id': _expense,
      'start_date': _start?.toIso8601String().split('T').first,
      'due_date': _due?.toIso8601String().split('T').first,
      if (!_termsLocked) ...{
        'scope_of_work': _scope.text.trim(),
        'advance_amount': (parseMoney(_advance.text) ?? 0).toStringAsFixed(2),
        'retention_pct': (parseMoney(_retention.text) ?? 0).toStringAsFixed(2),
        'defect_liability_months': int.tryParse(_dlp.text.trim()) ?? 0,
        'payment_terms': _terms.text.trim(),
      },
    };
    final api = ref.read(vendorsWorkApiProvider);
    try {
      final wo = e == null
          ? await api.createWorkOrder({...body, 'society_id': widget.societyId})
          : await api.updateWorkOrder(e!.id, body);
      ref.invalidate(workOrdersProvider(widget.societyId));
      ref.invalidate(workOrderProvider(wo.id));
      if (!mounted) return;
      Navigator.pop(context);
      if (e == null) context.push(workOrderRoute(wo.id));
    } catch (err) {
      if (mounted) showErrorToast(context, err);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final ledgers = ref.watch(ledgersProvider(widget.societyId));
    return BillingSheetFrame(
      title: e == null ? 'New Work Order' : 'Edit ${e!.woNumber}',
      child: Form(
        key: _form,
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          TextFormField(
            controller: _title,
            maxLength: 255,
            decoration: const InputDecoration(labelText: 'Work *', hintText: 'e.g. Waterproofing of terrace', counterText: ''),
            validator: (v) => (v ?? '').trim().isEmpty ? 'Describe the work' : null,
          ),
          const SizedBox(height: 12),
          DropdownButtonFormField<String>(
            initialValue: _category,
            decoration: const InputDecoration(labelText: 'Category *'),
            items: [for (final c in kVendorCategories) DropdownMenuItem(value: c.$1, child: Text(c.$2))],
            onChanged: (v) => setState(() => _category = v!),
          ),
          const SizedBox(height: 12),
          TextFormField(
            controller: _location,
            maxLength: 255,
            decoration: const InputDecoration(labelText: 'Location', hintText: 'e.g. B wing terrace', counterText: ''),
          ),
          const SizedBox(height: 12),
          TextFormField(
            controller: _scope,
            enabled: !_termsLocked,
            maxLength: 5000,
            minLines: 3,
            maxLines: 8,
            decoration: const InputDecoration(
                labelText: 'Scope of work',
                helperText: 'One item per line; printed on the work order',
                helperMaxLines: 2),
          ),
          const SizedBox(height: 12),
          TextFormField(
            controller: _estimate,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            inputFormatters: moneyInput,
            decoration: const InputDecoration(
                labelText: 'Estimated cost (₹)',
                helperText: 'Shows early whether tenders and the general body are needed',
                helperMaxLines: 2),
          ),
          const SizedBox(height: 12),
          ledgers.when(
            loading: () => const LinearProgressIndicator(),
            error: (err, _) => const SizedBox.shrink(),
            data: (list) {
              final heads = list.where((a) => a.nature == 'expense' && a.isActive).toList();
              return DropdownButtonFormField<String?>(
                initialValue: heads.any((a) => a.id == _expense) ? _expense : null,
                isExpanded: true,
                decoration: const InputDecoration(
                    labelText: 'Expense head', helperText: 'Bills on this work order are booked here'),
                items: [
                  const DropdownMenuItem<String?>(value: null, child: Text('By the vendor\'s category')),
                  for (final a in heads) DropdownMenuItem<String?>(value: a.id, child: Text(a.name)),
                ],
                onChanged: (v) => setState(() => _expense = v),
              );
            },
          ),
          const SizedBox(height: 12),
          Row(children: [
            Expanded(child: DateField(label: 'Start', value: _start, onChanged: (d) => setState(() => _start = d))),
            const SizedBox(width: 12),
            Expanded(
                child: DateField(
                    label: 'Complete by',
                    value: _due,
                    onChanged: (d) => setState(() => _due = d))),
          ]),
          const SizedBox(height: 16),
          Text(_termsLocked ? 'Terms (fixed by the sanction)' : 'Terms',
              style: const TextStyle(fontWeight: FontWeight.w600)),
          const SizedBox(height: 8),
          Row(children: [
            Expanded(
              child: TextFormField(
                controller: _advance,
                enabled: !_termsLocked,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                inputFormatters: moneyInput,
                decoration: const InputDecoration(labelText: 'Advance (₹)'),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: TextFormField(
                controller: _retention,
                enabled: !_termsLocked,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                inputFormatters: [FilteringTextInputFormatter.allow(RegExp(r'^\d{0,2}(\.\d{0,2})?'))],
                decoration: const InputDecoration(labelText: 'Retention %'),
                validator: (v) => (parseMoney(v ?? '') ?? 0) > 50 ? 'At most 50%' : null,
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: TextFormField(
                controller: _dlp,
                enabled: !_termsLocked,
                keyboardType: TextInputType.number,
                inputFormatters: [FilteringTextInputFormatter.digitsOnly, LengthLimitingTextInputFormatter(3)],
                decoration: const InputDecoration(labelText: 'Defect (mo)'),
                validator: (v) => (int.tryParse(v ?? '') ?? 0) > 120 ? 'At most 120' : null,
              ),
            ),
          ]),
          const SizedBox(height: 12),
          TextFormField(
            controller: _terms,
            enabled: !_termsLocked,
            maxLength: 2000,
            maxLines: 2,
            decoration: const InputDecoration(
                labelText: 'Payment terms', hintText: 'e.g. 20% advance; balance after completion is certified'),
          ),
          const SizedBox(height: 12),
          ElevatedButton(
            onPressed: _saving ? null : _save,
            child: _saving
                ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))
                : Text(e == null ? 'Create Work Order' : 'Save'),
          ),
        ]),
      ),
    );
  }
}

// ── Contracts ────────────────────────────────────────────────────────────────

class _ContractsTab extends ConsumerWidget {
  final String societyId;
  const _ContractsTab({required this.societyId});

  @override
  Widget build(BuildContext context, WidgetRef ref) => _asyncList<AmcContract>(
        ref,
        ref.watch(contractsProvider(societyId)),
        () => ref.invalidate(contractsProvider(societyId)),
        intro: 'Annual maintenance contracts — lift, security, housekeeping, pumps. Quotations and the sanction are '
            'recorded the same way as a work order; a contract starts only once it is sanctioned.',
        empty: 'No contracts yet',
        item: (c) => Card(
          margin: const EdgeInsets.only(bottom: 8),
          child: ListTile(
            onTap: () => context.push(contractRoute(c.id)),
            title: Text('${c.contractNumber} · ${c.contractName}', style: const TextStyle(fontWeight: FontWeight.w600)),
            subtitle: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('${c.vendorName ?? ''} · ${formatBillDate(c.startDate)} – ${formatBillDate(c.endDate)}'),
              const SizedBox(height: 4),
              StatusPill(
                  c.status == 'active' && c.daysToExpiry <= 60 ? 'Ends in ${c.daysToExpiry} days' : c.statusLabel,
                  c.status == 'active'
                      ? (c.daysToExpiry <= 60 ? AppTheme.warning : AppTheme.success)
                      : (c.isDraft ? AppTheme.warning : AppTheme.textSecondary)),
            ]),
            isThreeLine: true,
            trailing: c.annualValue != null
                ? Text('${formatRupees(c.annualValue!)}/yr', style: const TextStyle(fontWeight: FontWeight.w600))
                : null,
          ),
        ),
      );
}

class _ContractSheet extends ConsumerStatefulWidget {
  final String societyId;
  const _ContractSheet({required this.societyId});

  @override
  ConsumerState<_ContractSheet> createState() => _ContractSheetState();
}

class _ContractSheetState extends ConsumerState<_ContractSheet> {
  final _form = GlobalKey<FormState>();
  final _name = TextEditingController();
  final _scope = TextEditingController();
  String _category = 'lift';
  String _frequency = 'monthly';
  String? _vendor;
  DateTime? _start = DateTime.now();
  DateTime? _end;
  bool _saving = false;

  @override
  void dispose() {
    _name.dispose();
    _scope.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (!_form.currentState!.validate()) return;
    setState(() => _saving = true);
    try {
      final c = await ref.read(vendorsWorkApiProvider).createContract({
        'society_id': widget.societyId,
        'vendor_id': _vendor,
        'contract_name': _name.text.trim(),
        'category': _category,
        'service_frequency': _frequency,
        'start_date': _start!.toIso8601String().split('T').first,
        'end_date': _end!.toIso8601String().split('T').first,
        if (_scope.text.trim().isNotEmpty) 'scope_of_work': _scope.text.trim(),
      });
      ref.invalidate(contractsProvider(widget.societyId));
      if (!mounted) return;
      Navigator.pop(context);
      context.push(contractRoute(c.id));
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final vendors = ref.watch(vendorRecordsProvider(widget.societyId));
    return BillingSheetFrame(
      title: 'New Annual Contract',
      child: Form(
        key: _form,
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          TextFormField(
            controller: _name,
            maxLength: 255,
            decoration: const InputDecoration(labelText: 'Contract *', hintText: 'e.g. Lift AMC 2026-27', counterText: ''),
            validator: (v) => (v ?? '').trim().isEmpty ? 'Name the contract' : null,
          ),
          const SizedBox(height: 12),
          Row(children: [
            Expanded(
              child: DropdownButtonFormField<String>(
                initialValue: _category,
                decoration: const InputDecoration(labelText: 'Category *'),
                items: [for (final c in kVendorCategories) DropdownMenuItem(value: c.$1, child: Text(c.$2))],
                onChanged: (v) => setState(() => _category = v!),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: DropdownButtonFormField<String>(
                initialValue: _frequency,
                decoration: const InputDecoration(labelText: 'Service visits *'),
                items: [for (final f in kServiceFrequencies) DropdownMenuItem(value: f.$1, child: Text(f.$2))],
                onChanged: (v) => setState(() => _frequency = v!),
              ),
            ),
          ]),
          const SizedBox(height: 12),
          vendors.when(
            loading: () => const LinearProgressIndicator(),
            error: (e, _) => Text(friendlyErrorMessage(e), style: const TextStyle(color: AppTheme.error)),
            data: (list) => DropdownButtonFormField<String>(
              initialValue: _vendor,
              isExpanded: true,
              decoration: const InputDecoration(
                  labelText: 'Present vendor *',
                  helperText: 'The contract goes to whichever quotation is sanctioned'),
              items: [
                for (final v in list.where((v) => v.isActive))
                  DropdownMenuItem(value: v.id, child: Text(v.companyName)),
              ],
              onChanged: (v) => setState(() => _vendor = v),
              validator: (v) => v == null ? 'Choose a vendor' : null,
            ),
          ),
          const SizedBox(height: 12),
          Row(children: [
            Expanded(child: DateField(label: 'From', value: _start, required: true, onChanged: (d) => setState(() => _start = d))),
            const SizedBox(width: 12),
            Expanded(child: DateField(label: 'To', value: _end, required: true, onChanged: (d) => setState(() => _end = d))),
          ]),
          const SizedBox(height: 12),
          TextFormField(
            controller: _scope,
            maxLength: 5000,
            maxLines: 4,
            decoration: const InputDecoration(labelText: 'Scope of work'),
          ),
          const SizedBox(height: 12),
          ElevatedButton(
            onPressed: _saving ? null : _save,
            child: _saving
                ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))
                : const Text('Create Contract'),
          ),
        ]),
      ),
    );
  }
}

// ── Vendors ──────────────────────────────────────────────────────────────────

class _VendorsTab extends ConsumerWidget {
  final String societyId;
  final bool committee;
  const _VendorsTab({required this.societyId, required this.committee});

  Future<void> _blacklist(BuildContext context, WidgetRef ref, VendorRecord v) async {
    final reason = await askReason(context,
        title: 'Blacklist ${v.companyName}?',
        message: 'They won\'t be able to quote or be given work until made active again.',
        action: 'Blacklist');
    if (reason == null) return;
    try {
      await ref.read(vendorsWorkApiProvider).blacklistVendor(v.id, reason);
      ref.invalidate(vendorRecordsProvider(societyId));
      if (context.mounted) AppToast.success(context, '${v.companyName} blacklisted');
    } catch (e) {
      if (context.mounted) showErrorToast(context, e);
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) => _asyncList<VendorRecord>(
        ref,
        ref.watch(vendorRecordsProvider(societyId)),
        () => ref.invalidate(vendorRecordsProvider(societyId)),
        intro: 'The society\'s vendors and contractors. Keep GSTIN, PAN and bank details here — they print on '
            'work orders and are used for payments. A vendor whose phone or email is a committee member\'s can\'t '
            'be given work.',
        empty: 'No vendors yet',
        item: (v) => Card(
          margin: const EdgeInsets.only(bottom: 8),
          child: ListTile(
            onTap: committee
                ? () => showAppSheet(context: context, builder: (_) => VendorSheet(societyId: societyId, existing: v))
                : null,
            title: Text('${v.companyName} · ${v.vendorCode}', style: const TextStyle(fontWeight: FontWeight.w600)),
            subtitle: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text([
                vendorCategoryLabel(v.category),
                if (v.contactPerson != null) v.contactPerson!,
                v.mobile,
                if (v.gstNumber != null) 'GSTIN ${v.gstNumber}',
              ].join(' · ')),
              if (v.blacklistReason != null) Text('Blacklisted: ${v.blacklistReason}', style: const TextStyle(color: AppTheme.error)),
              const SizedBox(height: 4),
              StatusPill(v.statusLabel, switch (v.status) {
                'active' => AppTheme.success,
                'blacklisted' => AppTheme.error,
                _ => AppTheme.warning,
              }),
            ]),
            isThreeLine: true,
            trailing: committee && v.status != 'blacklisted'
                ? IconButton(
                    tooltip: 'Blacklist',
                    icon: const Icon(Icons.block_rounded),
                    onPressed: () => _blacklist(context, ref, v))
                : null,
          ),
        ),
      );
}

class VendorSheet extends ConsumerStatefulWidget {
  final String societyId;
  final VendorRecord? existing;
  const VendorSheet({super.key, required this.societyId, this.existing});

  @override
  ConsumerState<VendorSheet> createState() => _VendorSheetState();
}

class _VendorSheetState extends ConsumerState<VendorSheet> {
  final _form = GlobalKey<FormState>();
  late final VendorRecord? e = widget.existing;
  late final _name = TextEditingController(text: e?.companyName);
  late final _person = TextEditingController(text: e?.contactPerson);
  late final _mobile = TextEditingController(text: e?.mobile);
  late final _email = TextEditingController(text: e?.email);
  late final _address = TextEditingController(text: e?.address);
  late final _city = TextEditingController(text: e?.city);
  late final _pin = TextEditingController(text: e?.pincode);
  late final _gst = TextEditingController(text: e?.gstNumber);
  late final _pan = TextEditingController(text: e?.panNumber);
  late final _account = TextEditingController(text: e?.bankAccount);
  late final _bank = TextEditingController(text: e?.bankName);
  late final _ifsc = TextEditingController(text: e?.bankIfsc);
  late final _notes = TextEditingController(text: e?.notes);
  late String _category = e?.category ?? 'plumbing';
  late String _status = e?.status ?? 'active';
  bool _saving = false;

  List<TextEditingController> get _all =>
      [_name, _person, _mobile, _email, _address, _city, _pin, _gst, _pan, _account, _bank, _ifsc, _notes];

  @override
  void dispose() {
    for (final c in _all) {
      c.dispose();
    }
    super.dispose();
  }

  String? _t(TextEditingController c) => c.text.trim().isEmpty ? null : c.text.trim();

  Future<void> _save() async {
    if (!_form.currentState!.validate()) return;
    setState(() => _saving = true);
    final body = <String, dynamic>{
      'company_name': _name.text.trim(),
      'mobile': _mobile.text.trim(),
      'category': _category,
      'contact_person': _t(_person),
      'email': _t(_email),
      'address': _t(_address),
      'city': _t(_city),
      'gst_number': _t(_gst),
      'pan_number': _t(_pan),
      'bank_account': _t(_account),
      'bank_name': _t(_bank),
      'bank_ifsc': _t(_ifsc),
      'notes': _t(_notes),
    };
    final api = ref.read(vendorsWorkApiProvider);
    try {
      body['pincode'] = _t(_pin);
      if (e == null) {
        body.removeWhere((_, v) => v == null);
        await api.createVendor({...body, 'society_id': widget.societyId});
      } else {
        await api.updateVendor(e!.id, {...body, if (_status != e!.status) 'status': _status});
      }
      ref.invalidate(vendorRecordsProvider(widget.societyId));
      ref.invalidate(vendorsProvider(widget.societyId));     // the bill form's vendor list too
      if (mounted) {
        AppToast.success(context, e == null ? 'Vendor added' : 'Saved');
        Navigator.pop(context);
      }
    } catch (err) {
      if (mounted) showErrorToast(context, err);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Widget _field(TextEditingController c, String label,
          {int max = 100, String? Function(String?)? validator, TextCapitalization caps = TextCapitalization.none,
          TextInputType? keyboard}) =>
      Padding(
        padding: const EdgeInsets.only(bottom: 12),
        child: TextFormField(
          controller: c,
          maxLength: max,
          textCapitalization: caps,
          keyboardType: keyboard,
          decoration: InputDecoration(labelText: label, counterText: ''),
          validator: validator,
        ),
      );

  @override
  Widget build(BuildContext context) {
    const upper = TextCapitalization.characters;
    return BillingSheetFrame(
      title: e == null ? 'Add Vendor' : 'Edit ${e!.companyName}',
      child: Form(
        key: _form,
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          _field(_name, 'Company / name *', max: 255,
              validator: (v) => (v ?? '').trim().isEmpty ? 'Enter the name' : null),
          DropdownButtonFormField<String>(
            initialValue: _category,
            decoration: const InputDecoration(labelText: 'Category *'),
            items: [for (final c in kVendorCategories) DropdownMenuItem(value: c.$1, child: Text(c.$2))],
            onChanged: (v) => setState(() => _category = v!),
          ),
          const SizedBox(height: 12),
          if (e != null) ...[
            DropdownButtonFormField<String>(
              initialValue: _status,
              decoration: const InputDecoration(labelText: 'Status'),
              items: [
                if (e!.status == 'blacklisted') const DropdownMenuItem(value: 'blacklisted', child: Text('Blacklisted')),
                const DropdownMenuItem(value: 'active', child: Text('Active')),
                const DropdownMenuItem(value: 'inactive', child: Text('Inactive')),
                const DropdownMenuItem(value: 'under_review', child: Text('Under review')),
              ],
              onChanged: (v) => setState(() => _status = v!),
            ),
            const SizedBox(height: 12),
          ],
          _field(_person, 'Contact person', max: 255),
          _field(_mobile, 'Mobile *', max: 20, keyboard: TextInputType.phone,
              validator: (v) => RegExp(r'^\+?[0-9 \-()]{7,20}$').hasMatch((v ?? '').trim()) ? null : 'Enter a valid phone number'),
          _field(_email, 'Email', max: 255, keyboard: TextInputType.emailAddress),
          _field(_address, 'Address', max: 1000),
          Row(children: [
            Expanded(child: _field(_city, 'City')),
            const SizedBox(width: 12),
            Expanded(
                  child: _field(_pin, 'Pincode', max: 6, keyboard: TextInputType.number,
                      validator: (v) => (v ?? '').trim().isEmpty || RegExp(r'^\d{6}$').hasMatch(v!.trim())
                          ? null
                          : '6 digits')),
          ]),
          Row(children: [
            Expanded(child: _field(_gst, 'GSTIN', max: 15, caps: upper)),
            const SizedBox(width: 12),
            Expanded(child: _field(_pan, 'PAN', max: 10, caps: upper)),
          ]),
          _field(_account, 'Bank account no.', max: 34),
          Row(children: [
            Expanded(child: _field(_bank, 'Bank')),
            const SizedBox(width: 12),
            Expanded(child: _field(_ifsc, 'IFSC', max: 11, caps: upper)),
          ]),
          _field(_notes, 'Notes', max: 2000),
          if (e != null) _PaidToVendor(societyId: widget.societyId, vendorId: e!.id),
          ElevatedButton(
            onPressed: _saving ? null : _save,
            child: _saving
                ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))
                : Text(e == null ? 'Add Vendor' : 'Save'),
          ),
        ]),
      ),
    );
  }
}

// ── Limits (bye-law 157) ─────────────────────────────────────────────────────

class _LimitsTab extends ConsumerWidget {
  final String societyId;
  final bool committee;
  const _LimitsTab({required this.societyId, required this.committee});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(procurementLimitsProvider(societyId));
    return RefreshIndicator(
      onRefresh: () async => ref.invalidate(procurementLimitsProvider(societyId)),
      child: async.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => ListView(children: [
          Padding(padding: const EdgeInsets.all(24), child: Text(friendlyErrorMessage(e), style: const TextStyle(color: AppTheme.error))),
        ]),
        data: (l) => ResponsiveBody(
          maxWidth: 760,
          child: ListView(padding: const EdgeInsets.all(16), children: [
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  const Text('Spending limits', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
                  const SizedBox(height: 8),
                  InfoLine('Committee may sanction up to',
                      '${formatRupees(l.committeeLimit)}${l.committeeLimitSet ? ' (fixed by the general body)' : ' (bye-law 157 for ${l.members} members)'}'),
                  InfoLine('Tenders needed above',
                      '${formatRupees(l.tenderLimit)}${l.tenderLimitSet ? ' (fixed by the general body)' : ' (same as the committee\'s limit)'}'),
                  InfoLine('Tenders / quotations needed', 'At least ${l.minQuotations}, from different vendors'),
                  if (l.gbResolutionNo != null)
                    InfoLine('General body resolution',
                        '${l.gbResolutionNo}${l.gbMeetingDate != null ? ' of ${formatBillDate(l.gbMeetingDate!)}' : ''}'),
                  if (committee) ...[
                    const SizedBox(height: 12),
                    OutlinedButton.icon(
                      onPressed: () => showAppSheet(context: context, builder: (_) => _LimitsSheet(societyId: societyId, limits: l)),
                      icon: const Icon(Icons.edit_rounded, size: 18),
                      label: const Text('Change limits'),
                    ),
                  ],
                ]),
              ),
            ),
            const SizedBox(height: 12),
            const Card(
              child: Padding(
                padding: EdgeInsets.all(16),
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text('What the model bye-laws require', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
                  SizedBox(height: 8),
                  Text(
                    '• The committee may spend on repairs and maintenance on its own only up to ₹25,000 (up to 25 '
                    'members), ₹50,000 (26–50) or ₹1,00,000 (51 and above), unless the general body fixes another '
                    'limit. Beyond it the general body\'s prior sanction is needed (bye-law 157).\n'
                    '• Above the limit the general body fixes for work without tenders, tenders are invited; the '
                    'Secretary opens them in a committee meeting, the committee scrutinises them and places them '
                    'with its report before the general body, which decides.\n'
                    '• A committee member who has an interest in a contract with the society is disqualified, so '
                    'every sanction records the committee\'s declaration.\n'
                    '• Cheques and transfers are signed by two office-bearers.\n'
                    '• Check these against your society\'s registered bye-laws and any later amendment; set the '
                    'limits your general body has resolved.',
                    style: TextStyle(fontSize: 13, height: 1.45),
                  ),
                ]),
              ),
            ),
          ]),
        ),
      ),
    );
  }
}

class _LimitsSheet extends ConsumerStatefulWidget {
  final String societyId;
  final ProcurementLimits limits;
  const _LimitsSheet({required this.societyId, required this.limits});

  @override
  ConsumerState<_LimitsSheet> createState() => _LimitsSheetState();
}

class _LimitsSheetState extends ConsumerState<_LimitsSheet> {
  final _form = GlobalKey<FormState>();
  late final _committee = TextEditingController(text: widget.limits.committeeLimitSet ? widget.limits.committeeLimit : '');
  late final _tender = TextEditingController(text: widget.limits.tenderLimitSet ? widget.limits.tenderLimit : '');
  late final _min = TextEditingController(text: '${widget.limits.minQuotations}');
  late final _resolution = TextEditingController(text: widget.limits.gbResolutionNo);
  late DateTime? _meeting = widget.limits.gbMeetingDate;
  bool _saving = false;

  @override
  void dispose() {
    for (final c in [_committee, _tender, _min, _resolution]) {
      c.dispose();
    }
    super.dispose();
  }

  bool get _custom => _committee.text.trim().isNotEmpty || _tender.text.trim().isNotEmpty;

  Future<void> _save() async {
    if (!_form.currentState!.validate()) return;
    setState(() => _saving = true);
    try {
      await ref.read(vendorsWorkApiProvider).saveLimits(widget.societyId, {
        'committee_limit': _committee.text.trim().isEmpty ? null : parseMoney(_committee.text)!.toStringAsFixed(2),
        'tender_limit': _tender.text.trim().isEmpty ? null : parseMoney(_tender.text)!.toStringAsFixed(2),
        'min_quotations': int.parse(_min.text.trim()),
        'gb_resolution_no': _resolution.text.trim().isEmpty ? null : _resolution.text.trim(),
        'gb_meeting_date': _meeting?.toIso8601String().split('T').first,
      });
      ref.invalidate(procurementLimitsProvider(widget.societyId));
      if (mounted) Navigator.pop(context);
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) => BillingSheetFrame(
        title: 'Spending Limits',
        child: Form(
          key: _form,
          child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            Text('Leave a limit blank to follow the bye-law (${formatRupees(widget.limits.byeLawLimit)} for '
                '${widget.limits.members} members). Other figures must be resolved by the general body.',
                style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary)),
            const SizedBox(height: 12),
            TextFormField(
              controller: _committee,
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
              inputFormatters: moneyInput,
              onChanged: (_) => setState(() {}),
              decoration: const InputDecoration(labelText: 'Committee may sanction up to (₹)'),
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _tender,
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
              inputFormatters: moneyInput,
              onChanged: (_) => setState(() {}),
              decoration: const InputDecoration(labelText: 'Tenders needed above (₹)'),
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _min,
              keyboardType: TextInputType.number,
              inputFormatters: [FilteringTextInputFormatter.digitsOnly, LengthLimitingTextInputFormatter(2)],
              decoration: const InputDecoration(labelText: 'Tenders / quotations needed *'),
              validator: (v) {
                final n = int.tryParse(v ?? '');
                return n == null || n < 2 || n > 10 ? 'Between 2 and 10' : null;
              },
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _resolution,
              maxLength: 50,
              decoration: InputDecoration(labelText: 'General body resolution no.${_custom ? ' *' : ''}', counterText: ''),
              validator: (v) => _custom && (v ?? '').trim().isEmpty ? 'Needed for limits other than the bye-law\'s' : null,
            ),
            const SizedBox(height: 12),
            DateField(
                label: 'General body meeting date', value: _meeting, required: _custom, lastDate: DateTime.now(),
                onChanged: (d) => setState(() => _meeting = d)),
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: _saving ? null : _save,
              child: _saving
                  ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))
                  : const Text('Save'),
            ),
          ]),
        ),
      );
}


/// What the society has paid this vendor straight from expenses and payments, newest first — so what the
/// Vendor Master holds and what the books show are the same story.
class _PaidToVendor extends ConsumerWidget {
  final String societyId;
  final String vendorId;
  const _PaidToVendor({required this.societyId, required this.vendorId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final paid = ref.watch(vendorPaymentsProvider((societyId, vendorId)));
    return paid.maybeWhen(
      data: (rows) {
        if (rows.isEmpty) return const SizedBox.shrink();
        final total = rows.fold<double>(0, (a, v) => a + v.amount);
        return Container(
          margin: const EdgeInsets.only(bottom: 12),
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
              color: AppTheme.surface, borderRadius: BorderRadius.circular(12), border: Border.all(color: AppTheme.border)),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              const Expanded(child: Text('Paid from expenses', style: TextStyle(fontWeight: FontWeight.w700))),
              Text(formatInr(total), style: const TextStyle(fontWeight: FontWeight.w700)),
            ]),
            const SizedBox(height: 6),
            for (final v in rows.take(5))
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 2),
                child: Row(children: [
                  Expanded(
                    child: Text('${v.voucherNumber} · ${formatAccountsDate(v.voucherDate)}',
                        style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary)),
                  ),
                  Text(formatInr(v.amount), style: const TextStyle(fontSize: 12.5)),
                ]),
              ),
            if (rows.length > 5)
              Text('and ${rows.length - 5} more in the Day Book',
                  style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
          ]),
        );
      },
      orElse: () => const SizedBox.shrink(),
    );
  }
}
