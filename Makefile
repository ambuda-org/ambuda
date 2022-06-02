devserver:
	python runserver.py

lint:
	black .

tailwind_watcher:
	npx tailwindcss -i ./ambuda/static/css/style.css -o ./ambuda/static/gen/style.css --watch
