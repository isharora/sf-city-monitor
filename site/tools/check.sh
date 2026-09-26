#!/bin/zsh
# Render every view (light + dark) with headless Chrome, capture console errors, screenshot to
# /tmp/scm_site/, and run the in-page self-test (?selftest=1). Flags: --no-shots --no-selftest --no-bundle --only <prefix>
cd "$(dirname "$0")/.." || exit 1
exec python3 tools/check.py "$@"
