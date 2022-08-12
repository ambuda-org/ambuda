# Needed because we have folders called "docs" and "test" that confuse `make`.
.PHONY: docs test


# Setup commands
# ===============================================

# Install the repository from scratch.
# This command does NOT install data dependencies.
install:
	./scripts/install_from_scratch.sh


# Seed the database with just enough data for the devserver to be interesting.
db_seed_basic:
	python -m ambuda.seed.lookup.role
	python -m ambuda.seed.lookup.page_status
	python -m ambuda.seed.texts.gretil
	python -m ambuda.seed.dcs
	python -m ambuda.seed.dictionaries.monier


# Seed the database with all of the text, parse, and dictionary data we serve
# in production.
db_seed_all:
	python -m ambuda.seed.lookup.role
	python -m ambuda.seed.lookup.page_status
	python -m ambuda.seed.texts.gretil
	python -m ambuda.seed.texts.ramayana
	python -m ambuda.seed.texts.mahabharata
	python -m ambuda.seed.dcs
	python -m ambuda.seed.dictionaries.apte
	python -m ambuda.seed.dictionaries.monier
	python -m ambuda.seed.dictionaries.shabdakalpadruma
	python -m ambuda.seed.dictionaries.shabdartha_kaustubha
	python -m ambuda.seed.dictionaries.shabdasagara
	python -m ambuda.seed.dictionaries.vacaspatyam


# Development commands
# ===============================================

# Run the devserver, and live reload our CSS.
devserver:
	npx concurrently "flask run" "make tailwind_watcher"


# Run Tailwind to build our CSS, and rebuild our CSS every time a relevant file
# changes.
tailwind_watcher:
	npx tailwindcss -i ./ambuda/static/css/style.css -o ./ambuda/static/gen/style.css --watch


# Run a local Celery instance for background tasks.
celery:
	celery -A ambuda.tasks worker --loglevel=INFO


# Lint our JavaScript code.
eslint:
	npx eslint --fix ambuda/static/js/*.js


# Lint our Python and JavaScript code.
lint: eslint
	black .

# Lint our Python and JavaScript code. Fail on any issues.
lint-check: eslint
	black . --diff

# Run all Python unit tests.
test:
	pytest .

# Run all Python unit tests with a coverage report.
# After the command completes, open "htmlcov/index.html".
coverage:
	pytest --cov=ambuda --cov-report=html test/


# Generate Ambuda's technical documentation.
# After the command completes, open "docs/_build/index.html".
docs:
	cd docs && make html
