#!/usr/bin/env bash

# Exit if any step in this install script fails.
set -e

echo "Beginning clean install of Ambuda."

# Clean up any existing state so that we can do a clean install.
rm -Rf env/ node_modules/

# Install Node dependencies.
npm install

# Build initial Tailwind CSS
npx tailwindcss -i ./ambuda/static/css/style.css -o ambuda/static/gen/style.css --minify

# Install Python dependencies.
python3 -m venv env
source env/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Confirm that the setup worked.
make test

# Install environment variables.
cat << EOF > .env
FLASK_ENV=development
SQLALCHEMY_DATABASE_URI="sqlite:///database.db"

GOOGLE_APPLICATION_CREDENTIALS = "<insert your credentials here>"
EOF

# Initialize the database.
python -m scripts.initialize_db

cat << "EOF"
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
SUCCESS SUCCESS SUCCESS SUCCESS SUCCESS SUCCESS SUCCESS SUCCESS SUCCESS SUCCESS
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You have successfully installed Ambuda! To start the development server, run:

1. source env/bin/activate
2. make devserver

To add data to the database, try the commands below:

1. Run `python -m ambuda.seed.texts.gretil` to add texts from GRETIL.
2. Run `python -m ambuda.seed.dcs` to add parse data.
3. Run `python -m ambuda.seed.dictionaries.monier` to add the Monier-Williams
   dictionary. Other dictionaries are in `ambuda/seed/dictionaries`.

For help, join our Discord: https://discord.gg/7rGdTyWY7Z

Happy coding!
EOF
