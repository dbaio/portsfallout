#!/bin/sh

BASEDIR=$(dirname "$0")
cd "$BASEDIR" || exit 1

python3 import-index.py
RET=$?

rm -f INDEX-13.bz2

return $RET
