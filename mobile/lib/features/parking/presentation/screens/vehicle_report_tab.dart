import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import 'package:share_plus/share_plus.dart';
import 'package:ar_society_app/core/api/api_client.dart';
import 'package:ar_society_app/core/layout/app_sheet.dart';
import 'package:ar_society_app/core/motion/loading.dart';
import 'package:ar_society_app/core/theme/app_theme.dart';
import 'package:ar_society_app/core/utils/server_time.dart';
import 'package:ar_society_app/features/accounts/data/accounts_api.dart' show formatInr;
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/parking/data/vehicle_report_api.dart';
import 'package:ar_society_app/features/parking/presentation/providers/parking_providers.dart' show parkingVehiclesProvider;
import 'package:ar_society_app/features/society_structure/data/models/structure_models.dart' show FlatModel;
import 'package:ar_society_app/features/society_structure/presentation/providers/structure_providers.dart';
import 'package:ar_society_app/shared/utils/file_saver.dart';
import 'package:ar_society_app/shared/widgets/confirm_remove.dart';
import 'package:ar_society_app/shared/widgets/app_form.dart' show AppSheetFrame;
import 'package:ar_society_app/shared/widgets/app_widgets.dart';

const _xlsxMime = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';

String _monthKey(DateTime d) => '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}';
String _monthTitle(String month) {
  final p = month.split('-');
  return DateFormat('MMMM yyyy').format(DateTime(int.parse(p[0]), int.parse(p[1])));
}

String _stamp(Object? iso) {
  final d = parseStampOrNull(iso);
  return d == null ? '-' : DateFormat('d MMM, h:mm a').format(d);
}

String _day(Object? iso) {
  final d = DateTime.tryParse('$iso');
  return d == null ? '-' : DateFormat('d MMM yyyy').format(d);
}

String _minutes(int? m) => m == null ? '-' : (m >= 60 ? '${m ~/ 60}h ${(m % 60).toString().padLeft(2, '0')}m' : '$m min');

/// The vehicle report on the Parking screen: registered vehicles, parking, the month's violations and fines, and the month's
/// gate movements. Narrow it to a wing or a flat; print it or download it as a PDF or an Excel file.
class VehicleReportTab extends ConsumerStatefulWidget {
  final String societyId;
  const VehicleReportTab({super.key, required this.societyId});

  @override
  ConsumerState<VehicleReportTab> createState() => _VehicleReportTabState();
}

class _VehicleReportTabState extends ConsumerState<VehicleReportTab> {
  String? _month; // null: the current month, as the server counts it
  String? _wingId, _flatId;
  int _section = 0; // vehicles | parking | violations | gate
  bool _selecting = false; // choosing several vehicles to deregister together
  final Set<String> _selected = {};
  bool _busy = false;

  static const _sections = ['Vehicles', 'Parking', 'Violations', 'Gate'];

  VehicleReportKey get _key => (societyId: widget.societyId, month: _month, wingId: _wingId, flatId: _flatId);

  void _step(String shown, int by) {
    final p = shown.split('-');
    setState(() => _month = _monthKey(DateTime(int.parse(p[0]), int.parse(p[1]) + by)));
  }

