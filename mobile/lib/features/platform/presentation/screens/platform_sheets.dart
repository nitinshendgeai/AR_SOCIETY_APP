import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/widgets/billing_sheet_frame.dart';
import 'package:ar_society_app/features/platform/data/platform_api.dart';
import 'package:ar_society_app/features/platform/presentation/providers/platform_providers.dart';
import 'package:ar_society_app/features/vendor/presentation/widgets/procurement_widgets.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

Future<void> _run(BuildContext context, WidgetRef ref, void Function(bool) busy, Future<void> Function() action, String done) async {
  busy(true);
  try {
    await action();
    invalidatePlatform(ref);
    if (!context.mounted) return;
    AppToast.success(context, done);
    Navigator.of(context).pop(true);
  } catch (e) {
    if (context.mounted) {
      busy(false);
      showErrorToast(context, e);
    }
  }
}

// ── Extend a trial ───────────────────────────────────────────────────────────

class ExtendTrialSheet extends ConsumerStatefulWidget {
  final PlatformSociety society;
  const ExtendTrialSheet({super.key, required this.society});

  @override
  ConsumerState<ExtendTrialSheet> createState() => _ExtendTrialSheetState();
}

class _ExtendTrialSheetState extends ConsumerState<ExtendTrialSheet> {
  int _days = 15;
  bool _saving = false;

  @override
  Widget build(BuildContext context) {
    final s = widget.society;
    final base = (s.trialEnd != null && s.trialEnd!.isAfter(DateTime.now())) ? s.trialEnd! : DateTime.now();
    return BillingSheetFrame(
      title: 'Extend ${s.name}\'s trial',
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Text('Now: ${s.standing}', style: const TextStyle(color: AppTheme.textSecondary)),
        const SizedBox(height: 12),
        Wrap(spacing: 8, children: [
          for (final d in const [7, 15, 30, 60, 90])
            ChoiceChip(label: Text('$d days'), selected: _days == d, onSelected: (_) => setState(() => _days = d)),
        ]),
        const SizedBox(height: 10),
        Text('The trial will end on ${dayText(base.add(Duration(days: _days)))}.', style: const TextStyle(fontWeight: FontWeight.w600)),
        const SizedBox(height: 14),
        AppPrimaryButton(label: 'Extend', isLoading: _saving, onPressed: _saving ? null : () => _run(context, ref, (b) => setState(() => _saving = b), () => ref.read(platformApiProvider).extendTrial(s.id, _days), 'Trial extended')),
      ]),
    );
  }
}

// ── Put on a paid plan ───────────────────────────────────────────────────────

class ActivateSheet extends ConsumerStatefulWidget {
  final PlatformSociety society;
  const ActivateSheet({super.key, required this.society});

  @override
  ConsumerState<ActivateSheet> createState() => _ActivateSheetState();
}

class _ActivateSheetState extends ConsumerState<ActivateSheet> {
  String _plan = 'starter';
  DateTime? _until = DateTime.now().add(const Duration(days: 365));
  bool _saving = false;

  @override
  Widget build(BuildContext context) {
    final s = widget.society;
    return BillingSheetFrame(
      title: s.suspended ? 'Let ${s.name} back in' : 'Put ${s.name} on a paid plan',
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        if (s.suspended)
          const Padding(padding: EdgeInsets.only(bottom: 10), child: Text('Everyone in the society can sign in again straight away.', style: TextStyle(color: AppTheme.textSecondary))),
        Wrap(spacing: 8, children: [
          for (final p in kPlans) ChoiceChip(label: Text(p.$2), selected: _plan == p.$1, onSelected: (_) => setState(() => _plan = p.$1)),
        ]),
        const SizedBox(height: 12),
        DateField(label: 'Paid until (optional)', value: _until, onChanged: (v) => setState(() => _until = v)),
        const SizedBox(height: 14),
        AppPrimaryButton(label: 'Activate', isLoading: _saving, onPressed: _saving ? null : () => _run(context, ref, (b) => setState(() => _saving = b), () => ref.read(platformApiProvider).activate(s.id, _plan, _until), 'Activated')),
      ]),
    );
  }
}

// ── Suspend ──────────────────────────────────────────────────────────────────

class SuspendSheet extends ConsumerStatefulWidget {
  final PlatformSociety society;
  const SuspendSheet({super.key, required this.society});

