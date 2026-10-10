import 'package:flutter/material.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/layout/app_sheet.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/accounts/presentation/widgets/accounts_widgets.dart' show PdfActions;
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/maintenance_billing/data/maintenance_billing_api.dart' show formatBillDate, formatRupees;
import 'package:ar_society_app/features/maintenance_billing/presentation/widgets/billing_sheet_frame.dart';
import 'package:ar_society_app/features/vendor/data/vendors_work_api.dart';
import 'package:ar_society_app/features/vendor/presentation/providers/vendors_work_providers.dart';
import 'package:ar_society_app/features/vendor/presentation/screens/vendors_work_screen.dart';
import 'package:ar_society_app/features/vendor/presentation/widgets/procurement_widgets.dart';
import 'package:ar_society_app/shared/widgets/app_data_table.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';

/// One work order from quotations to closure. The manager prepares it and
/// enters quotations and bills; the committee sanctions, issues, certifies
/// completion, releases the retention and closes it.
class WorkOrderDetailScreen extends ConsumerStatefulWidget {
  final String workOrderId;
  const WorkOrderDetailScreen({super.key, required this.workOrderId});

  @override
  ConsumerState<WorkOrderDetailScreen> createState() => _WorkOrderDetailScreenState();
}

class _WorkOrderDetailScreenState extends ConsumerState<WorkOrderDetailScreen> {
  bool _busy = false;

  VendorsWorkApi get _api => ref.read(vendorsWorkApiProvider);