  /// Deregister [ids] after asking: they leave the active lists, their RFID tags are cleared and their parking is
  /// freed; the records are kept.
  Future<void> _deregister(List<String> ids) async {
    final many = ids.length > 1;
    final ok = await confirmRemove(
      context,
      title: many ? 'Deregister ${ids.length} vehicles?' : 'Deregister this vehicle?',
      message: '${many ? 'They stop' : 'It stops'} showing as active and ${many ? 'their' : 'its'} RFID '
          '${many ? 'tags are' : 'tag is'} cleared and ${many ? 'their' : 'its'} parking is freed. The records are kept.',
      action: 'Deregister',
    );
    if (!ok || !mounted) return;
    setState(() => _busy = true);
    try {
      final r = await ref.read(vehicleReportApiProvider).deregister(ids);
      ref.invalidate(vehicleReportProvider);
      ref.invalidate(parkingVehiclesProvider);
      if (!mounted) return;
      setState(() {
        _selected.clear();
        _selecting = false;
      });
      AppToast.success(context, '${r.deregistered} vehicle${r.deregistered == 1 ? '' : 's'} deregistered');
    } catch (e) {
      if (mounted) showErrorToast(context, e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _download() => showAppSheet<void>(
        context: context,
        builder: (_) => _DownloadSheet(
          load: (format) => ref
              .read(vehicleReportApiProvider)
              .file(widget.societyId, format, month: _month, wingId: _wingId, flatId: _flatId),
        ),
      );

  @override
  Widget build(BuildContext context) {
    final async = ref.watch(vehicleReportProvider(_key));
    final shown = async.valueOrNull?.month ?? _month ?? _monthKey(DateTime.now());
    return RefreshIndicator(
      onRefresh: () async => ref.invalidate(vehicleReportProvider(_key)),
      child: ListView(padding: const EdgeInsets.fromLTRB(16, 12, 16, 48), children: [
        _filters(),
        const SizedBox(height: 4),
        Align(
          alignment: Alignment.centerRight,
          child: OutlinedButton.icon(
            key: const Key('vehicle-report-download'),
            onPressed: _download,
            icon: const Icon(Icons.file_download_outlined, size: 18),
            label: const Text('Print or download'),
          ),
        ),
        const SizedBox(height: 8),
        Wrap(spacing: 8, runSpacing: 8, children: [
          for (final (i, label) in _sections.indexed)
            AppFilterPill(
                key: Key('vr-section-$i'), label: label, selected: _section == i, onTap: () => setState(() => _section = i)),
        ]),
        if (_section >= 2) _monthBar(shown) else const SizedBox(height: 8),
        if (_section < 2)
          Padding(
            padding: EdgeInsets.only(bottom: 8),
            child: Text('As on today', style: TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
          ),
        ...async.when(
          loading: () => [const Padding(padding: EdgeInsets.all(32), child: AppLoader())],
          error: (e, _) => [
            AppErrorState(compact: true, message: friendlyErrorMessage(e), onRetry: () => ref.invalidate(vehicleReportProvider(_key)))
          ],
          data: (r) => switch (_section) {
            0 => _vehicles(r),
            1 => _parking(r),
            2 => _violations(r),
            _ => _gate(r),
          },
        ),
      ]),
    );
  }

  // ── Filters ──

  Widget _filters() {
    final wings = (ref.watch(wingsProvider).valueOrNull ?? const []).where((w) => w.isActive).toList();
    final List<FlatModel> flats = _wingId == null
        ? const <FlatModel>[]
        : (ref.watch(flatsByWingProvider(_wingId!)).valueOrNull ?? const <FlatModel>[]).where((f) => f.isActive).toList();
    return Column(children: [
      Row(children: [
        Expanded(
          child: DropdownButtonFormField<String?>(
            key: const Key('vr-wing'),
            value: wings.any((w) => w.id == _wingId) ? _wingId : null,
            isExpanded: true,
            decoration: const InputDecoration(labelText: 'Wing'),
            items: [
              const DropdownMenuItem<String?>(value: null, child: Text('All wings')),
              for (final w in wings) DropdownMenuItem<String?>(value: w.id, child: Text(w.name, overflow: TextOverflow.ellipsis)),
            ],
            onChanged: (v) => setState(() {
              _wingId = v;
              _flatId = null;
            }),
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: DropdownButtonFormField<String?>(
            key: const Key('vr-flat'),
            value: flats.any((f) => f.id == _flatId) ? _flatId : null,
            isExpanded: true,
            decoration: const InputDecoration(labelText: 'Flat'),
            items: [
              const DropdownMenuItem<String?>(value: null, child: Text('All flats')),
              for (final f in flats) DropdownMenuItem<String?>(value: f.id, child: Text('Flat ${f.flatNumber}')),
            ],
            onChanged: _wingId == null ? null : (v) => setState(() => _flatId = v),
          ),
        ),
      ]),
      if (_wingId != null)
        Align(
          alignment: Alignment.centerRight,
          child: TextButton(
            key: const Key('vr-clear'),
            onPressed: () => setState(() {
              _wingId = null;
              _flatId = null;
            }),
            child: const Text('Clear filters'),
          ),
        ),
    ]);
  }

  Widget _monthBar(String shown) => Row(children: [
        IconButton(key: const Key('vr-prev'), onPressed: () => _step(shown, -1), icon: const Icon(Icons.chevron_left_rounded)),
        Expanded(
            child: Text(_monthTitle(shown),
                textAlign: TextAlign.center, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w800))),
        IconButton(
            key: const Key('vr-next'),
            onPressed: shown.compareTo(_monthKey(DateTime.now())) >= 0 ? null : () => _step(shown, 1),
            icon: const Icon(Icons.chevron_right_rounded)),
      ]);

  // ── Pieces ──

  Widget _tiles(List<(String, Object?, Color)> tiles) => Padding(
        padding: const EdgeInsets.only(bottom: 12),
        child: Row(children: [
          for (final (i, (label, value, color)) in tiles.indexed) ...[
            if (i > 0) const SizedBox(width: 8),
            Expanded(
              child: Container(
                padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 6),
                decoration: BoxDecoration(
                  color: color.withOpacity(0.08),
                  borderRadius: BorderRadius.circular(AppTheme.radiusM),
                  border: Border.all(color: color.withOpacity(0.3)),
                ),
                child: Column(children: [
                  FittedBox(
                      child: Text('$value', style: TextStyle(fontSize: 20, fontWeight: FontWeight.w800, color: color))),
                  const SizedBox(height: 2),
                  Text(label, textAlign: TextAlign.center, style: TextStyle(fontSize: 11.5, color: AppTheme.textSecondary)),
                ]),
              ),
            ),
          ],
        ]),
      );

  Widget _heading(String text) => Padding(
        padding: const EdgeInsets.only(top: 12, bottom: 8),
        child: Text(text, style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: AppTheme.textSecondary)),
      );

  Widget _line(String text, {Color? color}) => Padding(
        padding: const EdgeInsets.only(bottom: 4),
        child: Text(text, style: TextStyle(fontSize: 13, color: color ?? AppTheme.textSecondary)),
      );

  Widget _more(int shown, int total) => shown >= total
      ? const SizedBox.shrink()
      : Padding(
          padding: const EdgeInsets.only(top: 4, bottom: 8),
          child: Text('Showing the first $shown of $total. "Print or download" has them all.',
              style: TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
        );

  Widget _empty(String text) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 16),
        child: Text(text, style: TextStyle(color: AppTheme.textSecondary)),
      );

  String _counted(Object? by) => ((by as Map?) ?? const {}).entries.map((e) => '${e.key} ${e.value}').join(' · ');

  // ── Vehicles ──

  /// "Select" to tick several vehicles and deregister them together (a sheet imported wrongly); only committee and admin.
  Widget _selectBar(List<Map<String, dynamic>> rows) {
    final ids = [for (final v in rows) if (v['id'] != null) '${v['id']}'];
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Wrap(spacing: 8, runSpacing: 4, crossAxisAlignment: WrapCrossAlignment.center, children: [
        TextButton.icon(
          key: const Key('vr-select'),
          onPressed: () => setState(() {
            _selecting = !_selecting;
            _selected.clear();
          }),
          icon: Icon(_selecting ? Icons.close_rounded : Icons.checklist_rounded, size: 18),
          label: Text(_selecting ? 'Cancel selecting' : 'Select vehicles'),
        ),
        if (_selecting) ...[
          TextButton(
            key: const Key('vr-select-all'),
            onPressed: () => setState(() => _selected.addAll(ids)),
            child: Text('Select all ${ids.length} shown'),
          ),
          if (_selected.isNotEmpty) TextButton(onPressed: () => setState(_selected.clear), child: const Text('Clear')),
          FilledButton.icon(
            key: const Key('vr-deregister-selected'),
            style: FilledButton.styleFrom(backgroundColor: AppTheme.error),
            onPressed: _selected.isEmpty || _busy ? null : () => _deregister(_selected.toList()),
            icon: const Icon(Icons.delete_outline_rounded, size: 18),
            label: Text('Deregister ${_selected.length} selected'),
          ),
        ],
      ]),
    );
  }

