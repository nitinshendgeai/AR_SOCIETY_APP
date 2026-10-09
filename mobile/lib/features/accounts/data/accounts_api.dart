import 'dart:typed_data';
import 'package:ar_society_app/core/utils/server_time.dart';

import 'package:dio/dio.dart';
import 'package:intl/intl.dart';
import 'package:ar_society_app/core/api/api_client.dart';

// ── Formatting ───────────────────────────────────────────────────────────────

double _num(Object? v) => double.tryParse(v?.toString() ?? '') ?? 0;
DateTime _date(Object? v) => DateTime.parse(v as String);
String apiDate(DateTime d) => DateFormat('yyyy-MM-dd').format(d);

final _inr = NumberFormat.currency(locale: 'en_IN', symbol: '₹', decimalDigits: 2);
String formatInr(num v) => _inr.format(v);

/// "₹11.45 L", "₹1.20 Cr" — for tiles too narrow for the full figure.
String formatInrShort(num v) {
  final a = v.abs();
  final sign = v < 0 ? '-' : '';
  if (a >= 10000000) return '$sign₹${(a / 10000000).toStringAsFixed(2)} Cr';
  if (a >= 100000) return '$sign₹${(a / 100000).toStringAsFixed(2)} L';
  return formatInr(v);
}

String formatAccountsDate(DateTime d) => DateFormat('d MMM yyyy').format(d);

/// Start of the Indian financial year (1 April) a date falls in.
DateTime financialYearStart(DateTime d) => DateTime(d.month >= 4 ? d.year : d.year - 1, 4, 1);

/// A balance as the books show it: an amount and which side it's on.
class DrCr {
  final double amount;
  final String type; // Dr | Cr
  const DrCr(this.amount, this.type);

  factory DrCr.fromJson(Map<String, dynamic>? j) =>
      j == null ? const DrCr(0, 'Dr') : DrCr(_num(j['amount']), j['type'] as String? ?? 'Dr');

  bool get isZero => amount == 0;

  /// "₹1,500.00 Dr"; "₹0.00" for a nil balance.
  String get label => isZero ? formatInr(0) : '${formatInr(amount)} $type';
}

// ── Voucher types ────────────────────────────────────────────────────────────

const kManualVoucherTypes = ['receipt', 'payment', 'contra', 'journal'];

const kVoucherTypes = <String, String>{
  'receipt': 'Receipt',
  'payment': 'Payment',
  'contra': 'Contra',
  'journal': 'Journal',
  'bill': 'Member Bill',
  'purchase': 'Purchase',
  'closing': 'Year-end Closing',
};

String voucherTypeLabel(String t) => kVoucherTypes[t] ?? t;

String voucherTypeHint(String t) => switch (t) {
      'receipt' => 'Money received into cash or bank — interest, deposits, other income.',
      'payment' => 'Money paid out of cash or bank — electricity, salaries, repairs, taxes.',
      'contra' => 'Money moved between cash and bank — cash deposited or withdrawn.',
      _ => 'Adjustments that don\'t move cash or bank — depreciation, provisions, transfers to funds.',
    };

const kNatureLabels = <String, String>{
  'liability': 'Liabilities & Funds',
  'asset': 'Assets',
  'income': 'Income',
  'expense': 'Expenditure',
};

// ── Entities ─────────────────────────────────────────────────────────────────

class LedgerAccount {
  final String id;
  final String groupId;
  final String? groupName;
  final String? nature;
  final String? code;
  final String name;
  final String? systemKey;
  final String? description;
  final bool isSystem;
  final bool isActive;
  final double openingBalance;
  final String openingType;
  final bool isCash;
  final bool isBank;
  final bool isDefaultBank;
  final String? bankName;
  final String? bankAccountNumber;
  final String? bankIfsc;
  final String? bankBranch;

  /// The maintenance element this expense ledger counts towards (its spend
  /// feeds that element's budget in the monthly maintenance calculation).
  final String? maintenanceElementId;
  final String? maintenanceElementName;
  final DrCr? balance;

  const LedgerAccount({
    required this.id,
    required this.groupId,
    this.groupName,
    this.nature,
    this.code,
    required this.name,
    this.systemKey,
    this.description,
    required this.isSystem,
    required this.isActive,
    required this.openingBalance,
    required this.openingType,
    required this.isCash,
    required this.isBank,
    required this.isDefaultBank,
    this.bankName,
    this.bankAccountNumber,
    this.bankIfsc,
    this.bankBranch,
    this.maintenanceElementId,
    this.maintenanceElementName,
    this.balance,
  });

