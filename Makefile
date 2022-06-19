.PHONY: test

devserver:
	FLASK_ENV=development flask run

lint:
	black .
	npx eslint --fix ambuda/static/js/*.js

test:
	pytest .

coverage:
	pytest --cov=ambuda --cov-report=html test/

tailwind_watcher:
	npx tailwindcss -i ./ambuda/static/css/style.css -o ./ambuda/static/gen/style.css --watch
