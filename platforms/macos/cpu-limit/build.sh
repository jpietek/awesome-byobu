#!/bin/sh
set -eu
cd "$(dirname "$0")"
clang -O2 -Wall -Wextra -Wno-unused-parameter -Wno-sign-compare \
    -Wno-deprecated-non-prototype -D_GNU_SOURCE -o cpulimit-terminal \
    cpulimit-0.2/src/cpulimit.c cpulimit-0.2/src/list.c \
    cpulimit-0.2/src/process_group.c cpulimit-0.2/src/process_iterator.c \
    terminal_control.c

