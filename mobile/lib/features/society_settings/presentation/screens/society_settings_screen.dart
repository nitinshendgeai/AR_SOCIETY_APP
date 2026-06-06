import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/society_settings/data/models/society_settings_model.dart';
import 'package:ar_society_app/features/society_settings/presentation/providers/society_settings_providers.dart';

class SocietySettingsScreen extends ConsumerWidget {
  const SocietySettingsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final societyAsync = ref.watch(currentSocietyProvider);

    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(
        title: const Text('Society Settings'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh_rounded),
            onPressed: () =>
                ref.read(currentSocietyProvider.notifier).refresh(),
          ),
        ],
      ),
      body: societyAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.error_outline_rounded,
                  color: AppTheme.error, size: 40),
              const SizedBox(height: 12),
              Text(e.toString(),
                  textAlign: TextAlign.center,
                  style: const TextStyle(color: AppTheme.textSecondary)),
              const SizedBox(height: 16),
              ElevatedButton(
                onPressed: () =>
                    ref.read(currentSocietyProvider.notifier).refresh(),
                child: const Text('Retry'),
              ),
            ],
          ),
        ),
        data: (society) => DefaultTabController(
          length: 4,
          child: Column(
            children: [
              _SubscriptionBanner(society: society),
              const TabBar(
                isScrollable: true,
                labelColor: AppTheme.primary,
                unselectedLabelColor: AppTheme.textSecondary,
                indicatorColor: AppTheme.primary,
                tabAlignment: TabAlignment.start,
                tabs: [
                  Tab(text: 'General'),
                  Tab(text: 'Contact'),
                  Tab(text: 'Subscription'),
                  Tab(text: 'Security'),
                ],
              ),
              Expanded(
                child: TabBarView(
                  children: [
                    _GeneralTab(society: society),
                    _ContactTab(society: society),
                    _SubscriptionTab(society: society),
                    _SecurityTab(society: society),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// ── Subscription banner ───────────────────────────────────────────────────────

class _SubscriptionBanner extends StatelessWidget {
  final SocietySettingsModel society;
  const _SubscriptionBanner({required this.society});

  @override
  Widget build(BuildContext context) {
    if (!society.isTrial) return const SizedBox.shrink();
    final trialEnd = society.trialEndDate;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      color: AppTheme.warning.withOpacity(0.1),
      child: Row(
        children: [
          const Icon(Icons.access_time_rounded,
              color: AppTheme.warning, size: 16),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              'Trial account${trialEnd != null ? ' · Expires $trialEnd' : ''}',
              style: const TextStyle(
                  color: AppTheme.warning,
                  fontSize: 12,
                  fontWeight: FontWeight.w600),
            ),
          ),
        ],
      ),
    );
  }
}

// ── General Tab ───────────────────────────────────────────────────────────────

class _GeneralTab extends ConsumerStatefulWidget {
  final SocietySettingsModel society;
  const _GeneralTab({required this.society});

  @override
  ConsumerState<_GeneralTab> createState() => _GeneralTabState();
}

class _GeneralTabState extends ConsumerState<_GeneralTab>
    with AutomaticKeepAliveClientMixin {
  final _formKey = GlobalKey<FormState>();
  late TextEditingController _nameCtrl;
  late TextEditingController _addressCtrl;
  late TextEditingController _cityCtrl;
  late TextEditingController _stateCtrl;
  late TextEditingController _pincodeCtrl;
  late TextEditingController _countryCtrl;
  late TextEditingController _websiteCtrl;
  late TextEditingController _regNumberCtrl;
  late TextEditingController _gstCtrl;
  late TextEditingController _panCtrl;
  bool _saving = false;

  @override
  bool get wantKeepAlive => true;

  @override
  void initState() {
    super.initState();
    _nameCtrl      = TextEditingController(text: widget.society.name);
    _addressCtrl   = TextEditingController(text: widget.society.address ?? '');
    _cityCtrl      = TextEditingController(text: widget.society.city ?? '');
    _stateCtrl     = TextEditingController(text: widget.society.state ?? '');
    _pincodeCtrl   = TextEditingController(text: widget.society.pincode ?? '');
    _countryCtrl   = TextEditingController(
        text: widget.society.country ?? 'India');
    _websiteCtrl   = TextEditingController(text: widget.society.website ?? '');
    _regNumberCtrl = TextEditingController(
        text: widget.society.registrationNumber ?? '');
    _gstCtrl       = TextEditingController(text: widget.society.gstNumber ?? '');
    _panCtrl       = TextEditingController(text: widget.society.panNumber ?? '');
  }

  @override
  void dispose() {
    for (final c in [_nameCtrl, _addressCtrl, _cityCtrl, _stateCtrl,
        _pincodeCtrl, _countryCtrl, _websiteCtrl,
        _regNumberCtrl, _gstCtrl, _panCtrl]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _saving = true);
    try {
      await ref.read(currentSocietyProvider.notifier).updateSettings({
        'name':    _nameCtrl.text.trim(),
        'address': _addressCtrl.text.trim().isEmpty
            ? null
            : _addressCtrl.text.trim(),
        'city':    _cityCtrl.text.trim().isEmpty ? null : _cityCtrl.text.trim(),
        'state':   _stateCtrl.text.trim().isEmpty ? null : _stateCtrl.text.trim(),
        'pincode': _pincodeCtrl.text.trim().isEmpty
            ? null
            : _pincodeCtrl.text.trim(),
        'country': _countryCtrl.text.trim().isEmpty
            ? null
            : _countryCtrl.text.trim(),
        'website': _websiteCtrl.text.trim().isEmpty
            ? null
            : _websiteCtrl.text.trim(),
        'registration_number': _regNumberCtrl.text.trim().isEmpty
            ? null : _regNumberCtrl.text.trim(),
        'gst_number': _gstCtrl.text.trim().isEmpty
            ? null : _gstCtrl.text.trim(),
        'pan_number': _panCtrl.text.trim().isEmpty
            ? null : _panCtrl.text.trim(),
      });
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(const SnackBar(content: Text('Settings saved')));
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Error: $e'),
            backgroundColor: AppTheme.error,
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    super.build(context);
    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Form(
        key: _formKey,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            _SectionHeader('Society Profile'),
            _Field('Society Name', _nameCtrl,
                validator: (v) =>
                    v == null || v.trim().isEmpty ? 'Required' : null),
            _Field('Address', _addressCtrl),
            Row(
              children: [
                Expanded(child: _Field('City', _cityCtrl)),
                const SizedBox(width: 12),
                Expanded(child: _Field('State', _stateCtrl)),
              ],
            ),
            Row(
              children: [
                Expanded(child: _Field('Pincode', _pincodeCtrl)),
                const SizedBox(width: 12),
                Expanded(child: _Field('Country', _countryCtrl)),
              ],
            ),
            _Field('Website', _websiteCtrl,
                hint: 'https://example.com',
                keyboardType: TextInputType.url),
            const SizedBox(height: 16),
            _SectionHeader('Legal / Registration'),
            _Field('Registration Number', _regNumberCtrl,
                hint: 'e.g. MH-2024-001'),
            Row(children: [
              Expanded(
                child: _Field('GST Number', _gstCtrl,
                    hint: 'e.g. 27AAAAA0000A1Z5'),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: _Field('PAN Number', _panCtrl,
                    hint: 'e.g. AAAAA0000A'),
              ),
            ]),
            const SizedBox(height: 24),
            _SaveButton(saving: _saving, onSave: _save),
          ],
        ),
      ),
    );
  }
}

// ── Contact Tab ───────────────────────────────────────────────────────────────

class _ContactTab extends ConsumerStatefulWidget {
  final SocietySettingsModel society;
  const _ContactTab({required this.society});

  @override
  ConsumerState<_ContactTab> createState() => _ContactTabState();
}

class _ContactTabState extends ConsumerState<_ContactTab>
    with AutomaticKeepAliveClientMixin {
  final _formKey = GlobalKey<FormState>();
  late TextEditingController _emailCtrl;
  late TextEditingController _phoneCtrl;
  late TextEditingController _personCtrl;
  late TextEditingController _emgNameCtrl;
  late TextEditingController _emgPhoneCtrl;
  bool _saving = false;

  @override
  bool get wantKeepAlive => true;

  @override
  void initState() {
    super.initState();
    _emailCtrl   = TextEditingController(text: widget.society.contactEmail ?? '');
    _phoneCtrl   = TextEditingController(text: widget.society.contactPhone ?? '');
    _personCtrl  = TextEditingController(
        text: widget.society.contactPersonName ?? '');
    _emgNameCtrl = TextEditingController(
        text: widget.society.emergencyContactName ?? '');
    _emgPhoneCtrl = TextEditingController(
        text: widget.society.emergencyContactPhone ?? '');
  }

  @override
  void dispose() {
    for (final c in [
      _emailCtrl, _phoneCtrl, _personCtrl, _emgNameCtrl, _emgPhoneCtrl
    ]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _saving = true);
    try {
      await ref.read(currentSocietyProvider.notifier).updateSettings({
        'contact_email':           _emailCtrl.text.trim().isEmpty
            ? null : _emailCtrl.text.trim(),
        'contact_phone':           _phoneCtrl.text.trim().isEmpty
            ? null : _phoneCtrl.text.trim(),
        'contact_person_name':     _personCtrl.text.trim().isEmpty
            ? null : _personCtrl.text.trim(),
        'emergency_contact_name':  _emgNameCtrl.text.trim().isEmpty
            ? null : _emgNameCtrl.text.trim(),
        'emergency_contact_phone': _emgPhoneCtrl.text.trim().isEmpty
            ? null : _emgPhoneCtrl.text.trim(),
      });
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(const SnackBar(content: Text('Contact info saved')));
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text('Error: $e'),
          backgroundColor: AppTheme.error,
        ));
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    super.build(context);
    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Form(
        key: _formKey,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            _SectionHeader('Primary Contact'),
            _Field('Contact Email', _emailCtrl,
                keyboardType: TextInputType.emailAddress),
            _Field('Contact Phone', _phoneCtrl,
                keyboardType: TextInputType.phone),
            _Field('Contact Person Name', _personCtrl),
            const SizedBox(height: 8),
            _SectionHeader('Emergency Contact'),
            _Field('Emergency Contact Name', _emgNameCtrl),
            _Field('Emergency Contact Phone', _emgPhoneCtrl,
                keyboardType: TextInputType.phone),
            const SizedBox(height: 24),
            _SaveButton(saving: _saving, onSave: _save),
          ],
        ),
      ),
    );
  }
}