  List<Widget> _vehicles(VehicleReport r) {
    final canRemove = ref.watch(currentUserProvider)?.isAdminOrCommittee ?? false;
    final s = r.summaryOf(r.vehicles);
    final rows = r.rowsOf(r.vehicles);
    final without = ((r.vehicles['flats_without_vehicle'] as List?) ?? const []).cast<String>();
    final trouble = (s['insurance_expired'] as int) + (s['insurance_soon'] as int);
    return [
      _tiles([
        ('Vehicles', s['total'], AppTheme.primary),
        ('With parking', s['with_parking'], AppTheme.success),
        ('No parking', s['without_parking'], AppTheme.warning),
        ('Insurance', trouble, trouble == 0 ? AppTheme.textSecondary : AppTheme.error),
      ]),
      if (_counted(s['by_type']).isNotEmpty) _line('By type: ${_counted(s['by_type'])}'),
      if (trouble > 0 || (s['insurance_missing'] as int) > 0)
        _line('Insurance: ${s['insurance_expired']} expired · ${s['insurance_soon']} expiring within 30 days · '
            '${s['insurance_missing']} not recorded'),
      if (rows.isEmpty) _empty('No vehicle on record for this selection.'),
      if (canRemove && rows.isNotEmpty) _selectBar(rows),
      for (final v in rows)
        _RowCard(
          leading: canRemove && _selecting && v['id'] != null
              ? Checkbox(
                  key: Key('vr-select-${v['id']}'),
                  value: _selected.contains(v['id']),
                  onChanged: (on) => setState(() => on == true ? _selected.add('${v['id']}') : _selected.remove('${v['id']}')),
                )
              : null,
          trailing: canRemove && !_selecting && v['id'] != null
              ? IconButton(
                  key: Key('vr-remove-${v['id']}'),
                  tooltip: 'Deregister this vehicle',
                  icon: Icon(Icons.delete_outline_rounded, size: 20, color: AppTheme.error),
                  onPressed: _busy ? null : () => _deregister(['${v['id']}']),
                )
              : null,
          title: '${v['vehicle_number']} · ${v['type']}',
          subtitle: [
            for (final p in [v['make_model'], v['color'], v['flat'], v['owner']])
              if ('$p'.isNotEmpty && p != null) '$p'
          ].join(' · '),
          detail: v['parking_slot'] == '' ? 'No parking' : 'Parking ${v['parking_slot']}',
          detailColor: v['parking_slot'] == '' ? AppTheme.warning : AppTheme.textSecondary,
          tag: switch (v['insurance']) {
            'expired' => ('Insurance expired', AppTheme.error),
            'soon' => ('Insurance expires ${_day(v['insurance_expiry'])}', AppTheme.warning),
            _ => null,
          },
        ),
      _more(rows.length, r.rowCountOf(r.vehicles)),
      if (without.isNotEmpty) ...[
        _heading('Occupied flats with no vehicle on record (${s['flats_without_vehicle']})'),
        Text(without.join(', ') + ((s['flats_without_vehicle'] as int) > without.length ? ' …' : ''),
            style: const TextStyle(fontSize: 13)),
      ],
    ];
  }