  @override
  ConsumerState<SuspendSheet> createState() => _SuspendSheetState();
}

class _SuspendSheetState extends ConsumerState<SuspendSheet> {
  final _form = GlobalKey<FormState>();
  final _reason = TextEditingController();
  bool _saving = false;

  @override
  void dispose() {
    _reason.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final s = widget.society;
    return BillingSheetFrame(
      title: 'Suspend ${s.name}',
      child: Form(
        key: _form,
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(color: AppTheme.errorSoft, borderRadius: BorderRadius.circular(AppTheme.radiusM)),
            child: Text('Everyone in ${s.name} (${s.users} ${s.users == 1 ? 'person' : 'people'}) is signed out and cannot sign in or use the app until you let them back in. Their data is kept.',
                style: const TextStyle(height: 1.4)),
          ),
          const SizedBox(height: 12),
          TextFormField(
            controller: _reason,
            minLines: 2,
            maxLines: 4,
            decoration: const InputDecoration(labelText: 'Why *', alignLabelWithHint: true, hintText: 'e.g. Subscription unpaid since August'),
            validator: (v) => (v ?? '').trim().isEmpty ? 'Say why. It is kept in the record.' : null,
          ),
          const SizedBox(height: 14),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: AppTheme.error, padding: const EdgeInsets.symmetric(vertical: 14)),
            onPressed: _saving
                ? null
                : () {
                    if (!_form.currentState!.validate()) return;
                    _run(context, ref, (b) => setState(() => _saving = b), () => ref.read(platformApiProvider).suspend(s.id, _reason.text.trim()), 'Suspended');
                  },
            child: Text(_saving ? 'Suspending…' : 'Suspend'),
          ),
        ]),
      ),
    );
  }
}

// ── Limits ───────────────────────────────────────────────────────────────────

class LimitsSheet extends ConsumerStatefulWidget {
  final PlatformSociety society;
  const LimitsSheet({super.key, required this.society});

  @override
  ConsumerState<LimitsSheet> createState() => _LimitsSheetState();
}

class _LimitsSheetState extends ConsumerState<LimitsSheet> {
  final _form = GlobalKey<FormState>();
  late final _users = TextEditingController(text: '${widget.society.allowedUsers}');
  late final _flats = TextEditingController(text: '${widget.society.allowedFlats}');
  late final _storage = TextEditingController(text: '${widget.society.allowedStorageMb}');
  bool _saving = false;

  @override
  void dispose() {
    for (final c in [_users, _flats, _storage]) {
      c.dispose();
    }
    super.dispose();
  }

  Widget _field(TextEditingController c, String label, {int? atLeast}) => TextFormField(
        controller: c,
        keyboardType: TextInputType.number,
        inputFormatters: [FilteringTextInputFormatter.digitsOnly],
        decoration: InputDecoration(labelText: label, helperText: atLeast == null ? null : 'It has $atLeast now'),
        validator: (v) {
          final n = int.tryParse((v ?? '').trim()) ?? 0;
          if (n < 1) return 'At least 1';
          if (atLeast != null && n < atLeast) return 'Not below $atLeast';
          return null;
        },
      );

  @override
  Widget build(BuildContext context) {
    final s = widget.society;
    return BillingSheetFrame(
      title: 'Limits for ${s.name}',
      child: Form(
        key: _form,
        autovalidateMode: AutovalidateMode.onUserInteraction,
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          _field(_users, 'People who can have a login', atLeast: s.users),
          const SizedBox(height: 12),
          _field(_flats, 'Flats', atLeast: s.flats),
          const SizedBox(height: 12),
          _field(_storage, 'Storage (MB)'),
          const SizedBox(height: 8),
          const Text('These are recorded and shown against usage. The app does not stop a society going over them yet.', style: TextStyle(fontSize: 12, color: AppTheme.textSecondary, height: 1.35)),
          const SizedBox(height: 14),
          AppPrimaryButton(
            label: 'Save',
            isLoading: _saving,
            onPressed: _saving
                ? null
                : () {
                    if (!_form.currentState!.validate()) return;
                    _run(context, ref, (b) => setState(() => _saving = b),
                        () => ref.read(platformApiProvider).setLimits(s.id, int.parse(_users.text), int.parse(_flats.text), int.parse(_storage.text)), 'Limits saved');
                  },
          ),
        ]),
      ),
    );
  }
}