  factory LedgerAccount.fromJson(Map<String, dynamic> j) => LedgerAccount(
        id: j['id'] as String,
        groupId: j['group_id'] as String,
        groupName: j['group_name'] as String?,
        nature: j['nature'] as String?,
        code: j['code'] as String?,
        name: j['name'] as String,
        systemKey: j['system_key'] as String?,
        description: j['description'] as String?,
        isSystem: j['is_system'] as bool? ?? false,
        isActive: j['is_active'] as bool? ?? true,
        openingBalance: _num(j['opening_balance']),
        openingType: j['opening_type'] as String? ?? 'dr',
        isCash: j['is_cash'] as bool? ?? false,
        isBank: j['is_bank'] as bool? ?? false,
        isDefaultBank: j['is_default_bank'] as bool? ?? false,
        bankName: j['bank_name'] as String?,
        bankAccountNumber: j['bank_account_number'] as String?,
        bankIfsc: j['bank_ifsc'] as String?,
        bankBranch: j['bank_branch'] as String?,
        maintenanceElementId: j['maintenance_element_id'] as String?,
        maintenanceElementName: j['maintenance_element_name'] as String?,
        balance: j['balance_dr_cr'] == null ? null : DrCr.fromJson(j['balance_dr_cr'] as Map<String, dynamic>),
      );

  bool get isCashOrBank => isCash || isBank;
  bool get isMembersDues => systemKey == 'members_dues';
  bool get isCreditors => systemKey == 'sundry_creditors';
  String get openingLabel =>
      openingBalance == 0 ? '—' : '${formatInr(openingBalance)} ${openingType == 'dr' ? 'Dr' : 'Cr'}';
}

class AccountGroupRow {
  final String id;
  final String name;
  final String nature;
  final String? systemKey;
  final DrCr total;
  final List<LedgerAccount> accounts;

  const AccountGroupRow({
    required this.id,
    required this.name,
    required this.nature,
    this.systemKey,
    required this.total,
    required this.accounts,
  });

  factory AccountGroupRow.fromJson(Map<String, dynamic> j) => AccountGroupRow(
        id: j['id'] as String,
        name: j['name'] as String,
        nature: j['nature'] as String,
        systemKey: j['system_key'] as String?,
        total: DrCr.fromJson(j['total_dr_cr'] as Map<String, dynamic>?),
        accounts: (j['accounts'] as List).map((e) => LedgerAccount.fromJson(e as Map<String, dynamic>)).toList(),
      );
}

class VoucherEntry {
  final String accountId;
  final String? accountName;
  final double debit;
  final double credit;
  final String? flatId;
  final String? flatLabel;
  final String? vendorId;
  final String? vendorName;
  final String? narration;

  const VoucherEntry({
    required this.accountId,
    this.accountName,
    required this.debit,
    required this.credit,
    this.flatId,
    this.flatLabel,
    this.vendorId,
    this.vendorName,
    this.narration,
  });

  factory VoucherEntry.fromJson(Map<String, dynamic> j) => VoucherEntry(
        accountId: j['account_id'] as String,
        accountName: j['account_name'] as String?,
        debit: _num(j['debit']),
        credit: _num(j['credit']),
        flatId: j['flat_id'] as String?,
        flatLabel: j['flat_label'] as String?,
        vendorId: j['vendor_id'] as String?,
        vendorName: j['vendor_name'] as String?,
        narration: j['narration'] as String?,
      );

  /// "Members' Dues — A 101", "Sundry Creditors — Shield Security".
  String get title {
    final tag = flatLabel ?? vendorName;
    return tag == null ? (accountName ?? '—') : '${accountName ?? '—'} — $tag';
  }
}

class Voucher {
  final String id;
  final String voucherType;
  final String voucherTypeLabel;
  final String voucherNumber;
  final DateTime voucherDate;
  final String fiscalYear;
  final double amount;
  final String? narration;
  final String? reference;

  /// Who was paid, from the Vendor Master (a payment made to a vendor).
  final String? vendorId;
  final String? vendorName;

  /// `approved`, or `pending` / `rejected` for a manual payment waiting on the committee.
  final String approvalStatus;
  final String? sourceType;
  final bool isAuto;
  final bool isCancelled;

  /// Its financial year's books are closed — it can't be changed.
  final bool isLocked;

  /// Undone by a reversal entry in a later year (its own year was closed).
  final bool isReversed;
  final String? reversalOfId;
  final String? cancelReason;
  final String? createdByName;
  final DateTime? editedAt;
  final String? editedByName;

