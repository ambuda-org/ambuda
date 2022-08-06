#!/usr/bin/env bash

# Exit if any step in this install script fails.
set -e

echo "Beginning clean install of Ambuda."


# JavaScript dependencies
# =======================

# Clean up any existing state so that we can do a clean install.
rm -Rf env/ node_modules/

# Install Node dependencies.
npm install

# Build initial Tailwind CSS
npx tailwindcss -i ./ambuda/static/css/style.css -o ambuda/static/gen/style.css --minify


# Python dependencies
# ===================

# Install Python dependencies.
python3 -m venv env
source env/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Confirm that the setup worked.
make test

# Install environment variables.
cat << "EOF" > .env
# To see what these environment variables mean and how we use them in the
# application, see `config.py`.

FLASK_ENV=development
# FLASK_UPLOAD_FOLDER="<absolute path to where you want to store uploads.>"
SQLALCHEMY_DATABASE_URI="sqlite:///database.db"

GOOGLE_APPLICATION_CREDENTIALS="<Google API credentials>"
EOF


# Database setup
# ==============

# Create tables
python -m scripts.initialize_db

# Create Alembic's migrations table.
alembic ensure_version

# Set the most recent revision as the current one.
alembic stamp head


cat << "EOF"
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
SUCCESS SUCCESS SUCCESS SUCCESS SUCCESS SUCCESS SUCCESS SUCCESS SUCCESS SUCCESS
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You have successfully installed Ambuda! To start the development server, run
the following commands:

    # This command works on Bash. You might need to change this command for
    # other shells.
    source env/bin/activate

    # Run the devserver.
    make devserver

To add data to the database, try either of the commands below:

    # A smaller install with some missing data
    make db_seed_basic

    # A full install that's larger and slower
    make db_seed_all

For help, join our Discord: https://discord.gg/7rGdTyWY7Z

Happy coding!
EOF
