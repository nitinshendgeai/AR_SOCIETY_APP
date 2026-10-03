"""Errors no route handled still reach the browser: JSON with the CORS
headers (a cross-origin reply without them is dropped and the app shows
"could not reach the server"), and a database behind the code says so."""
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError, ProgrammingError

from app.main import app

ORIGIN = {"Origin": "https://society.duxos.in"}


def _raise(exc):
    def endpoint():
        raise exc
    return endpoint


@pytest.fixture(scope="module")
def raw_client():
    app.add_api_route("/_test/boom", _raise(RuntimeError("boom")))
    app.add_api_route("/_test/no-table", _raise(OperationalError("SELECT 1", {}, Exception("no such table: work_orders"))))
    app.add_api_route("/_test/pg-no-table",
                      _raise(ProgrammingError("SELECT 1", {}, SimpleNamespace(pgcode="42P01"))))
    app.add_api_route("/_test/pg-other", _raise(ProgrammingError("SELECT 1", {}, SimpleNamespace(pgcode="42601"))))
    return TestClient(app, raise_server_exceptions=False)


def test_an_unhandled_error_is_json_with_cors_headers(raw_client):
    r = raw_client.get("/_test/boom", headers=ORIGIN)
    assert r.status_code == 500
    assert r.headers.get("access-control-allow-origin")
    assert r.json()["code"] == "INTERNAL_ERROR"


@pytest.mark.parametrize("path", ["/_test/no-table", "/_test/pg-no-table"])
def test_a_missing_table_says_the_database_needs_updating(raw_client, path):
    r = raw_client.get(path, headers=ORIGIN)
    assert r.status_code == 503
    assert r.headers.get("access-control-allow-origin")
    assert r.json()["code"] == "SCHEMA_OUTDATED"
    assert "database" in r.json()["message"]


def test_other_database_errors_stay_internal_errors(raw_client):
    r = raw_client.get("/_test/pg-other", headers=ORIGIN)
    assert r.status_code == 500 and r.json()["code"] == "INTERNAL_ERROR"


def test_health_reports_migration_status(raw_client):
    r = raw_client.get("/health")
    assert r.status_code == 200
    assert "migrations" in r.json()
