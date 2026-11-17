import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/layout/app_sheet.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/staff/data/attendance_geo_api.dart';
import 'package:ar_society_app/features/staff/data/location_service.dart';
import 'package:ar_society_app/features/staff/domain/entities/attendance_geo.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart';
import 'package:ar_society_app/shared/widgets/app_widgets.dart';
import 'package:ar_society_app/shared/widgets/premium.dart';

const _modes = <(String, String, String)>[
  ('off', 'Off', 'Staff check in from anywhere, as before.'),
  ('flag', 'Flag', 'Everyone can check in. Anyone outside the spots, or without a usable location, is marked for the manager.'),
  ('block', 'Block', 'A check-in or check-out outside the spots is refused.'),
];

const _accuracyChoices = [10, 15, 20, 30, 50];

/// Where staff may check in and out from (the gate, the office...), and how strictly that is applied. Open it on the
/// phone while standing at the spot: "Add this spot here" reads the phone's location. Only the Admin and committee change
/// it; a manager can read it.
class AttendanceLocationScreen extends ConsumerStatefulWidget {
  const AttendanceLocationScreen({super.key});

  @override
  ConsumerState<AttendanceLocationScreen> createState() => _AttendanceLocationScreenState();
}

class _AttendanceLocationScreenState extends ConsumerState<AttendanceLocationScreen> {
  bool _busy = false;
  String? _distanceNote;