  // ── Parking ──

  List<Widget> _parking(VehicleReport r) {
    final s = r.summaryOf(r.parking);
    final zones = r.rowsOf(r.parking, 'zones');
    final short = r.rowsOf(r.parking, 'flats_short');
    final ending = r.rowsOf(r.parking, 'ending_soon');
    return [
      _tiles([
        ('Slots', s['slots'], AppTheme.primary),
        ('Allotted', s['allotted'], AppTheme.success),
        ('Free', s['free'], AppTheme.textSecondary),
        ('Blocked', s['blocked'], (s['blocked'] as int) > 0 ? AppTheme.warning : AppTheme.textSecondary),
      ]),
      if (zones.isEmpty) _empty('No parking zones set up yet.'),
      for (final z in zones)
        _RowCard(
          title: '${z['zone']}${(z['code'] as String).isEmpty ? '' : ' (${z['code']})'}',
          subtitle: '${z['total']} slots · ${z['allotted']} allotted · ${z['free']} free',
          detail: (z['reserved'] as int) + (z['blocked'] as int) == 0
              ? null
              : '${z['reserved']} reserved · ${z['blocked']} blocked or under repair',
        ),
      _heading('Flats with more vehicles than parking (${r.parking['flats_short_count']})'),
      if (short.isEmpty) _empty('Every flat has parking for each of its vehicles.'),
      for (final f in short)
        _RowCard(
          title: '${f['flat']}',
          subtitle: '${f['vehicles']} vehicles · ${f['with_parking']} with parking',
          tag: ('${f['without_parking']} without', AppTheme.warning),
        ),
      _more(short.length, (r.parking['flats_short_count'] as int?) ?? short.length),
      _heading('Parking that ends within 30 days (${r.parking['ending_soon_count']})'),
      if (ending.isEmpty) _empty('None.'),
      for (final e in ending)
        _RowCard(title: 'Slot ${e['slot']} · ${e['flat']}', subtitle: '${e['vehicle']}', detail: 'Ends ${_day(e['ends'])}'),
      _more(ending.length, (r.parking['ending_soon_count'] as int?) ?? ending.length),
    ];
  }

