#!/usr/bin/env python3
"""Local-only FTP bridge for Nebula ISO2GOD. Binds to loopback, never the LAN."""
from __future__ import annotations
import ftplib
import http.server
import json
import os
import secrets
import shutil
import socket
import sys
import tempfile
import threading
import time
import urllib.parse
import webbrowser
from pathlib import Path

HOST, PORT = "127.0.0.1", 8765
CONNECT_TIMEOUT = 25
TRANSFER_IDLE_TIMEOUT = 180  # Xbox USB/network writes can pause; allow 3 minutes without a packet.
ROOT = Path(__file__).resolve().parent
TOKEN = secrets.token_urlsafe(32)
LOCK = threading.Lock()
CONFIG = None
ACTIVE = {}
DRAG_EXPORTS = {}
DRAG_EXPORT_MAX_BYTES = 64 * 1024 * 1024
DRAG_EXPORT_TTL_SECONDS = 15 * 60


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
    ftp.connect(cfg["host"], cfg["port"], timeout=CONNECT_TIMEOUT)
    ftp.login(cfg["user"], cfg["password"])
    # Keep connection/login failures quick, but tolerate slow Xbox USB/HDD writes.
    ftp.timeout = TRANSFER_IDLE_TIMEOUT
    control = getattr(ftp, "sock", None)
    if control is not None:
        control.settimeout(TRANSFER_IDLE_TIMEOUT)
    ftp.set_pasv(True)
    return ftp


def clean_segments(segments, allow_empty=False):
    if not isinstance(segments, list) or (not allow_empty and not segments) or len(segments) > 64:
        raise ValueError("Invalid remote path.")
    result = []
    for seg in segments:
        name = str(seg)
        if not name or name in (".", "..") or "/" in name or "\\" in name or any(ord(ch) < 32 or ord(ch) == 127 for ch in name):
            raise ValueError("Unsafe path segment.")
        result.append(name)
    return result


def clean_name(value):
    name = str(value or "")
    if not name or name in (".", "..") or "/" in name or "\\" in name or any(ord(ch) < 32 or ord(ch) == 127 for ch in name):
        raise ValueError("Invalid file or folder name.")
    if len(name.encode("utf-8")) > 255:
        raise ValueError("File or folder name is too long.")
    return name


def cleanup_expired_drag_exports():
    now = time.time()
    expired = []
    with LOCK:
        for ident, item in list(DRAG_EXPORTS.items()):
            if item.get("expires", 0) <= now:
                expired.append(DRAG_EXPORTS.pop(ident))
    for item in expired:
        try: os.unlink(item["tmp"])
        except OSError: pass


def remove_drag_export(ident):
    with LOCK:
        item = DRAG_EXPORTS.pop(str(ident), None)
    if item:
        try: os.unlink(item["tmp"])
        except OSError: pass
    return item


def ftp_cwd(ftp, cfg, segments):
    ftp.cwd(cfg["basePath"])
    for segment in segments:
        ftp.cwd(segment)
    return ftp.pwd()


def parse_ftp_list_line(line):
    """Return a normalized entry from common UNIX/DOS FTP LIST formats."""
    import re
    line = str(line or "").rstrip("\r\n")
    if not line:
        return None
    unix = re.match(r"^([bcdlps-][rwxStTs-]{9})\s+\d+\s+\S+\s+\S+\s+(\d+)\s+\w{3}\s+\d+\s+[\d:]+\s+(.+)$", line)
    if unix:
        mode, size, name = unix.groups()
        if name in (".", ".."):
            return None
        return {"name": name, "type": "dir" if mode[0] == "d" else "link" if mode[0] == "l" else "file",
                "size": int(size), "modified": ""}
    dos = re.match(r"^(\d{2,4}[-/]\d{1,2}[-/]\d{1,4})\s+(\d{1,2}:\d{2}(?:AM|PM)?)\s+(<DIR>|\d+)\s+(.+)$", line, re.I)
    if dos:
        date, tm, size, name = dos.groups()
        if name in (".", ".."):
            return None
        return {"name": name, "type": "dir" if size.upper() == "<DIR>" else "file",
                "size": 0 if size.upper() == "<DIR>" else int(size), "modified": (date + " " + tm).strip()}
    return None


