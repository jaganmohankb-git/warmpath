#!/bin/bash
cd "$(dirname "$0")"
PORT=8080

# If something else is on 8080, kill it so we always use the same port
# (different ports = different localStorage = your data looks missing)
EXISTING=$(lsof -ti :$PORT -sTCP:LISTEN 2>/dev/null)
if [ -n "$EXISTING" ]; then
  echo "  Freeing port $PORT (was used by PID $EXISTING)…"
  kill "$EXISTING" 2>/dev/null
  sleep 0.5
fi

echo ""
echo "  WarmPath starting on http://localhost:$PORT"
echo "  Keep this window open while using the tool."
echo "  Press Ctrl+C to stop."
echo ""

# Write a small Python server that serves files + handles /proxy?url=... requests
cat > /tmp/warmpath_server.py << 'PYEOF'
import sys, os, urllib.request, urllib.parse, http.server, socketserver

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
DIRECTORY = sys.argv[2] if len(sys.argv) > 2 else os.getcwd()

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == '/proxy':
            params = urllib.parse.parse_qs(parsed.query)
            target = params.get('url', [''])[0]
            if not target:
                self.send_error(400, 'Missing url parameter')
                return
            try:
                req = urllib.request.Request(target, headers={
                    'User-Agent': 'Mozilla/5.0 (compatible; WarmPath/1.0)',
                    'Accept': 'text/html,application/xhtml+xml,*/*'
                })
                with urllib.request.urlopen(req, timeout=8) as resp:
                    body = resp.read(80000)  # cap at 80KB
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain; charset=utf-8')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                self.send_response(502)
                self.send_header('Content-Type', 'text/plain')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(str(e).encode())
            return
        super().do_GET()

    def log_message(self, format, *args):
        pass  # suppress request logs

socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(('', PORT), Handler) as httpd:
    httpd.serve_forever()
PYEOF

(sleep 1.2 && open "http://localhost:$PORT/index.html") &
python3 /tmp/warmpath_server.py $PORT "$(pwd)" 2>/dev/null || python3 -m http.server $PORT
