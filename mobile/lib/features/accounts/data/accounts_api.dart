import 'package:dio/dio.dart';
import 'package:intl/intl.dart';
import 'package:ar_society_app/core/api/api_client.dart';

// ── Formatting ───────────────────────────────────────────────────────────────

double _num(Object? v) => double.tryParse(v?.toString() ?? '') ?? 0;
DateTime _date(Object? v) => DateTime.parse(v as String);
String apiDate(DateTime d) => DateFormat('yyyy-MM-dd').format(d);

final _inr = NumberFormat.currency(locale: 'en_IN', symbol: '₹', decimalDigits: 2);
String formatInr(num v) => _inr.format(v);
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
  final String? vendorName;
  final String? narration;

  const VoucherEntry({
    required this.accountId,
    this.accountName,
    required this.debit,
    required this.credit,
    this.flatId,
    this.flatLabel,
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
  final String? sourceType;
  final bool isAuto;
  final bool isCancelled;
  final String? cancelReason;
  final String? createdByName;
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
    this.sourceType,
    required this.isAuto,
    required this.isCancelled,
    this.cancelReason,
    this.createdByName,
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
        sourceType: j['source_type'] as String?,
        isAuto: j['is_auto'] as bool? ?? false,
        isCancelled: j['is_cancelled'] as bool? ?? false,
        cancelReason: j['cancel_reason'] as String?,
        createdByName: j['created_by_name'] as String?,
        entries: (j['entries'] as List? ?? const [])
            .map((e) => VoucherEntry.fromJson(e as Map<String, dynamic>))
            .toList(),
      );

  List<VoucherEntry> get debits => entries.where((e) => e.debit > 0).toList();
  List<VoucherEntry> get credits => entries.where((e) => e.credit > 0).toList();

  /// Where it came from, for vouchers the app posted itself.
  String? get sourceLabel => switch (sourceType) {
        'maintenance_bill' => 'Posted from maintenance bill',
        'payment_receipt' || 'online_payment' => 'Posted from payment receipt',
        'vendor_invoice' => 'Posted from vendor bill',
        'vendor_payment' => 'Posted from vendor payment',
        _ => null,
      };
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
  const VoucherLineInput({required this.accountId, this.debit = 0, this.credit = 0, this.flatId});

  Map<String, dynamic> toJson() => {
        'account_id': accountId,
        'debit': debit.toStringAsFixed(2),
        'credit': credit.toStringAsFixed(2),
        if (flatId != null) 'flat_id': flatId,
      };
}

// ── API ──────────────────────────────────────────────────────────────────────

/// FastAPI /accounts/* — the society's books.
class AccountsApi {
  final Dio _dio;
  AccountsApi({Dio? dio}) : _dio = dio ?? ApiClient.instance;

  Future<AccountsSummary> summary(String societyId) async =>
      AccountsSummary.fromJson((await _dio.get('/accounts/summary/$societyId')).data as Map<String, dynamic>);

  Future<List<AccountGroupRow>> chart(String societyId) async => ((await _dio.get('/accounts/chart/$societyId'))
          .data as List)
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

  Future<List<Voucher>> vouchers(String societyId, {String? type, DateTime? from, DateTime? to}) async {
    final r = await _dio.get('/accounts/vouchers/society/$societyId', queryParameters: {
      if (type != null) 'voucher_type': type,
      if (from != null) 'date_from': apiDate(from),
      if (to != null) 'date_to': apiDate(to),
      'limit': 500,
    });
    return (r.data as List).map((e) => Voucher.fromJson(e as Map<String, dynamic>)).toList();
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
  }) async {
    final r = await _dio.post('/accounts/vouchers', data: {
      'society_id': societyId,
      'voucher_type': type,
      'voucher_date': apiDate(date),
      if (narration != null && narration.isNotEmpty) 'narration': narration,
      if (reference != null && reference.isNotEmpty) 'reference': reference,
      'entries': lines.map((l) => l.toJson()).toList(),
    });
    return Voucher.fromJson(r.data as Map<String, dynamic>);
  }

  Future<Voucher> cancelVoucher(String id, String reason) async => Voucher.fromJson(
      (await _dio.post('/accounts/vouchers/$id/cancel', data: {'reason': reason})).data as Map<String, dynamic>);

  /// Posts every bill, payment and vendor bill not yet in the books;
  /// returns how many vouchers were posted or cancelled.
  Future<int> sync(String societyId) async =>
      ((await _dio.post('/accounts/sync/$societyId')).data as Map<String, dynamic>)['total'] as int? ?? 0;
}
