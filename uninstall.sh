#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Thin wrapper: same as `nebulix undo` (back to how it was before Nebulix). Use `nebulix reset` for Ubuntu defaults.
cd "$(dirname "$0")" && export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}" && exec python3 -m nebulix undo "$@"
