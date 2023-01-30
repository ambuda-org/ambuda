#!/usr/bin/env bash

# Entrypoint for running the devserver from within Docker. 

set -e

. /venv/bin/activate

export PATH=$PATH:/venv/bin/
export PYTHONPATH=$PYTHONPATH:/app


function setup_vidyut_data () 
{
    VIDYUT_DATA_URL="https://github.com/ambuda-org/vidyut-py/releases/download/0.2.0/data-0.2.0.zip"
       
    if [ -z "${VIDYUT_DATA_DIR}" ]; 
    then
        echo "Error! Invalida Vidyut data dir. Please set env variable VIDYUT_DATA_DIR"
        return 1
    fi

    if [ -z "${VIDYUT_DATA_URL}" ]; 
    then
            echo "Error! Invalida URL to fetch Vidyut data. Please set env variable VIDYUT_DATA_URL"
        return 1
    fi
    VIDYUT_MARKER="${VIDYUT_DATA_DIR}/vidyut_is_here"
    if [ -f $VIDYUT_MARKER ];
    then
        # TODO: calculate SHA256 of installed files and compare
        echo "Vidyut data found!"
        return 0
    fi

    echo "Fetching Vidyut data from ${VIDYUT_DATA_URL} to ${VIDYUT_DATA_DIR}."
    mkdir -p $VIDYUT_DATA_DIR

    VIDYUT_DATA_FILE=$(basename -- "$VIDYUT_DATA_URL")
    VIDYUT_DATA_FILENAME_BASE="${VIDYUT_DATA_FILE%.*}"

    wget -P ${VIDYUT_DATA_DIR} ${VIDYUT_DATA_URL} -q
    unzip -d ${VIDYUT_DATA_DIR} -j ${VIDYUT_DATA_DIR}/${VIDYUT_DATA_FILE}
    if [ $? -ne 0 ]; then
        echo "Error! Failed to fetch from ${VIDYUT_DATA_URL}"
        return 1
    fi

    # Successfully installed. Leave a mark.
    touch $VIDYUT_MARKER
 
    return 0
}

# Git required only for this run. Keeping git here to curb docker image size.
apt-get -qq update && apt-get -qq install -y git wget unzip > /dev/null

# Setup SQLLite
python scripts/setup_database.py && echo "Database setup complete." || exit 1

# Setup Vidyut data
setup_vidyut_data && echo "Vidyut data setup complete" || echo "Error pulling from Vidyut. Setup vidyut data later."

exit 0