#!/bin/bash

# Exit when any command fails.
set -e

git clone --depth=1 --branch=master https://github.com/OliverHellwig/sanskrit.git dcs-repo
mv dcs-repo/dcs/data/conllu/ dcs-parse-data
rm -rf dcs-repo
