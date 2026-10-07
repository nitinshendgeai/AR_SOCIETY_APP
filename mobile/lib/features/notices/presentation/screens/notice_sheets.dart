import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/maintenance_billing/presentation/widgets/billing_sheet_frame.dart';
import 'package:ar_society_app/features/notices/data/notices_api.dart';
import 'package:ar_society_app/features/notices/presentation/providers/notices_providers.dart';
import 'package:ar_society_app/features/society_structure/presentation/providers/structure_providers.dart';
import 'package:ar_society_app/features/vendor/presentation/widgets/procurement_widgets.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

String? _trimmed(TextEditingController c) => c.text.trim().isEmpty ? null : c.text.trim();

// ── Write or change a notice ─────────────────────────────────────────────────

/// A notice starts as a draft nobody else can see. Publish it when it reads right: it then appears on the
/// notice board of everyone in the audience, and can't be changed (archive it and write another).
class NoticeFormSheet extends ConsumerStatefulWidget {
  final NoticeItem? draft;
  const NoticeFormSheet({super.key, this.draft});

  @override
  ConsumerState<NoticeFormSheet> createState() => _NoticeFormSheetState();
}

class _NoticeFormSheetState extends ConsumerState<NoticeFormSheet> {
  final _form = GlobalKey<FormState>();
  late final _title = TextEditingController(text: d?.title);
  late final _content = TextEditingController(text: d?.content);
  late String _category = d?.category ?? 'general';
  late String _priority = d?.priority ?? 'normal';
  late String _audience = d?.audience ?? 'all';
  late Set<String> _wings = {...?d?.wingIds};
  late Set<String> _flats = {...?d?.flatIds};
  late DateTime? _expiry = d?.expiryDate?.toLocal();
  late bool _ack = d?.ackRequired ?? false;
  bool _saving = false;

  NoticeItem? get d => widget.draft;

  @override
  void dispose() {
    _title.dispose();
    _content.dispose();
    super.dispose();
  }

  Map<String, dynamic> _body() => {
        'title': _title.text.trim(),
        'content': _content.text.trim(),
        'category': _category,
        'priority': _priority,
        'audience_type': _audience,
        'target_wing_ids': _audience == 'specific_wings' ? _wings.toList() : null,
        'target_flat_ids': _audience == 'specific_flats' ? _flats.toList() : null,
        // End of the chosen day.
        'expiry_date': _expiry == null ? null : DateTime(_expiry!.year, _expiry!.month, _expiry!.day, 23, 59).toUtc().toIso8601String(),
        'acknowledgement_required': _ack,
      };

  Future<void> _save({required bool publish}) async {
    if (!_form.currentState!.validate()) return;
    if (_audience == 'specific_wings' && _wings.isEmpty) {
      AppToast.warning(context, 'Choose at least one wing');
      return;
    }
    if (_audience == 'specific_flats' && _flats.isEmpty) {
      AppToast.warning(context, 'Choose at least one flat');
      return;
    }
    setState(() => _saving = true);
    try {
      final api = ref.read(noticesApiProvider);
      var saved = d == null ? await api.create(_body()..removeWhere((_, v) => v == null)) : await api.update(d!.id, _body());
      if (publish) saved = await api.publish(saved.id);
      invalidateNotices(ref);
      if (!mounted) return;
      AppToast.success(context, publish ? 'Published to ${saved.totalAudience} ${saved.totalAudience == 1 ? 'person' : 'people'}' : 'Draft saved');
      Navigator.of(context).pop(saved);
    } catch (e) {
      if (mounted) {
        setState(() => _saving = false);
        showErrorToast(context, e);
      }
    }
  }

  Future<void> _pickFlats() async {
    final picked = await showDialog<Set<String>>(context: context, builder: (_) => _FlatPicker(initial: _flats));
    if (picked != null) setState(() => _flats = picked);
  }

