# AR Society ERP — Development Commands

.PHONY: test test-security lint check-migrations check-migrations-db seed run

# Run test suite
test:
	DATABASE_URL="sqlite:///./test_ar_society.db" SECRET_KEY="test-secret" \
	python -m pytest tests/ -v

# The Phase 1 authentication / tenant-isolation / RBAC / readiness regression tests only
test-security:
	DATABASE_URL="sqlite:///./test_ar_society.db" SECRET_KEY="test-secret" \
	python -m pytest tests/security -ra -q -o log_cli=false

# No linter or formatter is configured for the backend. `lint` is the syntax + import check CI runs.
lint:
	python -m compileall -q app tests scripts
	DATABASE_URL="sqlite:///./test_ar_society.db" SECRET_KEY="test-secret" \
	python -c "from app.main import app; print('app imports,', len(app.routes), 'routes')"

# Migration history is one unbroken chain with one head (no database needed)
check-migrations:
	python scripts/ci/check_migrations.py graph

# Migration checks against a DISPOSABLE PostgreSQL server (it creates and drops its own databases):
#   make check-migrations-db ADMIN_DB_URL=postgresql://user:password@localhost:5432/postgres
check-migrations-db:
	python scripts/ci/check_migrations.py full --admin-url "$(ADMIN_DB_URL)"

# Run tests with coverage
test-cov:
	DATABASE_URL="sqlite:///./test_ar_society.db" SECRET_KEY="test-secret" \
	python -m pytest tests/ --tb=short -q

# Generate seed data (requires live DB in .env)
seed:
	python -m app.utils.seed

# Start dev server
run:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Alembic shortcuts
migrate:
	alembic upgrade head

migration:
	alembic revision --autogenerate -m "$(msg)"
