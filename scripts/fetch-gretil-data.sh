#!/bin/bash

# Exit when any command fails.
set -e

rm -r third-party-data/gretil/
mkdir -p third-party-data
git clone --depth=1 --branch=main https://github.com/ambuda-project/gretil.git gretil
mv gretil/1_sanskr/tei third-party-data/gretil
rm -rf gretil
