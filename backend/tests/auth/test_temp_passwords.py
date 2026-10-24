"""No account the system creates for someone else starts with a password that anyone could know in advance: each gets
its own random temporary password, shown once to whoever created it, and the account must change it at first sign-in."""
import re
from pathlib import Path

from app.core.passwords import generate_temp_password

API = "/api/v1"
OLD_DEFAULTS = ("Staff@1234", "admin1234", "Admin@1234")


def test_generator_makes_long_mixed_unique_passwords():
    seen = {generate_temp_password() for _ in range(300)}
    assert len(seen) == 300, "passwords repeated"
    for pwd in seen:
        assert len(pwd) == 12
        assert re.search(r"[A-Z]", pwd) and re.search(r"[a-z]", pwd) and re.search(r"\d", pwd)
        assert not set(pwd) & set("0Oo1lI"), "look-alike characters are left out"
    assert generate_temp_password(16) and len(generate_temp_password(16)) == 16


def test_no_fixed_default_password_in_the_application_code():
    """A fixed default is known to anyone who has read the code or a screen. Fail if one is put back."""
    app = Path(__file__).resolve().parents[2] / "app"
    hits = [f"{p.relative_to(app)}: {old}"
            for p in app.rglob("*.py") for old in OLD_DEFAULTS if old in p.read_text(encoding="utf-8")]
    assert not hits, f"fixed default password in the code: {hits}"


def _staff(client, headers, society_id, n):
    r = client.post(f"{API}/staff/", json={"society_id": str(society_id), "full_name": f"Staff {n}",
                                           "mobile": f"98120009{n:02d}", "email": f"s{n}@tempstaff.io",
                                           "department": "security"}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["temp_password"]


def test_each_new_staff_login_has_its_own_password(client, db):
    from tests.conftest import make_society, make_user
    from tests.staff.test_acceptance import _seed_roles
    _seed_roles(db)
    society = make_society(db, "Temp Staff Society")
    admin = make_user(db, "adm@tempstaff.io", role="Society Admin")
    first, second = (_staff(client, admin["headers"], society.id, n) for n in (1, 2))
    assert first != second
    assert not {first, second} & set(OLD_DEFAULTS)
    login = client.post(f"{API}/auth/login", json={"email": "s1@tempstaff.io", "password": first})
    assert login.status_code == 200
    # a password belongs to one login: the second person's does not open the first person's account
    wrong = client.post(f"{API}/auth/login", json={"email": "s1@tempstaff.io", "password": second})
    assert wrong.status_code == 401


def test_each_new_resident_login_has_its_own_password(client, db):
    from tests.conftest import make_flat, make_society, make_user, make_wing
    society = make_society(db, "Temp Resident Society")
    flat = make_flat(db, make_wing(db, society.id, "A").id, "101")
    admin = make_user(db, "adm@tempres.io", role="Society Admin")
    admin["user"].society_id = society.id
    db.commit()
    shown = []
    for n, phone in enumerate(("9000000071", "9000000072")):
        r = client.post(f"{API}/residents/", json={"flat_id": str(flat.id), "full_name": f"Person {n}",
                                                   "phone": phone}, headers=admin["headers"])
        assert r.status_code == 201, r.text
        shown.append(next(w for w in r.json()["warnings"] if "Password: " in w).split("Password: ", 1)[1].split(" ")[0])
    assert shown[0] != shown[1]
    assert not set(shown) & set(OLD_DEFAULTS)
    assert phone not in shown[1], "the password is not derived from the mobile number"


def test_each_first_account_of_a_new_society_has_its_own_password(client):
    payload = {"society_name": "Temp Pwd One", "society_code": "TPW001", "contact_person_name": "A B",
               "contact_email": "a@tpw001.example.com", "contact_mobile": "9876500101", "city": "Pune",
               "state": "Maharashtra", "country": "India", "total_wings": 1, "total_flats": 10, "terms_accepted": True}
    one = client.post(f"{API}/public/register", json=payload)
    two = client.post(f"{API}/public/register", json={**payload, "society_name": "Temp Pwd Two",
                                                      "society_code": "TPW002", "contact_email": "a@tpw002.example.com",
                                                      "contact_mobile": "9876500102"})
    assert one.status_code == 201 and two.status_code == 201, (one.text, two.text)
    p1 = [c["password"] for c in one.json()["credentials"]]
    p2 = [c["password"] for c in two.json()["credentials"]]
    assert len(p1) == 4 and len(set(p1)) == 4, "each of the four accounts has its own password"
    assert len(set(p1) | set(p2)) == 8, "and none is shared with the next society"
    assert not (set(p1) | set(p2)) & set(OLD_DEFAULTS)
    # one account's password does not open another's
    chairman = next(c for c in one.json()["credentials"] if c["role"] == "Committee Chairman")
    admin_pw = next(c["password"] for c in one.json()["credentials"] if c["role"] == "Society Admin")
    assert client.post(f"{API}/auth/login", json={"email": chairman["email"], "password": admin_pw}).status_code == 401
    admin = next(c for c in one.json()["credentials"] if c["role"] == "Society Admin")
    assert client.post(f"{API}/auth/login", json={"email": admin["email"], "password": admin["password"]}).status_code == 200
    old = client.post(f"{API}/auth/login", json={"email": admin["email"], "password": "Admin@1234"})
    assert old.status_code == 401


def test_report_lists_accounts_that_still_have_a_retired_default(db):
    """The read-only report finds accounts made before the change; an account with its own password is not listed."""
    import importlib.util
    from app.core.security import hash_password
    from app.models.user import User, UserStatus
    path = Path(__file__).resolve().parents[2] / "scripts" / "report_default_password_accounts.py"
    spec = importlib.util.spec_from_file_location("report_default_password_accounts", path)
    report = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(report)

    old = User(email="old.default@example.com", full_name="Old Default", hashed_password=hash_password("Staff@1234"),
               status=UserStatus.ACTIVE, must_change_password=True)
    safe = User(email="own.password@example.com", full_name="Own Password", hashed_password=hash_password(generate_temp_password()),
                status=UserStatus.ACTIVE, must_change_password=False)
    db.add_all([old, safe])
    db.commit()
    listed = {u.email for u, _ in report.find_default_password_accounts(db)}
    assert "old.default@example.com" in listed
    assert "own.password@example.com" not in listed