  Future<void> _run(Future<WorkOrder> Function() call, String done) async {
    setState(() => _busy = true);
    try {
      await call();
      _refresh();
      if (mounted) AppToast.success(context, done);
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _refresh() {
    ref.invalidate(workOrderProvider(widget.workOrderId));
    final sid = ref.read(currentUserProvider)?.societyId;
    if (sid != null) ref.invalidate(workOrdersProvider(sid));
  }

  Future<DateTime?> _pickDate(String help, {DateTime? first}) => showDatePicker(
        context: context,
        helpText: help,
        initialDate: DateTime.now(),
        firstDate: first ?? DateTime(2000),
        lastDate: DateTime.now(),
      );

  Future<void> _addQuotation(WorkOrder wo, String societyId) async {
    final vendors = await ref.read(vendorRecordsProvider(societyId).future);
    if (!mounted) return;
    showAppSheet(
      context: context,
      builder: (_) => QuotationSheet(
        vendors: vendors,
        alreadyQuoted: {for (final q in wo.quotations) q.vendorId},
        onSave: (q) async {
          await _api.addWorkOrderQuotation(wo.id, q);
          _refresh();
        },
      ),
    );
  }

  void _sanction(WorkOrder wo) => showAppSheet(
        context: context,
        builder: (_) => SanctionSheet(
          what: wo.woNumber,
          quotations: wo.quotations,
          requirements: wo.requirements,
          onSave: (s) async {
            await _api.sanctionWorkOrder(wo.id, s);
            _refresh();
          },
        ),
      );

  Future<void> _issue(WorkOrder wo) async {
    final d = await _pickDate('Work order issued on', first: wo.sanction.gbMeetingDate ?? wo.sanction.committeeMeetingDate);
    if (d != null) await _run(() => _api.issueWorkOrder(wo.id, d), '${wo.woNumber} issued');
  }

  void _complete(WorkOrder wo) =>
      showAppSheet(context: context, builder: (_) => _CompleteSheet(wo: wo, onDone: () => _refresh()));

  Future<void> _release(WorkOrder wo) async {
    final d = await _pickDate('Retention released on', first: wo.retentionDueOn);
    if (d != null) await _run(() => _api.releaseRetention(wo.id, d), 'Retention released');
  }

  Future<void> _close(WorkOrder wo) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text('Close ${wo.woNumber}?'),
        content: const Text('Every bill on it is paid. Closing marks the work done and settled.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Back')),
          TextButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Close it')),
        ],
      ),
    );
    if (ok == true) await _run(() => _api.closeWorkOrder(wo.id), '${wo.woNumber} closed');
  }

  Future<void> _cancel(WorkOrder wo) async {
    final reason = await askReason(context,
        title: 'Cancel ${wo.woNumber}?', message: 'The work won\'t go ahead.', action: 'Cancel it');
    if (reason != null) await _run(() => _api.cancelWorkOrder(wo.id, reason), 'Cancelled');
  }

  void _bill(WorkOrder wo, String societyId) => showAppSheet(
      context: context, builder: (_) => _BillSheet(wo: wo, societyId: societyId, onDone: () => _refresh()));

  void _revise(WorkOrder wo) =>
      showAppSheet(context: context, builder: (_) => _ReviseSheet(wo: wo, onDone: () => _refresh()));

  @override
  Widget build(BuildContext context) {
    final user = ref.watch(currentUserProvider);
    final societyId = user?.societyId ?? '';
    final committee = user?.isAdminOrCommittee ?? false;
    final async = ref.watch(workOrderProvider(widget.workOrderId));
    final wo = async.valueOrNull;
    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(
        title: Text(wo?.woNumber ?? 'Work Order'),
        actions: [
          if (wo != null && wo.canPrint)
            PdfActions(
                load: () => _api.workOrderPdf(wo.id), fileName: '${wo.woNumber}.pdf', subject: 'Work order ${wo.woNumber}'),
        ],
      ),
      body: async.when(
        loading: () => const AppLoader(),
        error: (e, _) => Center(child: Text(friendlyErrorMessage(e), style: const TextStyle(color: AppTheme.error))),
        data: (wo) => RefreshIndicator(
          onRefresh: () async => _refresh(),
          child: ResponsiveBody(
            maxWidth: 860,
            child: ListView(padding: const EdgeInsets.all(16), children: [
              _Section(children: [
                Row(children: [
                  Expanded(child: Text(wo.title, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700))),
                  StatusPill(wo.statusLabel, workOrderColor(wo.status)),
                ]),
                const SizedBox(height: 6),
                Text([
                  vendorCategoryLabel(wo.category),
                  if (wo.location != null) wo.location!,
                  if (wo.vendorName != null) 'Vendor: ${wo.vendorName}',
                ].join(' · '), style: const TextStyle(color: AppTheme.textSecondary)),
                if (wo.cancelReason != null) ...[
                  const SizedBox(height: 6),
                  Text('Cancelled: ${wo.cancelReason}', style: const TextStyle(color: AppTheme.error)),
                ],
                const SizedBox(height: 12),
                _NextStep(
                  wo: wo,
                  committee: committee,
                  busy: _busy,
                  onQuote: () => _addQuotation(wo, societyId),
                  onSanction: () => _sanction(wo),
                  onIssue: () => _issue(wo),
                  onBill: () => _bill(wo, societyId),
                  onComplete: () => _complete(wo),
                  onRelease: () => _release(wo),
                  onClose: () => _close(wo),
                  onPay: () => context.push(AppRoutes.vendorBills),
                ),
                Wrap(spacing: 8, children: [
                  if (wo.isDraft || wo.status == 'sanctioned')
                    TextButton.icon(
                        onPressed: () => showAppSheet(
                            context: context, builder: (_) => WorkOrderSheet(societyId: societyId, existing: wo)),
                        icon: const Icon(Icons.edit_rounded, size: 18),
                        label: const Text('Edit')),
                  if (committee && {'sanctioned', 'issued', 'completed'}.contains(wo.status))
                    TextButton.icon(
                        onPressed: () => _revise(wo),
                        icon: const Icon(Icons.price_change_rounded, size: 18),
                        label: const Text('Revise sanction')),
                  if (committee && {'draft', 'sanctioned', 'issued'}.contains(wo.status) && wo.bills.isEmpty)
                    TextButton.icon(
                        onPressed: () => _cancel(wo),
                        style: TextButton.styleFrom(foregroundColor: AppTheme.error),
                        icon: const Icon(Icons.cancel_outlined, size: 18),
                        label: const Text('Cancel')),
                ]),
              ]),
              if (wo.isDraft) ...[
                const SizedBox(height: 12),
                RequirementsBanner(wo.requirements),
              ],
              const SizedBox(height: 12),
              _Section(title: 'Quotations', children: [
                QuotationsList(
                  quotations: wo.quotations,
                  onRemove: wo.isDraft
                      ? (q) => _run(() => _api.removeWorkOrderQuotation(wo.id, q.id), 'Quotation removed')
                      : null,
                ),
                if (wo.isDraft)
                  Align(
                    alignment: Alignment.centerLeft,
                    child: TextButton.icon(
                        onPressed: () => _addQuotation(wo, societyId),
                        icon: const Icon(Icons.add_rounded),
                        label: const Text('Add quotation')),
                  ),
              ]),
              if (wo.sanction.isSanctioned) ...[
                const SizedBox(height: 12),
                _Section(title: 'Sanction', children: [SanctionSummary(wo.sanction)]),
              ],
              const SizedBox(height: 12),
              _Section(title: 'Work and terms', children: [
                if (wo.scopeOfWork != null)
                  Padding(padding: const EdgeInsets.only(bottom: 8), child: Text(wo.scopeOfWork!)),
                if (wo.estimatedCost != null) InfoLine('Estimated cost', formatRupees(wo.estimatedCost!)),
                InfoLine('Expense head', wo.expenseAccountName ?? 'By the vendor\'s category'),
                if (wo.startDate != null) InfoLine('Start', formatBillDate(wo.startDate!)),
                if (wo.dueDate != null) InfoLine('Complete by', formatBillDate(wo.dueDate!)),
                InfoLine('Advance', formatRupees(wo.advanceAmount)),
                InfoLine('Retention',
                    wo.hasRetention ? '${wo.retentionPct}% for ${wo.defectLiabilityMonths} months after completion' : 'None'),
                if (wo.paymentTerms != null) InfoLine('Payment terms', wo.paymentTerms!),
                if (wo.issuedOn != null) InfoLine('Issued on', formatBillDate(wo.issuedOn!)),
                if (wo.completedOn != null)
                  InfoLine('Completed',
                      '${formatBillDate(wo.completedOn!)}${wo.certifiedByName != null ? ' · certified by ${wo.certifiedByName}' : ''}'
                      '${wo.certificateRef != null ? ' · ${wo.certificateRef}' : ''}'),
                if (wo.completionNotes != null) InfoLine('Completion notes', wo.completionNotes!),
              ]),
              if (wo.sanction.isSanctioned) ...[
                const SizedBox(height: 12),
                _Section(title: 'Bills and payments', children: [
                  InfoLine('Sanctioned', formatRupees(wo.sanction.amount!)),
                  InfoLine('Billed', '${formatRupees(wo.billed)} · ${formatRupees(wo.unbilled)} still to be billed'),
                  InfoLine('Paid', formatRupees(wo.paid)),
                  if (wo.hasRetention)
                    InfoLine('Retention held',
                        wo.retentionReleasedOn != null
                            ? 'Released on ${formatBillDate(wo.retentionReleasedOn!)}'
                            : '${formatRupees(wo.retentionHeld)}${wo.retentionDueOn != null ? ' until ${formatBillDate(wo.retentionDueOn!)}' : ''}'),
                  InfoLine('Can be paid now', formatRupees(wo.payableNow)),
                  const Divider(),
                  if (wo.bills.isEmpty) const Text('No bills yet', style: TextStyle(color: AppTheme.textSecondary)),
                  for (final b in wo.bills)
                    ListTile(
                      contentPadding: EdgeInsets.zero,
                      dense: true,
                      title: Text('${b.invoiceNumber} · ${formatBillDate(b.invoiceDate)}'),
                      subtitle: Text('Paid ${formatRupees(b.paidAmount)} of ${formatRupees(b.totalAmount)}'),
                      trailing: StatusPill(b.isPaid ? 'Paid' : 'Due ${formatRupees(b.outstanding)}',
                          b.isPaid ? AppTheme.success : AppTheme.warning),
                    ),
                ]),
              ],
            ]),
          ),
        ),
      ),
    );
  }
}

