#!/usr/bin/env bash

# Build database with dictionaries, texts and other data. Initilalize Vidyut data.

set -e

. /venv/bin/activate

export PATH=$PATH:/venv/bin/
export PYTHONPATH=$PYTHONPATH:/app


function init_vidyut_data () 
{
    VIDYUT_DATA_URL="https://github.com/ambuda-org/vidyut-py/releases/download/0.2.0/data-0.2.0.zip"
       
    if [ -z "${VIDYUT_DATA_DIR}" ]; 
    then
        echo "Error! VIDYUT_DATA_DIR is not set. Please set environment variable VIDYUT_DATA_DIR"
        return 1
    fi

    if [ -z "${VIDYUT_DATA_URL}" ]; 
    then
            echo "Error! URL to fetch Vidyut data is not set. Please set environment variable VIDYUT_DATA_URL"
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

# Initialize SQLite database
python scripts/init_database.py && echo "Database set up complete." || exit 1

# Initialize Vidyut data
init_vidyut_data && echo "Vidyut data initialization completed" || echo "Error pulling from Vidyut. Fetch vidyut data later."

exit 0