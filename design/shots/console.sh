#!/bin/zsh
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
URL="file:///Users/ishita/sf-city-monitor/design/prototype/index.html?$1"
perl -e 'alarm 60; exec @ARGV' "$CHROME" --headless=new --disable-gpu --enable-logging=stderr --v=0 --virtual-time-budget=6000 --dump-dom "$URL" 2>&1 >/tmp/dom.html | grep -E "CONSOLE|Uncaught|Error" | grep -v "GPU\|gpu\|dbus\|Fontconfig" | head -20
echo "--- dom: $(wc -c </tmp/dom.html) bytes; title: $(grep -o '<title>[^<]*' /tmp/dom.html | head -1)"
