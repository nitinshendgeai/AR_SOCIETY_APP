"""Read-only configuration diagnostics.

Every check is its own SELECT, filtered by society_id in the query itself, returning only counts / booleans — never a
row, name, amount, resident, vendor or account detail. None of them calls an existing service or route (those seed
defaults and commit on a plain GET: AccountsService.ensure_chart, BillingService.list_elements, vendor_tds.
ensure_default_rules). `read_only_session` additionally refuses any flush or commit while a check runs and, on
PostgreSQL, puts the transaction in read-only mode.
"""
from contextlib import contextmanager
from typing import Callable, Dict, List
from uuid import UUID

from sqlalchemy import event, func, text
from sqlalchemy.orm import Session

from app.modules.accounts.models.accounts import Account
from app.modules.accounts.models.taxes import TaxConfiguration
from app.modules.assistant.schemas import Finding
from app.modules.billing.models.billing import MaintenanceChargeConfig, MaintenanceElement, MaintenanceSettings


class ReadOnlyViolation(RuntimeError):
    pass


@contextmanager
def read_only_session(db: Session):
    """Makes `db` refuse every write (flush or commit) for the duration of the block. The request's session is closed
    by get_db afterwards, which ends the read transaction."""
    def _no_flush(session, flush_context, instances):
        if session.new or session.dirty or session.deleted:
            raise ReadOnlyViolation("the assistant attempted to change data")

    def _no_commit(*a, **k):
        raise ReadOnlyViolation("the assistant attempted to commit")

    event.listen(db, "before_flush", _no_flush)
    original_commit = db.__dict__.get("commit")
    db.commit = _no_commit
    try:
        if db.get_bind().dialect.name == "postgresql":
            db.execute(text("SET LOCAL transaction_read_only = on"))
        yield db
    finally:
        event.remove(db, "before_flush", _no_flush)
        if original_commit is None:
            del db.__dict__["commit"]
        else:
            db.commit = original_commit


def _count(db: Session, column_or_entity, *filters) -> int:
    return int(db.query(func.count(column_or_entity)).filter(*filters).scalar() or 0)


def check_maintenance_elements(db: Session, sid: UUID) -> Finding:
    active = _count(db, MaintenanceElement.id, MaintenanceElement.society_id == sid, MaintenanceElement.is_active == True)  # noqa: E712
    if active == 0:
        return Finding(topic="maintenance_elements", status="not_initialised", count=0,
                       message="No maintenance elements are set up yet. Open Maintenance Billing → Elements to create "
                               "the standard elements, then follow the Element-wise Help Manual.")
    unlinked = _count(db, MaintenanceElement.id, MaintenanceElement.society_id == sid, MaintenanceElement.is_active == True,  # noqa: E712
                      ~MaintenanceElement.id.in_(db.query(Account.maintenance_element_id).filter(
                          Account.society_id == sid, Account.maintenance_element_id.isnot(None))))
    if unlinked:
        return Finding(topic="maintenance_elements", status="gap", count=unlinked,
                       message=f"{unlinked} of {active} active maintenance elements have no expense ledger linked, so "
                               "spend on them cannot feed the monthly maintenance. See the manual's section on linking.")
    return Finding(topic="maintenance_elements", status="ok", count=active,
                   message=f"{active} active maintenance elements, each with a linked expense ledger.")


def check_chart_of_accounts(db: Session, sid: UUID) -> Finding:
    system = _count(db, Account.id, Account.society_id == sid, Account.system_key.isnot(None))
    if system == 0:
        return Finding(topic="chart_of_accounts", status="not_initialised", count=0,
                       message="The society's books have not been opened yet (no standard chart of accounts). They "
                               "are created the first time an authorised person opens Accounts.")
    bank = _count(db, Account.id, Account.society_id == sid, Account.is_default_bank == True, Account.is_active == True)  # noqa: E712
    if bank == 0:
        return Finding(topic="chart_of_accounts", status="gap", count=system,
                       message="The chart of accounts exists but no active default bank ledger is set. See the "
                               "Accounts guide on bank ledgers.")
    return Finding(topic="chart_of_accounts", status="ok", count=system,
                   message="The chart of accounts is set up with a default bank ledger.")


def check_billing_setup(db: Session, sid: UUID) -> Finding:
    charges = _count(db, MaintenanceChargeConfig.id, MaintenanceChargeConfig.society_id == sid)
    settings_row = _count(db, MaintenanceSettings.id, MaintenanceSettings.society_id == sid)
    if charges == 0:
        return Finding(topic="billing_setup", status="gap", count=0,
                       message="No maintenance charge heads are configured, so a bill cycle would have nothing to "
                               "bill. See the Maintenance Billing guide, 'Set up the charges'.")
    note = "" if settings_row else " Society-wide billing rules are still at their defaults."
    return Finding(topic="billing_setup", status="ok", count=charges,
                   message=f"{charges} maintenance charge heads are configured.{note}")


def check_vendor_tds(db: Session, sid: UUID) -> Finding:
    rules = _count(db, TaxConfiguration.id, TaxConfiguration.society_id == sid, TaxConfiguration.tax_type == "TDS",
                   TaxConfiguration.is_active == True)  # noqa: E712
    if rules == 0:
        return Finding(topic="vendor_tds", status="not_initialised", count=0,
                       message="No TDS rules are stored yet. The starting rates are filled in the first time an "
                               "authorised person opens the TDS rules screen; review them against the Vendor guide.")
    return Finding(topic="vendor_tds", status="ok", count=rules, message=f"{rules} active TDS rules are configured.")


# topic → (check, the optional service it belongs to, or None for core). Order is the report order.
TOPICS: Dict[str, "tuple[Callable[[Session, UUID], Finding], str | None]"] = {
    "maintenance_elements": (check_maintenance_elements, None),
    "billing_setup": (check_billing_setup, None),
    "chart_of_accounts": (check_chart_of_accounts, "accounts"),
    "vendor_tds": (check_vendor_tds, "vendors"),
}

_KEYWORDS = {
    "maintenance_elements": ("element", "elements"),
    "billing_setup": ("bill", "billing", "maintenance", "cycle", "charge"),
    "chart_of_accounts": ("account", "accounts", "ledger", "chart", "bank", "voucher"),
    "vendor_tds": ("vendor", "tds", "contract", "work order"),
}


def topics_for_question(question: str) -> List[str]:
    q = question.lower()
    return [t for t, words in _KEYWORDS.items() if any(w in q for w in words)]


def run_diagnostics(db: Session, society_id: UUID, topics: List[str], enabled_services: set) -> List[Finding]:
    """Runs the requested topics for one society. A topic whose service the platform has switched off for that society
    is reported as unavailable without being queried."""
    findings: List[Finding] = []
    with read_only_session(db):
        for topic in topics:
            check, service = TOPICS[topic]
            if service is not None and service not in enabled_services:
                findings.append(Finding(topic=topic, status="unavailable",
                                        message="This area is not enabled for the society."))
                continue
            findings.append(check(db, society_id))
    return findings
