#!/bin/zsh
# usage: shoot.sh <view-query> <name> [theme]
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
Q="$1"; NAME="$2"; THEME="${3:-light}"
URL="file:///Users/ishita/sf-city-monitor/design/prototype/index.html?${Q}&theme=${THEME}"
perl -e 'alarm 60; exec @ARGV' "$CHROME" --headless=new --disable-gpu --hide-scrollbars --window-size=1440,1000 --virtual-time-budget=6000 --screenshot="/Users/ishita/sf-city-monitor/design/shots/${NAME}-${THEME}.png" "$URL" >/dev/null 2>&1
echo "shot ${NAME}-${THEME}"