  /// Earlier versions, newest first.
  final List<VoucherRevision> revisions;
  final List<VoucherEntry> entries;

  const Voucher({
    required this.id,
    required this.voucherType,
    required this.voucherTypeLabel,
    required this.voucherNumber,
    required this.voucherDate,
    required this.fiscalYear,
    required this.amount,
    this.narration,
    this.reference,
    this.vendorId,
    this.vendorName,
    this.approvalStatus = 'approved',
    this.sourceType,
    required this.isAuto,
    required this.isCancelled,
    this.isLocked = false,
    this.isReversed = false,
    this.reversalOfId,
    this.cancelReason,
    this.createdByName,
    this.editedAt,
    this.editedByName,
    this.revisions = const [],
    required this.entries,
  });

  factory Voucher.fromJson(Map<String, dynamic> j) => Voucher(
        id: j['id'] as String,
        voucherType: j['voucher_type'] as String,
        voucherTypeLabel: j['voucher_type_label'] as String? ?? kVoucherTypes[j['voucher_type']] ?? '',
        voucherNumber: j['voucher_number'] as String,
        voucherDate: _date(j['voucher_date']),
        fiscalYear: j['fiscal_year'] as String? ?? '',
        amount: _num(j['amount']),
        narration: j['narration'] as String?,
        reference: j['reference'] as String?,
        vendorId: j['vendor_id'] as String?,
        vendorName: j['vendor_name'] as String?,
        approvalStatus: j['approval_status'] as String? ?? 'approved',
        sourceType: j['source_type'] as String?,
        isAuto: j['is_auto'] as bool? ?? false,
        isCancelled: j['is_cancelled'] as bool? ?? false,
        isLocked: j['is_locked'] as bool? ?? false,
        isReversed: j['is_reversed'] as bool? ?? false,
        reversalOfId: j['reversal_of_id'] as String?,
        cancelReason: j['cancel_reason'] as String?,
        createdByName: j['created_by_name'] as String?,
        editedAt: parseStampOrNull(j['edited_at']),
        editedByName: j['edited_by_name'] as String?,
        revisions: (j['revisions'] as List? ?? const [])
            .map((e) => VoucherRevision.fromJson(e as Map<String, dynamic>))
            .toList(),
        entries:
            (j['entries'] as List? ?? const []).map((e) => VoucherEntry.fromJson(e as Map<String, dynamic>)).toList(),
      );

  /// Entered by the society, not cancelled, in an open year.
  bool get canEdit => !isAuto && !isCancelled && !isLocked;

  List<VoucherEntry> get debits => entries.where((e) => e.debit > 0).toList();
  List<VoucherEntry> get credits => entries.where((e) => e.credit > 0).toList();

  /// Where it came from, for vouchers the app posted itself.
  String? get sourceLabel => switch (sourceType) {
        'maintenance_bill' => 'Posted from maintenance bill',
        'payment_receipt' || 'online_payment' => 'Posted from payment receipt',
        'vendor_invoice' => 'Posted from vendor bill',
        'vendor_payment' => 'Posted from vendor payment',
        _ when voucherType == 'closing' => 'Posted when the year\'s books were closed',
        _ when reversalOfId != null => 'Reversal of an entry in a closed year',
        _ => null,
      };
}

/// A voucher as it stood before one of its edits.
class VoucherRevision {
  final int revisionNo;
  final String reason;
  final DateTime? editedAt;
  final String? editedByName;
  final String voucherNumber;
  final DateTime voucherDate;
  final double amount;
  final String? narration;
  final String? reference;
  final List<VoucherEntry> entries;

  const VoucherRevision({
    required this.revisionNo,
    required this.reason,
    this.editedAt,
    this.editedByName,
    required this.voucherNumber,
    required this.voucherDate,
    required this.amount,
    this.narration,
    this.reference,
    required this.entries,
  });

  factory VoucherRevision.fromJson(Map<String, dynamic> j) {
    final b = j['before'] as Map<String, dynamic>? ?? const {};
    return VoucherRevision(
      revisionNo: (j['revision_no'] as num?)?.toInt() ?? 0,
      reason: j['reason'] as String? ?? '',
      editedAt: parseStampOrNull(j['edited_at']),
      editedByName: j['edited_by_name'] as String?,
      voucherNumber: b['voucher_number'] as String? ?? '',
      voucherDate: _date(b['voucher_date']),
      amount: _num(b['amount']),
      narration: b['narration'] as String?,
      reference: b['reference'] as String?,
      entries:
          (b['entries'] as List? ?? const []).map((e) => VoucherEntry.fromJson(e as Map<String, dynamic>)).toList(),
    );
  }
}