class _Section extends StatelessWidget {
  final String? title;
  final List<Widget> children;
  const _Section({this.title, required this.children});

  @override
  Widget build(BuildContext context) => Card(
        margin: EdgeInsets.zero,
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            if (title != null) ...[
              Text(title!, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700)),
              const SizedBox(height: 8),
            ],
            ...children,
          ]),
        ),
      );
}

/// What to do next, with the button for it.
class _NextStep extends StatelessWidget {
  final WorkOrder wo;
  final bool committee;
  final bool busy;
  final VoidCallback onQuote, onSanction, onIssue, onBill, onComplete, onRelease, onClose, onPay;
  const _NextStep({
    required this.wo,
    required this.committee,
    required this.busy,
    required this.onQuote,
    required this.onSanction,
    required this.onIssue,
    required this.onBill,
    required this.onComplete,
    required this.onRelease,
    required this.onClose,
    required this.onPay,
  });

  @override
  Widget build(BuildContext context) {
    final waitingRetention = wo.hasRetention && wo.retentionReleasedOn == null;
    final releasable = waitingRetention && wo.retentionDueOn != null && !wo.retentionDueOn!.isAfter(DateTime.now());
    final allPaid = wo.bills.isNotEmpty && wo.bills.every((b) => b.isPaid);
    final (String text, List<(String, IconData, VoidCallback, bool)> actions) = switch (wo.status) {
      'draft' when wo.quotations.isEmpty => ('Collect quotations from vendors and enter them.', [
          ('Add quotation', Icons.add_rounded, onQuote, true),
        ]),
      'draft' => (
          committee
              ? 'Record the committee\'s decision once the quotations have been considered.'
              : 'Quotations are in. The committee records its sanction next.',
          [
            ('Add quotation', Icons.add_rounded, onQuote, true),
            ('Sanction', Icons.gavel_rounded, onSanction, committee),
          ]
        ),
      'sanctioned' => (
          'Sanctioned. Issue the written work order to ${wo.vendorName} (download it above to sign).',
          [('Issue work order', Icons.send_rounded, onIssue, committee)]
        ),
      'issued' => (
          'Work in progress. Bills can be entered; only the agreed advance can be paid until the committee '
              'certifies completion.',
          [
            ('Record bill', Icons.receipt_long_rounded, onBill, true),
            ('Certify completion', Icons.task_alt_rounded, onComplete, committee),
          ]
        ),
      'completed' => (
          waitingRetention
              ? (releasable
                  ? 'The defect liability period is over. Release the retention once the work has been checked.'
                  : 'Completed. The retention is held until ${wo.retentionDueOn == null ? '' : formatBillDate(wo.retentionDueOn!)}.')
              : (allPaid ? 'Every bill is paid. Close the work order.' : 'Completed. Pay the bills from Vendor Bills.'),
          [
            if (wo.unbilled != '0.00') ('Record bill', Icons.receipt_long_rounded, onBill, true),
            if (!allPaid) ('Pay bills', Icons.payments_rounded, onPay, true),
            if (releasable) ('Release retention', Icons.lock_open_rounded, onRelease, committee),
            if (allPaid) ('Close', Icons.done_all_rounded, onClose, committee),
          ]
        ),
      'closed' => ('Closed — the work is done and every bill paid.', <(String, IconData, VoidCallback, bool)>[]),
      _ => ('Cancelled.', <(String, IconData, VoidCallback, bool)>[]),
    };
    final shown = actions.where((a) => a.$4).toList();
    final needsCommittee = actions.any((a) => !a.$4);
    return Container(
      padding: const EdgeInsets.all(12),
      margin: const EdgeInsets.only(bottom: 4),
      decoration: BoxDecoration(color: AppTheme.primary.withOpacity(0.06), borderRadius: BorderRadius.circular(10)),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(text, style: const TextStyle(fontSize: 13.5, height: 1.35)),
        if (needsCommittee)
          const Padding(
            padding: EdgeInsets.only(top: 4),
            child: Text('Some steps are for the managing committee.',
                style: TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
          ),
        if (shown.isNotEmpty) ...[
          const SizedBox(height: 10),
          Wrap(spacing: 8, runSpacing: 8, children: [
            for (final (i, a) in shown.indexed)
              i == 0
                  ? FilledButton.icon(onPressed: busy ? null : a.$3, icon: Icon(a.$2, size: 18), label: Text(a.$1))
                  : OutlinedButton.icon(onPressed: busy ? null : a.$3, icon: Icon(a.$2, size: 18), label: Text(a.$1)),
          ]),
        ],
      ]),
    );
  }
}

