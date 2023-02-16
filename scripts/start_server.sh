#!/usr/bin/env bash

# Docker entrypoint for  Docker.
set -e

# Switch to python venv
. /venv/bin/activate

# Set PATH
export PATH=$PATH:/venv/bin/

# Start flask server. In local mode load 
echo "[$FLASK_ENV] Flask start from /venv/bin/flask with 0.0.0.0 on port 5000"
if [ "$FLASK_ENV" == "development" ]
then
    # Dynamically load css and js changes. Docker compose attaches to the ambuda/static directory on localhost
    ./node_modules/.bin/concurrently "/venv/bin/flask run -h 0.0.0.0 -p 5000" "npx tailwindcss -i /app/ambuda/static/css/style.css -o /app/ambuda/static/gen/style.css --watch" "npx esbuild /app/ambuda/static/js/main.js --outfile=/app/ambuda/static/gen/main.js --bundle --watch"
else
    # Build, Staging, and Production modes take this route. Loads static files from the container. 
    ./node_modules/.bin/concurrently "/venv/bin/flask run -h 0.0.0.0 -p 5000"
fi