class StatementLine {
  final String voucherId;
  final String voucherNumber;
  final String voucherType;
  final DateTime date;
  final String particulars;
  final String? narration;
  final double debit;
  final double credit;
  final DrCr balance;

  const StatementLine({
    required this.voucherId,
    required this.voucherNumber,
    required this.voucherType,
    required this.date,
    required this.particulars,
    this.narration,
    required this.debit,
    required this.credit,
    required this.balance,
  });

  factory StatementLine.fromJson(Map<String, dynamic> j) => StatementLine(
        voucherId: j['voucher_id'] as String,
        voucherNumber: j['voucher_number'] as String,
        voucherType: j['voucher_type'] as String,
        date: _date(j['date']),
        particulars: j['particulars'] as String? ?? '',
        narration: j['narration'] as String?,
        debit: _num(j['debit']),
        credit: _num(j['credit']),
        balance: DrCr.fromJson(j['balance_dr_cr'] as Map<String, dynamic>?),
      );
}

class LedgerStatement {
  final LedgerAccount account;
  final DrCr opening;
  final double totalDebit;
  final double totalCredit;
  final DrCr closing;
  final List<StatementLine> lines;

  const LedgerStatement({
    required this.account,
    required this.opening,
    required this.totalDebit,
    required this.totalCredit,
    required this.closing,
    required this.lines,
  });

  factory LedgerStatement.fromJson(Map<String, dynamic> j) => LedgerStatement(
        account: LedgerAccount.fromJson(j['account'] as Map<String, dynamic>),
        opening: DrCr.fromJson(j['opening_dr_cr'] as Map<String, dynamic>?),
        totalDebit: _num(j['total_debit']),
        totalCredit: _num(j['total_credit']),
        closing: DrCr.fromJson(j['closing_dr_cr'] as Map<String, dynamic>?),
        lines: (j['lines'] as List).map((e) => StatementLine.fromJson(e as Map<String, dynamic>)).toList(),
      );
}

class MemberBalance {
  final String flatId;
  final String flatLabel;
  final String memberName;
  final DrCr balance;

  const MemberBalance({required this.flatId, required this.flatLabel, required this.memberName, required this.balance});

  factory MemberBalance.fromJson(Map<String, dynamic> j) => MemberBalance(
        flatId: j['flat_id'] as String,
        flatLabel: j['flat_label'] as String? ?? '—',
        memberName: j['member_name'] as String? ?? '—',
        balance: DrCr.fromJson(j['balance_dr_cr'] as Map<String, dynamic>?),
      );

  /// Dr: the member owes the society; Cr: paid in advance.
  double get signed => balance.type == 'Dr' ? balance.amount : -balance.amount;
}

class MembersLedger {
  final String accountId;
  final List<MemberBalance> members;
  const MembersLedger({required this.accountId, required this.members});

  factory MembersLedger.fromJson(Map<String, dynamic> j) => MembersLedger(
        accountId: j['account_id'] as String,
        members: (j['members'] as List).map((e) => MemberBalance.fromJson(e as Map<String, dynamic>)).toList(),
      );
}

class AccountsSummary {
  final String fy;
  final double cash;
  final double bank;
  final DrCr membersDues;
  final double creditors;
  final double fyIncome;
  final double fyExpense;
  final double fySurplus;
  final List<LedgerAccount> cashBankAccounts;
  final int pendingPostings;

  const AccountsSummary({
    required this.fy,
    required this.cash,
    required this.bank,
    required this.membersDues,
    required this.creditors,
    required this.fyIncome,
    required this.fyExpense,
    required this.fySurplus,
    required this.cashBankAccounts,
    required this.pendingPostings,
  });

  factory AccountsSummary.fromJson(Map<String, dynamic> j) => AccountsSummary(
        fy: j['fy'] as String? ?? '',
        cash: _num(j['cash']),
        bank: _num(j['bank']),
        membersDues: DrCr.fromJson(j['members_dues_dr_cr'] as Map<String, dynamic>?),
        creditors: _num(j['creditors']),
        fyIncome: _num(j['fy_income']),
        fyExpense: _num(j['fy_expense']),
        fySurplus: _num(j['fy_surplus']),
        cashBankAccounts: (j['cash_bank_accounts'] as List? ?? const [])
            .map((e) => LedgerAccount.fromJson(e as Map<String, dynamic>))
            .toList(),
        pendingPostings: (j['pending_postings'] as num?)?.toInt() ?? 0,
      );
}

