#!/usr/bin/env bash

# Exit if any step in this install script fails.
set -e

if [ -f data ] || [ -f env ] || [ -f node_modules ] || [ -f .env ] || [ -f database.db ]; then
cat << "EOF"
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
WARNING WARNING WARNING WARNING WARNING WARNING WARNING WARNING WARNING WARNING
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Some of the files in your directory were created during a previous install. To
ensure that you have a clean install, this script will delete the following
files and directories, if they exist:

- database.db
- .env
- data/
- env/
- node_modules/

EOF
    python3 -c "exit(0) if input('Are you sure you want to continue? (y/n): ') == 'y' else exit(1)"

    echo "Cleaning up old state ..."
    rm -Rf .env database.db data/ env/ node_modules/
fi


echo "Beginning clean install of Ambuda."


# Frontend dependencies
# =====================

# Install Node dependencies.
npm install

# Build initial CSS and JavaScript.
make css-prod js-prod


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
cat << EOF > .env
# To see what these environment variables mean and how we use them in the
# application, see \`config.py\`.

FLASK_ENV=development
FLASK_UPLOAD_FOLDER="$(pwd)/data/file-uploads"
SECRET_KEY="insecure development secret key"
SQLALCHEMY_DATABASE_URI="sqlite:///database.db"

GOOGLE_APPLICATION_CREDENTIALS="<Google API credentials>"
EOF


# Database setup
# ==============

# Create tables
python -m scripts.initialize_db

# Add some starter data with a few basic seed scripts.
make db-seed-basic

# Create Alembic's migrations table.
alembic ensure_version

# Set the most recent revision as the current one.
alembic stamp head


cat << "EOF"
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
SUCCESS SUCCESS SUCCESS SUCCESS SUCCESS SUCCESS SUCCESS SUCCESS SUCCESS SUCCESS
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You have successfully installed Ambuda!

We've added some sample data to start you off. To load all of our texts,
dictionaries, and parse data into the development environment, you can run:

    make db-seed-all

(NOTE: the command above will be quite slow, since it must fetch several large
data files from several different websites.)

To create some sample data for our proofing interface, try the commands below.
In these commands, arguments in <angle-brackets> must be supplied by you:

    ./cli.py create-user
    ./cli.py add-role <username> admin
    ./cli.py create-project <project-title> <path-to-project-pdf>

To start the development server, run the following commands:

    # This command works on Bash. You might need to change this command for
    # other shells.
    source env/bin/activate

    # Run the devserver.
    make devserver

For help, join our Discord: https://discord.gg/7rGdTyWY7Z

Happy coding!
EOF