class _CompleteSheet extends ConsumerStatefulWidget {
  final WorkOrder wo;
  final VoidCallback onDone;
  const _CompleteSheet({required this.wo, required this.onDone});

  @override
  ConsumerState<_CompleteSheet> createState() => _CompleteSheetState();
}

class _CompleteSheetState extends ConsumerState<_CompleteSheet> {
  final _form = GlobalKey<FormState>();
  final _notes = TextEditingController();
  final _cert = TextEditingController();
  DateTime? _on = DateTime.now();
  bool _saving = false;

  @override
  void dispose() {
    _notes.dispose();
    _cert.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (!_form.currentState!.validate()) return;
    setState(() => _saving = true);
    try {
      await ref.read(vendorsWorkApiProvider).completeWorkOrder(widget.wo.id, _on!, _notes.text.trim(), _cert.text.trim());
      widget.onDone();
      if (mounted) {
        AppToast.success(context, 'Completion certified');
        Navigator.pop(context);
      }
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) => BillingSheetFrame(
        title: 'Certify Completion',
        child: Form(
          key: _form,
          child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            const Text('Certify only after the work has been inspected. The final payment is released after this.',
                style: TextStyle(fontSize: 12.5, color: AppTheme.textSecondary)),
            const SizedBox(height: 12),
            FormFieldBox(label: 'Completed on', child: DateField(
                label: '',value: _on, required: true, lastDate: DateTime.now(),
                onChanged: (d) => setState(() => _on = d))),
            const SizedBox(height: 12),
            FormFieldBox(label: 'What was checked', required: true, child: TextFormField(
              controller: _notes,
              maxLength: 2000,
              maxLines: 3,
              decoration: const InputDecoration(hintText: 'e.g. Tank tested for 24 h, no leaks'),
              validator: (v) => (v ?? '').trim().isEmpty ? 'Describe the inspection' : null,
            )),
            FormFieldBox(label: 'Architect / engineer certificate ref.', child: TextFormField(
              controller: _cert,
              maxLength: 100,
              decoration: const InputDecoration(
                  counterText: ''),
            )),
            const SizedBox(height: 12),
            ElevatedButton(
              onPressed: _saving ? null : _save,
              child: _saving
                  ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))
                  : const Text('Certify'),
            ),
          ]),
        ),
      );
}

