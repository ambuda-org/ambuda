Creating data from the command line
===================================

Ambuda exposes a basic CLI for common administrative tasks. This interface lets
you quickly create objects to interact with on the development server.

Create a new user::

    ./cli.py create-user

Make that user an administrator::

    ./cli.py add-role <username> admin

Create a fake proofing project::

    ./cli.py create-project --title <title> --pdf-path <path-to-your-pdf-file>
