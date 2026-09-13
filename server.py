"""Local-only, read-only game mount with HTTP Range and WebDAV discovery."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, unquote, quote
from xml.sax.saxutils import escape
import argparse, json, mimetypes, re, threading, time

BASE = Path(__file__).resolve().parent
GAME_NAME = '千恋万花（网页适配版）'
LOG_LOCK = threading.Lock()

def mount():
    files = {}
    # Native EXE/DLL, old saves, and optional CG overrides are deliberately not mounted.
    files.update({p.relative_to(BASE/'overlay').as_posix(): p for p in (BASE/'overlay').rglob('*') if p.is_file() and not p.name.endswith('.tmp')})
    return files

class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    def log_message(self, fmt, *args):
        with LOG_LOCK, (BASE/'case/server.log').open('a',encoding='utf8') as f:
            f.write(time.strftime('%H:%M:%S ')+(fmt % args)+'\n')
    def reply_headers(self, status, length, mime='application/octet-stream', extra=None):
        self.send_response(status)
        self.send_header('Content-Length', str(length))
        self.send_header('Content-Type', mime)
        self.send_header('Cross-Origin-Opener-Policy','same-origin')
        self.send_header('Cross-Origin-Embedder-Policy','require-corp')
        self.send_header('Cross-Origin-Resource-Policy','same-origin')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Cache-Control','no-cache')
        for k,v in (extra or {}).items(): self.send_header(k,v)
        self.end_headers()
    def send_data(self, data, mime='application/json', status=200, extra=None):
        if isinstance(data,str): data=data.encode('utf8')
        self.reply_headers(status,len(data),mime,extra)
        if self.command != 'HEAD': self.wfile.write(data)
    def do_OPTIONS(self):
        self.reply_headers(204,0,extra={'Allow':'GET, HEAD, OPTIONS, PROPFIND','DAV':'1'})
    def do_PROPFIND(self):
        n=int(self.headers_in('Content-Length','0'))
        if n: self.rfile.read(min(n,65536))
        path=unquote(urlsplit(self.path).path)
        if not path.startswith('/game/'):
            return self.send_data('Not found','text/plain',404)
        prefix=path[len('/game/'):].strip('/')
        files=mount(); entries={}
        for name,p in files.items():
            if prefix and not name.startswith(prefix+'/'): continue
            rest=name[len(prefix)+1:] if prefix else name
            part=rest.split('/')[0]; entries[part]=(None if '/' in rest else p)
        rows=[]
        def row(href,p):
            kind='<d:collection/>' if p is None else ''
            size=0 if p is None else p.stat().st_size
            return f'<d:response><d:href>{escape(href)}</d:href><d:propstat><d:prop><d:resourcetype>{kind}</d:resourcetype><d:getcontentlength>{size}</d:getcontentlength></d:prop><d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response>'
        rows.append(row(path,None))
        if self.headers_in('Depth','1')!='0':
            for name,p in entries.items(): rows.append(row(path.rstrip('/')+'/'+quote(name)+('/' if p is None else ''),p))
        self.send_data('<?xml version="1.0" encoding="utf-8"?><d:multistatus xmlns:d="DAV:">'+''.join(rows)+'</d:multistatus>','application/xml; charset=utf-8',207)
    def headers_in(self, key, default=None):
        return self.headers.get(key,default)
    def do_HEAD(self): self.do_GET()
    def do_GET(self):
        path=unquote(urlsplit(self.path).path)
        if path=='/api/status':
            files=mount()
            return self.send_data(json.dumps({'game':GAME_NAME,'files':len(files),'bytes':sum(p.stat().st_size for p in files.values()),'engine':'Kirikiroid2 Web','nativeExecutables':False,'originalFilesModified':False}))
        if path.startswith('/game/'):
            file=mount().get(path[len('/game/'):])
        elif path=='/': file=BASE/'index.html'
        elif path.startswith('/vendor/'):
            candidate=(BASE/path.lstrip('/')).resolve()
            file=candidate if candidate.is_relative_to(BASE/'vendor') else None
        else: file=None
        if file is None or not file.is_file(): return self.send_data('Not found','text/plain',404)
        size=file.stat().st_size; start=0; end=size-1; status=200
        extra={'Accept-Ranges':'bytes'}
        range_header=self.headers_in('Range')
        if range_header:
            m=re.fullmatch(r'bytes=(\d*)-(\d*)',range_header)
            if not m or not any(m.groups()): return self.send_data('',status=416,extra={'Content-Range':f'bytes */{size}'})
            a,b=m.groups()
            if a: start=int(a); end=min(int(b),end) if b else end
            else: start=max(0,size-int(b))
            if start>end or start>=size: return self.send_data('',status=416,extra={'Content-Range':f'bytes */{size}'})
            status=206; extra['Content-Range']=f'bytes {start}-{end}/{size}'
        mime='application/wasm' if file.suffix=='.wasm' else mimetypes.guess_type(str(file))[0] or 'application/octet-stream'
        self.reply_headers(status,max(0,end-start+1),mime,extra)
        if self.command=='HEAD': return
        try:
            with file.open('rb') as f:
                f.seek(start); left=end-start+1
                while left>0:
                    data=f.read(min(left,1024*1024))
                    if not data: break
                    self.wfile.write(data); left-=len(data)
        except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError): pass
    def do_POST(self):
        if urlsplit(self.path).path!='/api/log': return self.send_data('',status=404)
        n=int(self.headers_in('Content-Length','0'))
        if n>400000: return self.send_data('',status=413)
        try:
            rows=json.loads(self.rfile.read(n))
            with LOG_LOCK,(BASE/'case/browser.jsonl').open('a',encoding='utf8') as f:
                for row in rows[:100]: f.write(json.dumps({'time':time.time(),**row},ensure_ascii=False)+'\n')
        except (ValueError,TypeError): return self.send_data('',status=400)
        self.reply_headers(204,0)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8765);args=parser.parse_args()
    print(f'千恋万花网页启动器: http://127.0.0.1:{args.port}',flush=True)
    ThreadingHTTPServer(('127.0.0.1',args.port),Handler).serve_forever()
