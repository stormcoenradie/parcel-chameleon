import json, re, ssl, urllib.parse, urllib.request
from http.server import BaseHTTPRequestHandler

_IMAGE_CACHE = {}

def _ctx():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx

def search_image(q):
    if not q:
        return None
    if q in _IMAGE_CACHE:
        return _IMAGE_CACHE[q]
    ctx = _ctx()
    url = None
    try:
        html = urllib.request.urlopen(urllib.request.Request('https://duckduckgo.com/?q='+urllib.parse.quote(q)+'&iax=images&ia=images', headers={'User-Agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)','Accept':'text/html'}), context=ctx, timeout=10).read().decode('utf-8','ignore')
        m = re.search(r"vqd=([0-9-]+)", html)
        if m:
            vqd = m.group(1)
            data = urllib.request.urlopen(urllib.request.Request('https://duckduckgo.com/i.js?l=us-en&o=json&q=' + urllib.parse.quote(q) + '&vqd=' + vqd, headers={'User-Agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)','Referer':'https://duckduckgo.com/','Accept':'application/json'}), context=ctx, timeout=10).read().decode('utf-8','ignore')
            j = json.loads(data)
            res = j.get('results', [])
            if res:
                url = res[0].get('image')
    except Exception:
        url = None
    if not url:
        queries = [q]
        if q.split():
            queries.append(q.split()[0])
        queries.append("product")
        for qq in queries:
            if url:
                break
            search_url = "https://commons.wikimedia.org/w/api.php?action=query&list=search&srsearch=" + urllib.parse.quote(qq) + "&srnamespace=6&srlimit=8&format=json&origin=*"
            try:
                with urllib.request.urlopen(urllib.request.Request(search_url, headers={"User-Agent":"Mozilla/5.0"}), timeout=10, context=ctx) as r:
                    data = json.loads(r.read().decode("utf-8", "ignore"))
            except Exception:
                continue
            hits = (data.get("query", {}).get("search", []))
            titles = [h["title"] for h in hits]
            if not titles:
                continue
            info_url = "https://commons.wikimedia.org/w/api.php?action=query&titles=" + urllib.parse.quote("|".join(titles), safe="|") + "&prop=imageinfo&iiprop=url|mime|size&iiurlwidth=400&format=json&origin=*"
            try:
                with urllib.request.urlopen(urllib.request.Request(info_url, headers={"User-Agent":"Mozilla/5.0"}), timeout=10, context=ctx) as r:
                    data2 = json.loads(r.read().decode("utf-8", "ignore"))
            except Exception:
                continue
            pages = data2.get("query", {}).get("pages", {})
            for t in titles:
                if url:
                    break
                pg = None
                for k, v in pages.items():
                    if v.get("title") == t:
                        pg = v
                        break
                info = (pg or {}).get("imageinfo", [{}])[0] if pg else {}
                if info and str(info.get("mime", "")).startswith("image/") and (info.get("thumbwidth") or info.get("width") or 0) >= 200:
                    url = info.get("thumburl") or info.get("url")
    _IMAGE_CACHE[q] = url
    return url

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)
        q = (qs.get("q") or [""])[0]
        url = search_image(q)
        self._send({"url": url})

    def _send(self, obj, status=200):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)