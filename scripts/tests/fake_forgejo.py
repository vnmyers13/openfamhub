"""Fake Forgejo issues API for the script test harnesses.

python3 fake_forgejo.py <issues.json> <request_log> <port_file>
Serves GET/POST /api/v1/repos/<o>/<r>/issues (state, page, limit), POST .../comments,
POST .../pin and PATCH .../issues/<n>; the last body written goes to <issues.json>.last. Paths containing FAILME answer 500 to writes.
"""
import json
import re
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

issues = json.load(open(sys.argv[1]))
log = open(sys.argv[2], "a", buffering=1)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def reply(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def body(self):
        return json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")

    def do_GET(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        log.write(f"GET {u.path} state={q.get('state')} page={q.get('page')} auth={self.headers.get('Authorization')}\n")
        state = q.get("state", "open")
        match = [i for i in issues if state == "all" or i["state"] == state]
        limit, page = int(q.get("limit", 50)), int(q.get("page", 1))
        self.reply(200, match[(page - 1) * limit: page * limit])

    def do_POST(self):
        body = self.body()
        if "FAILME" in self.path:
            log.write(f"POST-FAIL {self.path}\n")
            return self.reply(500, {"message": "boom"})
        m = re.search(r"/issues/(\d+)/pin$", self.path)
        if m:
            log.write(f"PIN #{m.group(1)}\n")
            return self.reply(204 if "NOPIN" not in self.path else 404, {})
        m = re.search(r"/issues/(\d+)/comments$", self.path)
        if m:
            log.write(f"COMMENT #{m.group(1)} {body['body']}\n")
            return self.reply(201, {})
        number = max([i["number"] for i in issues] or [0]) + 1
        issues.append({"number": number, "title": body["title"], "body": body["body"], "state": "open", "labels": []})
        open(sys.argv[1] + ".last", "w").write(body["body"])
        log.write(f"CREATE #{number} {body['title']}\n")
        self.reply(201, {"number": number, "html_url": f"http://x/issues/{number}"})

    def do_PATCH(self):
        body = self.body()
        if "FAILME" in self.path:
            log.write(f"PATCH-FAIL {self.path}\n")
            return self.reply(500, {})
        number = int(self.path.rsplit("/", 1)[1])
        for i in issues:
            if i["number"] == number:
                i.update(body)
        if "body" in body:
            open(sys.argv[1] + ".last", "w").write(body["body"])
        log.write(f"PATCH #{number} {json.dumps(body) if 'body' not in body else 'body'}\n")
        self.reply(201, {})


server = HTTPServer(("127.0.0.1", 0), Handler)
open(sys.argv[3], "w").write(str(server.server_port))
server.serve_forever()
