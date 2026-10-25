import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/layout/app_sheet.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart' show formatInr;
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/vendor/data/vendor_master_api.dart';
import 'package:ar_society_app/shared/widgets/app_data_table.dart' show StatusPill;
import 'package:ar_society_app/shared/widgets/app_form.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// The society's TDS rates and limits, one row per section and kind of payee. They start from the usual rates and are
/// corrected here when the law changes or the chartered accountant says otherwise. Under a limit nothing is deducted;
/// an inactive rule deducts nothing. Only the committee changes them; a manager can read them.
class TdsRulesScreen extends ConsumerWidget {
  const TdsRulesScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final user = ref.watch(currentUserProvider);
    final societyId = user?.societyId;
    if (societyId == null) return const Scaffold(body: Center(child: Text('No society context')));
    final committee = user!.isAdminOrCommittee;
    final async = ref.watch(tdsRulesProvider(societyId));
    return AppPage(
      title: 'TDS Rates & Limits',
      body: async.when(
        loading: () => const AppLoader(),
        error: (e, _) => ListView(children: [
          Padding(padding: const EdgeInsets.all(24), child: Text(friendlyErrorMessage(e), style: const TextStyle(color: AppTheme.error)))
        ]),
        data: (rules) => RefreshIndicator(
          onRefresh: () async => ref.invalidate(tdsRulesProvider(societyId)),
          child: ResponsiveBody(
            maxWidth: 860,
            child: ListView(padding: const EdgeInsets.fromLTRB(16, 16, 16, 96), children: [
              const Text(
                  'The rate deducted when a vendor is paid, by nature of payment and kind of vendor. These start from the '
                  'usual rates; have your chartered accountant confirm them. A vendor with no PAN is deducted at 20% '
                  'whatever the rate here.',
                  style: TextStyle(fontSize: 12.5, color: AppTheme.textSecondary, height: 1.35)),
              const SizedBox(height: 12),
              for (final r in rules)
                _RuleTile(
                  rule: r,
                  committee: committee,
                  onEdit: () async {
                    final saved = await showAppSheet<bool>(
                        context: context, builder: (_) => EditTdsRuleSheet(rule: r));
                    if (saved == true) ref.invalidate(tdsRulesProvider(societyId));
                  },
                ),
            ]),
          ),
        ),
      ),
    );
  }
}

String _limit(String? v) => v == null ? 'None' : formatInr(double.tryParse(v) ?? 0);

class _RuleTile extends StatelessWidget {
  final TdsRule rule;
  final bool committee;
  final VoidCallback onEdit;
  const _RuleTile({required this.rule, required this.committee, required this.onEdit});

  @override
  Widget build(BuildContext context) {
    final r = rule;
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: ListTile(
        onTap: committee ? onEdit : null,
        title: Text('${r.name} · ${r.rateText}%', style: const TextStyle(fontWeight: FontWeight.w600)),
        subtitle: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('${r.payeeLabel} · section ${r.section}'),
          Text('Nothing deducted under: ${_limit(r.yearlyLimit)} in the year · ${_limit(r.singleLimit)} in one payment',
              style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
          if (!r.active) ...[const SizedBox(height: 4), StatusPill('Not in use', AppTheme.warning)],
        ]),
        isThreeLine: true,
        trailing: committee ? const Icon(Icons.edit_outlined, size: 18) : null,
      ),
    );
  }
}

/// Change a rule's rate and limits. Pops true once saved.
class EditTdsRuleSheet extends ConsumerStatefulWidget {
  final TdsRule rule;
  const EditTdsRuleSheet({super.key, required this.rule});

  @override
  ConsumerState<EditTdsRuleSheet> createState() => _EditTdsRuleSheetState();
}

class _EditTdsRuleSheetState extends ConsumerState<EditTdsRuleSheet> {
  final _form = GlobalKey<FormState>();
  late final _rate = TextEditingController(text: widget.rule.rateText);
  late final _yearly = TextEditingController(text: _plain(widget.rule.yearlyLimit));
  late final _single = TextEditingController(text: _plain(widget.rule.singleLimit));
  late bool _active = widget.rule.active;
  bool _busy = false;

  static String _plain(String? v) {
    final d = double.tryParse(v ?? '');
    return d == null ? '' : (d == d.roundToDouble() ? d.toStringAsFixed(0) : d.toString());
  }

  @override
  void dispose() {
    _rate.dispose();
    _yearly.dispose();
    _single.dispose();
    super.dispose();
  }

  String? _money(String? v) => (v ?? '').trim().isEmpty ? null : (double.tryParse(v!.trim()) == null ? 'Enter an amount' : null);

  Future<void> _save() async {
    if (!_form.currentState!.validate()) return;
    setState(() => _busy = true);
    try {
      await ref.read(vendorMasterApiProvider).updateTdsRule(widget.rule.id,
          rate: _rate.text.trim(),
          yearlyLimit: _yearly.text.trim().isEmpty ? null : _yearly.text.trim(),
          singleLimit: _single.text.trim().isEmpty ? null : _single.text.trim(),
          active: _active);
      if (!mounted) return;
      AppToast.success(context, 'Rate saved');
      Navigator.of(context).pop(true);
    } catch (e) {
      if (mounted) {
        setState(() => _busy = false);
        showErrorToast(context, e);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    const decimal = TextInputType.numberWithOptions(decimal: true);
    final money = [FilteringTextInputFormatter.allow(RegExp(r'^\d{0,12}(\.\d{0,2})?'))];
    return AppSheetFrame(
      title: widget.rule.name,
      subtitle: '${widget.rule.payeeLabel} · section ${widget.rule.section}',
      child: Form(
        key: _form,
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          FormFieldBox(
            label: 'Rate (%)',
            required: true,
            child: TextFormField(
              controller: _rate,
              keyboardType: decimal,
              inputFormatters: [FilteringTextInputFormatter.allow(RegExp(r'^\d{0,3}(\.\d{0,4})?'))],
              decoration: const InputDecoration(suffixText: '%'),
              validator: (v) {
                final d = double.tryParse((v ?? '').trim());
                return d == null || d < 0 || d > 100 ? 'Enter a rate from 0 to 100' : null;
              },
            ),
          ),
          FormFieldBox(
            label: 'Nothing deducted until the year\'s total passes',
            child: TextFormField(
                controller: _yearly,
                keyboardType: decimal,
                inputFormatters: money,
                decoration: const InputDecoration(prefixText: '₹ ', hintText: 'No limit'),
                validator: _money),
          ),
          FormFieldBox(
            label: 'Nothing deducted on one payment under',
            child: TextFormField(
                controller: _single,
                keyboardType: decimal,
                inputFormatters: money,
                decoration: const InputDecoration(prefixText: '₹ ', hintText: 'No limit'),
                validator: _money),
          ),
          SwitchListTile(
            contentPadding: EdgeInsets.zero,
            value: _active,
            onChanged: (v) => setState(() => _active = v),
            title: const Text('In use'),
            subtitle: const Text('Turn off and this section deducts nothing for this kind of vendor'),
          ),
          const SizedBox(height: 8),
          FilledButton(onPressed: _busy ? null : _save, child: const Text('Save')),
        ]),
      ),
    );
  }
}