// ── Subscription Tab ──────────────────────────────────────────────────────────

class _SubscriptionTab extends StatelessWidget {
  final SocietySettingsModel society;
  const _SubscriptionTab({required this.society});

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _SectionHeader('Account Status'),
          _InfoTile(
            icon: Icons.business_rounded,
            label: 'Account Status',
            value: society.accountStatus ?? 'Unknown',
            valueColor: society.isTrial ? AppTheme.warning : AppTheme.success,
          ),
          const SizedBox(height: 8),
          if (society.isTrial) ...[
            _InfoTile(
              icon: Icons.access_time_rounded,
              label: 'Trial Ends',
              value: society.trialEndDate ?? '—',
            ),
            const SizedBox(height: 8),
          ],
          _InfoTile(
            icon: Icons.receipt_long_rounded,
            label: 'Subscription Plan',
            value: society.subscriptionPlan ?? 'Free Trial',
          ),
          const SizedBox(height: 8),
          _InfoTile(
            icon: Icons.people_rounded,
            label: 'Allowed Users',
            value: '${society.allowedUsers}',
          ),
          const SizedBox(height: 8),
          _InfoTile(
            icon: Icons.home_rounded,
            label: 'Allowed Flats',
            value: '${society.allowedFlats}',
          ),
          const SizedBox(height: 24),
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: AppTheme.primary.withOpacity(0.05),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(
                  color: AppTheme.primary.withOpacity(0.2)),
            ),
            child: const Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Upgrade Plan',
                    style: TextStyle(
                        fontWeight: FontWeight.w700,
                        fontSize: 15,
                        color: AppTheme.textPrimary)),
                SizedBox(height: 4),
                Text(
                  'Contact support to upgrade your subscription and unlock more users, flats, and features.',
                  style: TextStyle(
                      fontSize: 13, color: AppTheme.textSecondary),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

// ── Security Tab ──────────────────────────────────────────────────────────────

class _SecurityTab extends ConsumerStatefulWidget {
  final SocietySettingsModel society;
  const _SecurityTab({required this.society});

  @override
  ConsumerState<_SecurityTab> createState() => _SecurityTabState();
}

class _SecurityTabState extends ConsumerState<_SecurityTab>
    with AutomaticKeepAliveClientMixin {
  late bool _allowTenantPortal;
  late bool _requireVisitorApproval;
  late TextEditingController _maintenanceDayCtrl;
  late TextEditingController _lateFeeCtrl;
  bool _saving = false;

  @override
  bool get wantKeepAlive => true;

  @override
  void initState() {
    super.initState();
    _allowTenantPortal     = widget.society.allowTenantPortal;
    _requireVisitorApproval = widget.society.requireVisitorApproval;
    _maintenanceDayCtrl = TextEditingController(
        text: widget.society.maintenanceDay?.toString() ?? '');
    _lateFeeCtrl = TextEditingController(
        text: widget.society.lateFeePercent?.toString() ?? '');
  }

  @override
  void dispose() {
    _maintenanceDayCtrl.dispose();
    _lateFeeCtrl.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    setState(() => _saving = true);
    try {
      await ref.read(currentSocietyProvider.notifier).updateSettings({
        'allow_tenant_portal':      _allowTenantPortal,
        'require_visitor_approval': _requireVisitorApproval,
        'maintenance_day': _maintenanceDayCtrl.text.trim().isEmpty
            ? null
            : int.tryParse(_maintenanceDayCtrl.text.trim()),
        'late_fee_percent': _lateFeeCtrl.text.trim().isEmpty
            ? null
            : int.tryParse(_lateFeeCtrl.text.trim()),
      });
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(const SnackBar(content: Text('Settings saved')));
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text('Error: $e'),
          backgroundColor: AppTheme.error,
        ));
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    super.build(context);
    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _SectionHeader('Access Controls'),
          _SwitchTile(
            title: 'Tenant Portal',
            subtitle: 'Allow tenants to access the resident portal',
            value: _allowTenantPortal,
            onChanged: (v) => setState(() => _allowTenantPortal = v),
          ),
          const SizedBox(height: 8),
          _SwitchTile(
            title: 'Visitor Approval Required',
            subtitle: 'Require resident approval before visitor entry',
            value: _requireVisitorApproval,
            onChanged: (v) =>
                setState(() => _requireVisitorApproval = v),
          ),
          const SizedBox(height: 16),
          _SectionHeader('Billing Settings'),
          _Field('Maintenance Day (1–28)', _maintenanceDayCtrl,
              hint: 'e.g. 1',
              keyboardType: TextInputType.number),
          _Field('Late Fee %', _lateFeeCtrl,
              hint: 'e.g. 5',
              keyboardType: TextInputType.number),
          const SizedBox(height: 24),
          _SaveButton(saving: _saving, onSave: _save),
        ],
      ),
    );
  }
}

