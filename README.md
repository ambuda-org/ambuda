Ambuda
======

Ambuda aims to make Sanskrit literature radically accessible.

Our initial offering is a Sanskrit reader with a dictionary available on the
same page. We hope that this reader will make it easier for Sanskrit students
to look up words as they read.


Setup
-----

Install dependencies:

    # Python dependencies
    python3 -m venv env
    source env/bin/activate
    pip install -r requirements.txt

    # Node dependencies (for Tailwind CSS)
    npm install

Seed the database:

    python -m ambuda.seed.monier
    python -m ambuda.seed.ramayana
    python -m ambuda.seed.mahabharata

Run the development server:

    make devserver

Regenerate CSS with a Tailwind watcher:

    make tailwind_watcher

Lint:

    make lint
