"""Bill, receipt, item and asset numbers run per society: the second society's
first one is 00001 too (they were unique platform-wide, so it used to fail)."""
from datetime import date

from app.modules.billing.models.billing import MaintenanceBill
from tests.billing.test_defaulters import _two_cycles
from tests.billing.test_payment_allocation import _pay
from tests.conftest import make_society, make_user
from tests.inventory.test_inventory import _create_item


def test_two_societies_bill_and_receive_with_the_same_numbers(client, db):
    a = _two_cycles(client, db, "ns1")
    b = _two_cycles(client, db, "ns2")
    year = date.today().year
    for society, *_ in (a, b):
        numbers = sorted(x.invoice_number for x in db.query(MaintenanceBill).filter_by(society_id=society.id))
        assert numbers[0] == f"INV-{year}-00001" and len(set(numbers)) == len(numbers)
    p1 = _pay(client, a[3]["headers"], a[1], "100.00")
    p2 = _pay(client, b[3]["headers"], b[1], "100.00")
    assert p1["receipt_number"] == p2["receipt_number"] == f"OPS-{year}-00001"


def test_two_societies_inventory_codes(client, db):
    codes = []
    for i in (1, 2):
        admin = make_user(db, f"nsinv{i}@inv.com", role="Society Admin")
        society = make_society(db, f"Inventory Numbers {i}")
        admin["user"].society_id = society.id
        db.commit()
        r = _create_item(client, admin["headers"], society.id)
        assert r.status_code == 201, r.text
        codes.append(r.json()["item_code"])
    assert codes[0] == codes[1] == "INV-00001"