class _BillSheet extends ConsumerStatefulWidget {
  final WorkOrder wo;
  final String societyId;
  final VoidCallback onDone;
  const _BillSheet({required this.wo, required this.societyId, required this.onDone});

  @override
  ConsumerState<_BillSheet> createState() => _BillSheetState();
}

class _BillSheetState extends ConsumerState<_BillSheet> {
  final _form = GlobalKey<FormState>();
  final _number = TextEditingController();
  final _amount = TextEditingController();
  final _gst = TextEditingController(text: '0');
  final _desc = TextEditingController();
  DateTime? _date = DateTime.now();
  bool _saving = false;

  @override
  void dispose() {
    for (final c in [_number, _amount, _gst, _desc]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _save() async {
    if (!_form.currentState!.validate()) return;
    setState(() => _saving = true);
    try {
      await ref.read(vendorsWorkApiProvider).recordBill(
            societyId: widget.societyId,
            wo: widget.wo,
            invoiceNumber: _number.text.trim(),
            invoiceDate: _date!,
            amount: parseMoney(_amount.text)!,
            gst: parseMoney(_gst.text) ?? 0,
            description: _desc.text.trim().isEmpty ? '${widget.wo.woNumber} ${widget.wo.title}' : _desc.text.trim(),
          );
      widget.onDone();
      if (mounted) {
        AppToast.success(context, 'Bill recorded');
        Navigator.pop(context);
      }
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final total = (parseMoney(_amount.text) ?? 0) + (parseMoney(_gst.text) ?? 0);
    return BillingSheetFrame(
      title: 'Bill from ${widget.wo.vendorName ?? 'vendor'}',
      child: Form(
        key: _form,
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Text('Up to ${formatRupees(widget.wo.unbilled)} more can be billed on ${widget.wo.woNumber}.',
              style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary)),
          const SizedBox(height: 12),
          FormFieldBox(label: 'Vendor\'s bill no. *', child: TextFormField(
            controller: _number,
            maxLength: 50,
            decoration: const InputDecoration(counterText: ''),
            validator: (v) => (v ?? '').trim().isEmpty ? 'Enter the bill number' : null,
          )),
          const SizedBox(height: 12),
          FormFieldBox(label: 'Bill date', child: DateField(
              label: '',value: _date, required: true, lastDate: DateTime.now(),
              onChanged: (d) => setState(() => _date = d))),
          const SizedBox(height: 12),
          Row(children: [
            Expanded(
              child: FormFieldBox(label: 'Amount (₹)', required: true, child: TextFormField(
                controller: _amount,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                inputFormatters: moneyInput,
                onChanged: (_) => setState(() {}),
                decoration: const InputDecoration(),
                validator: (v) => (parseMoney(v ?? '') ?? 0) <= 0 ? 'Enter the amount' : null,
              )),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: FormFieldBox(label: 'GST (₹)', child: TextFormField(
                controller: _gst,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                inputFormatters: moneyInput,
                onChanged: (_) => setState(() {}),
                decoration: const InputDecoration(),
              )),
            ),
          ]),
          const SizedBox(height: 6),
          Text('Total ${formatRupees(total.toStringAsFixed(2))}', style: const TextStyle(fontWeight: FontWeight.w600)),
          const SizedBox(height: 12),
          FormFieldBox(label: 'Description', child: TextFormField(controller: _desc, maxLength: 2000, decoration: const InputDecoration())),
          const SizedBox(height: 12),
          ElevatedButton(
            onPressed: _saving ? null : _save,
            child: _saving
                ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))
                : const Text('Record Bill'),
          ),
        ]),
      ),
    );
  }
}

