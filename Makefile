# Needed because we have folders called "docs" and "test" that confuse `make`.
.PHONY: docs test py-venv-check clean deploy

# Setup commands
# ===============================================

# Install the repository from scratch.
# This command does NOT install data dependencies.
install:
	./scripts/install_from_scratch.sh

# Install frontend dependencies and build CSS and JS assets.
install-frontend:
	npm install
	make css-prod js-prod

# Install Python dependencies.
install-python:
	uv sync

# Fetch and build all i18n files.
install-i18n:
	uv run python -m ambuda.scripts.fetch_i18n_files
	# Force a build with `-f`. Transifex files have a `fuzzy` annotation, so if
	# we build without this flag, then all of the files will be skipped with:
	#
	#     "catalog <file>.po" is marked as fuzzy, skipping"
	#
	# There's probably a nicer workaround for this, but `-f` works and unblocks
	# this command for now.
	uv run pybabel compile -d ambuda/translations -f

# Upgrade an existing setup.
upgrade:
	make install-frontend install-python
	uv run make install-i18n
	uv run alembic upgrade head
	uv run python -m ambuda.seed.lookup

# Seed the database with a minimal dataset for CI. We fetch data only if it is
# hosted on GitHub. Other resources are less predictable.
db-seed-ci:
	uv run python -m ambuda.seed.lookup
	uv run python -m ambuda.seed.texts.gretil
	uv run python -m ambuda.seed.dcs

# Seed the database with just enough data for the devserver to be interesting.
db-seed-basic:
	uv run python -m ambuda.seed.lookup
	uv run python -m ambuda.seed.texts.gretil
	uv run python -m ambuda.seed.dcs
	uv run python -m ambuda.seed.dictionaries.monier

# Seed the database with all of the text, parse, and dictionary data we serve
# in production.
db-seed-all:
	uv run python -m ambuda.seed.lookup.role
	uv run python -m ambuda.seed.lookup.page_status
	uv run python -m ambuda.seed.texts.gretil
	uv run python -m ambuda.seed.texts.ramayana
	uv run python -m ambuda.seed.texts.mahabharata
	uv run python -m ambuda.seed.dcs
	uv run python -m ambuda.seed.dictionaries.amarakosha
	uv run python -m ambuda.seed.dictionaries.apte
	uv run python -m ambuda.seed.dictionaries.apte_sanskrit_hindi
	uv run python -m ambuda.seed.dictionaries.monier
	uv run python -m ambuda.seed.dictionaries.shabdakalpadruma
	uv run python -m ambuda.seed.dictionaries.shabdartha_kaustubha
	uv run python -m ambuda.seed.dictionaries.shabdasagara
	uv run python -m ambuda.seed.dictionaries.vacaspatyam


# Local run commands
# ===============================================

.PHONY: devserver celery

# For Docker try `make mode=dev docker-start`
devserver:
	./node_modules/.bin/concurrently "uv run flask run -h 0.0.0.0 -p 5000" "npx tailwindcss -i ambuda/static/css/style.css -o ambuda/static/gen/style.css --watch" "npx esbuild ambuda/static/js/main.js --outfile=ambuda/static/gen/main.js --bundle --watch"
	
# Run a local Celery instance for background tasks.
celery: 
	uv run celery -A ambuda.tasks worker --loglevel=INFO

deploy:
	uv run fab deploy


# Docker commands
# ===============================================

# Start all development services (web, celery, redis) with hot-reloading
ambuda-dev:
	@echo "🚀 Starting Ambuda development environment in Docker..."
	@echo "   This will start: web server, Celery workers, and Redis"
	@mkdir -p data/database data/file-uploads data/vidyut
	docker compose -f docker-compose.dev.yml up

ambuda-dev-shell:
	docker compose -f docker-compose.dev.yml exec web /bin/bash

# Run database migrations in Docker
ambuda-dev-migrate:
	docker compose -f docker-compose.dev.yml exec web uv run alembic upgrade head

# Seed the database with basic data
ambuda-dev-seed-basic:
	docker compose -f docker-compose.dev.yml exec web uv run python -m ambuda.seed.lookup
	docker compose -f docker-compose.dev.yml exec web uv run python -m ambuda.seed.texts.gretil
	docker compose -f docker-compose.dev.yml exec web uv run python -m ambuda.seed.dcs
	docker compose -f docker-compose.dev.yml exec web uv run python -m ambuda.seed.dictionaries.monier


# Lint commands
# ===============================================

# Link checks on Python code
py-lint:
	uv run ruff format .

# Lint our Python and JavaScript code. Fail on any issues.
lint-check: js-lint
	uv run ruff format . --check


# Test, coverage and documentation commands
# ===============================================

# Run all Python unit tests.
test:
	uv run pytest .

# Run all Python unit tests with a coverage report.
# After the command completes, open "htmlcov/index.html".
coverage:
	uv run pytest --cov=ambuda --cov-report=html test/

coverage-report: coverage
	coverage report --fail-under=80

# Generate Ambuda's technical documentation.
# After the command completes, open "docs/_build/index.html".
docs:
	cd docs && make html


# CSS commands
# ===============================================

# Run Tailwind to build our CSS, and rebuild our CSS every time a relevant file
# changes.
css-dev:
	npx tailwindcss -i ./ambuda/static/css/style.css -o ./ambuda/static/gen/style.css --watch

# Build CSS for production.
css-prod:
	npx tailwindcss -i ./ambuda/static/css/style.css -o ./ambuda/static/gen/style.css --minify


# JavaScript commands
# ===============================================

# Run esbuild to build our JavaScript, and rebuild our JavaScript every time a
# relevant file changes.
js-dev:
	npx esbuild ambuda/static/js/main.js --outfile=ambuda/static/gen/main.js --bundle --watch

# Build JS for production.
js-prod:
	npx esbuild ambuda/static/js/main.js --outfile=ambuda/static/gen/main.js --bundle --minify

js-test:
	npx jest

js-coverage:
	npx jest --coverage

# Lint our JavaScript code.
js-lint:
	npx eslint --fix ambuda/static/js/* --ext .js,.ts

# Check our JavaScript code for type consistency.
js-check-types:
	npx tsc ambuda/static/js/*.ts -noEmit


# i18n and l10n commands
# ===============================================

# Extract all translatable text from the application and save it in `messages.pot`.
babel-extract:
	uv run pybabel extract --mapping babel.cfg --keywords _l --output-file messages.pot .

# Create a new translation file from `messages.pot`.
babel-init:
	uv run pybabel init -i messages.pot -d ambuda/translations --locale $(locale)

# Update all translation files with new text from `messages.pot`
babel-update:
	uv run pybabel update -i messages.pot -d ambuda/translations

# Compile all translation files.
# NOTE: you probably want `make install-i18n` instead.
babel-compile:
	uv run pybabel compile -d ambuda/translations

# Clean up
# ===============================================

clean:
	@rm -rf data/
	@rm -rf ambuda/translations/*
