"""The books can be limited to the residents' vouchers or to the society's own (operations): the Cash and Bank Book,
a ledger statement, the Expenses register and the Trial Balance, Income & Expenditure and Receipts & Payments reports.
Everything together is still the default, and the two halves add up to it."""
from decimal import Decimal

from tests.accounts.test_reports import API, _amount, _books, _report


def _book(client, h, sid, **params):
    r = client.get(f"{API}/registers/cash-bank/{sid}", params=params, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def test_cash_and_bank_book_split_into_residents_and_operations(client, db):
    society, _flat, admin, *_ = _books(client, db, "sc1")
    h, sid = admin["headers"], str(society.id)
    everything = _book(client, h, sid)
    mine = _book(client, h, sid, scope="members")
    ours = _book(client, h, sid, scope="society")

    assert everything["scope"] is None and everything["totals"]["receipts"] == "46000.00"
    assert everything["totals"]["payments"] == "30000.00"
    # the residents' side: what a flat paid; nothing paid out
    assert mine["scope"] == "members" and mine["scope_label"]
    assert mine["totals"]["receipts"] == "45000.00" and mine["totals"]["payments"] == "0.00"
    # operations: the interest in and the electricity out
    assert ours["totals"]["receipts"] == "1000.00" and ours["totals"]["payments"] == "30000.00"
    # the halves add up to the whole
    for key in ("receipts", "payments"):
        assert Decimal(mine["totals"][key]) + Decimal(ours["totals"][key]) == Decimal(everything["totals"][key])
    # the accounts' own opening balance belongs to neither half
    assert mine["totals"]["opening"] == "0.00" == ours["totals"]["opening"]
    assert everything["totals"]["opening"] == "100000.00"
    # every line shown is of that scope's vouchers
    assert all(l["voucher_type"] == "receipt" for s in mine["sections"] for l in s["lines"])
    assert client.get(f"{API}/registers/cash-bank/{sid}", params={"scope": "members", "format": "pdf"},
                      headers=h).status_code == 200


def test_ledger_statement_and_expenses_register_take_the_scope(client, db):
    society, _flat, admin, _m, _r, L = _books(client, db, "sc2")
    h, sid = admin["headers"], str(society.id)
    st = client.get(f"{API}/ledgers/{L['bank']['id']}/statement", params={"scope": "society"}, headers=h).json()
    assert st["scope"] == "society" and st["total_debit"] == "1000.00" and st["total_credit"] == "30000.00"
    assert st["opening"] == "0.00"
    own = client.get(f"{API}/registers/expenses/{sid}", params={"scope": "society"}, headers=h).json()
    assert [r["head"] for r in own["rows"]] == ["Electricity Charges (Common Areas)"]
    assert "Operations" in own["subtitle"]
    mine = client.get(f"{API}/registers/expenses/{sid}", params={"scope": "members"}, headers=h).json()
    assert mine["rows"] == []


def test_reports_split_and_the_balance_sheet_stays_whole(client, db):
    society, _flat, admin, *_ = _books(client, db, "sc3")
    h, sid = admin["headers"], str(society.id)

    ie_mine = _report_scoped(client, h, sid, "income-expenditure", "members")
    exp, inc = ie_mine["sides"]
    assert _amount(inc["sections"], "Service Charges") == 50000
    assert ie_mine["heading"].endswith("Residents' accounts only") and ie_mine["scope"] == "members"
    assert not any(r["label"] == "Electricity Charges (Common Areas)" for s in exp["sections"] for r in s["rows"])

    ie_ours = _report_scoped(client, h, sid, "income-expenditure", "society")
    exp, inc = ie_ours["sides"]
    assert _amount(exp["sections"], "Electricity Charges (Common Areas)") == 30000
    assert ie_ours["heading"].endswith("Operations only")
    assert not any(r["label"] == "Service Charges" for s in inc["sections"] for r in s["rows"])

    rp = _report_scoped(client, h, sid, "receipts-payments", "society")
    assert rp["balanced"]
    rp_mine = _report_scoped(client, h, sid, "receipts-payments", "members")
    assert rp_mine["balanced"]
    tb = _report_scoped(client, h, sid, "trial-balance", "society")
    assert tb["balanced"]

    # unscoped is unchanged
    assert _report(client, h, sid, "income-expenditure", "2024-25")["result"]["amounts"][0] == "21000.00"
    # the balance sheet and funds can't be split
    r = client.get(f"{API}/reports/{sid}/balance-sheet", params={"fy": "2024-25", "scope": "members"}, headers=h)
    assert r.status_code == 422
    assert client.get(f"{API}/reports/{sid}/income-expenditure",
                      params={"fy": "2024-25", "scope": "members", "format": "pdf"}, headers=h).status_code == 200


def test_an_unknown_scope_is_refused(client, db):
    society, _flat, admin, *_ = _books(client, db, "sc4")
    h, sid = admin["headers"], str(society.id)
    assert client.get(f"{API}/registers/cash-bank/{sid}", params={"scope": "everyone"}, headers=h).status_code == 422
    assert client.get(f"{API}/reports/{sid}/trial-balance", params={"scope": "x"}, headers=h).status_code == 422


def _report_scoped(client, h, sid, report, scope):
    r = client.get(f"{API}/reports/{sid}/{report}", params={"fy": "2024-25", "scope": scope}, headers=h)
    assert r.status_code == 200, r.text
    return r.json()