// ── Shared components ─────────────────────────────────────────────────────────

class _SectionHeader extends StatelessWidget {
  final String title;
  const _SectionHeader(this.title);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Text(title,
          style: const TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w600,
              color: AppTheme.textSecondary,
              letterSpacing: 0.3)),
    );
  }
}

class _Field extends StatelessWidget {
  final String label;
  final TextEditingController controller;
  final String? hint;
  final TextInputType? keyboardType;
  final String? Function(String?)? validator;

  const _Field(this.label, this.controller,
      {this.hint, this.keyboardType, this.validator});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label,
              style: const TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                  color: AppTheme.textPrimary)),
          const SizedBox(height: 4),
          TextFormField(
            controller: controller,
            keyboardType: keyboardType,
            validator: validator,
            decoration: InputDecoration(
              hintText: hint,
              hintStyle: const TextStyle(
                  color: AppTheme.textSecondary, fontSize: 13),
              contentPadding:
                  const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
              filled: true,
              fillColor: AppTheme.cardBg,
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(10),
                borderSide: const BorderSide(color: AppTheme.border),
              ),
              enabledBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(10),
                borderSide: const BorderSide(color: AppTheme.border),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _SwitchTile extends StatelessWidget {
  final String title;
  final String subtitle;
  final bool value;
  final ValueChanged<bool> onChanged;
  const _SwitchTile(
      {required this.title,
      required this.subtitle,
      required this.value,
      required this.onChanged});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: AppTheme.cardBg,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: AppTheme.border),
      ),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title,
                    style: const TextStyle(
                        fontWeight: FontWeight.w600,
                        fontSize: 13,
                        color: AppTheme.textPrimary)),
                const SizedBox(height: 2),
                Text(subtitle,
                    style: const TextStyle(
                        fontSize: 11, color: AppTheme.textSecondary)),
              ],
            ),
          ),
          Switch(
            value: value,
            activeColor: AppTheme.success,
            onChanged: onChanged,
          ),
        ],
      ),
    );
  }
}

class _InfoTile extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;
  final Color? valueColor;
  const _InfoTile(
      {required this.icon,
      required this.label,
      required this.value,
      this.valueColor});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppTheme.cardBg,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: AppTheme.border),
      ),
      child: Row(
        children: [
          Icon(icon, size: 18, color: AppTheme.textSecondary),
          const SizedBox(width: 12),
          Expanded(
            child: Text(label,
                style: const TextStyle(
                    fontSize: 13, color: AppTheme.textSecondary)),
          ),
          Text(value,
              style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                  color: valueColor ?? AppTheme.textPrimary)),
        ],
      ),
    );
  }
}

class _SaveButton extends StatelessWidget {
  final bool saving;
  final VoidCallback onSave;
  const _SaveButton({required this.saving, required this.onSave});

  @override
  Widget build(BuildContext context) {
    return ElevatedButton.icon(
      onPressed: saving ? null : onSave,
      icon: saving
          ? const SizedBox(
              width: 16,
              height: 16,
              child: CircularProgressIndicator(
                  strokeWidth: 2, color: Colors.white))
          : const Icon(Icons.save_rounded, size: 18),
      label: Text(saving ? 'Saving…' : 'Save Changes'),
    );
  }
}
