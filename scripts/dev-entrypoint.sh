#!/usr/bin/env bash
# dev entrypoint script for Docker

set -e

echo "🚀 Starting Ambuda development environment..."


# Database
DB_FILE_PATH="/app/data/database/database.db"
if [ ! -f "$DB_FILE_PATH" ]; then
    echo "Database not found. Initializing new database at $DB_FILE_PATH..."

    mkdir -p "$(dirname "$DB_FILE_PATH")"

    echo "- Creating database tables..."
    uv run python -m ambuda.seed.utils.data_utils

    echo "- Seeding basic data (lookup tables, sample texts)..."
    uv run python -m ambuda.seed.lookup
    uv run python -m ambuda.seed.texts.gretil
    uv run python -m ambuda.seed.dcs

    echo "- Setting up database migrations..."
    uv run alembic ensure_version
    uv run alembic stamp head

    echo "Database initialization complete."
else
    echo "Database found at $DB_FILE_PATH"

    echo "- Updating lookup tables..."
    uv run python -m ambuda.seed.lookup

    echo "- Running database migrations..."
    uv run alembic upgrade head
fi

# File uploads
mkdir -p /app/data/file-uploads

# Start Flask with CSS and JS watchers concurrently with hot reloading
exec ./node_modules/.bin/concurrently \
    --names "FLASK,CSS,JS" \
    --prefix-colors "blue,green,yellow" \
    "uv run flask run -h 0.0.0.0 -p 5000" \
    "npx tailwindcss -i /app/ambuda/static/css/style.css -o /app/ambuda/static/gen/style.css --watch" \
    "npx esbuild /app/ambuda/static/js/main.js --outfile=/app/ambuda/static/gen/main.js --bundle --watch"