  @override
  Widget build(BuildContext context) {
    final wings = ref.watch(wingsProvider).valueOrNull ?? const [];
    final hint = kAudiences.firstWhere((a) => a.$1 == _audience).$3;
    return BillingSheetFrame(
      title: d == null ? 'New notice' : 'Edit draft',
      child: Form(
        key: _form,
        autovalidateMode: AutovalidateMode.onUserInteraction,
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          TextFormField(
            controller: _title,
            maxLength: 255,
            textCapitalization: TextCapitalization.sentences,
            decoration: const InputDecoration(labelText: 'Title *', hintText: 'e.g. Water supply off on Sunday', counterText: ''),
            validator: (v) => (v ?? '').trim().isEmpty ? 'Give the notice a title' : null,
          ),
          const SizedBox(height: 12),
          TextFormField(
            controller: _content,
            minLines: 4,
            maxLines: 12,
            textCapitalization: TextCapitalization.sentences,
            decoration: const InputDecoration(labelText: 'Notice *', alignLabelWithHint: true),
            validator: (v) => (v ?? '').trim().isEmpty ? 'Write the notice' : null,
          ),
          const SizedBox(height: 12),
          DropdownButtonFormField<String>(
            initialValue: _category,
            isExpanded: true,
            decoration: const InputDecoration(labelText: 'About'),
            items: [
              for (final c in kNoticeCategories)
                DropdownMenuItem(value: c.$1, child: Row(children: [
                  Icon(c.$3, size: 18, color: AppTheme.textSecondary),
                  const SizedBox(width: 10),
                  Text(c.$2),
                ])),
            ],
            onChanged: (v) => setState(() => _category = v ?? 'general'),
          ),
          const SizedBox(height: 12),
          const Text('How important', style: TextStyle(fontSize: 12.5, color: AppTheme.textSecondary)),
          const SizedBox(height: 6),
          Wrap(spacing: 8, children: [
            for (final p in kNoticePriorities)
              ChoiceChip(
                label: Text(p.$2),
                selected: _priority == p.$1,
                selectedColor: noticePriorityColor(p.$1).withOpacity(0.18),
                onSelected: (_) => setState(() => _priority = p.$1),
              ),
          ]),
          const SizedBox(height: 14),
          DropdownButtonFormField<String>(
            initialValue: _audience,
            isExpanded: true,
            decoration: InputDecoration(labelText: 'Who is it for', helperText: hint, helperMaxLines: 2),
            items: [for (final a in kAudiences) DropdownMenuItem(value: a.$1, child: Text(a.$2))],
            onChanged: (v) => setState(() => _audience = v ?? 'all'),
          ),
          if (_audience == 'specific_wings') ...[
            const SizedBox(height: 10),
            Wrap(spacing: 8, runSpacing: 4, children: [
              for (final w in wings)
                FilterChip(
                  label: Text('Wing ${w.name}'),
                  selected: _wings.contains(w.id),
                  onSelected: (on) => setState(() => on ? _wings.add(w.id) : _wings.remove(w.id)),
                ),
              if (wings.isEmpty) const Text('No wings added yet', style: TextStyle(color: AppTheme.textSecondary)),
            ]),
          ],
          if (_audience == 'specific_flats') ...[
            const SizedBox(height: 10),
            OutlinedButton.icon(
              onPressed: _pickFlats,
              icon: const Icon(Icons.apartment_rounded, size: 18),
              label: Text(_flats.isEmpty ? 'Choose flats' : '${_flats.length} flat${_flats.length == 1 ? '' : 's'} chosen. Change'),
            ),
          ],
          const SizedBox(height: 12),
          DateField(
            label: 'Take it down after (optional)',
            value: _expiry,
            onChanged: (v) => setState(() => _expiry = v),
          ),
          SwitchListTile(
            contentPadding: EdgeInsets.zero,
            value: _ack,
            onChanged: (v) => setState(() => _ack = v),
            title: const Text('Ask people to confirm they have read it'),
            subtitle: const Text('Each person taps “I have read this”. You see who has and who has not.'),
          ),
          const SizedBox(height: 14),
          AppPrimaryButton(label: 'Publish now', isLoading: _saving, onPressed: _saving ? null : () => _save(publish: true)),
          const SizedBox(height: 8),
          OutlinedButton(onPressed: _saving ? null : () => _save(publish: false), child: const Text('Save as draft')),
        ]),
      ),
    );
  }
}

class _FlatPicker extends ConsumerStatefulWidget {
  final Set<String> initial;
  const _FlatPicker({required this.initial});

  @override
  ConsumerState<_FlatPicker> createState() => _FlatPickerState();
}

class _FlatPickerState extends ConsumerState<_FlatPicker> {
  late final Set<String> _chosen = {...widget.initial};
  String _q = '';

  @override
  Widget build(BuildContext context) {
    final flats = ref.watch(flatsBySocietyProvider);
    return AlertDialog(
      title: const Text('Choose flats'),
      content: SizedBox(
        width: 420,
        height: 420,
        child: flats.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, _) => Text(friendlyErrorMessage(e)),
          data: (all) {
            final shown = all.where((f) => '${f.wingName ?? ''} ${f.flatNumber}'.toLowerCase().contains(_q)).toList()
              ..sort((a, b) => '${a.wingName}${a.flatNumber}'.compareTo('${b.wingName}${b.flatNumber}'));
            return Column(children: [
              TextField(
                decoration: const InputDecoration(hintText: 'Search, e.g. A 101', prefixIcon: Icon(Icons.search_rounded)),
                onChanged: (v) => setState(() => _q = v.trim().toLowerCase()),
              ),
              const SizedBox(height: 8),
              Expanded(
                child: ListView(children: [
                  for (final f in shown)
                    CheckboxListTile(
                      dense: true,
                      value: _chosen.contains(f.id),
                      title: Text('${f.wingName ?? ''} / ${f.flatNumber}'),
                      onChanged: (on) => setState(() => on == true ? _chosen.add(f.id) : _chosen.remove(f.id)),
                    ),
                ]),
              ),
            ]);
          },
        ),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Cancel')),
        FilledButton(onPressed: () => Navigator.of(context).pop(_chosen), child: Text('Done (${_chosen.length})')),
      ],
    );
  }
}

