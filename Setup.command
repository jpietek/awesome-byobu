#!/bin/sh
cd "$(dirname "$0")" || exit 1
if ./setup.sh "$@"; then
    echo 'Setup completed.'
else
    echo 'Setup stopped. See the error above; rerunning is safe.' >&2
    printf 'Press Return to close: '; read -r reply
    exit 1
fi
