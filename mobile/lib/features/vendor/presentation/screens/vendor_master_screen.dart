import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ar_society_app/core/layout/app_shell.dart' show isDesktopLayout;
import 'package:ar_society_app/core/layout/app_sheet.dart';
import 'package:ar_society_app/core/router/app_router.dart';
import 'package:ar_society_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ar_society_app/features/vendor/presentation/screens/vendors_work_screen.dart' show VendorsTab;
import 'package:ar_society_app/features/vendor/presentation/widgets/vendor_master_sheet.dart';
import 'package:ar_society_app/shared/widgets/app_data_table.dart' show HeaderActionButton;
import 'package:ar_society_app/shared/widgets/app_form.dart';

/// The Vendor Master: every vendor the society deals with, with its type, PAN, GSTIN, bank details and TDS section.
/// The committee adds and edits vendors, imports a vendor list from Excel / CSV, and reviews every vendor's TDS setup;
/// the manager can look vendors up. Quotations, work orders and contracts are in Vendors & Work.
class VendorMasterScreen extends ConsumerStatefulWidget {
  const VendorMasterScreen({super.key});

  @override
  ConsumerState<VendorMasterScreen> createState() => _VendorMasterScreenState();
}

class _VendorMasterScreenState extends ConsumerState<VendorMasterScreen> {
  String _query = '';

  @override
  Widget build(BuildContext context) {
    final user = ref.watch(currentUserProvider);
    final societyId = user?.societyId;
    if (societyId == null) return const Scaffold(body: Center(child: Text('No society context')));
    final committee = user!.isAdminOrCommittee;
    void add() => showAppSheet(context: context, builder: (_) => VendorSheet(societyId: societyId));
    return AppPage(
      title: 'Vendor Master',
      actions: [
        if (committee) ...[
          IconButton(
            key: const Key('vendors-import'),
            icon: const Icon(Icons.upload_file_rounded),
            tooltip: 'Import vendors from Excel / CSV',
            onPressed: () => context.push(AppRoutes.vendorsImport),
          ),
          IconButton(
            key: const Key('vendors-tds-review'),
            icon: const Icon(Icons.fact_check_outlined),
            tooltip: 'TDS review',
            onPressed: () => context.push(AppRoutes.vendorTdsReview),
          ),
          if (isDesktopLayout(context)) HeaderActionButton(icon: Icons.add_rounded, label: 'Add Vendor', onPressed: add),
        ],
      ],
      floatingActionButton: committee && !isDesktopLayout(context)
          ? FloatingActionButton.extended(
              key: const Key('vendor-add'), onPressed: add, icon: const Icon(Icons.add_rounded), label: const Text('Add Vendor'))
          : null,
      body: Column(children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
          child: TextField(
            key: const Key('vendor-search'),
            decoration: const InputDecoration(
              prefixIcon: Icon(Icons.search_rounded),
              hintText: 'Search by name, code, phone, GSTIN or PAN',
              isDense: true,
            ),
            onChanged: (v) => setState(() => _query = v),
          ),
        ),
        Expanded(child: VendorsTab(societyId: societyId, committee: committee, query: _query)),
      ]),
    );
  }
}