  Future<void> _run(Future<void> Function() action, String societyId, {String? done}) async {
    setState(() => _busy = true);
    try {
      await action();
      ref.invalidate(attendanceGeoConfigProvider(societyId));
      if (mounted && done != null) AppToast.success(context, done);
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  /// Read the phone here and say how far it is from each spot: a way to check a spot before relying on it.
  Future<void> _checkHere(GeoConfig cfg) async {
    setState(() {
      _busy = true;
      _distanceNote = null;
    });
    try {
      final r = await ref.read(locationServiceProvider).read(wantAccuracyM: cfg.maxAccuracyM.toDouble());
      if (cfg.spots.isEmpty) {
        _distanceNote = 'Location read (accurate to ${r.accuracyM?.round() ?? '?'} m). There is no spot yet.';
      } else {
        final near = [
          for (final s in cfg.spots) (s, distanceMetres(r.latitude, r.longitude, s.latitude, s.longitude))
        ]..sort((a, b) => a.$2.compareTo(b.$2));
        final (spot, d) = near.first;
        final inside = d <= spot.radiusM;
        _distanceNote = '${d.round()} m from ${spot.name} (allowed ${spot.radiusM} m): ${inside ? 'inside' : 'outside'}. '
            'Phone accuracy ±${r.accuracyM?.round() ?? '?'} m.';
      }
    } on LocationUnavailable catch (e) {
      _distanceNote = e.message;
    } catch (_) {
      _distanceNote = "Couldn't read the location.";
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final user = ref.watch(currentUserProvider);
    final societyId = user?.societyId;
    if (societyId == null) return const Scaffold(body: Center(child: Text('No society context')));
    final committee = user!.isAdminOrCommittee;
    final async = ref.watch(attendanceGeoConfigProvider(societyId));
    return AppPage(
      title: 'Attendance location',
      subtitle: 'Where staff may check in and out',
      body: async.when(
        loading: () => const AppLoader(),
        error: (e, _) => AppErrorState(
            message: friendlyErrorMessage(e), onRetry: () => ref.invalidate(attendanceGeoConfigProvider(societyId))),
        data: (cfg) => ResponsiveBody(
          maxWidth: 720,
          child: ListView(padding: const EdgeInsets.fromLTRB(16, 16, 16, 96), children: [
            const Text(
                "Staff check in and out only from the spots below. The phone's location is read at that moment only: it is "
                'never tracked in between. Phones are usually accurate to 3 to 10 m outdoors, and worse indoors.',
                style: TextStyle(fontSize: 12.5, color: AppTheme.textSecondary, height: 1.35)),
            const SizedBox(height: 14),
            const SectionHeading('How strictly'),
            const SizedBox(height: 8),
            SegmentedButton<String>(
              key: const Key('geo-mode'),
              segments: [for (final (v, label, _) in _modes) ButtonSegment(value: v, label: Text(label))],
              selected: {cfg.mode},
              onSelectionChanged: !committee || _busy
                  ? null
                  : (s) => _run(
                      () => ref.read(attendanceGeoApiProvider).saveSettings(societyId, mode: s.first, maxAccuracyM: cfg.maxAccuracyM),
                      societyId,
                      done: 'Saved'),
            ),
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: Text(_modes.firstWhere((m) => m.$1 == cfg.mode).$3,
                  style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary, height: 1.35)),
            ),
            const SizedBox(height: 12),
            Row(children: [
              const Expanded(
                  child: Text('Ignore location readings less accurate than',
                      style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600))),
              DropdownButton<int>(
                key: const Key('geo-accuracy'),
                value: _accuracyChoices.contains(cfg.maxAccuracyM) ? cfg.maxAccuracyM : null,
                items: [for (final m in _accuracyChoices) DropdownMenuItem(value: m, child: Text('$m m'))],
                onChanged: !committee || _busy
                    ? null
                    : (v) => _run(
                        () => ref.read(attendanceGeoApiProvider).saveSettings(societyId, mode: cfg.mode, maxAccuracyM: v!),
                        societyId,
                        done: 'Saved'),
              ),
            ]),
            const SizedBox(height: 18),
            Row(children: [
              const Expanded(child: SectionHeading('Spots')),
              if (committee)
                FilledButton.icon(
                  key: const Key('geo-add'),
                  onPressed: _busy
                      ? null
                      : () async {
                          final saved = await showAppSheet<bool>(
                              context: context, builder: (_) => _SpotSheet(societyId: societyId, maxAccuracyM: cfg.maxAccuracyM));
                          if (saved == true) ref.invalidate(attendanceGeoConfigProvider(societyId));
                        },
                  icon: const Icon(Icons.add_location_alt_rounded, size: 18),
                  label: const Text('Add spot here'),
                ),
            ]),
            const SizedBox(height: 8),
            if (cfg.spots.isEmpty)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 20),
                child: Text('No spot yet: staff can check in from anywhere. Stand at the gate and tap "Add spot here".',
                    textAlign: TextAlign.center, style: TextStyle(color: AppTheme.textSecondary)),
              ),
            for (final s in cfg.spots)
              Card(
                margin: const EdgeInsets.only(bottom: 8),
                child: ListTile(
                  key: Key('geo-spot-${s.name}'),
                  leading: const Icon(Icons.location_on_rounded, color: AppTheme.primary),
                  title: Text(s.name, style: const TextStyle(fontWeight: FontWeight.w600)),
                  subtitle: Text('${s.latitude.toStringAsFixed(6)}, ${s.longitude.toStringAsFixed(6)} · within ${s.radiusM} m'),
                  trailing: committee
                      ? Row(mainAxisSize: MainAxisSize.min, children: [
                          IconButton(
                              tooltip: 'Edit',
                              icon: const Icon(Icons.edit_outlined, size: 20),
                              onPressed: () async {
                                final saved = await showAppSheet<bool>(
                                    context: context,
                                    builder: (_) => _SpotSheet(societyId: societyId, maxAccuracyM: cfg.maxAccuracyM, spot: s));
                                if (saved == true) ref.invalidate(attendanceGeoConfigProvider(societyId));
                              }),
                          IconButton(
                              tooltip: 'Remove',
                              icon: const Icon(Icons.delete_outline_rounded, size: 20, color: AppTheme.error),
                              onPressed: () async {
                                final ok = await showDialog<bool>(
                                    context: context,
                                    builder: (c) => AlertDialog(
                                          title: Text('Remove ${s.name}?'),
                                          content: const Text('Staff can no longer check in from this spot.'),
                                          actions: [
                                            TextButton(onPressed: () => Navigator.pop(c, false), child: const Text('Keep')),
                                            FilledButton(onPressed: () => Navigator.pop(c, true), child: const Text('Remove')),
                                          ],
                                        ));
                                if (ok == true) {
                                  await _run(() => ref.read(attendanceGeoApiProvider).removeSpot(s.id), societyId, done: 'Removed');
                                }
                              }),
                        ])
                      : null,
                ),
              ),
            const SizedBox(height: 14),
            OutlinedButton.icon(
              key: const Key('geo-check-here'),
              onPressed: _busy ? null : () => _checkHere(cfg),
              icon: const Icon(Icons.my_location_rounded, size: 18),
              label: const Text('How far am I from the spots?'),
            ),
            if (_distanceNote != null)
              Padding(
                padding: const EdgeInsets.only(top: 8),
                child: Text(_distanceNote!, key: const Key('geo-note'), style: const TextStyle(fontSize: 13, height: 1.35)),
              ),
          ]),
        ),
      ),
    );
  }
}

/// Add a spot, or change one. "Use my location now" fills the coordinates from the phone; they can also be typed (for
/// instance copied from a map app). Pops true once saved.
class _SpotSheet extends ConsumerStatefulWidget {
  final String societyId;
  final int maxAccuracyM;
  final GeoSpot? spot;
  const _SpotSheet({required this.societyId, required this.maxAccuracyM, this.spot});

  @override
  ConsumerState<_SpotSheet> createState() => _SpotSheetState();
}

class _SpotSheetState extends ConsumerState<_SpotSheet> {
  final _form = GlobalKey<FormState>();
  late final _name = TextEditingController(text: widget.spot?.name ?? '');
  late final _lat = TextEditingController(text: widget.spot?.latitude.toString() ?? '');
  late final _lng = TextEditingController(text: widget.spot?.longitude.toString() ?? '');
  late final _radius = TextEditingController(text: (widget.spot?.radiusM ?? 10).toString());
  bool _busy = false;
  String? _readNote;

