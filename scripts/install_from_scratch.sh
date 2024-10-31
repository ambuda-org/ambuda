#!/usr/bin/env bash

# Exit if any step in this install script fails.
set -e

if ! command -v uv 2>&1 >/dev/null
then
    echo "Before installing Ambuda, please install the 'uv' command."
    echo "You can download it here: https://docs.astral.sh/uv/getting-started/installation/"
    exit 1
fi

if [ -f data ] || [ -f env ] || [ -f node_modules ] || [ -f .env ] || [ -f deploy/data/ ]; then
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
    rm -Rf .env .venv deploy/data/ env/ node_modules/
fi


echo "Beginning clean install of Ambuda."

make install-frontend
make install-python

# For pybabel, etc. (install-i18n)
source .venv/bin/activate

# i18n/l10n setup
make install-i18n

# Confirm that the setup worked.
make test

# Install environment variables.
cat << EOF > .env
# To see what these environment variables mean and how we use them in the
# application, see \`config.py\`.

# Flask parameters
FLASK_ENV=development
FLASK_UPLOAD_FOLDER="$(pwd)/deploy/data/file-uploads"
SECRET_KEY="insecure development secret key"

# Database
SQLALCHEMY_DATABASE_URI="sqlite:///$(pwd)/deploy/data/database/database.db"

# Side data
VIDYUT_DATA_FOLDER="$(pwd)/deploy/vidyut-0.2.0"

# OCR and BOT credentials
AMBUDA_BOT_PASSWORD="insecure bot password"
GOOGLE_APPLICATION_CREDENTIALS="<Google API credentials>"
EOF

source .env

make db-seed-basic

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
    ./cli.py add-role --username <username> --role admin
    ./cli.py create-project <project-title> <path-to-project-pdf>

To start the development server, run the following commands:

    # This command works on Bash. You might need to change this command for
    # other shells.
    source .venv/bin/activate

    # Run the devserver.
    make devserver

For help, join our Discord: https://discord.gg/7rGdTyWY7Z

Happy coding!
EOF
