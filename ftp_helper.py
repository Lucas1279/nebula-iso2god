#!/usr/bin/env python3
"""Local-only FTP bridge for Nebula ISO2GOD. Binds to loopback, never the LAN."""
from __future__ import annotations
import ftplib
import http.server
import json
import os
import secrets
import shutil
import tempfile
import threading
import urllib.parse
import webbrowser
from pathlib import Path

HOST, PORT = "127.0.0.1", 8765
ROOT = Path(__file__).resolve().parent
TOKEN = secrets.token_urlsafe(32)
LOCK = threading.Lock()
CONFIG = None
ACTIVE = {}


def send_json(handler, status, obj):
    data = json.dumps(obj).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(data)


def ftp_login(cfg):
    ftp = ftplib.FTP()
    ftp.connect(cfg["host"], cfg["port"], timeout=25)
    ftp.login(cfg["user"], cfg["password"])
    ftp.set_pasv(True)
    return ftp


def clean_segments(segments):
    if not isinstance(segments, list) or not segments or len(segments) > 16:
        raise ValueError("Invalid package path.")
    result = []
    for seg in segments:
        name = str(seg)
        if not name or name in (".", "..") or "/" in name or "\\" in name or "\x00" in name:
            raise ValueError("Unsafe path segment.")
        result.append(name)
    return result


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "NebulaLocalBridge/1.0"

    def log_message(self, fmt, *args):
        # Never log request bodies or FTP credentials.
        print("[bridge] " + (fmt % args))

    def _authorized(self):
        origin = self.headers.get("Origin", "")
        if origin and origin not in (f"http://{HOST}:{PORT}", f"http://localhost:{PORT}"):
            send_json(self, 403, {"error": "Unexpected page origin."})
            return False
        if self.headers.get("X-Nebula-Token") != TOKEN:
            send_json(self, 403, {"error": "Local bridge token missing or invalid. Refresh the page."})
            return False
        return True

    def _body(self):
        size = int(self.headers.get("Content-Length", "0"))
        if size < 0 or size > 8 * 1024 * 1024:
            raise ValueError("Request chunk exceeds 8 MiB.")
        return self.rfile.read(size)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/token":
            return send_json(self, 200, {"token": TOKEN})
        if parsed.path == "/api/status":
            return send_json(self, 200, {"connected": CONFIG is not None})
        if parsed.path == "/" or parsed.path == "/index.html":
            target = ROOT / "index.html"
            if not target.is_file():
                return send_json(self, 404, {"error": "index.html is missing beside ftp_helper.py."})
            data = target.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return self.wfile.write(data)
        return send_json(self, 404, {"error": "Not found."})

    def do_POST(self):
        global CONFIG
        if not self._authorized():
            return
        parsed = urllib.parse.urlparse(self.path)
        try:
            if parsed.path == "/api/connect":
                data = json.loads(self._body().decode("utf-8"))
                host = str(data.get("host", "")).strip()
                port = int(data.get("port", 21))
                user = str(data.get("user", ""))
                password = str(data.get("password", ""))
                base = str(data.get("basePath", "Hdd1:/")).strip()
                if not host or len(host) > 253 or port < 1 or port > 65535 or not user:
                    raise ValueError("Enter a valid Xbox IP/host, port, and username.")
                if any(c in value for value in (host, user, password, base) for c in ("\n", "\r", "\x00")):
                    raise ValueError("Invalid connection field.")
                trial = {"host": host, "port": port, "user": user, "password": password, "basePath": base}
                ftp = ftp_login(trial)
                try:
                    ftp.cwd(base)
                    pwd = ftp.pwd()
                finally:
                    try: ftp.quit()
                    except Exception: pass
                with LOCK:
                    CONFIG = trial
                return send_json(self, 200, {"ok": True, "cwd": pwd})

            if parsed.path == "/api/disconnect":
                with LOCK:
                    CONFIG = None
                return send_json(self, 200, {"ok": True})

            if parsed.path == "/api/file/begin":
                data = json.loads(self._body().decode("utf-8"))
                segments = clean_segments(data.get("segments"))
                expected = int(data.get("size", -1))
                if expected < 0 or expected > 20 * 1024 * 1024 * 1024:
                    raise ValueError("Invalid expected file size.")
                if not CONFIG:
                    raise ValueError("Connect to the Xbox FTP server first.")
                ident = secrets.token_urlsafe(18)
                fd, tmp = tempfile.mkstemp(prefix="nebula-ftp-", suffix=".part")
                os.close(fd)
                ACTIVE[ident] = {"segments": segments, "expected": expected, "written": 0, "tmp": tmp}
                return send_json(self, 200, {"id": ident})

            if parsed.path == "/api/file/chunk":
                ident = urllib.parse.parse_qs(parsed.query).get("id", [""])[0]
                item = ACTIVE.get(ident)
                if not item:
                    raise ValueError("No active file upload.")
                body = self._body()
                if item["written"] + len(body) > item["expected"]:
                    raise ValueError("Received more bytes than expected.")
                with open(item["tmp"], "ab") as out:
                    out.write(body)
                item["written"] += len(body)
                return send_json(self, 200, {"written": item["written"]})

            if parsed.path == "/api/file/finish":
                data = json.loads(self._body().decode("utf-8"))
                ident = str(data.get("id", ""))
                item = ACTIVE.pop(ident, None)
                if not item:
                    raise ValueError("No active file upload.")
                if item["written"] != item["expected"]:
                    try: os.unlink(item["tmp"])
                    except OSError: pass
                    raise ValueError(f"File was incomplete ({item['written']} of {item['expected']} bytes).")
                cfg = CONFIG
                if not cfg:
                    os.unlink(item["tmp"])
                    raise ValueError("FTP connection was closed.")
                ftp = ftp_login(cfg)
                try:
                    ftp.cwd(cfg["basePath"])
                    for seg in item["segments"][:-1]:
                        try: ftp.mkd(seg)
                        except ftplib.error_perm as exc:
                            # Directory may already exist; verify it can be entered.
                            try: ftp.cwd(seg)
                            except Exception: raise exc
                        else:
                            ftp.cwd(seg)
                    with open(item["tmp"], "rb") as src:
                        ftp.storbinary("STOR " + item["segments"][-1], src, blocksize=1024 * 1024)
                finally:
                    try: ftp.quit()
                    except Exception: pass
                    try: os.unlink(item["tmp"])
                    except OSError: pass
                return send_json(self, 200, {"ok": True, "bytes": item["written"]})

            if parsed.path == "/api/file/abort":
                data = json.loads(self._body().decode("utf-8"))
                item = ACTIVE.pop(str(data.get("id", "")), None)
                if item:
                    try: os.unlink(item["tmp"])
                    except OSError: pass
                return send_json(self, 200, {"ok": True})

            return send_json(self, 404, {"error": "Unknown API route."})
        except Exception as exc:
            return send_json(self, 400, {"error": str(exc) or exc.__class__.__name__})

    def do_OPTIONS(self):
        return send_json(self, 405, {"error": "Cross-origin requests are not supported."})


def main():
    httpd = http.server.ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Nebula ISO2GOD FTP helper is running at http://{HOST}:{PORT}/")
    print("Loopback-only: this service is not exposed to your network or the internet.")
    print("Keep this window open. Press Ctrl+C to stop it.")
    try:
        webbrowser.open(f"http://{HOST}:{PORT}/")
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        for item in list(ACTIVE.values()):
            try: os.unlink(item["tmp"])
            except OSError: pass
        print("Stopped.")

if __name__ == "__main__":
    main()
