![Unit Tests](https://github.com/ambuda-org/ambuda/actions/workflows/basic-tests.yml/badge.svg)

<div align="center">
<h1>Ambuda</h1>
<p><i>A breakthrough Sanskrit library</i></p>
</div>

[Ambuda](https://ambuda.org) is an online Sanskrit library. This repository contains Ambuda's core
code, and this README will show you how to build and change it.

## Contents

- [Quickstart](#quickstart)
- [Architecture](#architecture)
- [Documentation](#documentation)
- [Contributing](#contributing)

## Quickstart

This quickstart will show you how to:

- start Ambuda with Docker
- create an admin user
- upload content to the site

## Starting Ambuda with Docker

The quickest way to run Ambuda on your computer is to use `docker compose` from your command line.

> [!TIP]
> You can install `docker compose` through either the [Docker website][docker] or your favorite
> package manager. If you have a Unix machine and don't like Docker Desktop, we recommend
> [Colima][colima].
>
> [docker]: https://docs.docker.com/get-docker/
> [colima]: https://github.com/abiosoft/colima

Once you have `docker` configured, starting the site is simple:

```
make ambuda-dev
```

The `make ambuda-dev` command will do the following:

- Build an Ambuda Docker image. This will likely take a few minutes the first time it runs, but it
  will be substantially faster on subsequent runs.

- Start Ambuda's main services: the web server, a Celery pool for background tasks, and Redis for
  Celery interop.

- Initialize a Sqlite database with sample data. Data is persisted to the `data/` directory and
  survives across restarts.

- Set up hot reloading for Python, CSS, and JavaScript.

- Start the web server at http://localhost:5000.

To quit, press `Ctrl+C` to stop all services.

> [!TIP]
> If you ever run into build issues with `make ambuda-dev`, first run `make ambuda-dev-build`
> then try again.

> [!WARNING]
> When running `make ambuda-dev` if you see an error as follows:\
> `env file /path/to/ambuda/.env.docker.local not found: stat /path/to/ambuda/.env.docker.local: no such file or directory` \
> then you can fix it by simply creating an empty file using the command `touch .env.docker.local`

## Creating an admin user

Once the Docker service is up, create an admin user so that you can log in:

```
make ambuda-dev-shell

# Inside the shell

# This command creates a new user.
> uv run cli.py create-user

# This command assigns the `admin` role to your new user.
> uv run cli.py add-role --username <your-username> --role admin
```

After you've created your admin user, go to `http://localhost:5000/sign-in` to sign in.

## Uploading content to the site

(Under revision.)

Once you've logged in as an admin user go to `https://localhost:5000/admin/` to open the Admin UI.

## Architecture

(Under revision.)

Essentials:

- Web backend: Flask
- Task runner: Celery, with a Redis message broker.
- Frontend: Alpine.js and small amounts of Typescript.
- Storage: S3

## Documentation

(Under revision.)

## Contributing

For details on how to contribute to Ambuda, see [`CONTRIBUTING.md`][CONTRIBUTING.md]. We also
strongly recommend joining our [Discord channel][discord], where we have an
ongoing informal discussion about Ambuda's technical problems and roadmap.

[discord]: https://discord.gg/7rGdTyWY7Z
[CONTRIBUTING.md]: /CONTRIBUTING.md
