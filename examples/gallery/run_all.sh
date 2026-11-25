#!/bin/sh
# Regenerates every gallery image from toy data (no ROOT, no real analysis files).
cd "$(dirname "$0")" && for s in 0*.py; do python "$s"; done
