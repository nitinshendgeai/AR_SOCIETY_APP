"""Real-PostgreSQL checks (outbox atomicity under true transactions, FOR UPDATE SKIP LOCKED claiming).

Skipped unless AGENT_TEST_PG_URL points at a THROWAWAY PostgreSQL database, e.g.
    AGENT_TEST_PG_URL=postgresql://postgres@localhost:5432/agent_test pytest tests/accounts_agent/test_postgres_integration.py
The schema is created (and dropped) by the test run."""
import os
import uuid
from datetime import datetime

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

PG = os.environ.get("AGENT_TEST_PG_URL")
pytestmark = pytest.mark.skipif(not PG, reason="AGENT_TEST_PG_URL not set")


@pytest.fixture(scope="module")
def pg():
    import app.models  # noqa: F401
    from app.core.rbac_seed import seed_form_definitions, seed_permission_definitions
    from app.db.base import Base
    engine = create_engine(PG)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        seed_permission_definitions(conn)
        seed_form_definitions(conn)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


def _setup(pg):
    from app.models.society import Society
    from app.modules.accounts.services.accounts_service import AccountsService
    with Session(pg) as s:
        soc = Society(name=f"PG {uuid.uuid4().hex[:8]}", city="Pune", state="MH")
        s.add(soc); s.commit()
        chart = AccountsService(s).ensure_chart(soc.id); s.commit()
        return soc.id, {k: a.id for k, a in chart.items()}


def _post(s, sid, ids, amount="100.00"):
    from decimal import Decimal
    from datetime import date
    from app.modules.accounts.models.accounts import Account
    from app.modules.accounts.services.accounts_service import AccountsService, Line
    a, b = s.get(Account, ids["office_expenses"]), s.get(Account, ids["bank"])
    return AccountsService(s).build_voucher(sid, "payment", date.today(), [Line(a, debit=Decimal(amount)), Line(b, credit=Decimal(amount))])


def _events(pg, sid):
    with pg.connect() as c:
        return c.execute(text("select count(*) from accounts_agent_events where society_id=:s"), {"s": sid}).scalar()


def test_event_commits_with_the_voucher_and_vanishes_on_rollback(pg):
    sid, ids = _setup(pg)
    with Session(pg) as s:
        _post(s, sid, ids); s.commit()
    assert _events(pg, sid) == 1
    with Session(pg) as s:
        _post(s, sid, ids); s.rollback()
    assert _events(pg, sid) == 1                      # the rolled-back posting left no event
    with Session(pg) as s:
        try:
            with s.begin_nested():
                _post(s, sid, ids)
                raise RuntimeError("posting hook failed")
        except RuntimeError:
            pass
        s.commit()
    assert _events(pg, sid) == 1


def test_broken_agent_table_cannot_abort_a_posting(pg, monkeypatch):
    from app.modules.accounts_agent.services import outbox
    sid, ids = _setup(pg)
    real = outbox._insert_ignoring_duplicates

    def bad(connection, rows):                        # a failing SQL statement inside the savepoint
        connection.execute(text("insert into accounts_agent_events (id) values (null)"))
    monkeypatch.setattr(outbox, "_insert_ignoring_duplicates", bad)
    with Session(pg) as s:
        v = _post(s, sid, ids); s.commit()            # PostgreSQL would normally mark the transaction aborted
        vid = v.id
    from app.modules.accounts.models.accounts import Voucher
    with Session(pg) as s:
        assert s.get(Voucher, vid) is not None
    assert _events(pg, sid) == 0


def test_two_workers_claim_disjoint_batches(pg):
    from app.modules.accounts_agent import worker
    sid, ids = _setup(pg)
    with Session(pg) as s:
        for _ in range(6):
            _post(s, sid, ids)
        s.commit()
    s1, s2 = Session(pg), Session(pg)
    try:
        q = lambda s: s.query(worker.AgentEvent).filter(worker.AgentEvent.society_id == sid, worker.AgentEvent.status == "pending") \
            .order_by(worker.AgentEvent.created_at).limit(3).with_for_update(skip_locked=True)   # noqa: E731
        a = {e.id for e in q(s1).all()}
        b = {e.id for e in q(s2).all()}                # s1 still holds its row locks
        assert len(a) == 3 and len(b) == 3 and not a & b
    finally:
        s1.rollback(); s2.rollback(); s1.close(); s2.close()
    # and the real claim function is usable end to end
    with Session(pg) as s:
        got = worker.claim_batch(s, "pgw", limit=10)
        assert len(got) >= 6                       # earlier tests left their own events pending too
        assert worker.claim_batch(s, "pgw2", limit=10) == []
