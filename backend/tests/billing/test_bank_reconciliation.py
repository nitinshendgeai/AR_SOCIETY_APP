"""Bank Reconciliation — import a bank statement and match it against
PENDING online payment submissions to confirm they actually landed."""
import io
from datetime import date, timedelta
import pytest
from tests.conftest import make_user, make_society, make_wing, make_flat


def _rig(db):
    society = make_society(db, "Reco Society")
    wing = make_wing(db, society.id, "Wing A")
    flat = make_flat(db, wing.id, "A-101")
    manager = make_user(db, "manager@reco.com", role="Manager")
    resident = make_user(db, "resident@reco.com", role="Resident")
    return society, wing, flat, manager, resident


def _submit_online_payment(client, flat_id, headers, amount="5500.00", payment_date=None, mode="upi"):
    data = {
        "flat_id": str(flat_id),
        "amount": amount,
        "payment_date": str(payment_date or date.today()),
        "payment_mode": mode,
        "transaction_ref": "UTR999",
    }
    files = {"screenshot": ("upi.jpg", io.BytesIO(b"\xff\xd8\xff\xe0fake"), "image/jpeg")} if mode != "cash" else None
    return client.post("/api/v1/billing/online-payments", data=data, files=files, headers=headers)


def _import_csv(client, society_id, headers, csv_text, filename="statement.csv"):
    return client.post(
        f"/api/v1/billing/bank-reconciliation/society/{society_id}/import",
        files={"statement": (filename, io.BytesIO(csv_text.encode("utf-8")), "text/csv")},
        headers=headers,
    )


def test_import_csv_creates_unmatched_entries(client, db):
    society, wing, flat, manager, resident = _rig(db)
    csv_text = (
        "Date,Description,Reference,Amount\n"
        "2026-01-05,NEFT CR ACME,UTR999,5500.00\n"
    )
    r = _import_csv(client, society.id, manager["headers"], csv_text)
    assert r.status_code == 201, r.text
    body = r.json()
    assert len(body) == 1
    assert body[0]["match_status"] == "unmatched"
    assert body[0]["amount"] == "5500.00"
    assert body[0]["reference"] == "UTR999"


def test_import_csv_missing_required_column_rejected(client, db):
    society, wing, flat, manager, resident = _rig(db)
    csv_text = "Date,Amount\n2026-01-05,5500.00\n"
    r = _import_csv(client, society.id, manager["headers"], csv_text)
    assert r.status_code == 422
    assert "description" in r.json()["detail"].lower()


def test_import_csv_skips_debit_and_blank_rows(client, db):
    society, wing, flat, manager, resident = _rig(db)
    csv_text = (
        "Date,Description,Amount\n"
        "2026-01-05,Credit row,5500.00\n"
        "2026-01-06,Debit row,-1200.00\n"
        ",,\n"
    )
    r = _import_csv(client, society.id, manager["headers"], csv_text)
    assert r.status_code == 201
    body = r.json()
    assert len(body) == 1
    assert body[0]["description"] == "Credit row"


def test_import_csv_bad_date_rejected(client, db):
    society, wing, flat, manager, resident = _rig(db)
    csv_text = "Date,Description,Amount\nnot-a-date,Row,5500.00\n"
    r = _import_csv(client, society.id, manager["headers"], csv_text)
    assert r.status_code == 422
    assert "date" in r.json()["detail"].lower()


def test_candidates_suggests_matching_pending_submission(client, db):
    society, wing, flat, manager, resident = _rig(db)
    sub_r = _submit_online_payment(client, flat.id, manager["headers"], amount="5500.00")
    assert sub_r.status_code == 201

    csv_text = "Date,Description,Amount\n" + f"{date.today()},NEFT CR,5500.00\n"
    import_r = _import_csv(client, society.id, manager["headers"], csv_text)
    entry_id = import_r.json()[0]["id"]

    cand_r = client.get(f"/api/v1/billing/bank-reconciliation/{entry_id}/candidates",
                         headers=manager["headers"])
    assert cand_r.status_code == 200
    candidates = cand_r.json()
    assert len(candidates) == 1
    assert candidates[0]["receipt_number"] == sub_r.json()["receipt_number"]


def test_candidates_excludes_non_matching_amount(client, db):
    society, wing, flat, manager, resident = _rig(db)
    _submit_online_payment(client, flat.id, manager["headers"], amount="5500.00")

    csv_text = "Date,Description,Amount\n" + f"{date.today()},NEFT CR,9999.00\n"
    import_r = _import_csv(client, society.id, manager["headers"], csv_text)
    entry_id = import_r.json()[0]["id"]

    cand_r = client.get(f"/api/v1/billing/bank-reconciliation/{entry_id}/candidates",
                         headers=manager["headers"])
    assert cand_r.json() == []


def test_candidates_excludes_dates_outside_match_window(client, db):
    society, wing, flat, manager, resident = _rig(db)
    old_date = date.today() - timedelta(days=30)
    _submit_online_payment(client, flat.id, manager["headers"], amount="5500.00", payment_date=old_date)

    csv_text = "Date,Description,Amount\n" + f"{date.today()},NEFT CR,5500.00\n"
    import_r = _import_csv(client, society.id, manager["headers"], csv_text)
    entry_id = import_r.json()[0]["id"]

    cand_r = client.get(f"/api/v1/billing/bank-reconciliation/{entry_id}/candidates",
                         headers=manager["headers"])
    assert cand_r.json() == []


