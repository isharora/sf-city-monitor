#!/bin/sh
# Prints console errors/warnings for a page state. Usage: shots/console.sh "<query>"
CH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
URL="file://$HOME/sf-city-monitor/design/insights/prototype/insights.html?$1"
"$CH" --headless=new --disable-gpu --enable-logging=stderr --v=0 --virtual-time-budget=6000 --dump-dom "$URL" 2>&1 >/dev/null | grep -E "CONSOLE|Uncaught|Error" | grep -v "GPU\|gpu\|dbus\|Fontconfig" || echo "console clean"
