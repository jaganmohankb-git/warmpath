#!/bin/bash
cd "$(dirname "$0")"
PORT=8080
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then PORT=8181; fi
echo ""
echo "  WarmPath starting on http://localhost:$PORT"
echo "  Keep this window open while using the tool."
echo "  Press Ctrl+C to stop."
echo ""
(sleep 1.2 && open "http://localhost:$PORT/index.html") &
python3 -m http.server $PORT 2>/dev/null || python -m SimpleHTTPServer $PORT