def test_confirm_match_reconciles_submission_and_marks_entry_matched(client, db):
    society, wing, flat, manager, resident = _rig(db)
    sub_r = _submit_online_payment(client, flat.id, manager["headers"], amount="5500.00")
    submission_id = sub_r.json()["id"]
    assert sub_r.json()["status"] == "pending"

    csv_text = "Date,Description,Amount\n" + f"{date.today()},NEFT CR,5500.00\n"
    import_r = _import_csv(client, society.id, manager["headers"], csv_text)
    entry_id = import_r.json()[0]["id"]

    confirm_r = client.post(f"/api/v1/billing/bank-reconciliation/{entry_id}/confirm",
                             json={"submission_id": submission_id}, headers=manager["headers"])
    assert confirm_r.status_code == 200, confirm_r.text
    body = confirm_r.json()
    assert body["match_status"] == "matched"
    assert body["matched_submission_id"] == submission_id

    sub_check = client.get(f"/api/v1/billing/online-payments/{submission_id}", headers=manager["headers"])
    assert sub_check.json()["status"] == "reconciled"


def test_confirm_match_rejects_amount_mismatch(client, db):
    society, wing, flat, manager, resident = _rig(db)
    sub_r = _submit_online_payment(client, flat.id, manager["headers"], amount="5500.00")
    submission_id = sub_r.json()["id"]

    csv_text = "Date,Description,Amount\n" + f"{date.today()},NEFT CR,9999.00\n"
    import_r = _import_csv(client, society.id, manager["headers"], csv_text)
    entry_id = import_r.json()[0]["id"]

    confirm_r = client.post(f"/api/v1/billing/bank-reconciliation/{entry_id}/confirm",
                             json={"submission_id": submission_id}, headers=manager["headers"])
    assert confirm_r.status_code == 422


def test_confirm_match_rejects_already_matched_entry(client, db):
    society, wing, flat, manager, resident = _rig(db)
    sub1 = _submit_online_payment(client, flat.id, manager["headers"], amount="5500.00")
    sub2 = _submit_online_payment(client, flat.id, manager["headers"], amount="5500.00")

    csv_text = "Date,Description,Amount\n" + f"{date.today()},NEFT CR,5500.00\n"
    import_r = _import_csv(client, society.id, manager["headers"], csv_text)
    entry_id = import_r.json()[0]["id"]

    r1 = client.post(f"/api/v1/billing/bank-reconciliation/{entry_id}/confirm",
                      json={"submission_id": sub1.json()["id"]}, headers=manager["headers"])
    assert r1.status_code == 200

    r2 = client.post(f"/api/v1/billing/bank-reconciliation/{entry_id}/confirm",
                      json={"submission_id": sub2.json()["id"]}, headers=manager["headers"])
    assert r2.status_code == 409


def test_ignore_entry_marks_ignored_with_reason(client, db):
    society, wing, flat, manager, resident = _rig(db)
    csv_text = "Date,Description,Amount\n" + f"{date.today()},Bank interest credit,50.00\n"
    import_r = _import_csv(client, society.id, manager["headers"], csv_text)
    entry_id = import_r.json()[0]["id"]

    r = client.post(f"/api/v1/billing/bank-reconciliation/{entry_id}/ignore",
                     json={"reason": "Bank interest, not a resident payment"}, headers=manager["headers"])
    assert r.status_code == 200
    assert r.json()["match_status"] == "ignored"
    assert r.json()["ignore_reason"] == "Bank interest, not a resident payment"


def test_list_bank_statement_entries_filters_by_match_status(client, db):
    society, wing, flat, manager, resident = _rig(db)
    csv_text = (
        "Date,Description,Amount\n"
        f"{date.today()},Row one,5500.00\n"
        f"{date.today()},Row two,1200.00\n"
    )
    import_r = _import_csv(client, society.id, manager["headers"], csv_text)
    entries = import_r.json()
    client.post(f"/api/v1/billing/bank-reconciliation/{entries[0]['id']}/ignore",
                json={"reason": "test"}, headers=manager["headers"])

    unmatched_r = client.get(f"/api/v1/billing/bank-reconciliation/society/{society.id}",
                              params={"match_status": "unmatched"}, headers=manager["headers"])
    assert len(unmatched_r.json()) == 1
    assert unmatched_r.json()[0]["amount"] == "1200.00"

    ignored_r = client.get(f"/api/v1/billing/bank-reconciliation/society/{society.id}",
                            params={"match_status": "ignored"}, headers=manager["headers"])
    assert len(ignored_r.json()) == 1


def test_resident_cannot_access_bank_reconciliation(client, db):
    society, wing, flat, manager, resident = _rig(db)
    r = client.get(f"/api/v1/billing/bank-reconciliation/society/{society.id}", headers=resident["headers"])
    assert r.status_code == 403
