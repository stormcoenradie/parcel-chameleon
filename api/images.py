import json, urllib.parse
from http.server import BaseHTTPRequestHandler
from _utils import search_images

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)
        q = (qs.get("q") or [""])[0]
        try:
            count = int((qs.get("count") or ["3"])[0])
        except ValueError:
            count = 3
        count = max(1, min(count, 6))
        urls = search_images(q, count)
        self._send({"urls": urls})

    def _send(self, obj, status=200):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)