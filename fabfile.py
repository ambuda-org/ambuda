import os
from pathlib import Path

from dotenv import load_dotenv
from fabric import Connection, task

load_dotenv()
APP_DIRECTORY = Path(os.environ["SERVER_APP_DIRECTORY"])
UPLOADS_DIRECTORY = Path(os.environ["SERVER_UPLOADS_DIRECTORY"])
SECRETS_DIRECTORY = Path(os.environ["SERVER_SECRETS_DIRECTORY"])

USER = os.environ["SERVER_USER"]
HOST = os.environ["SERVER_HOST"]
DEPLOY_BRANCH = "release"

r = Connection(f"root@{HOST}")
c = Connection(f"{USER}@{HOST}")


@task
def init_python_3_10(_):
    py_3_10 = "https://www.python.org/ftp/python/3.10.4/Python-3.10.4.tgz"

    r.sudo("apt-get install libssl-dev openssl make gcc")
    r.sudo("apt-get install libsqlite3-dev")

    with c.cd("/opt"):
        c.sudo("cd /opt")
        c.sudo(f"wget {py_3_10}")
        c.sudo("tar xzvf Python-3.10.4.tgz")

    with c.cd("/opt/Python-3.10.4"):
        c.sudo("./configure --enable-loadable-sqlite-extensions")
        c.sudo("make")
        c.sudo("make install")

    c.sudo("ln -fs /opt/Python-3.10.4 /usr/bin/python3.10")
    c.run("python3.10 --version")


@task
def init_secrets(_):
    c.run(f"mkdir -p {SECRETS_DIRECTORY}")
    json_path = str(SECRETS_DIRECTORY / "google-cloud-credentials.json")
    c.put("production/google-cloud-credentials.json", json_path)


@task
def init_repo(_):
    url = "https://github.com/ambuda-org/ambuda.git"
    with c.cd(APP_DIRECTORY):
        c.run("git init .")
        c.run(f"git remote add origin {url}")
    deploy(c)


def deploy_to_commit(_, pointer: str):
    """Deploy the given branch pointer to production.

    :param pointer: a commit SHA, branch name, etc.
    """
    with c.cd(APP_DIRECTORY):
        # Fetch the application code.
        c.run("git fetch origin")
        c.run("git checkout main")
        c.run(f"git reset --hard origin/{pointer}")

        # uv migration (first step)
        c.run("uv sync")

        # Install project requirements.
        c.run("make install-python")
        c.run("make install-frontend")

        # Verify that unit tests pass on prod.
        c.run("make test")

        # Copy production config settings.
        env_path = str(APP_DIRECTORY / ".env")
        c.put("production/prod-env", env_path)

        # Build i18n and l10n files
        c.run("make install-i18n")

        # Verify that the production setup is well-formed.
        c.run("uv run python -m scripts.check_prod_setup")

        # Upgrade the database last -- If we upgrade and a downstream check
        # fails, we'll affect the production application.
        # FIXME: but, what if we upgrade then app restart fails? Should we stop
        # the prod server first? Surely there's a saner way to manage this.
        c.run("make upgrade")

    print("Restarting application ...")
    restart_application(_)

    print("Restarting Celery task runner ...")
    restart_celery(_)

    c.local("python test_prod.py")
    print("Deploy complete! 🪔")


@task
def deploy(_):
    """Deploy the latest production commit."""
    deploy_to_commit(_, DEPLOY_BRANCH)


@task
def rollback(_, commit):
    """Roll back to a specific prior commit.

    :param commit: the commit SHA to roll back to.
    """
    deploy_to_commit(_, commit)


@task
def restart_application(_):
    """Restart the production gunicorn instance."""
    r.run("systemctl restart ambuda")


@task
def restart_celery(_):
    """Restart the production celery instance."""
    r.run("systemctl restart celery")


@task
def run_module(_, module):
    assert module
    with c.cd(APP_DIRECTORY):
        print(f"{module}")
        print("=" * len(module))
        c.run(f"uv run python -m {module}")


@task
def seed_gretil(_):
    with c.cd(APP_DIRECTORY):
        c.run("./scripts/fetch-gretil-data.sh")
        run_module(_, "ambuda.seed.gretil")
