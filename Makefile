.PHONY: docs test

install:
	./scripts/install_from_scratch.sh

devserver:
	flask run

tailwind_watcher:
	npx tailwindcss -i ./ambuda/static/css/style.css -o ./ambuda/static/gen/style.css --watch

eslint:
	npx eslint --fix ambuda/static/js/*.js

lint: eslint
	black .

test:
	pytest .

coverage:
	pytest --cov=ambuda --cov-report=html test/

docs:
	cd docs; make html
