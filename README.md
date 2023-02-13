![Unit Tests](https://github.com/ambuda-org/ambuda/actions/workflows/basic-tests.yml/badge.svg)

Ambuda
======

Ambuda is an online Sanskrit archive whose mission is to make the Sanskrit
tradition radically accessible. Our archive is hosted at https://ambuda.org.

This repository contains Ambuda's core code. It also includes database seeding
scripts, which will automatically pull external data sources as needed.


Documentation
-------------

A full technical reference for this repository can be found here:

https://ambuda.readthedocs.io/en/latest/

It includes installation instructions, architecture notes, and other reference
documentation about Ambuda's technical design.

Quick Installation
------------------

1. Clone git repo `$ git clone https://github.com/ambuda-org/ambuda.git`
2. Go to Ambuda code `$ cd ambuda`
3. Start Ambuda `$ make docker-start`. (Get [docker](https://docs.docker.com/get-docker/) if not installed on your computer.)
4. Open https://localhost:5090/

How to contribute
-----------------

For details on how to contribute to Ambuda, see [`CONTRIBUTING.md`][CONTRIBUTING.md]. We also
strongly recommend joining our [Discord channel][discord], where we have an
ongoing informal discussion about Ambuda's technical problems and roadmap.

[discord]: https://discord.gg/7rGdTyWY7Z
[CONTRIBUTING.md]: /CONTRIBUTING.md
