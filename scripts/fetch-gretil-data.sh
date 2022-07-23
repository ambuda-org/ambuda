#!/bin/bash

# Exit when any command fails.
set -e

rm -r data/ambuda-gretil/ || true
mkdir -p data
git clone --depth=1 --branch=main https://github.com/ambuda-project/gretil.git gretil
mv gretil/1_sanskr/tei data/ambuda-gretil
rm -rf gretil
