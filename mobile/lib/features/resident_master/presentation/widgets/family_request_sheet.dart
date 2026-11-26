import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/l10n/app_locale.dart';
import 'package:ar_society_app/core/layout/app_sheet.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/resident_master/data/family_requests_api.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

/// A resident asks to add a member of the family. The request goes to the society office; the person is on the flat's
/// list (and can use the gym) only once the office approves.
Future<bool?> showFamilyRequestSheet(BuildContext context, {required String flatId}) {
  return showAppSheet<bool>(
    context: context,
    constraints: const BoxConstraints(maxWidth: 480),
    builder: (ctx) => _FamilyRequestSheet(flatId: flatId),
  );
}

class _FamilyRequestSheet extends ConsumerStatefulWidget {
  final String flatId;
  const _FamilyRequestSheet({required this.flatId});

  @override
  ConsumerState<_FamilyRequestSheet> createState() => _FamilyRequestSheetState();
}

class _FamilyRequestSheetState extends ConsumerState<_FamilyRequestSheet> {
  final _formKey = GlobalKey<FormState>();
  final _name = TextEditingController();
  final _phone = TextEditingController();
  String _type = 'family';
  DateTime? _dob;
  bool _busy = false;
  String? _error;

  @override
  void dispose() {
    _name.dispose();
    _phone.dispose();
    super.dispose();
  }

  Future<void> _pickDob() async {
    final now = DateTime.now();
    final d = await showDatePicker(
      context: context,
      initialDate: _dob ?? DateTime(now.year - 20),
      firstDate: DateTime(now.year - 110),
      lastDate: now,
    );
    if (d != null) setState(() => _dob = d);
  }

  Future<void> _send() async {
    if (_busy || !_formKey.currentState!.validate()) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await ref.read(familyRequestsApiProvider).create(
            fullName: _name.text.trim(),
            residentType: _type,
            phone: _phone.text.trim(),
            dateOfBirth: _dob,
            flatId: widget.flatId,
          );
      ref.invalidate(myFamilyRequestsProvider);
      if (!mounted) return;
      Navigator.of(context).pop(true);
      AppToast.success(context, 'Sent to the society office. They will be added once it is approved.');
    } catch (e) {
      if (mounted) {
        setState(() {
          _busy = false;
          _error = friendlyErrorMessage(e);
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return AppSheetFrame(
      title: 'Add a family member',
      subtitle: 'The society office will check and approve. Until then they will not be on the list.',
      child: Form(
        key: _formKey,
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          FormFieldBox(
            label: 'Full name',
            required: true,
            child: TextFormField(
              key: const Key('family-name'),
              controller: _name,
              textCapitalization: TextCapitalization.words,
              decoration: const InputDecoration(),
              validator: (v) => (v == null || v.trim().length < 2) ? 'Enter the full name' : null,
            ),
          ),
          const SizedBox(height: 14),
          SegmentedButton<String>(
            key: const Key('family-type'),
            segments: [
              ButtonSegment(value: 'family', label: Text(context.tr('Family'))),
              ButtonSegment(value: 'dependent', label: Text(context.tr('Dependent'))),
            ],
            selected: {_type},
            onSelectionChanged: (s) => setState(() => _type = s.first),
          ),
          const SizedBox(height: 14),
          FormFieldBox(
            label: 'Mobile (optional)',
            child: TextFormField(
              key: const Key('family-phone'),
              controller: _phone,
              keyboardType: TextInputType.phone,
              decoration: const InputDecoration(),
            ),
          ),
          const SizedBox(height: 14),
          OutlinedButton.icon(
            key: const Key('family-dob'),
            onPressed: _pickDob,
            icon: const Icon(Icons.cake_outlined, size: 18),
            label: Text(_dob == null ? context.tr('Date of birth (optional)') : DateFormat('d MMM yyyy').format(_dob!)),
          ),
          if (_error != null) ...[
            const SizedBox(height: 12),
            Text(_error!, key: const Key('family-error'), style: TextStyle(color: AppTheme.error, fontSize: 13)),
          ],
          const SizedBox(height: 18),
          AppPrimaryButton(label: 'Send for approval', isLoading: _busy, onPressed: _send),
        ]),
      ),
    );
  }
}
