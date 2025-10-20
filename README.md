![Unit Tests](https://github.com/ambuda-org/ambuda/actions/workflows/basic-tests.yml/badge.svg)

<div align="center">
<h1>Ambuda</h1>
<p><i>A breakthrough Sanskrit library</i></p>
</div>

[Ambuda](https://ambuda.org) is an online Sanskrit library whose mission is to make Sanskrit
literature accessible to all. This repository contains Ambuda's core code, and this README will
show you how to build it.


Contents
--------

- [Quickstart][#quickstart]
- [Architecture][#architecture]
- [Documentation][#documentation]
- [Contributing][#contributing]


Quickstart
----------

The quickest way to run Ambuda on your computer is to use docker compose` from your command line.
You can install `docker compose` through either the [Docker website][docker] or your favorite
package manager. If you have a Unix machine and don't like Docker Desktop, we recommend
[Colima][colima].

[docker]: https://docs.docker.com/get-docker/
[colima]: https://github.com/abiosoft/colima

Once you have both installed, starting the site is simple:

```
make ambuda-dev
```

This command will do the following:

- Build an Ambuda Docker image. This will likely take a few minutes the first time it runs, but it
  will be substantially faster on subsequent runs.

- Start Ambuda's main services: the web server, a Celery pool for background tasks, and Redis for
  Celery interop.

- Initialize a Sqlite database with sample data. Data is persisted to the `data/` directory and
  survives across restarts.

- Set up hot-reloading for Python, CSS, and JavaScript

- Start the web server at http://localhost:5000

To quit, press `Ctrl+C` to stop all services.


Architecture
------------

(Under revision.)


Documentation
-------------

(Under revision.)

A full technical reference for this repository can be found here:

https://ambuda.readthedocs.io/en/latest/

It includes installation instructions, architecture notes, and other reference
documentation about Ambuda's technical design.


Contributing
------------

(Under revision.)

For details on how to contribute to Ambuda, see [`CONTRIBUTING.md`][CONTRIBUTING.md]. We also
strongly recommend joining our [Discord channel][discord], where we have an
ongoing informal discussion about Ambuda's technical problems and roadmap.

[discord]: https://discord.gg/7rGdTyWY7Z
[CONTRIBUTING.md]: /CONTRIBUTING.md