  // ── Violations ──

  List<Widget> _violations(VehicleReport r) {
    final s = r.summaryOf(r.violations);
    final rows = r.rowsOf(r.violations);
    final repeat = r.rowsOf(r.violations, 'repeat_offenders');
    return [
      _tiles([
        ('Violations', s['total'], AppTheme.primary),
        ('Open', s['open'], (s['open'] as int) > 0 ? AppTheme.error : AppTheme.textSecondary),
        ('Fines charged', formatInr((s['fines_charged'] as int).toDouble()), AppTheme.warning),
        ('Taken off', formatInr((s['fines_taken_off'] as int).toDouble()), AppTheme.textSecondary),
      ]),
      if (_counted(s['by_type']).isNotEmpty) _line('By type: ${_counted(s['by_type'])}'),
      if ((s['fines_not_charged'] as int) > 0)
        _line('${formatInr((s['fines_not_charged'] as int).toDouble())} of fines set but not charged to a flat yet', color: AppTheme.warning),
      if (repeat.isNotEmpty)
        _line('Repeat offenders: ${[for (final o in repeat) '${o['vehicle_number']} ×${o['count']}'].join(', ')}',
            color: AppTheme.error),
      if (rows.isEmpty) _empty('No violation in ${r.monthLabel}.'),
      for (final v in rows)
        _RowCard(
          title: '${v['vehicle_number']} · ${v['type']}',
          subtitle: [
            for (final p in [_day(v['date']), v['flat'], v['description']])
              if ('$p'.isNotEmpty) '$p'
          ].join(' · '),
          detail: (v['fine'] as int) > 0 ? '${formatInr((v['fine'] as int).toDouble())}${v['fine_status'] == '' ? '' : ' · ${v['fine_status']}'}' : null,
          tag: (v['resolved'] as bool) ? ('Resolved', AppTheme.success) : ('Open', AppTheme.error),
        ),
      _more(rows.length, r.rowCountOf(r.violations)),
    ];
  }

  // ── Gate ──

  List<Widget> _gate(VehicleReport r) {
    final s = r.summaryOf(r.gate);
    final rows = r.rowsOf(r.gate);
    final inside = r.rowsOf(r.gate, 'visitors_inside');
    return [
      _tiles([
        ('Movements', s['total'], AppTheme.primary),
        ('In', s['entries'], AppTheme.success),
        ('Out', s['exits'], AppTheme.textSecondary),
        ('Not allowed', s['not_allowed'], (s['not_allowed'] as int) > 0 ? AppTheme.error : AppTheme.textSecondary),
      ]),
      _line('Residents ${s['residents']} · Visitors ${s['visitors']} · Unknown ${s['unknown']}'),
      _line('Visitor parking: ${s['visitor_visits']} visits · average stay ${_minutes(s['visitor_avg_stay_minutes'] as int?)}'
          ' · ${s['visitor_overstayed']} stayed past the time given'),
      if (inside.isNotEmpty) ...[
        _heading('Visitor vehicles inside now (${inside.length})'),
        for (final v in inside)
          _RowCard(
            title: '${v['vehicle_number']}',
            subtitle: 'Visiting ${v['host_flat'] == '' ? '-' : v['host_flat']} · since ${_stamp(v['since'])}',
            detail: 'Inside ${_minutes(v['minutes'] as int?)} of ${v['expected_hours']} h given',
            tag: (v['overstayed'] as bool) ? ('Overstayed', AppTheme.error) : null,
          ),
      ],
      _heading('Movements in ${r.monthLabel}'),
      if (rows.isEmpty) _empty('No vehicle movement recorded.'),
      for (final g in rows)
        _RowCard(
          title: '${g['vehicle_number']} · ${g['direction']}',
          subtitle: [
            _stamp(g['time']),
            switch (g['who']) { 'resident' => g['flat'] == '' ? 'Resident' : 'Resident ${g['flat']}', 'visitor' => 'Visitor', _ => 'Unknown' },
            g['method'],
          ].join(' · '),
          tag: (g['allowed'] as bool) ? null : ('Not allowed', AppTheme.error),
        ),
      _more(rows.length, r.rowCountOf(r.gate)),
    ];
  }
}

