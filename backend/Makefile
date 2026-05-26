# AR Society ERP — Development Commands

.PHONY: test seed run lint

# Run test suite
test:
	DATABASE_URL="sqlite:///./test_ar_society.db" SECRET_KEY="test-secret" \
	python -m pytest tests/ -v

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