/// One line of a voucher being entered.
class VoucherLineInput {
  final String accountId;
  final double debit;
  final double credit;
  final String? flatId;
  final String? vendorId;
  final String? narration;
  const VoucherLineInput(
      {required this.accountId, this.debit = 0, this.credit = 0, this.flatId, this.vendorId, this.narration});

  Map<String, dynamic> toJson() => {
        'account_id': accountId,
        'debit': debit.toStringAsFixed(2),
        'credit': credit.toStringAsFixed(2),
        if (flatId != null) 'flat_id': flatId,
        if (vendorId != null) 'vendor_id': vendorId,
        if (narration != null && narration!.isNotEmpty) 'narration': narration,
      };
}

// ── Spend per maintenance element ────────────────────────────────────────────

class LedgerSpend {
  final String accountId;
  final String name;
  final double amount;
  const LedgerSpend({required this.accountId, required this.name, required this.amount});

  factory LedgerSpend.fromJson(Map<String, dynamic> j) =>
      LedgerSpend(accountId: j['account_id'] as String, name: j['name'] as String, amount: _num(j['amount']));
}

class ElementSpend {
  final String elementId;
  final String code;
  final String name;
  final double total;
  final List<LedgerSpend> ledgers;
  const ElementSpend(
      {required this.elementId, required this.code, required this.name, required this.total, required this.ledgers});

  factory ElementSpend.fromJson(Map<String, dynamic> j) => ElementSpend(
        elementId: j['element_id'] as String,
        code: j['code'] as String,
        name: j['name'] as String,
        total: _num(j['total']),
        ledgers: ((j['ledgers'] as List?) ?? const [])
            .map((e) => LedgerSpend.fromJson(e as Map<String, dynamic>))
            .toList(),
      );
}

/// What was spent on each maintenance element between two dates, and on expense ledgers no element covers.
class ExpensesByElement {
  final DateTime from;
  final DateTime to;
  final double total;
  final double linkedTotal;
  final double unlinkedTotal;
  final List<ElementSpend> elements;
  final List<LedgerSpend> unlinked;
  const ExpensesByElement({
    required this.from,
    required this.to,
    required this.total,
    required this.linkedTotal,
    required this.unlinkedTotal,
    required this.elements,
    required this.unlinked,
  });

  factory ExpensesByElement.fromJson(Map<String, dynamic> j) => ExpensesByElement(
        from: DateTime.parse(j['date_from'] as String),
        to: DateTime.parse(j['date_to'] as String),
        total: _num(j['total']),
        linkedTotal: _num(j['linked_total']),
        unlinkedTotal: _num(j['unlinked_total']),
        elements: ((j['elements'] as List?) ?? const [])
            .map((e) => ElementSpend.fromJson(e as Map<String, dynamic>))
            .toList(),
        unlinked: ((j['unlinked'] as List?) ?? const [])
            .map((e) => LedgerSpend.fromJson(e as Map<String, dynamic>))
            .toList(),
      );
}

// ── Financial years & statements ─────────────────────────────────────────────

class FinancialYear {
  final String fy;
  final DateTime start;
  final DateTime end;
  final bool isCurrent;
  final bool isClosed;
  final bool hasEntries;
  final double income;
  final double expenditure;
  final double surplus;
  final bool canClose;
  final String? closeBlockedReason;
  final bool canReopen;
  final double suggestedReservePct;
  final DateTime? closedAt;
  final String? closedByName;
  final double? reservePct;
  final double? reserveTransfer;
  final String? closingVoucherId;

  const FinancialYear({
    required this.fy,
    required this.start,
    required this.end,
    required this.isCurrent,
    required this.isClosed,
    required this.hasEntries,
    required this.income,
    required this.expenditure,
    required this.surplus,
    required this.canClose,
    this.closeBlockedReason,
    required this.canReopen,
    required this.suggestedReservePct,
    this.closedAt,
    this.closedByName,
    this.reservePct,
    this.reserveTransfer,
    this.closingVoucherId,
  });

