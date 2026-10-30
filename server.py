import http.server, socketserver, urllib.parse, urllib.request, json, os, re, ssl

ROOT = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("PORT", "8000"))

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def do_GET(self):
        try:
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path == "/api/video":
                qs = urllib.parse.parse_qs(parsed.query)
                q = (qs.get("q") or [""])[0]
                vid = search_youtube(q)
                self._json({"id": vid})
                return
            if parsed.path == "/api/image":
                qs = urllib.parse.parse_qs(parsed.query)
                q = (qs.get("q") or [""])[0]
                url = search_image(q)
                self._json({"url": url})
                return
            if parsed.path == "/api/images":
                qs = urllib.parse.parse_qs(parsed.query)
                q = (qs.get("q") or [""])[0]
                try:
                    count = int((qs.get("count") or ["3"])[0])
                except ValueError:
                    count = 3
                count = max(1, min(count, 6))
                urls = search_images(q, count)
                self._json({"urls": urls})
                return
            return super().do_GET()
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:
            try:
                self._json({"error": str(e)}, status=500)
            except Exception:
                pass

    def _json(self, obj, status=200):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

_IMAGE_CACHE = {}
def search_images(q, limit=3):
    if not q:
        return []
    key = q + "::" + str(limit)
    if key in _IMAGE_CACHE:
        return list(_IMAGE_CACHE[key])
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    urls = []
    def add(u):
        nonlocal urls
        if u and u not in urls and len(urls) < limit:
            urls.append(u)
    # Try DuckDuckGo image search first (better product photos)
    try:
        html = urllib.request.urlopen(urllib.request.Request('https://duckduckgo.com/?q='+urllib.parse.quote(q)+'&iax=images&ia=images', headers={'User-Agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)','Accept':'text/html'}), context=ctx, timeout=15).read().decode('utf-8','ignore')
        m = re.search(r"vqd=([0-9-]+)", html)
        if m:
            vqd = m.group(1)
            url = 'https://duckduckgo.com/i.js?l=us-en&o=json&q=' + urllib.parse.quote(q) + '&vqd=' + vqd
            data = urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)','Referer':'https://duckduckgo.com/','Accept':'application/json'}), context=ctx, timeout=15).read().decode('utf-8','ignore')
            j = json.loads(data)
            res = j.get('results', [])
            for r in res:
                add(r.get('image'))
                if len(urls) >= limit:
                    break
    except Exception:
        pass
    # Fallback: Wikimedia Commons
    if len(urls) < limit:
        queries = [q]
        if q.split():
            queries.append(q.split()[0])
        queries.append("product")
        for qq in queries:
            if len(urls) >= limit:
                break
            search_url = "https://commons.wikimedia.org/w/api.php?action=query&list=search&srsearch=" + urllib.parse.quote(qq) + "&srnamespace=6&srlimit=12&format=json&origin=*"
            try:
                with urllib.request.urlopen(urllib.request.Request(search_url, headers={"User-Agent":"Mozilla/5.0"}), timeout=15, context=ctx) as r:
                    data = json.loads(r.read().decode("utf-8", "ignore"))
            except Exception:
                continue
            hits = (data.get("query", {}).get("search", []))
            titles = [h["title"] for h in hits]
            if not titles:
                continue
            info_url = "https://commons.wikimedia.org/w/api.php?action=query&titles=" + urllib.parse.quote("|".join(titles), safe="|") + "&prop=imageinfo&iiprop=url|mime|size&iiurlwidth=400&format=json&origin=*"
            try:
                with urllib.request.urlopen(urllib.request.Request(info_url, headers={"User-Agent":"Mozilla/5.0"}), timeout=15, context=ctx) as r:
                    data2 = json.loads(r.read().decode("utf-8", "ignore"))
            except Exception:
                continue
            pages = data2.get("query", {}).get("pages", {})
            for t in titles:
                if len(urls) >= limit:
                    break
                pg = None
                for k, v in pages.items():
                    if v.get("title") == t:
                        pg = v
                        break
                info = (pg or {}).get("imageinfo", [{}])[0] if pg else {}
                if info and str(info.get("mime", "")).startswith("image/") and (info.get("thumbwidth") or info.get("width") or 0) >= 200:
                    add(info.get("thumburl") or info.get("url"))
    _IMAGE_CACHE[key] = list(urls)
    return list(urls)

def search_image(q):
    res = search_images(q, 1)
    return res[0] if res else None

def search_youtube(q):
    if not q:
        return None
    url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote(q)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        with urllib.request.urlopen(req, timeout=15, context=ctx) as r:
            html = r.read().decode("utf-8", "ignore")
    except Exception:
        return None
    m = re.search(r'"videoId":"([A-Za-z0-9_-]{11})"', html)
    return m.group(1) if m else None

socketserver.ThreadingTCPServer.allow_reuse_address = True
socketserver.ThreadingTCPServer.daemon_threads = True
with socketserver.ThreadingTCPServer(("0.0.0.0", PORT), Handler) as httpd:
    print("Serving on", PORT)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
PY