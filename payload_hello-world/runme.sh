#! /usr/bin/env sh

PAYLOADDIR="$( cd -- "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )"

echo "HPS boot payload"
echo "PAYLOADDIR=${PAYLOADDIR}"
echo "Hello world"

echo "payload over, shutting down"
shutdown -h now