def ftp_list_entries(ftp):
    # Xbox dashboard servers commonly support LIST but not MLSD, so try the
    # traditional command first and prefer it when its output is recognizable.
    lines = []
    try:
        ftp.dir(lines.append)
    except (AttributeError, ftplib.Error, OSError, EOFError):
        lines = []
    entries = []
    for line in lines:
        entry = parse_ftp_list_line(line)
        if entry:
            entries.append(entry)
    if entries:
        return entries

    # Some newer servers expose structured MLSD facts; use them when LIST is
    # unsupported, empty, or emitted an unfamiliar format.
    try:
        for name, facts in ftp.mlsd():
            if name in (".", ".."):
                continue
            typ = facts.get("type", "file").lower()
            entries.append({"name": name, "type": "dir" if typ in ("dir", "cdir", "pdir") else "link" if typ == "slink" else "file",
                            "size": int(facts.get("size", 0) or 0), "modified": facts.get("modify", "")})
        if entries:
            return entries
    except (AttributeError, ftplib.Error, OSError, EOFError):
        pass

    # Last-resort listing for minimal servers: probe each name by cwd/size.
    try:
        names = ftp.nlst()
    except (ftplib.error_perm, OSError, EOFError) as exc:
        raise RuntimeError("This Xbox FTP server did not provide a readable directory listing: " + str(exc))
    current = ftp.pwd()
    seen = set()
    for raw_name in names:
        name = str(raw_name).rstrip("/").rsplit("/", 1)[-1]
        if not name or name in (".", "..") or name in seen:
            continue
        seen.add(name)
        typ, size = "file", 0
        try:
            ftp.cwd(name)
            ftp.cwd(current)
            typ = "dir"
        except (ftplib.error_perm, OSError):
            try:
                value = ftp.size(name)
                size = int(value or 0)
            except (ftplib.error_perm, OSError, ValueError):
                pass
        entries.append({"name": name, "type": typ, "size": size, "modified": ""})
    return entries


def ftp_remove_tree(ftp, name, depth=0):
    if depth > 64:
        raise ValueError("Folder nesting is too deep to delete safely.")
    parent = ftp.pwd()
    ftp.cwd(name)
    children = ftp_list_entries(ftp)
    for child in children:
        child_name = clean_name(child["name"])
        if child["type"] == "dir":
            ftp_remove_tree(ftp, child_name, depth + 1)
        elif child["type"] == "file":
            ftp.delete(child_name)
        else:
            raise ValueError("Folder contains a link or unrecognized item; it was not recursively deleted.")
    ftp.cwd(parent)
    ftp.rmd(name)


