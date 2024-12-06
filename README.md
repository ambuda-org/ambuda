![Unit Tests](https://github.com/ambuda-org/ambuda/actions/workflows/basic-tests.yml/badge.svg)


Ambuda
======

Ambuda is an online Sanskrit library whose mission is to make Sanskrit
literature accessible to all. Our library is hosted at https://ambuda.org.

This repository contains Ambuda's core code. It also includes *seed* scripts,
which will automatically pull external data sources and populate a development
database.


Quickstart
----------

(This setup process requires Docker and UV. If you don't have Docker installed on your
machine, you can install it [here][docker] and [here][uv].)

To install and run Ambuda locally, please run the commands below:

```
$ git clone https://github.com/ambuda-org/ambuda.git
$ cd ambuda
$ uv venv env
$ source env/bin/activate && uv pip install --upgrade pip && uv pip install -r requirements.txt
$ make devserver
```

Then, navigate to `http://localhost:5000` in your web browser.

[docker]: https://docs.docker.com/get-docker/
[uv]: https://github.com/astral-sh/uv


Documentation
-------------

A full technical reference for this repository can be found here:

https://ambuda.readthedocs.io/en/latest/

It includes installation instructions, architecture notes, and other reference
documentation about Ambuda's technical design.


Contributing
------------

For details on how to contribute to Ambuda, see [`CONTRIBUTING.md`][CONTRIBUTING.md]. We also
strongly recommend joining our [Discord channel][discord], where we have an
ongoing informal discussion about Ambuda's technical problems and roadmap.

[discord]: https://discord.gg/7rGdTyWY7Z
[CONTRIBUTING.md]: /CONTRIBUTING.md
