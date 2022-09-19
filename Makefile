# Needed because we have folders called "docs" and "test" that confuse `make`.
.PHONY: docs test py-venv-check

py-venv-check: 
ifeq ("$(VIRTUAL_ENV)","")
	@echo "Error! Python venv not activated. Activate venv to proceed. Run: "
	@echo "  > source env/bin/activate"
	@echo
	exit 1
endif

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

# Upgrade an existing setup.
upgrade:
	make install-frontend install-python
	. env/bin/activate; python -m ambuda.seed.lookup
	. env/bin/activate; alembic upgrade head

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
	python -m ambuda.seed.dictionaries.apte
	python -m ambuda.seed.dictionaries.monier
	python -m ambuda.seed.dictionaries.shabdakalpadruma
	python -m ambuda.seed.dictionaries.shabdartha_kaustubha
	python -m ambuda.seed.dictionaries.shabdasagara
	python -m ambuda.seed.dictionaries.vacaspatyam


# Common development commands
# ===============================================

# Run the devserver, and live reload our CSS and JS.
devserver: py-venv-check
	npx concurrently "flask run" "make css-dev" "make js-dev"

# Start using Docker.
start-docker:
	docker-compose up --build --force-recreate

# Run a local Celery instance for background tasks.
celery: 
	celery -A ambuda.tasks worker --loglevel=INFO

lint-isort:
	@echo "Running Python isort to organize module imports"
	@git ls-files '*.py' | xargs isort --check 2>&1

lint-black:
	@echo "Running Python Black to check formatting"
	@git ls-files '*.py' | xargs black 2>&1

lint-flake8:
	@echo "Running Python flake8 to conform with PEP8"	
	@git ls-files '*.py' | xargs flake8 --config=./.flake8 2>&1

# Add isort when imports are organized better
py-lint: py-venv-check lint-black lint-isort lint-flake8
	@echo "Python lint completed"

# Lint our Python and JavaScript code.
lint: js-lint py-lint
	@echo 'Lint completed'

# Lint our Python and JavaScript code. Fail on any issues.
lint-check: js-lint
	black . --diff

# Run all Python unit tests.
test: py-venv-check
	pytest .

# Run all Python unit tests with a coverage report.
# After the command completes, open "htmlcov/index.html".
coverage:
	pytest --cov=ambuda --cov-report=html test/

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
babel-compile: py-venv-check
	pybabel compile -d ambuda/translations -D "messages text"
