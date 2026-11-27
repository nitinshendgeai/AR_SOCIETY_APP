import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/features/accounts_agent/data/accounts_agent_api.dart';
import 'package:ar_society_app/features/accounts_agent/data/assist_api.dart';
import 'package:ar_society_app/features/accounts_agent/presentation/screens/agent_notice_draft_screen.dart';

Dio _server(List<RequestOptions> seen, Object reply) {
  final dio = Dio();
  dio.interceptors.add(InterceptorsWrapper(onRequest: (options, handler) {
    seen.add(options);
    handler.resolve(Response(requestOptions: options, statusCode: 200, data: reply));
  }));
  return dio;
}

void main() {
  test('a bye-law answer keeps its clause references and flags', () async {
    final seen = <RequestOptions>[];
    final a = await AssistApi(dio: _server(seen, {
      'answer': 'Fourteen clear days [C1].', 'answered_by_sources': true, 'needs_professional_review': false,
      'ai_generated': true, 'notes': ['Based on the model bye-laws'], 'society_facts': null,
      'disclaimer': 'Not legal advice.',
      'sources': [
        {'cite': 'C1', 'clause_ref': '12', 'heading': 'Notice of general meeting', 'page': 3, 'source': 'Model bye-laws',
         'document_title': 'Model bye-laws', 'society_specific': false, 'document_verified': true, 'clause_verified': false,
         'cited': true, 'text': '12. Notice …'},
        {'cite': 'C2', 'clause_ref': '13', 'source': 'Model bye-laws', 'document_title': 'Model bye-laws',
         'society_specific': false, 'cited': false, 'text': '13. Quorum …'},
      ],
    })).askBylaws('How many days notice for the AGM?');
    expect(seen.single.path, '/accounts-agent/bylaws/ask');
    expect(seen.single.data, {'question': 'How many days notice for the AGM?'});
    expect(a.aiGenerated, isTrue);
    expect(a.cited.map((s) => s.cite), ['C1']);
    expect(a.cited.single.label, 'Model bye-laws — clause 12, page 3');
    expect(a.cited.single.verified, isFalse); // the clause itself is not verified
  });

  test('the entry form sends only what was given, and needs an amount or a description', () {
    expect(() => entryDraftPayload(save: false), throwsFormatException);
    expect(() => entryDraftPayload(amount: '-5', save: false), throwsFormatException);
    expect(() => entryDraftPayload(amount: 'abc', save: false), throwsFormatException);
    expect(entryDraftPayload(text: ' paid lift AMC ', save: false), {'text': 'paid lift AMC', 'save': false});
    expect(
      entryDraftPayload(voucherType: 'payment', amount: '12,000', date: DateTime(2026, 11, 3), ledgerId: 'L1',
          moneyAccount: 'bank', reference: ' CP-NOV ', narration: '', save: true),
      {'voucher_type': 'payment', 'amount': '12000', 'voucher_date': '2026-11-03', 'ledger_id': 'L1',
       'money_account': 'bank', 'reference': 'CP-NOV', 'save': true},
    );
  });

  test('a saved entry is reported as pending', () async {
    final seen = <RequestOptions>[];
    final r = await AssistApi(dio: _server(seen, {
      'voucher_type': 'payment', 'voucher_date': '2026-11-03', 'amount': '12000.00', 'saved': true,
      'voucher_number': 'PV/2026-27/0040', 'approval_status': 'pending', 'basis': ['Ledger chosen by you.'], 'unclear': [],
      'lines': [
        {'account': 'Housekeeping & Cleaning', 'debit': '12000.00', 'credit': '0'},
        {'account': 'Bank Account', 'debit': '0', 'credit': '12000.00'},
      ],
    })).draftEntry(entryDraftPayload(amount: '12000', save: true));
    expect(seen.single.path, '/accounts-agent/entries/draft');
    expect(r.saved, isTrue);
    expect(r.approvalStatus, 'pending');
    expect(r.lines.first.debit, 12000);
  });

  test('notice form payloads', () {
    expect(() => noticeDraftPayload(kind: 'SGM', save: false), throwsFormatException);
    expect(
      noticeDraftPayload(kind: 'SGM', subject: ' Terrace repairs ', resolutions: 'Approve ₹1,50,000\n\n Appoint contractor ',
          meetingDate: DateTime(2026, 12, 6), venue: 'Clubhouse', save: false),
      {'kind': 'SGM', 'meeting_date': '2026-12-06', 'venue': 'Clubhouse', 'subject': 'Terrace repairs',
       'resolutions': ['Approve ₹1,50,000', 'Appoint contractor'], 'save': false},
    );
    expect(noticeDraftPayload(kind: 'DUES', onlyDefaulters: false, save: true),
        {'kind': 'DUES', 'only_defaulters': false, 'pay_within_days': 15, 'save': true});
  });

  test('dues drafts and saved ids are parsed', () async {
    final seen = <RequestOptions>[];
    final r = await AssistApi(dio: _server(seen, {
      'kind': 'DUES', 'title': 'Dues reminders (1 flat(s))', 'content': null, 'agenda_items': null, 'bylaw_refs': [],
      'drafts': [{'flat': 'A-101', 'outstanding': '3000.00', 'content': '…'}], 'saved_notice_ids': ['n1'],
    })).draftNotice({'kind': 'DUES', 'save': true});
    expect(seen.single.path, '/accounts-agent/notices/draft');
    expect(r.dues.single['flat'], 'A-101');
    expect(r.savedNoticeIds, ['n1']);
  });

  test('a reused answer says it cost no AI tokens', () async {
    final a = await AssistApi(dio: _server([], {
      'answer': 'Fourteen clear days [C1].', 'answered_by_sources': true, 'needs_professional_review': false,
      'ai_generated': true, 'notes': [], 'disclaimer': '', 'sources': [],
      'answered_from': 'saved_answer', 'token_note': 'Same question answered before: no AI tokens used.',
    })).askBylaws('सभेसाठी किती दिवसांची नोटीस?');
    expect(a.answeredFrom, 'saved_answer');
    expect(a.tokenNote, contains('no AI tokens'));
    final old = await AssistApi(dio: _server([], {'answer': 'x', 'sources': []})).askBylaws('q');
    expect(old.answeredFrom, 'library');          // an older server without the fields
    expect(old.tokenNote, isNull);
  });

  test('AI usage for the month is read with its savings', () async {
    final seen = <RequestOptions>[];
    final u = await AccountsAgentApi(dio: _server(seen, {
      'month': '2026-11', 'budget_tokens': 300000, 'spent_tokens': 4200, 'left_tokens': 295800, 'used_pct': 1.4,
      'requests': 10, 'answered_without_ai': 7, 'without_ai_pct': 70.0, 'ai_calls': 3, 'reused_answers': 5,
      'answered_locally': 2, 'over_budget': 0, 'failed_calls': 0, 'kept_answers': 3, 'ai_enabled': true,
      'by_feature': [
        {'feature': 'bylaw_answer', 'label': 'Bye-law answers', 'ai_calls': 3, 'input_tokens': 3600, 'output_tokens': 600,
         'reused_answers': 5, 'answered_locally': 1, 'over_budget': 0},
      ],
    })).aiUsage();
    expect(seen.single.path, '/accounts-agent/ai-usage');
    expect(u.spentTokens, 4200);
    expect(u.answeredWithoutAi, 7);
    expect(u.byFeature.single.tokens, 4200);
    expect(u.byFeature.single.withoutAi, 6);
  });

  test('a member payment comes back as a hand-off to Billing, not a voucher', () async {
    final r = await AssistApi(dio: _server([], {
      'redirect': {'kind': 'member_receipt', 'flat': 'A Wing 101', 'amount': '3500.00',
                   'message': "This is a member's payment from A Wing 101.", 'accounting': "Dr Bank / Cash · Cr Members' Dues (that flat)"},
      'saved': false, 'lines': [], 'basis': [], 'unclear': [],
    })).draftEntry(entryDraftPayload(text: 'received 3500 from A-101', save: false));
    expect(r.redirect?.kind, 'member_receipt');
    expect(r.redirect?.flat, 'A Wing 101');
    expect(r.redirect?.accounting, contains("Members' Dues"));
    expect(r.lines, isEmpty);
  });

  test('a vendor payment can be confirmed as not for the booked bills', () {
    expect(entryDraftPayload(amount: '500', notAgainstBill: true, save: false),
        {'amount': '500', 'not_against_bill': true, 'save': false});
    expect(entryDraftPayload(amount: '500', save: false).containsKey('not_against_bill'), isFalse);
  });
}
