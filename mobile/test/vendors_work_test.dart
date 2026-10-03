import 'package:flutter_test/flutter_test.dart';
import 'package:ar_society_app/features/vendor/data/vendors_work_api.dart';

Map<String, dynamic> _sanction({String? amount}) => {
      'sanctioned_amount': amount,
      'sanction_level': amount == null ? null : 'general_body',
      'committee_resolution_no': amount == null ? null : 'MC/9',
      'committee_meeting_date': amount == null ? null : '2026-09-20',
      'gb_resolution_no': amount == null ? null : 'SGM/2',
      'gb_meeting_date': amount == null ? null : '2026-09-27',
      'tenders_opened_on': null,
      'selection_reason': null,
      'no_interest_declared': amount != null,
      'sanctioned_by_name': amount == null ? null : 'Asha',
      'sanctioned_at': null,
    };

const _req = {
  'amount': '100000.00',
  'committee_limit': '50000',
  'tender_limit': '50000',
  'min_quotations': 3,
  'needs_tenders': true,
  'needs_general_body': true,
};

const _quote = {
  'id': 'q1',
  'vendor_id': 'v1',
  'vendor_name': 'Aqua Plumbing',
  'vendor_code': 'VND-0001',
  'quotation_ref': 'AQ/1',
  'quotation_date': '2026-09-10',
  'valid_until': null,
  'amount': '84745.76',
  'gst_amount': '15254.24',
  'total_amount': '100000.00',
  'remarks': null,
  'doc_url': null,
  'is_selected': true,
  'is_lowest': true,
};

void main() {
  test('a work order reads its sanction, quotations, requirements and money', () {
    final wo = WorkOrder.fromJson({
      'id': 'w1',
      'society_id': 's1',
      'wo_number': 'WO-2026-0001',
      'title': 'Terrace tanks',
      'scope_of_work': 'Replace tanks',
      'location': 'Terrace',
      'category': 'plumbing',
      'estimated_cost': '90000.00',
      'status': 'issued',
      'status_label': 'Work order issued',
      'vendor_id': 'v1',
      'vendor_name': 'Aqua Plumbing',
      'expense_account_id': null,
      'expense_account_name': null,
      'start_date': '2026-10-05',
      'due_date': null,
      'payment_terms': null,
      'advance_amount': '20000.00',
      'retention_pct': '10.00',
      'defect_liability_months': 12,
      'issued_on': '2026-10-01',
      'completed_on': null,
      'completion_notes': null,
      'certificate_ref': null,
      'certified_by_name': null,
      'retention_due_on': null,
      'retention_released_on': null,
      'cancel_reason': null,
      ..._sanction(amount: '100000.00'),
      'quotations': [_quote],
      'requirements': _req,
      'bills': [
        {
          'id': 'b1', 'invoice_number': 'AQ-55', 'invoice_date': '2026-10-02', 'total_amount': '20000.00',
          'paid_amount': '20000.00', 'outstanding': '0.00', 'is_paid': true,
        }
      ],
      'billed': '20000.00',
      'paid': '20000.00',
      'unbilled': '80000.00',
      'retention_amount': '2000.00',
      'retention_held': '2000.00',
      'payable_now': '0.00',
    });
    expect(wo.sanction.isSanctioned, isTrue);
    expect(wo.sanction.byGeneralBody, isTrue);
    expect(wo.canBill, isTrue);
    expect(wo.canPrint, isTrue);
    expect(wo.isDraft, isFalse);
    expect(wo.hasRetention, isTrue);
    expect(wo.quotations.single.isLowest, isTrue);
    expect(wo.requirements.needsTenders, isTrue);
    expect(wo.requirements.minQuotations, 3);
    expect(wo.bills.single.isPaid, isTrue);
    expect(wo.startDate, DateTime(2026, 10, 5));
  });

  test('a contract waiting for its sanction says so', () {
    final c = AmcContract.fromJson({
      'id': 'c1', 'society_id': 's1', 'contract_number': 'AMC-2026-0001', 'contract_name': 'Lift AMC',
      'vendor_id': 'v1', 'vendor_name': 'Lift Co', 'category': 'lift', 'status': 'draft',
      'start_date': '2026-10-01', 'end_date': '2027-09-30', 'days_to_expiry': 362, 'service_frequency': 'monthly',
      'sla_response_hours': null, 'scope_of_work': null, 'annual_value': null, 'auto_renew': false,
      'renewal_notice_days': 30, 'document_url': null,
      ..._sanction(), 'quotations': [], 'requirements': {..._req, 'amount': null, 'needs_tenders': false,
          'needs_general_body': false, 'min_quotations': 1},
    });
    expect(c.isDraft, isTrue);
    expect(c.sanction.isSanctioned, isFalse);
    expect(c.statusLabel, 'Collecting quotations');
  });

  test('limits and inputs', () {
    final l = ProcurementLimits.fromJson({
      'members': 30, 'bye_law_limit': '50000', 'committee_limit': '50000', 'committee_limit_set': false,
      'tender_limit': '50000', 'tender_limit_set': false, 'min_quotations': 3, 'gb_resolution_no': null,
      'gb_meeting_date': null,
    });
    expect(l.members, 30);
    expect(l.committeeLimitSet, isFalse);

    final q = QuotationInput(vendorId: 'v1', date: DateTime(2026, 9, 10), amount: 100.1, gst: 18.02).toJson();
    expect(q['total_amount'], '118.12');
    expect(q.containsKey('valid_until'), isFalse);

    final s = SanctionInput(
      quotationId: 'q1', committeeResolutionNo: 'MC/1', committeeMeetingDate: DateTime(2026, 9, 20),
      noInterestDeclared: true,
    ).toJson();
    expect(s['committee_meeting_date'], '2026-09-20');
    expect(s.containsKey('gb_resolution_no'), isFalse);
    expect(vendorCategoryLabel('pest_control'), 'Pest control');
  });
}