  factory FinancialYear.fromJson(Map<String, dynamic> j) => FinancialYear(
        fy: j['fy'] as String,
        start: _date(j['start']),
        end: _date(j['end']),
        isCurrent: j['is_current'] as bool? ?? false,
        isClosed: j['is_closed'] as bool? ?? false,
        hasEntries: j['has_entries'] as bool? ?? false,
        income: _num(j['income']),
        expenditure: _num(j['expenditure']),
        surplus: _num(j['surplus']),
        canClose: j['can_close'] as bool? ?? false,
        closeBlockedReason: j['close_blocked_reason'] as String?,
        canReopen: j['can_reopen'] as bool? ?? false,
        suggestedReservePct: _num(j['suggested_reserve_pct']),
        closedAt: j['closed_at'] == null ? null : DateTime.parse(j['closed_at'] as String).toLocal(),
        closedByName: j['closed_by_name'] as String?,
        reservePct: j['reserve_pct'] == null ? null : _num(j['reserve_pct']),
        reserveTransfer: j['reserve_transfer'] == null ? null : _num(j['reserve_transfer']),
        closingVoucherId: j['closing_voucher_id'] as String?,
      );

  /// "FY 2026-27"
  String get label => 'FY $fy';
}

/// The financial statements, as the backend names them.
const kFinancialReports = <String, (String, String)>{
  'balance-sheet': ('Balance Sheet', 'Funds, liabilities and assets as at the year end'),
  'income-expenditure': ('Income & Expenditure', 'The year\'s income, expenditure and surplus'),
  'receipts-payments': ('Receipts & Payments', 'Cash and bank in and out, with balances'),
  'trial-balance': ('Trial Balance', 'Every ledger\'s balance — debits equal credits'),
  'funds': ('Schedule of Funds', 'Sinking, repair and other funds — additions and use'),
};

/// One amount of a statement: a blank is null.
double? _amt(Object? v) => (v == null || v == '') ? null : double.tryParse(v.toString());

class ReportRow {
  final String label;
  final String? code;
  final List<double?> values;
  final bool bold;
  final int level;
  final String? accountId;

  const ReportRow(
      {required this.label, this.code, required this.values, this.bold = false, this.level = 1, this.accountId});

  factory ReportRow.fromJson(Map<String, dynamic> j) => ReportRow(
        label: j['label'] as String? ?? '',
        code: j['code'] as String?,
        values: ((j['amounts'] ?? j['cells']) as List? ?? const []).map(_amt).toList(),
        bold: j['bold'] as bool? ?? false,
        level: (j['level'] as num?)?.toInt() ?? 1,
        accountId: j['account_id'] as String?,
      );
}

class ReportSection {
  final String? title;
  final List<ReportRow> rows;
  final List<double?> total;
  const ReportSection({this.title, required this.rows, required this.total});

  factory ReportSection.fromJson(Map<String, dynamic> j) => ReportSection(
        title: j['title'] as String?,
        rows: (j['rows'] as List).map((e) => ReportRow.fromJson(e as Map<String, dynamic>)).toList(),
        total: (j['total'] as List? ?? const []).map(_amt).toList(),
      );
}

class ReportSide {
  final String title;
  final List<ReportSection> sections;
  final List<double?> total;
  const ReportSide({required this.title, required this.sections, required this.total});

  factory ReportSide.fromJson(Map<String, dynamic> j) => ReportSide(
        title: j['title'] as String,
        sections: (j['sections'] as List).map((e) => ReportSection.fromJson(e as Map<String, dynamic>)).toList(),
        total: (j['total'] as List).map(_amt).toList(),
      );
}

/// A financial statement: two-sided (Income & Expenditure, Balance Sheet,
/// Receipts & Payments — [sides], one amount per year in [columns]) or a
/// table (Trial Balance, Schedule of Funds — [rows] of [columns] cells).
class FinancialReport {
  final String report;
  final String title;
  final String heading;
  final String fy;
  final bool provisional;
  final bool twoSided;
  final List<String> columns;
  final List<ReportSide> sides;
  final List<ReportRow> rows;
  final List<double?> totals;
  final ReportRow? result;
  final List<String> notes;
  final bool balanced;

  const FinancialReport({
    required this.report,
    required this.title,
    required this.heading,
    required this.fy,
    required this.provisional,
    required this.twoSided,
    required this.columns,
    this.sides = const [],
    this.rows = const [],
    this.totals = const [],
    this.result,
    this.notes = const [],
    required this.balanced,
  });

