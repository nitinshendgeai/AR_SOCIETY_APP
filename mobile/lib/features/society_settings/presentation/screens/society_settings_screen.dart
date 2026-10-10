import 'package:flutter/material.dart';
import 'package:ar_society_app/core/layout/app_shell.dart' show kDesktopBreakpoint;
import 'package:ar_society_app/shared/widgets/app_form.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/society_settings/data/models/society_settings_model.dart';
import 'package:ar_society_app/features/society_settings/presentation/providers/society_settings_providers.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

class SocietySettingsScreen extends ConsumerWidget {
  const SocietySettingsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final societyAsync = ref.watch(currentSocietyProvider);
    final desktop = MediaQuery.sizeOf(context).width >= kDesktopBreakpoint;
    final gutter = desktop ? 32.0 : 0.0;
    final refresh = IconButton(
      tooltip: 'Refresh',
      icon: const Icon(Icons.refresh_rounded),
      onPressed: () => ref.read(currentSocietyProvider.notifier).refresh(),
    );

    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: desktop ? null : AppBar(title: const Text('Society Settings'), actions: [refresh]),
      body: societyAsync.when(
        loading: () => const AppLoader(),
        error: (e, _) => Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.error_outline_rounded, color: AppTheme.error, size: 40),
              const SizedBox(height: 12),
              Text(friendlyErrorMessage(e),
                  textAlign: TextAlign.center, style: const TextStyle(color: AppTheme.textSecondary)),
              const SizedBox(height: 16),
              ElevatedButton(
                onPressed: () => ref.read(currentSocietyProvider.notifier).refresh(),
                child: const Text('Retry'),
              ),
            ],
          ),
        ),
        data: (society) => DefaultTabController(
          length: 4,
          child: Column(
            children: [
              if (desktop)
                Padding(
                  padding: EdgeInsets.fromLTRB(gutter, 24, gutter, 8),
                  child: Align(
                    alignment: Alignment.topCenter,
                    child: ConstrainedBox(
                      constraints: const BoxConstraints(maxWidth: 1080),
                      child: AppPageHeader(
                        title: 'Society Settings',
                        subtitle: 'Profile, contacts, subscription and security',
                        actions: [refresh],
                      ),
                    ),
                  ),
                ),
              _SubscriptionBanner(society: society),
              Align(
                alignment: Alignment.topCenter,
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 1080),
                  child: const TabBar(
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
                ),
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
            content: Text(friendlyErrorMessage(e)),
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
    return Form(
      key: _formKey,
      child: SettingsColumn(
        save: _SaveButton(saving: _saving, onSave: _save),
        children: [
          FormSection(
            title: 'Society profile',
            description: 'Printed on bills, receipts and certificates.',
            children: [
              FormFieldBox(
                label: 'Society name',
                required: true,
                child: TextFormField(controller: _nameCtrl, validator: (v) => v == null || v.trim().isEmpty ? 'Required' : null),
              ),
              FormFieldBox(label: 'Website', child: TextFormField(controller: _websiteCtrl, keyboardType: TextInputType.url, decoration: const InputDecoration(hintText: 'https://example.com'))),
              FormFull(child: FormFieldBox(label: 'Address', child: TextFormField(controller: _addressCtrl))),
              FormFieldBox(label: 'City', child: TextFormField(controller: _cityCtrl)),
              FormFieldBox(label: 'State', child: TextFormField(controller: _stateCtrl)),
              FormFieldBox(
                label: 'Pincode',
                child: TextFormField(
                  controller: _pincodeCtrl,
                  keyboardType: TextInputType.number,
                  validator: (v) {
                    final t = (v ?? '').replaceAll(' ', '');
                    return t.isEmpty || RegExp(r'^[0-9]{6}$').hasMatch(t) ? null : 'Pincode must be 6 digits';
                  },
                ),
              ),
              FormFieldBox(label: 'Country', child: TextFormField(controller: _countryCtrl)),
            ],
          ),
          FormSection(
            title: 'Legal and registration',
            description: 'Registration and tax numbers, used on bills and statutory reports.',
            children: [
              FormFieldBox(
                label: 'Registration number',
                child: TextFormField(controller: _regNumberCtrl, decoration: const InputDecoration(hintText: 'e.g. MH-2024-001')),
              ),
              const SizedBox.shrink(),
              FormFieldBox(
                label: 'GST number',
                child: TextFormField(
                  controller: _gstCtrl,
                  decoration: const InputDecoration(hintText: 'e.g. 27AAAAA0000A1Z5'),
                  validator: (v) {
                    final t = (v ?? '').replaceAll(' ', '').toUpperCase();
                    return t.isEmpty || RegExp(r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$').hasMatch(t)
                        ? null
                        : 'GSTIN is 15 characters, like 27AAAAA0000A1Z5';
                  },
                ),
              ),
              FormFieldBox(
                label: 'PAN number',
                child: TextFormField(
                  controller: _panCtrl,
                  decoration: const InputDecoration(hintText: 'e.g. AAAAA0000A'),
                  validator: (v) {
                    final t = (v ?? '').replaceAll(' ', '').toUpperCase();
                    return t.isEmpty || RegExp(r'^[A-Z]{5}[0-9]{4}[A-Z]$').hasMatch(t) ? null : 'PAN looks like ABCDE1234F';
                  },
                ),
              ),
            ],
          ),
        ],
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
          content: Text(friendlyErrorMessage(e)),
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
    return Form(
      key: _formKey,
      child: SettingsColumn(
        save: _SaveButton(saving: _saving, onSave: _save),
        children: [
          FormSection(
            title: 'Primary contact',
            description: 'Who the society office can be reached through.',
            children: [
              FormFieldBox(label: 'Contact email', child: TextFormField(controller: _emailCtrl, keyboardType: TextInputType.emailAddress)),
              FormFieldBox(label: 'Contact phone', child: TextFormField(controller: _phoneCtrl, keyboardType: TextInputType.phone)),
              FormFieldBox(label: 'Contact person', child: TextFormField(controller: _personCtrl)),
            ],
          ),
          FormSection(
            title: 'Emergency contact',
            description: 'Called when something urgent happens in the society.',
            children: [
              FormFieldBox(label: 'Name', child: TextFormField(controller: _emgNameCtrl)),
              FormFieldBox(label: 'Phone', child: TextFormField(controller: _emgPhoneCtrl, keyboardType: TextInputType.phone)),
            ],
          ),
        ],
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
    return SettingsColumn(
      children: [
        FormSection(
          title: 'Account and plan',
          description: 'Your subscription and what it allows.',
          columns: 1,
          children: [
            _InfoTile(
              icon: Icons.business_rounded,
              label: 'Account status',
              value: society.accountStatus ?? 'Unknown',
              valueColor: society.isTrial ? AppTheme.warning : AppTheme.success,
            ),
            if (society.isTrial) _InfoTile(icon: Icons.access_time_rounded, label: 'Trial ends', value: society.trialEndDate ?? '—'),
            _InfoTile(icon: Icons.receipt_long_rounded, label: 'Subscription plan', value: society.subscriptionPlan ?? 'Free Trial'),
            _InfoTile(icon: Icons.people_rounded, label: 'Allowed users', value: '${society.allowedUsers}'),
            _InfoTile(icon: Icons.home_rounded, label: 'Allowed flats', value: '${society.allowedFlats}'),
          ],
        ),
        DecoratedBox(
          decoration: BoxDecoration(
            color: AppTheme.primarySoft.withOpacity(0.6),
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: AppTheme.primary.withOpacity(0.2)),
          ),
          child: const Padding(
            padding: EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Upgrade plan', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 15, color: AppTheme.textPrimary)),
                SizedBox(height: 4),
                Text('Contact support to upgrade your subscription and unlock more users, flats and features.',
                    style: TextStyle(fontSize: 13, color: AppTheme.textSecondary)),
              ],
            ),
          ),
        ),
      ],
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
  final _settingsFormKey = GlobalKey<FormState>();
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
    if (!(_settingsFormKey.currentState?.validate() ?? true)) return;
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
          content: Text(friendlyErrorMessage(e)),
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
    return Form(
      key: _settingsFormKey,
      child: SettingsColumn(
        save: _SaveButton(saving: _saving, onSave: _save),
        children: [
          FormSection(
            title: 'Access controls',
            description: 'Who can use the app, and what needs approval.',
            columns: 1,
            children: [
              FormSwitchTile(
                title: 'Tenant portal',
                subtitle: 'Allow tenants to use the resident portal',
                value: _allowTenantPortal,
                onChanged: (v) => setState(() => _allowTenantPortal = v),
              ),
              FormSwitchTile(
                title: 'Visitor approval required',
                subtitle: 'Require resident approval before a visitor is let in',
                value: _requireVisitorApproval,
                onChanged: (v) => setState(() => _requireVisitorApproval = v),
              ),
            ],
          ),
          FormSection(
            title: 'Billing settings',
            description: 'Defaults used when maintenance bills are made.',
            children: [
              FormFieldBox(
                label: 'Maintenance day (1–28)',
                child: TextFormField(
                  controller: _maintenanceDayCtrl,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(hintText: 'e.g. 1'),
                  validator: (v) {
                    final t = (v ?? '').trim();
                    if (t.isEmpty) return null;
                    final n = int.tryParse(t);
                    return n == null || n < 1 || n > 28 ? 'Enter a day from 1 to 28' : null;
                  },
                ),
              ),
              FormFieldBox(
                label: 'Late fee %',
                child: TextFormField(
                  controller: _lateFeeCtrl,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(hintText: 'e.g. 5'),
                  validator: (v) {
                    final t = (v ?? '').trim();
                    if (t.isEmpty) return null;
                    final n = int.tryParse(t);
                    return n == null || n < 0 || n > 100 ? 'Enter a percentage from 0 to 100' : null;
                  },
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

// ── Shared components ─────────────────────────────────────────────────────────




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
  Widget build(BuildContext context) => AppPrimaryButton(
        label: 'Save Changes',
        icon: Icons.save_rounded,
        isLoading: saving,
        expand: MediaQuery.sizeOf(context).width < kDesktopBreakpoint,
        onPressed: saving ? null : onSave,
      );
}
