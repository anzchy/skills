"""Local stand-in for the Baidu OCR HTTP API. Serves /oauth/2.0/token and /rest/2.0/ocr/v1/accurate_basic.

Answers are taken from STUB_BAIDU_MAP (json: sha-agnostic list consumed in call order) so tests stay deterministic.
Every request is appended to STUB_BAIDU_LOG so tests can assert what was (not) sent.
"""
import base64
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

ANSWERS = json.load(open(os.environ["STUB_BAIDU_MAP"], encoding="utf-8"))
LOG = os.environ["STUB_BAIDU_LOG"]
state = {"calls": 0}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def reply(self, payload, code=200):
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        url = urlparse(self.path)
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode()
        with open(LOG, "a", encoding="utf-8") as log:
            log.write(json.dumps({"path": url.path, "query": parse_qs(url.query), "has_image": "image=" in body}) + "\n")
        if url.path == "/oauth/2.0/token":
            q = parse_qs(url.query)
            if q.get("client_id", [""])[0] != "KEY" or q.get("client_secret", [""])[0] != "SECRET":
                return self.reply({"error": "invalid_client"}, 400)
            return self.reply({"access_token": "TOKEN", "expires_in": 2592000})
        if url.path.endswith("accurate_basic"):
            if parse_qs(url.query).get("access_token", [""])[0] != "TOKEN":
                return self.reply({"error_code": 110, "error_msg": "Access token invalid"})
            answer = ANSWERS[state["calls"] % len(ANSWERS)]
            state["calls"] += 1
            if isinstance(answer, dict):
                return self.reply(answer)
            return self.reply({"words_result": [{"words": w} for w in answer], "words_result_num": len(answer)})
        self.reply({}, 404)


server = HTTPServer(("127.0.0.1", 0), Handler)
print(server.server_address[1], flush=True)
server.serve_forever()