class Handler(http.server.BaseHTTPRequestHandler):
    # Reuse the loopback HTTP connection for successive staging chunks. Every
    # response includes Content-Length, so HTTP/1.1 keep-alive is safe here.
    protocol_version = "HTTP/1.1"
    server_version = "NebulaLocalBridge/1.0"

    def log_message(self, fmt, *args):
        # Avoid flooding Terminal with the live progress polling and 4 MiB data chunks.
        if (self.path.startswith("/api/file/chunk?") or self.path.startswith("/api/file/status?")
                or self.path.startswith("/api/drag-export/chunk?") or self.path.startswith("/api/drag-export/file/")):
            return
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

    def _serve_vendor_asset(self, encoded_path):
        """Serve only JS/WASM files bundled under vendor for local browser workers."""
        vendor_root = (ROOT / "vendor").resolve()
        try:
            requested = urllib.parse.unquote(encoded_path).lstrip("/")
            target = (ROOT / requested).resolve(strict=True)
            target.relative_to(vendor_root)
        except (OSError, ValueError):
            return send_json(self, 404, {"error": "Not found."})
        if not target.is_file() or target.suffix.lower() not in (".js", ".wasm"):
            return send_json(self, 404, {"error": "Not found."})
        data = target.read_bytes()
        content_type = "application/wasm" if target.suffix.lower() == ".wasm" else "text/javascript; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path.startswith("/api/drag-export/file/"):
            cleanup_expired_drag_exports()
            ident = urllib.parse.unquote(parsed.path.rsplit("/", 1)[-1])
            with LOCK:
                item = DRAG_EXPORTS.get(ident)
                item = dict(item) if item and item.get("state") == "ready" else None
            if not item or not os.path.isfile(item["tmp"]):
                return send_json(self, 404, {"error": "This prepared drag-out file expired or no longer exists. Prepare it again."})
            name = item["name"]
            fallback_name = "".join(ch if ch.isascii() and 32 <= ord(ch) < 127 and ch not in ('"', '\\') else "_" for ch in name) or "download"
            encoded_name = urllib.parse.quote(name, safe="")
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(item["size"]))
            self.send_header("Content-Disposition", f"attachment; filename=\"{fallback_name}\"; filename*=UTF-8''{encoded_name}")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            with open(item["tmp"], "rb") as source:
                while True:
                    block = source.read(1024 * 1024)
                    if not block: break
                    self.wfile.write(block)
            return
        if parsed.path.startswith("/vendor/"):
            return self._serve_vendor_asset(parsed.path)
        if parsed.path == "/api/token":
            return send_json(self, 200, {"token": TOKEN})
        if parsed.path == "/api/status":
            return send_json(self, 200, {"connected": CONFIG is not None})
        if parsed.path == "/api/file/status":
            if not self._authorized():
                return
            ident = urllib.parse.parse_qs(parsed.query).get("id", [""])[0]
            with LOCK:
                item = ACTIVE.get(ident)
                if not item:
                    return send_json(self, 404, {"error": "No active transfer status."})
                status = {"state": item.get("state", "staging"),
                          "sent": item.get("sent", 0),
                          "expected": item.get("expected", 0),
                          "error": item.get("error", "")}
            return send_json(self, 200, status)
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

    def do_HEAD(self):
        parsed = urllib.parse.urlparse(self.path)
        if not parsed.path.startswith("/api/drag-export/file/"):
            return self.send_error(405, "Method not allowed")
        cleanup_expired_drag_exports()
        ident = urllib.parse.unquote(parsed.path.rsplit("/", 1)[-1])
        with LOCK:
            item = DRAG_EXPORTS.get(ident)
            item = dict(item) if item and item.get("state") == "ready" else None
        if not item or not os.path.isfile(item["tmp"]):
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return
        fallback_name = "".join(ch if ch.isascii() and 32 <= ord(ch) < 127 and ch not in ('"', '\\') else "_" for ch in item["name"]) or "download"
        encoded_name = urllib.parse.quote(item["name"], safe="")
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(item["size"]))
        self.send_header("Content-Disposition", "attachment; filename=" + chr(34) + fallback_name + chr(34) + "; filename*=UTF-8''" + encoded_name)
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()

    def do_POST(self):
        global CONFIG
        if not self._authorized():
            return
        parsed = urllib.parse.urlparse(self.path)
        try:
            if parsed.path == "/api/drag-export/begin":
                cleanup_expired_drag_exports()
                data = json.loads(self._body().decode("utf-8"))
                name = clean_name(data.get("name"))
                size = int(data.get("size", -1))
                if size < 0 or size > DRAG_EXPORT_MAX_BYTES:
                    raise ValueError("Drag-out exports are limited to 64 MiB per file.")
                with LOCK:
                    active_bytes = sum(int(item.get("size", 0)) for item in DRAG_EXPORTS.values())
                    if len(DRAG_EXPORTS) >= 8 or active_bytes + size > 2 * DRAG_EXPORT_MAX_BYTES:
                        raise ValueError("Too many prepared drag-out files are pending. Drag or clear the current selection, then retry.")
                fd, tmp = tempfile.mkstemp(prefix="nebula-drag-export-", suffix=".part")
                os.close(fd)
                ident = secrets.token_urlsafe(32)
                with LOCK:
                    DRAG_EXPORTS[ident] = {"tmp": tmp, "name": name, "size": size, "written": 0,
                                           "state": "staging", "expires": time.time() + DRAG_EXPORT_TTL_SECONDS}
                return send_json(self, 200, {"id": ident})

            if parsed.path == "/api/drag-export/chunk":
                ident = urllib.parse.parse_qs(parsed.query).get("id", [""])[0]
                body = self._body()
                with LOCK:
                    item = DRAG_EXPORTS.get(ident)
                    if not item or item.get("state") != "staging":
                        raise ValueError("No active drag-out export is being staged.")
                    if item["written"] + len(body) > item["size"]:
                        raise ValueError("Received more bytes than expected for this drag-out file.")
                    with open(item["tmp"], "ab") as output:
                        output.write(body)
                    item["written"] += len(body)
                    written = item["written"]
                return send_json(self, 200, {"written": written})

            if parsed.path == "/api/drag-export/finish":
                data = json.loads(self._body().decode("utf-8"))
                ident = str(data.get("id", ""))
                with LOCK:
                    item = DRAG_EXPORTS.get(ident)
                    if not item:
                        raise ValueError("No active drag-out export exists.")
                    if item.get("state") == "ready":
                        return send_json(self, 200, {"ok": True, "url": "/api/drag-export/file/" + ident,
                                                    "expiresIn": DRAG_EXPORT_TTL_SECONDS})
                    if item.get("state") != "staging" or item["written"] != item["size"]:
                        raise ValueError("The drag-out file is incomplete; prepare it again.")
                    item["state"] = "ready"
                    item["expires"] = time.time() + DRAG_EXPORT_TTL_SECONDS
                return send_json(self, 200, {"ok": True, "url": "/api/drag-export/file/" + ident,
                                            "expiresIn": DRAG_EXPORT_TTL_SECONDS})

            if parsed.path == "/api/drag-export/abort":
                data = json.loads(self._body().decode("utf-8"))
                remove_drag_export(data.get("id", ""))
                return send_json(self, 200, {"ok": True})

            if parsed.path == "/api/connect":
                data = json.loads(self._body().decode("utf-8"))
                host = str(data.get("host", "")).strip()
                port = int(data.get("port", 21))
                user = str(data.get("user", ""))
                password = str(data.get("password", ""))
                base = str(data.get("basePath", "Hdd1:/"))
                if not base.strip():
                    base = "Hdd1:/"
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

            if parsed.path == "/api/fs/list":
                data = json.loads(self._body().decode("utf-8"))
                segments = clean_segments(data.get("segments", []), allow_empty=True)
                cfg = CONFIG
                if not cfg:
                    raise ValueError("Connect to the Xbox FTP server first.")
                ftp = ftp_login(cfg)
                try:
                    cwd = ftp_cwd(ftp, cfg, segments)
                    # Browsing should fail fast rather than leave the page stuck if
                    # an Xbox dashboard's directory-list command stalls.
                    ftp.timeout = 12
                    control = getattr(ftp, "sock", None)
                    if control is not None:
                        control.settimeout(12)
                    entries = ftp_list_entries(ftp)
                    entries.sort(key=lambda item: (item["type"] != "dir", item["name"].casefold()))
                    return send_json(self, 200, {"ok": True, "cwd": cwd, "segments": segments, "entries": entries})
                finally:
                    try: ftp.quit()
                    except Exception: pass

            if parsed.path == "/api/fs/download":
                data = json.loads(self._body().decode("utf-8"))
                segments = clean_segments(data.get("segments"))
                parent, name = segments[:-1], clean_name(segments[-1])
                cfg = CONFIG
                if not cfg:
                    raise ValueError("Connect to the Xbox FTP server first.")
                ftp = ftp_login(cfg)
                data_sock = None
                headers_sent = False
                try:
                    ftp_cwd(ftp, cfg, parent)
                    ftp.timeout = 12
                    control = getattr(ftp, "sock", None)
                    if control is not None:
                        control.settimeout(12)
                    entry = next((item for item in ftp_list_entries(ftp) if item["name"] == name), None)
                    if not entry:
                        raise ValueError("That remote item no longer exists; refresh the folder.")
                    if entry["type"] != "file":
                        raise ValueError("Only selected files can be imported; open folders and select the files inside.")
                    max_bytes = 20 * 1024 * 1024 * 1024
                    requested_limit = data.get("maxBytes")
                    if requested_limit is not None:
                        if isinstance(requested_limit, bool):
                            raise ValueError("Invalid download size limit.")
                        try:
                            requested_limit = int(requested_limit)
                        except (TypeError, ValueError):
                            raise ValueError("Invalid download size limit.")
                        if requested_limit < 1 or requested_limit > max_bytes:
                            raise ValueError("Download size limit must be between 1 byte and 20 GiB.")
                        max_bytes = requested_limit
                    if int(entry.get("size", 0) or 0) > max_bytes:
                        raise ValueError("That file exceeds the requested import size limit.")
                    # Stream the Xbox RETR response directly to the browser; no
                    # intermediate download copy is written to Mac system storage.
                    ftp.timeout = TRANSFER_IDLE_TIMEOUT
                    if control is not None:
                        control.settimeout(TRANSFER_IDLE_TIMEOUT)
                    data_sock = ftp.transfercmd("RETR " + name)
                    fallback_name = "".join(ch if ch.isascii() and 32 <= ord(ch) < 127 and ch not in ('"', '\\') else "_" for ch in name) or "download"
                    encoded_name = urllib.parse.quote(name, safe="")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/octet-stream")
                    self.send_header("Transfer-Encoding", "chunked")
                    self.send_header("Content-Disposition", f"attachment; filename=\"{fallback_name}\"; filename*=UTF-8''{encoded_name}")
                    self.send_header("X-Content-Type-Options", "nosniff")
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    headers_sent = True
                    downloaded = 0
                    while True:
                        block = data_sock.recv(1024 * 1024)
                        if not block:
                            break
                        downloaded += len(block)
                        if downloaded > max_bytes:
                            raise ValueError("That file exceeds the 20 GiB import limit.")
                        self.wfile.write((format(len(block), "X") + "\r\n").encode("ascii"))
                        self.wfile.write(block)
                        self.wfile.write(b"\r\n")
                        self.wfile.flush()
                    data_sock.close()
                    data_sock = None
                    ftp.voidresp()
                    self.wfile.write(b"0\r\n\r\n")
                    self.wfile.flush()
                    return
                except Exception:
                    if headers_sent:
                        # The browser will reject a truncated chunked response.
                        self.close_connection = True
                        return
                    raise
                finally:
                    if data_sock is not None:
                        try: data_sock.close()
                        except Exception: pass
                    try: ftp.quit()
                    except Exception: pass

            if parsed.path == "/api/fs/mkdir":
                data = json.loads(self._body().decode("utf-8"))
                segments = clean_segments(data.get("segments", []), allow_empty=True)
                name = clean_name(data.get("name"))
                cfg = CONFIG
                if not cfg:
                    raise ValueError("Connect to the Xbox FTP server first.")
                ftp = ftp_login(cfg)
                try:
                    ftp_cwd(ftp, cfg, segments)
                    try:
                        ftp.mkd(name)
                        created = True
                    except ftplib.error_perm:
                        # Treat an existing directory as success, but never silently
                        # accept an existing file with the same name.
                        try:
                            ftp.cwd(name)
                            ftp.cwd("..")
                            created = False
                        except Exception:
                            raise
                    return send_json(self, 200, {"ok": True, "created": created, "name": name})
                finally:
                    try: ftp.quit()
                    except Exception: pass

            if parsed.path == "/api/fs/move":
                data = json.loads(self._body().decode("utf-8"))
                source = clean_segments(data.get("sourceSegments"))
                destination = clean_segments(data.get("destinationSegments"))
                if len(source) < 1 or len(destination) < 2:
                    raise ValueError("Choose one remote file and a destination folder.")
                source_parent, name = source[:-1], clean_name(source[-1])
                destination_parent = destination[:-1]
                if destination[-1] != name:
                    raise ValueError("Moving files keeps the original filename unchanged.")
                if len(destination_parent) <= len(source_parent) or destination_parent[:len(source_parent)] != source_parent:
                    raise ValueError("Drag a remote file into a subfolder of its current folder to move it.")
                target_subfolder = destination_parent[len(source_parent):]
                if not target_subfolder:
                    raise ValueError("Choose a destination subfolder.")
                cfg = CONFIG
                if not cfg:
                    raise ValueError("Connect to the Xbox FTP server first.")
                ftp = ftp_login(cfg)
                try:
                    ftp_cwd(ftp, cfg, source_parent)
                    source_entry = next((item for item in ftp_list_entries(ftp) if item["name"] == name), None)
                    if not source_entry or source_entry["type"] != "file":
                        raise ValueError("Only a listed remote file can be moved; refresh and try again.")
                    ftp_cwd(ftp, cfg, destination_parent)
                    target_listing = ftp_list_entries(ftp)
                    if any(item["name"].casefold() == name.casefold() for item in target_listing):
                        raise ValueError("A same-named item already exists in the destination folder. It was not overwritten.")
                    ftp_cwd(ftp, cfg, source_parent)
                    new_path = "/".join(target_subfolder + [name])
                    ftp.rename(name, new_path)
                    return send_json(self, 200, {"ok": True, "name": name, "destinationSegments": destination})
                finally:
                    try: ftp.quit()
                    except Exception: pass

            if parsed.path == "/api/fs/rename":
                data = json.loads(self._body().decode("utf-8"))
                segments = clean_segments(data.get("segments"))
                parent, old_name = segments[:-1], clean_name(segments[-1])
                new_name = clean_name(data.get("newName"))
                if new_name == old_name:
                    return send_json(self, 200, {"ok": True, "oldName": old_name, "newName": new_name, "renamed": False})
                if new_name.casefold() == old_name.casefold():
                    raise ValueError("Case-only renames are not supported; choose a different filename.")
                cfg = CONFIG
                if not cfg:
                    raise ValueError("Connect to the Xbox FTP server first.")
                ftp = ftp_login(cfg)
                try:
                    ftp_cwd(ftp, cfg, parent)
                    listing = ftp_list_entries(ftp)
                    source = next((item for item in listing if item["name"] == old_name), None)
                    if not source or source["type"] != "file":
                        raise ValueError("Only an existing remote file can be renamed; refresh and try again.")
                    if any(item["name"].casefold() == new_name.casefold() for item in listing):
                        raise ValueError("A same-named item already exists in this folder. It was not overwritten.")
                    ftp.rename(old_name, new_name)
                    return send_json(self, 200, {"ok": True, "oldName": old_name, "newName": new_name, "renamed": True})
                finally:
                    try: ftp.quit()
                    except Exception: pass

            if parsed.path == "/api/fs/delete":
                data = json.loads(self._body().decode("utf-8"))
                segments = clean_segments(data.get("segments"))
                recursive = data.get("recursive", False) is True
                cfg = CONFIG
                if not cfg:
                    raise ValueError("Connect to the Xbox FTP server first.")
                parent = segments[:-1]
                name = clean_name(segments[-1])
                ftp = ftp_login(cfg)
                try:
                    ftp_cwd(ftp, cfg, parent)
                    listing = ftp_list_entries(ftp)
                    entry = next((item for item in listing if item["name"] == name), None)
                    if not entry:
                        raise ValueError("That remote item no longer exists; refresh the folder.")
                    if entry["type"] == "dir":
                        if recursive:
                            ftp_remove_tree(ftp, name)
                        else:
                            ftp.rmd(name)
                    elif entry["type"] == "file":
                        ftp.delete(name)
                    else:
                        raise ValueError("Links or unrecognized remote items cannot be removed by this file manager.")
                    return send_json(self, 200, {"ok": True, "deleted": name, "type": entry["type"]})
                finally:
                    try: ftp.quit()
                    except Exception: pass

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
                with LOCK:
                    ACTIVE[ident] = {"segments": segments, "expected": expected, "written": 0,
                                     "sent": 0, "state": "staging", "error": "", "tmp": tmp}
                return send_json(self, 200, {"id": ident})

            if parsed.path == "/api/file/chunk":
                ident = urllib.parse.parse_qs(parsed.query).get("id", [""])[0]
                with LOCK:
                    item = ACTIVE.get(ident)
                if not item or item.get("state") != "staging":
                    raise ValueError("No active staging upload.")
                body = self._body()
                with LOCK:
                    if item["written"] + len(body) > item["expected"]:
                        raise ValueError("Received more bytes than expected.")
                    with open(item["tmp"], "ab") as out:
                        out.write(body)
                    item["written"] += len(body)
                    written = item["written"]
                return send_json(self, 200, {"written": written})

            if parsed.path == "/api/file/finish":
                data = json.loads(self._body().decode("utf-8"))
                ident = str(data.get("id", ""))
                with LOCK:
                    item = ACTIVE.get(ident)
                    if not item:
                        raise ValueError("No active file upload.")
                    # A repeated finish is safe if the prior FTP result succeeded but
                    # its HTTP response did not reach the browser.
                    if item.get("state") == "done":
                        return send_json(self, 200, {"ok": True, "bytes": item["written"]})
                    if item.get("state") not in ("staging", "error"):
                        raise ValueError("This file is already being transferred.")
                    if item["written"] != item["expected"]:
                        try: os.unlink(item["tmp"])
                        except OSError: pass
                        item["state"] = "error"
                        item["error"] = f"File was incomplete ({item['written']} of {item['expected']} bytes)."
                        raise ValueError(item["error"])
                    cfg = CONFIG
                    if not cfg:
                        item["state"] = "error"
                        item["error"] = "FTP connection was closed."
                        raise ValueError(item["error"])
                    item["state"] = "connecting"
                    item["sent"] = 0
                    item["error"] = ""
                ftp = None
                try:
                    ftp = ftp_login(cfg)
                    ftp.cwd(cfg["basePath"])
                    for seg in item["segments"][:-1]:
                        try: ftp.mkd(seg)
                        except ftplib.error_perm as exc:
                            # Directory may already exist; verify it can be entered.
                            try: ftp.cwd(seg)
                            except Exception: raise exc
                        else:
                            ftp.cwd(seg)
                    with LOCK:
                        item["state"] = "uploading"
                    sent = 0
                    def report_block(block):
                        nonlocal sent
                        sent += len(block)
                        with LOCK:
                            item["sent"] = sent
                    with open(item["tmp"], "rb") as src:
                        ftp.storbinary("STOR " + item["segments"][-1], src,
                                       blocksize=1024 * 1024, callback=report_block)
                    with LOCK:
                        item["sent"] = item["expected"]
                        item["state"] = "done"
                except Exception as exc:
                    message = str(exc) or exc.__class__.__name__
                    if isinstance(exc, (TimeoutError, socket.timeout)) or message.lower() == "timed out":
                        message = "FTP transfer stalled for 180 seconds. Check the Xbox/USB/network, then retry; wired Ethernet is more reliable."
                    with LOCK:
                        item["state"] = "error"
                        item["error"] = message
                    raise RuntimeError(message) from exc
                finally:
                    if ftp is not None:
                        try: ftp.quit()
                        except Exception: pass
                return send_json(self, 200, {"ok": True, "bytes": item["written"]})

            if parsed.path == "/api/file/ack":
                data = json.loads(self._body().decode("utf-8"))
                ident = str(data.get("id", ""))
                with LOCK:
                    item = ACTIVE.get(ident)
                    if item and item.get("state") != "done":
                        raise ValueError("The FTP file has not completed successfully; retry it or cancel.")
                    if item:
                        ACTIVE.pop(ident, None)
                if item:
                    try: os.unlink(item["tmp"])
                    except OSError: pass
                return send_json(self, 200, {"ok": True})

            if parsed.path == "/api/file/abort":
                data = json.loads(self._body().decode("utf-8"))
                with LOCK:
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


