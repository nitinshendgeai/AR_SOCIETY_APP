import 'package:dio/dio.dart';
import 'package:ar_society_app/core/api/api_client.dart';

/// The Accounts Agent assistant: bye-law questions with clause references, entries drafted for approval, and
/// notice / agenda drafts. The society is taken from the signed-in user by the server.
List<Map<String, dynamic>> _maps(Object? v) => [for (final x in (v as List? ?? const [])) (x as Map).cast<String, dynamic>()];

/// One bye-law clause the answer is based on.
class BylawSource {
  final String cite; // "C1"
  final String clauseRef;
  final String? heading;
  final int? page;
  final String source; // "Registered bye-laws" | "Bye-law amendment" | "Model bye-laws"
  final String documentTitle;
  final bool societySpecific;
  final bool verified; // document and clause both verified
  final bool cited;
  final String text;
  const BylawSource(this.cite, this.clauseRef, this.heading, this.page, this.source, this.documentTitle,
      this.societySpecific, this.verified, this.cited, this.text);
  factory BylawSource.fromJson(Map<String, dynamic> j) => BylawSource(
        j['cite'] as String? ?? '',
        j['clause_ref'] as String? ?? '',
        j['heading'] as String?,
        j['page'] as int?,
        j['source'] as String? ?? '',
        j['document_title'] as String? ?? '',
        j['society_specific'] as bool? ?? false,
        (j['document_verified'] as bool? ?? false) && (j['clause_verified'] as bool? ?? false),
        j['cited'] as bool? ?? true,
        j['text'] as String? ?? '',
      );
  String get label => '${source.isEmpty ? 'Bye-laws' : source} — clause $clauseRef${page == null ? '' : ', page $page'}';
}

class BylawAnswer {
  final String answer;
  final bool answeredBySources;
  final bool needsProfessionalReview;
  final bool aiGenerated;
  final List<String> notes;
  final String? societyFacts;
  final List<BylawSource> sources;
  final String disclaimer;
  const BylawAnswer(this.answer, this.answeredBySources, this.needsProfessionalReview, this.aiGenerated, this.notes,
      this.societyFacts, this.sources, this.disclaimer);
  factory BylawAnswer.fromJson(Map<String, dynamic> j) => BylawAnswer(
        j['answer'] as String? ?? '',
        j['answered_by_sources'] as bool? ?? false,
        j['needs_professional_review'] as bool? ?? true,
        j['ai_generated'] as bool? ?? false,
        [for (final n in (j['notes'] as List? ?? const [])) '$n'],
        j['society_facts'] as String?,
        [for (final s in _maps(j['sources'])) BylawSource.fromJson(s)],
        j['disclaimer'] as String? ?? '',
      );
  List<BylawSource> get cited => sources.where((s) => s.cited).toList();
}

class DraftLine {
  final String account;
  final double debit;
  final double credit;
  const DraftLine(this.account, this.debit, this.credit);
}

/// The voucher the agent proposes (and, once saved, the pending voucher it created).
class EntryDraftResult {
  final String voucherType;
  final String voucherDate;
  final double amount;
  final String? narration;
  final String? reference;
  final List<DraftLine> lines;
  final List<String> basis;
  final List<String> unclear;
  final bool saved;
  final String? voucherNumber;
  final String? approvalStatus;
  const EntryDraftResult(this.voucherType, this.voucherDate, this.amount, this.narration, this.reference, this.lines,
      this.basis, this.unclear, this.saved, this.voucherNumber, this.approvalStatus);
  factory EntryDraftResult.fromJson(Map<String, dynamic> j) => EntryDraftResult(
        j['voucher_type'] as String? ?? 'payment',
        j['voucher_date'] as String? ?? '',
        double.tryParse('${j['amount']}') ?? 0,
        j['narration'] as String?,
        j['reference'] as String?,
        [
          for (final l in _maps(j['lines']))
            DraftLine(l['account'] as String? ?? '', double.tryParse('${l['debit']}') ?? 0, double.tryParse('${l['credit']}') ?? 0),
        ],
        [for (final b in (j['basis'] as List? ?? const [])) '$b'],
        [for (final u in (j['unclear'] as List? ?? const [])) '$u'],
        j['saved'] as bool? ?? false,
        j['voucher_number'] as String?,
        j['approval_status'] as String?,
      );
}

/// What the entry form sends. `text` is the entry in the user's own words; the other fields override it.
Map<String, dynamic> entryDraftPayload({
  String? text,
  String? voucherType,
  String? amount,
  DateTime? date,
  String? vendorId,
  String? ledgerId,
  String? moneyAccount,
  String? reference,
  String? narration,
  required bool save,
}) {
  String? clean(String? s) => (s == null || s.trim().isEmpty) ? null : s.trim();
  final amt = clean(amount)?.replaceAll(',', '');
  if (clean(text) == null && amt == null) {
    throw const FormatException('Describe the entry or give at least the amount');
  }
  if (amt != null && (double.tryParse(amt) == null || double.parse(amt) <= 0)) {
    throw const FormatException('The amount must be a positive number');
  }
  return {
    if (clean(text) != null) 'text': clean(text),
    if (voucherType != null) 'voucher_type': voucherType,
    if (amt != null) 'amount': amt,
    if (date != null)
      'voucher_date': '${date.year.toString().padLeft(4, '0')}-${date.month.toString().padLeft(2, '0')}-${date.day.toString().padLeft(2, '0')}',
    if (vendorId != null) 'vendor_id': vendorId,
    if (ledgerId != null) 'ledger_id': ledgerId,
    if (moneyAccount != null) 'money_account': moneyAccount,
    if (clean(reference) != null) 'reference': clean(reference),
    if (clean(narration) != null) 'narration': clean(narration),
    'save': save,
  };
}

class NoticeDraftResult {
  final String kind;
  final String title;
  final String? content; // meetings
  final List<String> agendaItems;
  final List<Map<String, dynamic>> bylawRefs;
  final List<Map<String, dynamic>> dues; // one reminder per flat (DUES)
  final List<String> savedNoticeIds;
  const NoticeDraftResult(this.kind, this.title, this.content, this.agendaItems, this.bylawRefs, this.dues, this.savedNoticeIds);
  factory NoticeDraftResult.fromJson(Map<String, dynamic> j) => NoticeDraftResult(
        j['kind'] as String? ?? '',
        j['title'] as String? ?? '',
        j['content'] as String?,
        [for (final a in (j['agenda_items'] as List? ?? const [])) '$a'],
        _maps(j['bylaw_refs']),
        _maps(j['drafts']),
        [for (final x in (j['saved_notice_ids'] as List? ?? const [])) '$x'],
      );
}

class AssistApi {
  final Dio _dio;
  AssistApi({Dio? dio}) : _dio = dio ?? ApiClient.instance;
  static const _base = '/accounts-agent';

  Future<BylawAnswer> askBylaws(String question) async => BylawAnswer.fromJson(
      (await _dio.post('$_base/bylaws/ask', data: {'question': question})).data as Map<String, dynamic>);

  Future<EntryDraftResult> draftEntry(Map<String, dynamic> payload) async =>
      EntryDraftResult.fromJson((await _dio.post('$_base/entries/draft', data: payload)).data as Map<String, dynamic>);

  Future<NoticeDraftResult> draftNotice(Map<String, dynamic> payload) async =>
      NoticeDraftResult.fromJson((await _dio.post('$_base/notices/draft', data: payload)).data as Map<String, dynamic>);
}