  @override
  void dispose() {
    _name.dispose();
    _lat.dispose();
    _lng.dispose();
    _radius.dispose();
    super.dispose();
  }

  Future<void> _useMyLocation() async {
    setState(() {
      _busy = true;
      _readNote = 'Reading your location…';
    });
    try {
      final r = await ref.read(locationServiceProvider).read(
            wantAccuracyM: 8,
            timeout: const Duration(seconds: 25),
            onAccuracy: (a) {
              if (mounted) setState(() => _readNote = 'Reading your location… accurate to ${a.round()} m');
            },
          );
      _lat.text = r.latitude.toStringAsFixed(6);
      _lng.text = r.longitude.toStringAsFixed(6);
      final acc = r.accuracyM?.round();
      _readNote = acc == null
          ? 'Location read.'
          : acc <= 10
              ? 'Location read, accurate to $acc m.'
              : 'Accurate only to $acc m. Go outdoors, away from buildings, and read again for a better spot.';
    } on LocationUnavailable catch (e) {
      _readNote = e.message;
    } catch (_) {
      _readNote = "Couldn't read the location.";
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _save() async {
    if (!_form.currentState!.validate()) return;
    setState(() => _busy = true);
    final api = ref.read(attendanceGeoApiProvider);
    final lat = double.parse(_lat.text.trim()), lng = double.parse(_lng.text.trim());
    final radius = int.parse(_radius.text.trim());
    try {
      if (widget.spot == null) {
        await api.addSpot(widget.societyId, name: _name.text.trim(), latitude: lat, longitude: lng, radiusM: radius);
      } else {
        await api.editSpot(widget.spot!.id, name: _name.text.trim(), latitude: lat, longitude: lng, radiusM: radius);
      }
      if (!mounted) return;
      AppToast.success(context, 'Spot saved');
      Navigator.of(context).pop(true);
    } catch (e) {
      if (mounted) {
        setState(() => _busy = false);
        showErrorToast(context, e);
      }
    }
  }

  String? _number(String? v, double min, double max, String what) {
    final d = double.tryParse((v ?? '').trim());
    return d == null || d < min || d > max ? 'Enter $what' : null;
  }

  @override
  Widget build(BuildContext context) {
    final signed = [FilteringTextInputFormatter.allow(RegExp(r'^-?\d{0,3}(\.\d{0,8})?'))];
    return AppSheetFrame(
      title: widget.spot == null ? 'Add a spot' : 'Edit ${widget.spot!.name}',
      subtitle: 'Stand where staff should check in, then read your location',
      child: Form(
        key: _form,
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          FormFieldBox(
            label: 'Name',
            required: true,
            child: TextFormField(
                key: const Key('geo-name'),
                controller: _name,
                decoration: const InputDecoration(hintText: 'Main gate'),
                validator: (v) => (v ?? '').trim().isEmpty ? 'Give the spot a name' : null),
          ),
          OutlinedButton.icon(
            key: const Key('geo-read'),
            onPressed: _busy ? null : _useMyLocation,
            icon: const Icon(Icons.my_location_rounded, size: 18),
            label: const Text('Use my location now'),
          ),
          if (_readNote != null)
            Padding(
              padding: const EdgeInsets.only(top: 6, bottom: 4),
              child: Text(_readNote!, style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary, height: 1.35)),
            ),
          const SizedBox(height: 8),
          Row(children: [
            Expanded(
              child: FormFieldBox(
                label: 'Latitude',
                required: true,
                child: TextFormField(
                    key: const Key('geo-lat'),
                    controller: _lat,
                    keyboardType: const TextInputType.numberWithOptions(decimal: true, signed: true),
                    inputFormatters: signed,
                    validator: (v) => _number(v, -90, 90, 'a latitude, -90 to 90')),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: FormFieldBox(
                label: 'Longitude',
                required: true,
                child: TextFormField(
                    key: const Key('geo-lng'),
                    controller: _lng,
                    keyboardType: const TextInputType.numberWithOptions(decimal: true, signed: true),
                    inputFormatters: signed,
                    validator: (v) => _number(v, -180, 180, 'a longitude, -180 to 180')),
              ),
            ),
          ]),
          FormFieldBox(
            label: 'Allowed distance from the spot (metres)',
            helper: '10 is usual. Phones are rarely better than 5 m, so very small values turn honest staff away.',
            required: true,
            child: TextFormField(
              key: const Key('geo-radius'),
              controller: _radius,
              keyboardType: TextInputType.number,
              inputFormatters: [FilteringTextInputFormatter.digitsOnly],
              decoration: const InputDecoration(suffixText: 'm'),
              validator: (v) {
                final d = int.tryParse((v ?? '').trim());
                return d == null || d < 5 || d > 200 ? 'Between 5 and 200 metres' : null;
              },
            ),
          ),
          const SizedBox(height: 8),
          FilledButton(key: const Key('geo-save'), onPressed: _busy ? null : _save, child: const Text('Save')),
        ]),
      ),
    );
  }
}