  factory FinancialReport.fromJson(Map<String, dynamic> j) => FinancialReport(
        report: j['report'] as String,
        title: j['title'] as String,
        heading: j['heading'] as String,
        fy: j['fy'] as String,
        provisional: j['provisional'] as bool? ?? false,
        twoSided: j['kind'] == 'two_sided',
        columns: (j['columns'] as List).map((e) => e.toString()).toList(),
        sides: (j['sides'] as List? ?? const []).map((e) => ReportSide.fromJson(e as Map<String, dynamic>)).toList(),
        rows: (j['rows'] as List? ?? const []).map((e) => ReportRow.fromJson(e as Map<String, dynamic>)).toList(),
        totals: (j['totals'] as List? ?? const []).map(_amt).toList(),
        result: j['result'] == null ? null : ReportRow.fromJson(j['result'] as Map<String, dynamic>),
        notes: (j['notes'] as List? ?? const []).map((e) => e.toString()).toList(),
        balanced: j['balanced'] as bool? ?? true,
      );
}

/// "1,234.00", "(1,234.00)" for a negative amount, "" for a blank.
String formatStatementAmount(double? v) {
  if (v == null || v == 0) return '';
  final s = NumberFormat('#,##,##0.00', 'en_IN').format(v.abs());
  return v < 0 ? '($s)' : s;
}

// ── API ──────────────────────────────────────────────────────────────────────

/// FastAPI /accounts/* — the society's books.
class AccountsApi {
  final Dio _dio;
  AccountsApi({Dio? dio}) : _dio = dio ?? ApiClient.instance;

  Future<AccountsSummary> summary(String societyId) async =>
      AccountsSummary.fromJson((await _dio.get('/accounts/summary/$societyId')).data as Map<String, dynamic>);

  Future<ExpensesByElement> expensesByElement(String societyId, DateTime from, DateTime to) async =>
      ExpensesByElement.fromJson((await _dio.get('/accounts/expenses-by-element/$societyId',
              queryParameters: {'date_from': apiDate(from), 'date_to': apiDate(to)}))
          .data as Map<String, dynamic>);

  Future<List<AccountGroupRow>> chart(String societyId) async =>
      ((await _dio.get('/accounts/chart/$societyId')).data as List)
          .map((e) => AccountGroupRow.fromJson(e as Map<String, dynamic>))
          .toList();

  Future<List<LedgerAccount>> ledgers(String societyId) async =>
      ((await _dio.get('/accounts/ledgers/$societyId')).data as List)
          .map((e) => LedgerAccount.fromJson(e as Map<String, dynamic>))
          .toList();

  Future<LedgerAccount> createLedger(Map<String, dynamic> fields) async =>
      LedgerAccount.fromJson((await _dio.post('/accounts/ledgers', data: fields)).data as Map<String, dynamic>);

  Future<LedgerAccount> updateLedger(String id, Map<String, dynamic> changes) async =>
      LedgerAccount.fromJson((await _dio.patch('/accounts/ledgers/$id', data: changes)).data as Map<String, dynamic>);

  Future<LedgerStatement> statement(String accountId,
      {DateTime? from, DateTime? to, String? flatId, String? vendorId}) async {
    final r = await _dio.get('/accounts/ledgers/$accountId/statement', queryParameters: {
      if (from != null) 'date_from': apiDate(from),
      if (to != null) 'date_to': apiDate(to),
      if (flatId != null) 'flat_id': flatId,
      if (vendorId != null) 'vendor_id': vendorId,
    });
    return LedgerStatement.fromJson(r.data as Map<String, dynamic>);
  }

  Future<MembersLedger> members(String societyId) async =>
      MembersLedger.fromJson((await _dio.get('/accounts/members/$societyId')).data as Map<String, dynamic>);

  Future<List<Voucher>> vouchers(String societyId,
      {String? type, DateTime? from, DateTime? to, String? vendorId}) async {
    final r = await _dio.get('/accounts/vouchers/society/$societyId', queryParameters: {
      if (type != null) 'voucher_type': type,
      if (vendorId != null) 'vendor_id': vendorId,
      if (from != null) 'date_from': apiDate(from),
      if (to != null) 'date_to': apiDate(to),
      'limit': 500,
    });
    return (r.data as List).map((e) => Voucher.fromJson(e as Map<String, dynamic>)).toList();
  }

  /// The number the next voucher of this type will carry, shown on a form before it is saved.
  Future<String> nextVoucherNumber(String societyId, String type, DateTime on) async {
    final r = await _dio.get('/accounts/vouchers/next-number/$societyId',
        queryParameters: {'voucher_type': type, 'on': apiDate(on)});
    return (r.data as Map<String, dynamic>)['voucher_number'] as String;
  }

  Future<Voucher> voucher(String id) async =>
      Voucher.fromJson((await _dio.get('/accounts/vouchers/$id')).data as Map<String, dynamic>);

