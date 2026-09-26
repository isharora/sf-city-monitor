#!/bin/sh
# Usage: shots/shoot.sh <name> "<query>" [height] [width]   → shots/<name>.png
CH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
URL="file://$HOME/sf-city-monitor/design/insights/prototype/insights.html?$2"
H=${3:-1000}; W=${4:-1440}
"$CH" --headless=new --disable-gpu --hide-scrollbars --window-size=$W,$H --virtual-time-budget=6000 --screenshot="$HOME/sf-city-monitor/design/insights/shots/$1.png" "$URL" >/dev/null 2>&1
echo "$1.png"
