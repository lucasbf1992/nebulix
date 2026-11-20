#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Thin wrapper: applies the theme for the current user (same as `nebulix apply`). Use --dry-run first.
cd "$(dirname "$0")" && export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}" && exec python3 -m nebulix apply "$@"