/// One line of the report: a title, a few words under it, and what to flag on the right.
class _RowCard extends StatelessWidget {
  final String title;
  final String? subtitle, detail;
  final Color? detailColor;
  final (String, Color)? tag;
  final Widget? leading, trailing;
  const _RowCard({required this.title, this.subtitle, this.detail, this.detailColor, this.tag, this.leading, this.trailing});

  @override
  Widget build(BuildContext context) => Container(
        margin: const EdgeInsets.only(bottom: 8),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: AppTheme.cardBg,
          borderRadius: BorderRadius.circular(AppTheme.radiusM),
          border: Border.all(color: AppTheme.border),
        ),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          if (leading != null) leading!,
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(title, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700)),
              if (subtitle != null && subtitle!.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(top: 2),
                  child: Text(subtitle!, style: TextStyle(fontSize: 12.5, color: AppTheme.textSecondary)),
                ),
              if (detail != null)
                Padding(
                  padding: const EdgeInsets.only(top: 2),
                  child: Text(detail!, style: TextStyle(fontSize: 12.5, color: detailColor ?? AppTheme.textSecondary)),
                ),
            ]),
          ),
          if (tag != null) ...[
            const SizedBox(width: 8),
            Flexible(
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(color: tag!.$2.withOpacity(0.12), borderRadius: BorderRadius.circular(999)),
                child: Text(tag!.$1,
                    textAlign: TextAlign.center,
                    style: TextStyle(fontSize: 11.5, fontWeight: FontWeight.w700, color: tag!.$2)),
              ),
            ),
          ],
          if (trailing != null) trailing!,
        ]),
      );
}

/// Print, share or download the report in full, for the month and the wing or flat chosen on the screen.
class _DownloadSheet extends StatefulWidget {
  final Future<Uint8List> Function(String format) load;
  const _DownloadSheet({required this.load});

  @override
  State<_DownloadSheet> createState() => _DownloadSheetState();
}

class _DownloadSheetState extends State<_DownloadSheet> {
  String? _busy;

  Future<void> _run(String tag, String format, {required bool share}) async {
    setState(() => _busy = tag);
    try {
      final bytes = await widget.load(format);
      final name = 'Vehicle-Report-${DateTime.now().toIso8601String().substring(0, 10)}.$format';
      final mime = format == 'pdf' ? 'application/pdf' : _xlsxMime;
      if (format == 'pdf' && !share && await openFileBytes(() async => bytes, mimeType: mime)) {
        if (mounted) Navigator.of(context).pop();
        return;
      }
      if (share || format == 'pdf') {
        await Share.shareXFiles([XFile.fromData(bytes, name: name, mimeType: mime)],
            fileNameOverrides: [name], subject: 'Vehicle report');
      } else if (await saveFileBytes(bytes, name, mimeType: mime) && mounted) {
        AppToast.success(context, '$name downloaded');
      }
      if (mounted) Navigator.of(context).pop();
    } catch (e) {
      if (mounted) {
        setState(() => _busy = null);
        AppToast.error(context, friendlyErrorMessage(e));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    Widget action(String tag, IconData icon, String label, String format, {required bool share}) => OutlinedButton.icon(
          key: Key('vr-$tag'),
          onPressed: _busy != null ? null : () => _run(tag, format, share: share),
          icon: _busy == tag
              ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
              : Icon(icon, size: 18),
          label: Text(label),
        );
    return AppSheetFrame(
      title: 'Print or download the vehicle report',
      subtitle: 'All four parts, in full, for the month, wing and flat chosen on the screen.',
      child: Wrap(spacing: 8, runSpacing: 8, children: [
        action('pdf-open', Icons.print_rounded, 'Print / open PDF', 'pdf', share: false),
        action('pdf-share', Icons.ios_share_rounded, 'Share PDF', 'pdf', share: true),
        action('xlsx-download', Icons.table_chart_outlined, 'Download Excel', 'xlsx', share: false),
        action('xlsx-share', Icons.ios_share_rounded, 'Share Excel', 'xlsx', share: true),
      ]),
    );
  }
}