def cleanup_stale_staging_files():
    """Remove abandoned upload/download temp files after this helper claims its port."""
    removed = 0
    try:
        temp_root = Path(tempfile.gettempdir())
        for pattern in ("nebula-ftp-*.part", "nebula-download-*.part", "nebula-drag-export-*.part"):
            for path in temp_root.glob(pattern):
                try:
                    if path.is_file():
                        path.unlink()
                        removed += 1
                except OSError:
                    pass
    except OSError:
        pass
    if removed:
        print(f"Removed {removed} stale temporary FTP staging file(s).")


def drag_export_cleanup_loop():
    while True:
        time.sleep(60)
        cleanup_expired_drag_exports()


def main():
    # Binding succeeds only when another helper is not already using this port,
    # so any matching staging files here belong to an earlier stopped/crashed run.
    httpd = http.server.ThreadingHTTPServer((HOST, PORT), Handler)
    cleanup_stale_staging_files()
    cleanup_thread = threading.Thread(target=drag_export_cleanup_loop, name="drag-export-cleanup", daemon=True)
    cleanup_thread.start()
    print(f"Nebula ISO2GOD FTP helper is running at http://{HOST}:{PORT}/")
    print("Loopback-only: this service is not exposed to your network or the internet.")
    print("Keep this window open. Press Ctrl+C to stop it.")
    try:
        if "--no-browser" not in sys.argv[1:]:
            webbrowser.open(f"http://{HOST}:{PORT}/")
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        for item in list(ACTIVE.values()):
            try: os.unlink(item["tmp"])
            except OSError: pass
        with LOCK:
            drag_exports = list(DRAG_EXPORTS.values())
            DRAG_EXPORTS.clear()
        for item in drag_exports:
            try: os.unlink(item["tmp"])
            except OSError: pass
        print("Stopped.")

if __name__ == "__main__":
    main()
