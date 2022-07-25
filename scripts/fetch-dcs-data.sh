#!/bin/bash

# Exit when any command fails.
set -e

git clone --depth=1 --branch=master https://github.com/OliverHellwig/sanskrit.git dcs-repo
mkdir -p data
mv dcs-repo/dcs/data/conllu/ data/dcs-raw
rm -rf dcs-repo