  Future<Voucher> createVoucher({
    required String societyId,
    required String type,
    required DateTime date,
    required List<VoucherLineInput> lines,
    String? narration,
    String? reference,
    String? vendorId,
  }) async {
    final r = await _dio.post('/accounts/vouchers', data: {
      'society_id': societyId,
      'voucher_type': type,
      'voucher_date': apiDate(date),
      if (narration != null && narration.isNotEmpty) 'narration': narration,
      if (reference != null && reference.isNotEmpty) 'reference': reference,
      if (vendorId != null) 'vendor_id': vendorId,
      'entries': lines.map((l) => l.toJson()).toList(),
    });
    return Voucher.fromJson(r.data as Map<String, dynamic>);
  }

  /// Correct a voucher the society entered; the earlier version is kept.
  Future<Voucher> updateVoucher(
    String id, {
    required DateTime date,
    required List<VoucherLineInput> lines,
    required String reason,
    String? narration,
    String? reference,
    String? vendorId,
  }) async {
    final r = await _dio.put('/accounts/vouchers/$id', data: {
      'voucher_date': apiDate(date),
      'narration': (narration?.isEmpty ?? true) ? null : narration,
      'reference': (reference?.isEmpty ?? true) ? null : reference,
      'vendor_id': vendorId,
      'entries': lines.map((l) => l.toJson()).toList(),
      'reason': reason,
    });
    return Voucher.fromJson(r.data as Map<String, dynamic>);
  }

  Future<Uint8List> _pdf(String path, [Map<String, dynamic>? query]) async {
    final r =
        await _dio.get<List<int>>(path, queryParameters: query, options: Options(responseType: ResponseType.bytes));
    return Uint8List.fromList(r.data!);
  }

  /// The voucher printed with signature boxes.
  Future<Uint8List> voucherPdf(String id) => _pdf('/accounts/vouchers/$id/pdf');

  Future<Uint8List> statementPdf(String accountId, {DateTime? from, DateTime? to, String? flatId, String? vendorId}) =>
      _pdf('/accounts/ledgers/$accountId/statement', {
        'format': 'pdf',
        if (from != null) 'date_from': apiDate(from),
        if (to != null) 'date_to': apiDate(to),
        if (flatId != null) 'flat_id': flatId,
        if (vendorId != null) 'vendor_id': vendorId,
      });

  Future<Uint8List> dayBookPdf(String societyId, {String? type, DateTime? from, DateTime? to}) =>
      _pdf('/accounts/day-book/$societyId/pdf', {
        if (type != null) 'voucher_type': type,
        if (from != null) 'date_from': apiDate(from),
        if (to != null) 'date_to': apiDate(to),
      });

  Future<Uint8List> membersLedgerPdf(String societyId) => _pdf('/accounts/members/$societyId', {'format': 'pdf'});

  Future<Voucher> cancelVoucher(String id, String reason) async => Voucher.fromJson(
      (await _dio.post('/accounts/vouchers/$id/cancel', data: {'reason': reason})).data as Map<String, dynamic>);

  /// Posts every bill, payment and vendor bill not yet in the books;
  /// returns how many vouchers were posted or cancelled.
  Future<int> sync(String societyId) async =>
      ((await _dio.post('/accounts/sync/$societyId')).data as Map<String, dynamic>)['total'] as int? ?? 0;

  /// Every financial year with entries up to the current one, newest first.
  Future<List<FinancialYear>> years(String societyId) async =>
      ((await _dio.get('/accounts/years/$societyId')).data as List)
          .map((e) => FinancialYear.fromJson(e as Map<String, dynamic>))
          .toList();

  Future<void> closeYear(String societyId, String fy, {required double reservePct, String? notes}) =>
      _dio.post('/accounts/years/$societyId/$fy/close', data: {
        'reserve_pct': reservePct.toStringAsFixed(2),
        if (notes != null && notes.isNotEmpty) 'notes': notes,
      });

  Future<void> reopenYear(String societyId, String fy, String reason) =>
      _dio.post('/accounts/years/$societyId/$fy/reopen', data: {'reason': reason});

  Future<FinancialReport> report(String societyId, String report, String fy) async => FinancialReport.fromJson(
      (await _dio.get('/accounts/reports/$societyId/$report', queryParameters: {'fy': fy})).data
          as Map<String, dynamic>);

  Future<Uint8List> reportPdf(String societyId, String report, String fy) =>
      _pdf('/accounts/reports/$societyId/$report', {'fy': fy, 'format': 'pdf'});
}
