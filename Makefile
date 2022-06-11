.PHONY: test

devserver:
	FLASK_ENV=development flask run

lint:
	black .

test:
	pytest .

tailwind_watcher:
	npx tailwindcss -i ./ambuda/static/css/style.css -o ./ambuda/static/gen/style.css --watch