// ── Raise an emergency alert ─────────────────────────────────────────────────

/// For a fire, a medical emergency, a gas leak: tell the whole society at once. The alert shows as a red bar on
/// every page until someone ends it.
class AlertSheet extends ConsumerStatefulWidget {
  const AlertSheet({super.key});

  @override
  ConsumerState<AlertSheet> createState() => _AlertSheetState();
}

class _AlertSheetState extends ConsumerState<AlertSheet> {
  final _form = GlobalKey<FormState>();
  final _title = TextEditingController();
  final _where = TextEditingController();
  final _what = TextEditingController();
  String _type = 'fire';
  bool _residents = true, _security = true, _committee = true;
  bool _sending = false;

  @override
  void dispose() {
    _title.dispose();
    _where.dispose();
    _what.dispose();
    super.dispose();
  }

  Future<void> _send() async {
    if (!_form.currentState!.validate()) return;
    setState(() => _sending = true);
    try {
      final a = await ref.read(noticesApiProvider).raiseAlert(
          type: _type, title: _title.text.trim(), description: _trimmed(_what), location: _trimmed(_where),
          residents: _residents, security: _security, committee: _committee);
      invalidateNotices(ref);
      if (!mounted) return;
      AppToast.success(context, 'Alert sent to ${a.reached ?? 0} people');
      Navigator.of(context).pop(true);
    } catch (e) {
      if (mounted) {
        setState(() => _sending = false);
        showErrorToast(context, e);
      }
    }
  }

  @override
  Widget build(BuildContext context) => BillingSheetFrame(
        title: 'Emergency alert',
        child: Form(
          key: _form,
          child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            const Text('Everyone chosen below sees a red bar at the top of the app until the alert is ended.',
                style: TextStyle(fontSize: 12.5, color: AppTheme.textSecondary, height: 1.35)),
            const SizedBox(height: 12),
            Wrap(spacing: 8, runSpacing: 8, children: [
              for (final t in kAlertTypes)
                ChoiceChip(
                  avatar: Icon(t.$3, size: 18, color: _type == t.$1 ? AppTheme.error : AppTheme.textSecondary),
                  label: Text(t.$2),
                  selected: _type == t.$1,
                  selectedColor: AppTheme.error.withOpacity(0.14),
                  onSelected: (_) => setState(() => _type = t.$1),
                ),
            ]),
            const SizedBox(height: 14),
            TextFormField(
              controller: _title,
              maxLength: 255,
              textCapitalization: TextCapitalization.sentences,
              decoration: const InputDecoration(labelText: 'What is happening *', hintText: 'e.g. Fire in Wing B basement', counterText: ''),
              validator: (v) => (v ?? '').trim().isEmpty ? 'Say what is happening' : null,
            ),
            const SizedBox(height: 12),
            TextFormField(controller: _where, maxLength: 255, decoration: const InputDecoration(labelText: 'Where', counterText: '')),
            const SizedBox(height: 12),
            TextFormField(
              controller: _what,
              minLines: 2,
              maxLines: 4,
              textCapitalization: TextCapitalization.sentences,
              decoration: const InputDecoration(labelText: 'What people should do', hintText: 'e.g. Leave by the stairs. Do not use the lift.'),
            ),
            const SizedBox(height: 8),
            SwitchListTile(contentPadding: EdgeInsets.zero, value: _residents, onChanged: (v) => setState(() => _residents = v), title: const Text('Residents and tenants')),
            SwitchListTile(contentPadding: EdgeInsets.zero, value: _security, onChanged: (v) => setState(() => _security = v), title: const Text('Security team')),
            SwitchListTile(contentPadding: EdgeInsets.zero, value: _committee, onChanged: (v) => setState(() => _committee = v), title: const Text('Committee')),
            const SizedBox(height: 10),
            FilledButton.icon(
              style: FilledButton.styleFrom(backgroundColor: AppTheme.error, padding: const EdgeInsets.symmetric(vertical: 14)),
              onPressed: _sending ? null : _send,
              icon: const Icon(Icons.warning_amber_rounded),
              label: Text(_sending ? 'Sending…' : 'Send alert'),
            ),
          ]),
        ),
      );
}