class _ReviseSheet extends ConsumerStatefulWidget {
  final WorkOrder wo;
  final VoidCallback onDone;
  const _ReviseSheet({required this.wo, required this.onDone});

  @override
  ConsumerState<_ReviseSheet> createState() => _ReviseSheetState();
}

class _ReviseSheetState extends ConsumerState<_ReviseSheet> {
  final _form = GlobalKey<FormState>();
  late final _amount = TextEditingController(text: widget.wo.sanction.amount);
  final _reason = TextEditingController();
  final _resolution = TextEditingController();
  final _gbResolution = TextEditingController();
  DateTime? _meeting;
  DateTime? _gbMeeting;
  bool _saving = false;

  @override
  void dispose() {
    for (final c in [_amount, _reason, _resolution, _gbResolution]) {
      c.dispose();
    }
    super.dispose();
  }

  bool get _needsGb {
    final a = parseMoney(_amount.text) ?? 0;
    final r = widget.wo.requirements;
    return a > (double.tryParse(r.committeeLimit) ?? 0) || a > (double.tryParse(r.tenderLimit) ?? 0);
  }

  Future<void> _save() async {
    if (!_form.currentState!.validate()) return;
    setState(() => _saving = true);
    try {
      await ref.read(vendorsWorkApiProvider).reviseSanction(widget.wo.id, {
        'amount': parseMoney(_amount.text)!.toStringAsFixed(2),
        'reason': _reason.text.trim(),
        'committee_resolution_no': _resolution.text.trim(),
        'committee_meeting_date': _meeting!.toIso8601String().split('T').first,
        if (_needsGb) 'gb_resolution_no': _gbResolution.text.trim(),
        if (_needsGb) 'gb_meeting_date': _gbMeeting!.toIso8601String().split('T').first,
      });
      widget.onDone();
      if (mounted) {
        AppToast.success(context, 'Sanction revised');
        Navigator.pop(context);
      }
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) => BillingSheetFrame(
        title: 'Revise Sanction',
        child: Form(
          key: _form,
          child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            Text('Extra work beyond the sanctioned ${formatRupees(widget.wo.sanction.amount ?? '0')} needs a fresh '
                'resolution before it is billed.', style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary)),
            const SizedBox(height: 12),
            FormFieldBox(label: 'New sanctioned amount (₹)', required: true, child: TextFormField(
              controller: _amount,
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
              inputFormatters: moneyInput,
              onChanged: (_) => setState(() {}),
              decoration: const InputDecoration(),
              validator: (v) => (parseMoney(v ?? '') ?? 0) <= 0 ? 'Enter the amount' : null,
            )),
            const SizedBox(height: 12),
            FormFieldBox(label: 'Why', required: true, child: TextFormField(
              controller: _reason,
              maxLength: 1000,
              maxLines: 2,
              decoration: const InputDecoration(),
              validator: (v) => (v ?? '').trim().isEmpty ? 'Record why' : null,
            )),
            FormFieldBox(label: 'Committee resolution no.', required: true, child: TextFormField(
              controller: _resolution,
              maxLength: 50,
              decoration: const InputDecoration(counterText: ''),
              validator: (v) => (v ?? '').trim().isEmpty ? 'Enter the resolution number' : null,
            )),
            const SizedBox(height: 12),
            FormFieldBox(label: 'Committee meeting date', child: DateField(
                label: '',value: _meeting, required: true, lastDate: DateTime.now(),
                onChanged: (d) => setState(() => _meeting = d))),
            if (_needsGb) ...[
              const SizedBox(height: 12),
              FormFieldBox(label: 'General body resolution no.', required: true, child: TextFormField(
                controller: _gbResolution,
                maxLength: 50,
                decoration: const InputDecoration(counterText: ''),
                validator: (v) => (v ?? '').trim().isEmpty ? 'This amount needs the general body' : null,
              )),
              const SizedBox(height: 12),
              FormFieldBox(label: 'General body meeting date', child: DateField(
                  label: '',value: _gbMeeting, required: true, lastDate: DateTime.now(),
                  onChanged: (d) => setState(() => _gbMeeting = d))),
            ],
            const SizedBox(height: 12),
            ElevatedButton(
              onPressed: _saving ? null : _save,
              child: _saving
                  ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))
                  : const Text('Revise'),
            ),
          ]),
        ),
      );
}
