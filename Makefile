.PHONY: test

devserver:
	FLASK_ENV=development flask run

eslint:
	npx eslint --fix ambuda/static/js/*.js

lint: eslint
	black .

test:
	pytest .

coverage:
	pytest --cov=ambuda --cov-report=html test/

tailwind_watcher:
	npx tailwindcss -i ./ambuda/static/css/style.css -o ./ambuda/static/gen/style.css --watch
