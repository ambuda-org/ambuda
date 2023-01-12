# Needed because we have folders called "docs" and "test" that confuse `make`.
.PHONY: docs test py-venv-check clean

.EXPORT_ALL_VARIABLES:

# Git and docker params
GITCOMMIT=$(shell git rev-parse --short HEAD)
GITBRANCH=$(shell git rev-parse --abbrev-ref --short HEAD)
AMBUDA_VERSION=v0.1
AMBUDA_NAME=ambuda
AMBUDA_IMAGE=${AMBUDA_NAME}:${AMBUDA_VERSION}-${GITBRANCH}-${GITCOMMIT}
AMBUDA_IMAGE_LATEST="$(AMBUDA_NAME)-rel:latest"

# Environment. Valid values are: local, staging, and prod
AMBUDA_DEPLOYMENT_ENV=local
AMBUDA_HOST_IP=0.0.0.0
AMBUDA_HOST_PORT=5090

py-venv-check: 
ifeq ("$(VIRTUAL_ENV)","")
	@echo "Error! Python venv not activated. Activate venv to proceed. Run: "
	@echo "  > source env/bin/activate"
	@echo
	exit 1
endif	

DB_FILE = ${PWD}/deploy/data/database/database.db

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
	python3 -m venv env
	. env/bin/activate; pip install --upgrade pip
	. env/bin/activate; pip install -r requirements.txt

# Fetch and build all i18n files.
install-i18n: py-venv-check
	python -m ambuda.scripts.fetch_i18n_files
	# Force a build with `-f`. Transifex files have a `fuzzy` annotation, so if
	# we build without this flag, then all of the files will be skipped with:
	#
	#     "catalog <file>.po" is marked as fuzzy, skipping"
	#
	# There's probably a nicer workaround for this, but `-f` works and unblocks
	# this command for now.
	pybabel compile -d ambuda/translations -f

# Upgrade an existing setup.
upgrade:
	make install-frontend install-python
	. env/bin/activate; make install-i18n
	. env/bin/activate; alembic upgrade head
	. env/bin/activate; python -m ambuda.seed.lookup

# Seed the database with a minimal dataset for CI. We fetch data only if it is
# hosted on GitHub. Other resources are less predictable.
db-seed-ci: py-venv-check
	python -m ambuda.seed.lookup
	python -m ambuda.seed.texts.gretil
	python -m ambuda.seed.dcs

# Seed the database with just enough data for the devserver to be interesting.
db-seed-basic: py-venv-check
	python -m ambuda.seed.lookup
	python -m ambuda.seed.texts.gretil
	python -m ambuda.seed.dcs
	python -m ambuda.seed.dictionaries.monier

# Seed the database with all of the text, parse, and dictionary data we serve
# in production.
db-seed-all: py-venv-check
	python -m ambuda.seed.lookup.role
	python -m ambuda.seed.lookup.page_status
	python -m ambuda.seed.texts.gretil
	python -m ambuda.seed.texts.ramayana
	python -m ambuda.seed.texts.mahabharata
	python -m ambuda.seed.dcs
	python -m ambuda.seed.dictionaries.amarakosha
	python -m ambuda.seed.dictionaries.apte
	python -m ambuda.seed.dictionaries.apte_sanskrit_hindi
	python -m ambuda.seed.dictionaries.monier
	python -m ambuda.seed.dictionaries.shabdakalpadruma
	python -m ambuda.seed.dictionaries.shabdartha_kaustubha
	python -m ambuda.seed.dictionaries.shabdasagara
	python -m ambuda.seed.dictionaries.vacaspatyam


# Common development commands
# ===============================================

# Start DB using Docker.
docker-setup-db: docker-build 
ifneq ("$(wildcard $(DB_FILE))","")
	@echo "Ambuda using your existing database!"
else
	@docker compose -f deploy/${AMBUDA_DEPLOYMENT_ENV}/docker-compose-dbsetup.yml up
	@echo "Ambuda database is Ready!"
endif
	
# Build docker image. All tag the latest to the most react image
# docker-build: lint-check
docker-build: 
	@docker build -t ${AMBUDA_IMAGE} -t ${AMBUDA_IMAGE_LATEST} -f build/containers/Dockerfile.final ${PWD}
	@echo ">>>>>> ${AMBUDA_IMAGE} is now ${AMBUDA_IMAGE_LATEST}"

# Start Docker services.
docker-start: docker-build docker-setup-db
	@docker compose -f deploy/${AMBUDA_DEPLOYMENT_ENV}/docker-compose.yml up --detach
	@echo "Ambuda URL http://${AMBUDA_HOST_IP}:${AMBUDA_HOST_PORT} is up"

# Stop docker services
docker-stop: 
	@docker compose -f deploy/${AMBUDA_DEPLOYMENT_ENV}/docker-compose.yml stop
	@docker compose -f deploy/${AMBUDA_DEPLOYMENT_ENV}/docker-compose.yml rm
	@echo "Ambuda URL stopped"

# Show docker logs
docker-logs: 
	@docker compose -f deploy/${AMBUDA_DEPLOYMENT_ENV}/docker-compose.yml logs

# Run a local Celery instance for background tasks.
celery: 
	celery -A ambuda.tasks worker --loglevel=INFO

# Check imports in Python code
lint-isort:
	@echo "Running Python isort to organize module imports"
	@git ls-files '*.py' | xargs isort --check 2>&1

# Check formatting in Python code
lint-black:
	@echo "Running Python Black to check formatting"
	@git ls-files '*.py' | xargs black 2>&1

# Check Python code complyies with PEP8
lint-flake8:
	@echo "Running Python flake8 to conform with PEP8"	
	@git ls-files '*.py' | xargs flake8 --config=./.flake8 2>&1

# Link checks on Python code
py-lint: py-venv-check lint-black lint-isort lint-flake8
	@echo "Python lint completed"

# Lint our Python and JavaScript code. Fail on any issues.
lint-check: js-lint py-lint
	black . --diff
	@echo 'Lint completed'

# Run all Python unit tests.
test: py-venv-check
	pytest .

# Run all Python unit tests with a coverage report.
# After the command completes, open "htmlcov/index.html".
coverage:
	pytest --cov=ambuda --cov-report=html test/

# Generate Ambuda's technical documentation.
# After the command completes, open "docs/_build/index.html".
docs: py-venv-check
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

# Extract all translatable text from the application.
babel-extract: py-venv-check
	pybabel extract --mapping babel.cfg --keywords _l --output-file messages.pot .

# Create a new translation file from `messages.pot`.
babel-init: py-venv-check
	pybabel init -i messages.pot -d ambuda/translations --locale $(locale)

# Update all translation files with new text from `messages.pot`
babel-update: py-venv-check
	pybabel update -i messages.pot -d ambuda/translations

# Compile all translation files.
# NOTE: you probably want `make install-i18n` instead.
babel-compile: py-venv-check
	pybabel compile -d ambuda/translations

clean:
	@rm -rf deploy/data/
	@rm -rf ambuda/translations/*
