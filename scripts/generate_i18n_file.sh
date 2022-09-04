#!/usr/bin/env bash
set -o nounset

pybabel init -i messages.pot -d ambuda/translations -l "$1"
